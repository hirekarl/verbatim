# Tokeninfo

Reference documentation for validating a Google OAuth2 access token before trusting it.

## `GET /tokeninfo`

Given an access token, returns metadata about it (or an error if it's invalid/expired). Used defensively here — the caller doesn't get anything from this endpoint that lets it *use* the token, only whether the token is legitimate and who it was issued for.

Reference: <https://developers.google.com/identity/protocols/oauth2#validatingaccesstoken>

### Request

```http
GET https://oauth2.googleapis.com/tokeninfo?access_token=<token>
```

No auth header — the token being validated is the query parameter itself.

### Response

```json
{
  "azp": "1234567890-abc.apps.googleusercontent.com",
  "aud": "1234567890-abc.apps.googleusercontent.com",
  "scope": "https://www.googleapis.com/auth/documents https://www.googleapis.com/auth/drive",
  "exp": "1799999999",
  "expires_in": "3599",
  "email": "user@example.com",
  "email_verified": "true",
  "access_type": "online"
}
```

An invalid, malformed, or expired token returns HTTP 400:

```json
{
  "error": "invalid_token",
  "error_description": "Invalid Value"
}
```

### What `token_validator.py` checks

Per `docs/workspace-addon-migration.md` §4 and issue #21:

1. **HTTP status is 200.** A non-200 response means the token itself is invalid/expired/malformed — reject outright.
1. **`aud` (or `azp`) matches the expected OAuth client ID** (`GOOGLE_OAUTH_CLIENT_ID` env var — the single GCP project's client ID the Add-on is bound to, per #24's resolution). This is the actual security check: without it, *any* valid Google access token from *any* app would be accepted, not just ones minted for this Add-on.
1. **`scope` includes the scope(s) the request is about to use** (at minimum `https://www.googleapis.com/auth/documents`, matching `docs_client.py`'s `WRITE_SCOPES`) — catches a token that's legitimately Google-issued and audience-matched but wasn't actually granted the access this backend is about to attempt with it.

### Gotchas

- **`aud` vs. `azp`:** for access tokens obtained through a normal user-consent flow (which is what `ScriptApp.getOAuthToken()` produces), these are typically the same value — but check `aud` first, falling back to `azp` if absent, rather than assuming which field is populated.
- **This is a network call on every request.** No caching — tokens are short-lived (on the order of an hour, per `../google-workspace-addons/concept-oauth-scopes-and-triggers.md`) and single-use per the same leaf's guidance, so caching validation results isn't worth the complexity it'd add for this project's request volume.
- **Treat tokeninfo unreachability differently from an invalid token.** A network error/timeout calling this endpoint is a backend-side problem (upstream Google service unavailable), not proof the caller's token is bad — don't conflate the two into the same rejection reason.
- **Never log the raw token value**, including in error messages — it's a live credential for the duration of its validity.
