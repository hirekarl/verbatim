# Add-on OAuth model and triggers

Reference: <https://developers.google.com/apps-script/guides/services/authorization>, <https://developers.google.com/apps-script/add-ons/concepts/scopes>, <https://developers.google.com/apps-script/guides/triggers>

## How this differs from `docs_client.py`'s auth today

`src/verbatim/docs_client.py`'s `from_local_credentials()` runs `InstalledAppFlow.from_client_secrets_file(...).run_local_server(port=0)` — a one-time interactive browser consent flow, with the resulting token cached to `token.json` and refreshed locally thereafter. That entire model assumes one local user with a browser and a filesystem.

An Add-on has neither. Instead:

- **Authorization happens once, implicitly, when the user installs/first runs the Add-on** — Google shows the standard OAuth consent screen listing the scopes from `appsscript.json`'s `oauthScopes` (see `concept-appsscript-manifest.md`), the user approves, and Google manages the underlying token from then on. There's no `client_secret.json`, no `run_local_server`, no manual refresh logic — Apps Script's platform handles all of it.
- **`ScriptApp.getOAuthToken()`** returns a short-lived access token for the *currently executing user*, scoped to whatever `oauthScopes` the manifest declares, valid for the duration of the current script execution. This is the token the Add-on shell forwards to the Python backend per `docs/workspace-addon-migration.md` §4 option 2 — the backend then builds `google.oauth2.credentials.Credentials(token=...)` from it (issue #19, `GoogleDocsClient.from_access_token()`).
- **No server-side token storage or refresh needed at all.** Apps Script re-mints a fresh token on every invocation; there's no equivalent of `token.json` to persist or refresh in this model. This is explicitly why `docs/workspace-addon-migration.md` §4 calls the domain-wide-delegation alternative unnecessary — every run is already user-initiated with a fresh token in hand.

## Triggers relevant to the Add-on shell

- **`homepageTrigger`** (declared in the manifest) — fires when the user opens the Add-on's sidebar; returns the initial `Card`. This is where `buildAuditCard()` (see `concept-cardservice-ui.md`) gets wired in.
- **Simple triggers (`onOpen`, `onEdit`)** — Verbatim's Add-on is user-initiated by a button click, not a document-open or edit-driven workflow, so these aren't expected to be needed for v1. Note if that changes: simple triggers run with restricted authorization (can't call services needing scopes beyond a small default set) unless installed as **installable triggers**, which is a separate setup step.

## Gotchas

- **A token from `ScriptApp.getOAuthToken()` is short-lived** (on the order of an hour) and tied to the current execution — the backend can't cache and reuse it across separate user sessions/requests. Each `UrlFetchApp` call to the backend should carry a freshly-fetched token, and the backend should treat every incoming token as single-use rather than something worth persisting.
- **The backend must independently verify the token is legitimate** before trusting it to build credentials — a bearer token arriving over HTTPS from an internet-reachable endpoint isn't automatically proof of anything by itself. This is the open concern tracked as issue #21 (not solved by this leaf) — likely mechanism is a call to Google's tokeninfo endpoint checking the token's audience/client ID match the Add-on's expected OAuth client.
- **Scope mismatches fail at token-mint time, not at the API-call site.** If `appsscript.json` doesn't list a scope `docs_client.py`'s downstream Docs/Drive calls need, `ScriptApp.getOAuthToken()` still succeeds — it just won't include that scope, and the *Python backend's* API call will fail with a 403 far from where the actual misconfiguration is. Keep `appsscript.json`'s `oauthScopes` in sync with `docs_client.py`'s `WRITE_SCOPES` by hand; nothing enforces this automatically across the two languages.
