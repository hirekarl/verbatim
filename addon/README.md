# Verbatim Editor Add-on

The Apps Script side of the Workspace Add-on migration (`docs/workspace-addon-migration.md`, issue #22). A thin trigger/UI shell only — no Docs/Drive API calls happen here; all of that stays in `src/verbatim/docs_client.py`, called by the Python backend (`src/verbatim/http_api.py`) this shell talks to over HTTPS.

## Files

- `appsscript.json` — the manifest: runtime, `oauthScopes`, and the Docs Editor Add-on registration (`homepageTrigger`). See `.knowledge-base/google-workspace-addons/concept-appsscript-manifest.md`.
- `Code.gs` — the homepage trigger and `CardService` sidebar UI (the button, and rendering results/errors back into the card). See `.knowledge-base/google-workspace-addons/concept-cardservice-ui.md`.
- `Backend.gs` — the `UrlFetchApp` call to the Python backend, forwarding `ScriptApp.getOAuthToken()` as a bearer token. See `.knowledge-base/google-workspace-addons/concept-urlfetchapp.md`.

## Setup (not yet done — this is source only)

No Apps Script project has been created yet; this directory is the source that would be pushed to one via [`clasp`](https://github.com/google/clasp) (Apps Script's CLI), chosen over the online IDE so this source stays in the same repo/history as the Python backend it calls.

1. `npm install -g @google/clasp` (or `npx clasp`), then `clasp login`.
1. `clasp create --type docs --title "Verbatim"` (or `clasp clone <scriptId>` if a project already exists) inside this directory — this generates a `.clasp.json` pointing at the new script's ID. `.clasp.json` is deliberately not committed (it's per-developer/per-environment); each person setting this up creates their own.
1. `clasp push` to upload `appsscript.json`/`Code.gs`/`Backend.gs`.
1. In the Apps Script project's **Project Settings → Script Properties**, set:
   - `BACKEND_URL` — the deployed backend's base URL (issue #23; e.g. a Cloud Run service URL — see `docs/workspace-addon-migration.md` §6 for the `Dockerfile`/`gcloud run deploy` steps). No default — the Add-on throws a clear error if unset rather than silently failing.
   - `BRIEF_ID` — the campaign brief's Google Docs document ID to audit against. Per issue #24's resolution, v1 uses this fixed config value rather than a sidebar picker.
   - `CHANNEL` — optional; a target marketing channel (e.g. `email`, `blog`, `twitter`) to activate channel-specific evaluator rules. Leave unset to omit it from the request.
1. Test via **Deploy → Test deployments** against a real Google Doc, with the backend (`uv run verbatim-server`, or its Cloud Run deployment) reachable and `GOOGLE_OAUTH_CLIENT_ID` configured there to match this Add-on's OAuth client.

## Known limitation (flagged, not solved here)

`UrlFetchApp.fetch()` blocks synchronously for the whole backend call, and Apps Script's default fetch timeout (roughly 30–60s) may be shorter than a real audit run's LLM tool-calling loop (up to `max_tool_call_rounds=20` round trips) takes to complete. Per `.knowledge-base/google-workspace-addons/concept-urlfetchapp.md`, this needs confirming against real end-to-end latency once the backend is deployed (#23) — if it's a problem, v2 would need the backend to return a job ID immediately and have the Add-on poll a second endpoint, rather than this v1's single blocking call.
