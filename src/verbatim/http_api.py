"""FastAPI HTTP entrypoint wrapping run_agent() for a hosted Workspace Add-on backend.

Kept alongside cli.py, not as a replacement for it: cli.py remains the
local-dev/direct-run entrypoint, and this module is the hosted entrypoint a
future Apps Script Add-on calls over HTTPS via UrlFetchApp.
"""

import os
from typing import Annotated

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from verbatim.agent import run_agent
from verbatim.brand_guidelines import BrandGuidelines
from verbatim.docs_client import AuthenticationError, DocsClientError, GoogleDocsClient
from verbatim.llm_client import LLMClientError, OpenRouterClient
from verbatim.token_validator import validate_access_token

DEFAULT_MODEL = "google/gemini-2.5-flash"

_STATUS_BY_ERROR: dict[type[Exception], int] = {
    AuthenticationError: 401,
    DocsClientError: 502,
    LLMClientError: 502,
    FileNotFoundError: 400,
    ValueError: 400,
    KeyError: 400,
}

app = FastAPI(title="Verbatim Audit API")
_bearer_scheme = HTTPBearer(auto_error=False)


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


def _status_for(err: Exception) -> int:
    """Map a raised exception to an HTTP status code, most-specific type first.

    Args:
        err: The exception raised during the audit run.

    Returns:
        The HTTP status code to respond with; 500 if the type is unmapped.
    """
    for error_type in type(err).__mro__:
        if error_type in _STATUS_BY_ERROR:
            return _STATUS_BY_ERROR[error_type]
    return 500


@app.post("/audit", response_model=AuditResponse)
def audit(
    request: AuditRequest,
    credentials: Annotated[
        HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)
    ],
) -> AuditResponse:
    """Run one audit pass over a Google Doc via a hosted Add-on backend.

    Args:
        request: The document/brief/channel/model to audit.
        credentials: The bearer token forwarded by the calling Add-on, via
            ``ScriptApp.getOAuthToken()`` on the Apps Script side.

    Returns:
        The audit run's outcome (suggestions/comments made, cap status).

    Raises:
        HTTPException: 401 if the Authorization header is missing/malformed
            or the bearer token fails tokeninfo validation, or mapped from
            any DocsClientError/LLMClientError/FileNotFoundError/
            ValueError/KeyError raised during the run.
    """
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

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id=request.document_id,
            brief_id=request.brief_id,
            brand_guidelines=brand_guidelines,
            target_channel=request.channel,
        )
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

    return AuditResponse(
        suggestions_made=result.suggestions_made,
        comments_made=result.comments_made,
        stopped_due_to_max_rounds=result.stopped_due_to_max_rounds,
    )


def run() -> None:
    """Run the Verbatim audit API server via uvicorn, for local dev/manual testing."""
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))


if __name__ == "__main__":
    run()
