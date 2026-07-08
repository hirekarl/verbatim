# Verbatim Editor Add-on

The Apps Script side of the Workspace Add-on migration (`docs/workspace-addon-migration.md`, issue #22). A thin trigger/UI shell only — no Docs/Drive API calls happen here; all of that stays in `src/verbatim/docs_client.py`, called by the Python backend (`src/verbatim/http_api.py`) this shell talks to over HTTPS.

## Files

- `appsscript.json` — the manifest: runtime, `oauthScopes`, and the Docs Editor Add-on registration (`homepageTrigger`). See `.knowledge-base/google-workspace-addons/concept-appsscript-manifest.md`.
- `Code.gs` — the homepage trigger and `CardService` sidebar UI: a "Campaign Brief (Doc ID or share link)" text field, a "Run Verbatim Audit" button, and rendering results/errors back into the card. See `.knowledge-base/google-workspace-addons/concept-cardservice-ui.md`.
- `Backend.gs` — the `UrlFetchApp` call to the Python backend, forwarding `ScriptApp.getOAuthToken()` as a bearer token. See `.knowledge-base/google-workspace-addons/concept-urlfetchapp.md`.

## Current status

A real **standalone** Apps Script project exists (Editor Add-ons must be standalone, not container-bound to one Doc): <https://script.google.com/d/1jggJP1gj_kM_016UwTcCM-iMge-l0_V8xDelLhPYX1omnkhS0NvxKhP1/edit>, associated with the `verbatim-501715` GCP project, source pushed via `clasp`. Still outstanding: the Script Properties below and an actual end-to-end run via **Deploy → Test deployments**.

## Setup

This directory is the source, pushed to the Apps Script project via [`clasp`](https://github.com/google/clasp) (Apps Script's CLI), chosen over the online IDE so this source stays in the same repo/history as the Python backend it calls.

1. `npm install -g @google/clasp` (or `npx clasp`), then `clasp login`. Requires the Apps Script API to be enabled first, one-time, at <https://script.google.com/home/usersettings>.
1. `clasp create --type standalone --title "Verbatim"` (or `clasp clone <scriptId>` if a project already exists) inside this directory — this generates a `.clasp.json` pointing at the new script's ID. `.clasp.json` is deliberately not committed (it's per-developer/per-environment); each person setting this up creates their own. **Note**: `clasp create` overwrites `appsscript.json` with a generic default — restore this repo's version (`git checkout -- addon/appsscript.json`) before pushing.
1. `clasp push --force` to upload `appsscript.json`/`Code.gs`/`Backend.gs`. `--force` is needed the first time since `clasp create`'s own manifest differs from this repo's.
1. Associate the script with the backend's GCP project, so `token_validator.py` has a real, discoverable OAuth client ID to check tokens against (a script left on Google's hidden default project has none): in the script editor, **Project Settings → Google Cloud Platform (GCP) Project → Change project**, enter the target project's number. Then find the auto-created OAuth 2.0 Client ID under that project's Credentials page and set it as the backend's `GOOGLE_OAUTH_CLIENT_ID`.
1. In the Apps Script project's **Project Settings → Script Properties**, set:
   - `BACKEND_URL` — the deployed backend's base URL (issue #23; e.g. a Cloud Run service URL — see `docs/workspace-addon-migration.md` §6 for the `Dockerfile`/`gcloud run deploy` steps). No default — the Add-on throws a clear error if unset rather than silently failing.
   - `BACKEND_SHARED_SECRET` — must match the backend's `BACKEND_SHARED_SECRET` env var exactly. A cheap first-line filter checked before the backend even looks at the `Authorization` bearer token; no default, request is rejected with a clear error if unset on either side.
   - `DEFAULT_BRIEF_ID` — optional; pre-fills the sidebar's brief-ID field so a copywriter running repeated audits against the same campaign doesn't have to retype it each time. Accepts either a raw document ID or a full Google Docs share URL (see below) — nothing about which brief to use is otherwise baked into the deployment.
   - `CHANNEL` — optional; a target marketing channel (e.g. `email`, `blog`, `twitter`) to activate channel-specific evaluator rules. Leave unset to omit it from the request.
1. Test via **Deploy → Test deployments** against a real Google Doc, with the backend reachable and `GOOGLE_OAUTH_CLIENT_ID`/`BACKEND_SHARED_SECRET` configured there to match this Add-on.

## Brief ID input

Per Karl's reconsideration of issue #24's original "hardcoded/config value" resolution, the campaign brief is **not** a fixed Script Property — the sidebar has a text field for it (`CardService.newTextInput`, per `.knowledge-base/google-workspace-addons/concept-cardservice-ui.md`), read fresh on every run via `e.formInput.briefId`. `Code.gs`'s `extractDocId()` accepts either a raw document ID or a full Google Docs/Drive share URL (`.../document/d/<ID>/edit`, `.../file/d/<ID>/view`, etc.) and pulls the ID out of the `/d/<ID>` path segment, so users never have to hand-strip a URL down to its ID — applied to both the brief ID and the currently-open document's ID (`e.docs.id`), even though the latter is already expected to be a clean ID from the Docs framework.

## Known limitation (flagged, not solved here)

`UrlFetchApp.fetch()` blocks synchronously for the whole backend call, and Apps Script's default fetch timeout (roughly 30–60s) may be shorter than a real audit run's LLM tool-calling loop (up to `max_tool_call_rounds=20` round trips) takes to complete. Per `.knowledge-base/google-workspace-addons/concept-urlfetchapp.md`, this needs confirming against real end-to-end latency now that the backend is deployed (#23) — if it's a problem, v2 would need the backend to return a job ID immediately and have the Add-on poll a second endpoint, rather than this v1's single blocking call.

Separately, the deployed backend uses `--allow-unauthenticated` at the Cloud Run platform level (app-level checks — `BACKEND_SHARED_SECRET` and tokeninfo validation — are the real gate). Fronting it with an internal auth-proxy to close that gap is tracked as a deliberate follow-up on [#33](https://github.com/hirekarl/verbatim/issues/33).
