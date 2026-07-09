"""FastAPI HTTP entrypoint wrapping run_agent() for a hosted Workspace Add-on backend.

Kept alongside cli.py, not as a replacement for it: cli.py remains the
local-dev/direct-run entrypoint, and this module is the hosted entrypoint a
future Apps Script Add-on calls over HTTPS via UrlFetchApp.
"""

import os
import secrets
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Annotated, Literal

import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from verbatim.agent import run_agent
from verbatim.brand_guidelines import BrandGuidelines
from verbatim.docs_client import AuthenticationError, DocsClientError, GoogleDocsClient
from verbatim.llm_client import LLMClientError, OpenRouterClient
from verbatim.token_validator import validate_access_token

DEFAULT_MODEL = "google/gemini-2.5-flash"
BACKEND_SECRET_HEADER = "X-Backend-Shared-Secret"

_STATUS_BY_ERROR: dict[type[Exception], int] = {
    AuthenticationError: 401,
    DocsClientError: 502,
    LLMClientError: 502,
    FileNotFoundError: 400,
    ValueError: 400,
    KeyError: 400,
}

_bearer_scheme = HTTPBearer(auto_error=False)

# In-process job store for the audit-job submit/poll pattern below. Only
# valid because the Cloud Run service this backend runs as is pinned to a
# single instance (--min-instances=1 --max-instances=1) with a single
# uvicorn worker process (no `workers=` in run()'s uvicorn.run call, no
# gunicorn wrapper) -- a demo-scoped shortcut, same spirit as the
# --allow-unauthenticated Cloud Run flag documented in
# docs/workspace-addon-migration.md. A real multi-instance-safe deployment
# would need Firestore/Redis/etc instead of a plain dict.
_JobStatus = Literal["queued", "running", "done", "error"]
_jobs_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=4)


def create_app() -> FastAPI:
    """Build the Verbatim Audit API app.

    Interactive docs (``/docs``, ``/redoc``, ``/openapi.json``) are enabled
    by default for local dev, and disabled when ``VERBATIM_DISABLE_DOCS`` is
    set -- an internet-reachable deployment shouldn't hand out a free map of
    its API surface.

    Returns:
        A configured FastAPI app, not yet bound to a server.
    """
    docs_enabled = os.environ.get("VERBATIM_DISABLE_DOCS", "").lower() not in (
        "1",
        "true",
        "yes",
    )
    return FastAPI(
        title="Verbatim Audit API",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )


app = create_app()


def _get_expected_backend_secret() -> str:
    """Load the shared secret inbound requests must present, from the environment.

    Loads a `.env` file first, if one is present, mirroring
    `OpenRouterClient.from_env`'s environment-loading behavior.

    Returns:
        The configured BACKEND_SHARED_SECRET value.

    Raises:
        RuntimeError: BACKEND_SHARED_SECRET is not set -- a server
            misconfiguration, not something a caller can fix.
    """
    load_dotenv()
    secret = os.environ.get("BACKEND_SHARED_SECRET")
    if not secret:
        raise RuntimeError("BACKEND_SHARED_SECRET environment variable is not set")
    return secret


class AuditRequest(BaseModel):
    """Request body for POST /audit."""

    document_id: str
    brief_id: str
    channel: str | None = None
    model: str = DEFAULT_MODEL


class AuditResponse(BaseModel):
    """Response body for a completed audit run."""

    suggestions_made: int
    comments_made: int
    stopped_due_to_max_rounds: bool
    category_counts: dict[str, int]


class AuditJobSubmitResponse(BaseModel):
    """Response body for a successfully submitted POST /audit request."""

    job_id: str


class AuditJobStatusResponse(BaseModel):
    """Response body for GET /audit/{job_id}."""

    job_id: str
    status: _JobStatus
    result: AuditResponse | None = None
    error: str | None = None


@dataclass
class _JobRecord:
    """Server-side state for one submitted audit job."""

    status: _JobStatus
    result: AuditResponse | None = None
    error: str | None = None


_jobs: dict[str, _JobRecord] = {}


def _status_for(err: Exception) -> int:
    """Map a raised exception to an HTTP status code, most-specific type first.

    Args:
        err: The exception raised while validating/setting up an audit request.

    Returns:
        The HTTP status code to respond with; 500 if the type is unmapped.
    """
    for error_type in type(err).__mro__:
        if error_type in _STATUS_BY_ERROR:
            return _STATUS_BY_ERROR[error_type]
    return 500


def _check_shared_secret(x_backend_shared_secret: str | None) -> None:
    """Reject a request that doesn't present the correct backend shared secret.

    Args:
        x_backend_shared_secret: The header value the caller presented, if any.

    Raises:
        HTTPException: 500 if the backend itself is misconfigured; 401 if the
            header is missing or doesn't match.
    """
    try:
        expected_secret = _get_expected_backend_secret()
    except RuntimeError as err:
        raise HTTPException(status_code=500, detail=str(err)) from err

    if not x_backend_shared_secret or not secrets.compare_digest(
        x_backend_shared_secret, expected_secret
    ):
        raise HTTPException(
            status_code=401, detail="Invalid or missing backend shared secret"
        )


def _run_audit_job(
    job_id: str,
    docs_client: GoogleDocsClient,
    llm_client: OpenRouterClient,
    brand_guidelines: BrandGuidelines,
    document_id: str,
    brief_id: str,
    channel: str | None,
) -> None:
    """Run the agent loop in the background and record its outcome.

    Runs on the module-level thread pool, well past the point where any
    HTTPException could reach a caller -- every outcome, success or failure,
    is written into ``_jobs`` for a later GET /audit/{job_id} to read.

    Args:
        job_id: The id this job was submitted under.
        docs_client: The Google Docs/Drive client to audit with.
        llm_client: The OpenRouter client to audit with.
        brand_guidelines: The brand guidelines to audit against.
        document_id: The draft document to audit.
        brief_id: The campaign brief document to audit against.
        channel: The target channel, if any.
    """
    with _jobs_lock:
        _jobs[job_id] = _JobRecord(status="running")

    try:
        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id=document_id,
            brief_id=brief_id,
            brand_guidelines=brand_guidelines,
            target_channel=channel,
        )
    except Exception as err:
        with _jobs_lock:
            _jobs[job_id] = _JobRecord(status="error", error=str(err))
        return

    with _jobs_lock:
        _jobs[job_id] = _JobRecord(
            status="done",
            result=AuditResponse(
                suggestions_made=result.suggestions_made,
                comments_made=result.comments_made,
                stopped_due_to_max_rounds=result.stopped_due_to_max_rounds,
                category_counts=result.category_counts,
            ),
        )


@app.post("/audit", status_code=202, response_model=AuditJobSubmitResponse)
def audit(
    request: AuditRequest,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
    x_backend_shared_secret: Annotated[
        str | None, Header(alias=BACKEND_SECRET_HEADER)
    ] = None,
) -> AuditJobSubmitResponse:
    """Submit one audit pass over a Google Doc, returning a job id immediately.

    The actual audit (an LLM tool-calling loop of up to 20 round trips) runs
    on a background thread after this returns -- ``UrlFetchApp.fetch()`` on
    the Apps Script side has a hard, non-configurable 60-second timeout,
    which a real audit routinely exceeds, so the caller must poll
    GET /audit/{job_id} for the outcome instead of waiting on this call.

    Args:
        request: The document/brief/channel/model to audit.
        credentials: The bearer token forwarded by the calling Add-on, via
            ``ScriptApp.getOAuthToken()`` on the Apps Script side.
        x_backend_shared_secret: A static secret known to the Add-on and
            this backend, checked before any Google API call is made --
            a cheap first-line filter against internet scanning/probing,
            independent of the (more expensive) tokeninfo check below.

    Returns:
        The id of the submitted job, to poll via GET /audit/{job_id}.

    Raises:
        HTTPException: 401 if the shared secret or Authorization header is
            missing/invalid, or the bearer token fails tokeninfo
            validation; 500 if the backend itself is misconfigured; or
            mapped from any DocsClientError/LLMClientError/
            FileNotFoundError/ValueError/KeyError raised while setting up
            the audit clients (before the background job starts).
    """
    _check_shared_secret(x_backend_shared_secret)

    if credentials is None:
        raise HTTPException(
            status_code=401, detail="Missing or invalid Authorization header"
        )

    try:
        validate_access_token(credentials.credentials)
        docs_client = GoogleDocsClient.from_access_token(
            credentials.credentials, include_drive=True
        )
        llm_client = OpenRouterClient.from_env(model=request.model)
        brand_guidelines = BrandGuidelines(None)
    except (
        DocsClientError,
        LLMClientError,
        FileNotFoundError,
        ValueError,
        KeyError,
    ) as err:
        raise HTTPException(status_code=_status_for(err), detail=str(err)) from err
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {err}") from err

    job_id = str(uuid.uuid4())
    with _jobs_lock:
        _jobs[job_id] = _JobRecord(status="queued")

    _executor.submit(
        _run_audit_job,
        job_id,
        docs_client,
        llm_client,
        brand_guidelines,
        request.document_id,
        request.brief_id,
        request.channel,
    )

    return AuditJobSubmitResponse(job_id=job_id)


@app.get("/audit/{job_id}", response_model=AuditJobStatusResponse)
def get_audit_status(
    job_id: str,
    x_backend_shared_secret: Annotated[
        str | None, Header(alias=BACKEND_SECRET_HEADER)
    ] = None,
) -> AuditJobStatusResponse:
    """Poll a previously submitted audit job for its current status.

    Deliberately checks only the shared secret, not a bearer token: no
    Docs/Drive write happens here (those already happened, if at all, during
    background execution), so an unguessable job id plus the shared secret
    is enough gating for a single-demo-user deployment.

    Args:
        job_id: The id returned by a prior POST /audit call.
        x_backend_shared_secret: A static secret known to the Add-on and
            this backend.

    Returns:
        The job's current status, and its result/error once terminal.

    Raises:
        HTTPException: 401 if the shared secret is missing/invalid; 404 if
            no job exists under this id (either it was never submitted, or
            the backend instance that held it has since restarted).
    """
    _check_shared_secret(x_backend_shared_secret)

    with _jobs_lock:
        record = _jobs.get(job_id)

    if record is None:
        raise HTTPException(status_code=404, detail="Unknown job id")

    return AuditJobStatusResponse(
        job_id=job_id,
        status=record.status,
        result=record.result,
        error=record.error,
    )


def run() -> None:
    """Run the Verbatim audit API server via uvicorn, for local dev/manual testing."""
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))


if __name__ == "__main__":
    run()
