"""Validates inbound Google OAuth bearer tokens before trusting them.

Used only by the HTTP entrypoint (`http_api.py`) -- a bearer token arriving
over HTTPS from an internet-reachable endpoint isn't automatically proof of
anything by itself. The CLI's `from_local_credentials()` auth path has no
equivalent need, since a locally obtained token is already implicitly
trusted by the user running it. See `.knowledge-base/google-oauth2-api/` and
`docs/workspace-addon-migration.md` §4.
"""

import os

import httpx
from dotenv import load_dotenv

from verbatim.docs_client import AuthenticationError, DocsClientError

TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
REQUIRED_SCOPE = "https://www.googleapis.com/auth/documents"


class TokenValidationError(AuthenticationError):
    """Raised when an inbound bearer token fails tokeninfo validation."""


def _get_expected_client_id() -> str:
    """Load the expected OAuth client ID (audience) from the environment.

    Loads a `.env` file first, if one is present, mirroring
    `OpenRouterClient.from_env`'s environment-loading behavior.

    Returns:
        The configured GOOGLE_OAUTH_CLIENT_ID value.

    Raises:
        RuntimeError: GOOGLE_OAUTH_CLIENT_ID is not set -- a server
            misconfiguration, not something a caller's token can fix.
    """
    load_dotenv()
    client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    if not client_id:
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_ID environment variable is not set")
    return client_id


def validate_access_token(token: str) -> None:
    """Validate an inbound bearer token against Google's tokeninfo endpoint.

    Args:
        token: The bearer token forwarded by the calling Add-on, via
            ``ScriptApp.getOAuthToken()`` on the Apps Script side.

    Raises:
        TokenValidationError: The token is invalid/expired, its audience
            doesn't match the expected OAuth client, or it's missing the
            scope this backend is about to use it for.
        DocsClientError: The tokeninfo endpoint couldn't be reached.
        RuntimeError: GOOGLE_OAUTH_CLIENT_ID isn't configured.
    """
    expected_client_id = _get_expected_client_id()

    try:
        response = httpx.get(TOKENINFO_URL, params={"access_token": token}, timeout=5.0)
    except httpx.HTTPError as err:
        raise DocsClientError(
            f"Unable to reach Google tokeninfo endpoint: {err}"
        ) from err

    if response.status_code != 200:
        raise TokenValidationError("Bearer token is invalid or expired")

    payload = response.json()
    audience = payload.get("aud") or payload.get("azp")
    if audience != expected_client_id:
        raise TokenValidationError(
            "Bearer token audience does not match expected OAuth client"
        )

    scopes = (payload.get("scope") or "").split()
    if REQUIRED_SCOPE not in scopes:
        raise TokenValidationError("Bearer token missing required scope")
