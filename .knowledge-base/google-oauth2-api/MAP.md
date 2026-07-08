# Google OAuth2 API (tokeninfo)

Reference documentation index for validating inbound Google OAuth access tokens.

## Service Endpoint

- **Base URL:** `https://oauth2.googleapis.com`
- **Reference:** <https://developers.google.com/identity/protocols/oauth2#validatingaccesstoken>

## Authentication

None — this is itself the mechanism used to authenticate/validate a token presented by a caller. Called by `src/verbatim/token_validator.py` before an inbound bearer token (forwarded by an Add-on via `ScriptApp.getOAuthToken()`, see `../google-workspace-addons/concept-oauth-scopes-and-triggers.md`) is trusted to build `GoogleDocsClient.from_access_token()` credentials (issue #21).

## Leaf Files

- [`resource-tokeninfo.md`](resource-tokeninfo.md) — `GET /tokeninfo`, request/response schema, and the audience/scope checks Verbatim performs on the response.
