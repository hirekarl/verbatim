# Workspace Add-on migration: feasibility & direction

**Status: in progress, started ahead of the original post-demo schedule (Karl-solo, #18/#19 merged 2026-07-08).**

This isn't new scope. `docs/research-notes.snapshot.md` already states the product intent plainly: "To minimize workflow friction, the agent must be built as a **Google Docs Workspace Add-on**." The CLI built for the demo (`src/verbatim/cli.py`) was originally scoped as a stand-in for that target, but per #20's discussion it's being kept as a permanent, first-class local-dev/direct-run entrypoint alongside the new hosted HTTP entrypoint, not retired once the Add-on ships.

A Chrome extension, floated as an alternative, isn't the right fit: Google Docs' editor body is canvas-rendered, so a content script has no reliable way to inject UI into, or read/write from, the document surface. A Workspace Add-on (sidebar UI, native Docs/Drive API access) is Google's actual supported extensibility mechanism for exactly this workflow, and it's what the original research already called for.

## 1. Why this doc exists / non-goals

This is a direction-setting document to scope a backlog item — not an implementation plan, not an infra buildout, not something with acceptance criteria yet.

Non-goal: rewriting `evaluator.py`, `agent.py`, `llm_client.py`, or `prompt.py` in Apps Script. The tool-calling loop, deterministic evaluator, and prompt assembly are Python today and should stay Python — none of that logic needs to move.

## 2. Current architecture recap

The CLI flow: `cli.py` parses `document_id`/`brief_id`/options, calls `GoogleDocsClient.from_local_credentials(scopes=WRITE_SCOPES, include_drive=True)`, then `agent.run_agent(...)`, which fetches the document and campaign brief, runs the deterministic evaluator, builds the system prompt, and loops over OpenRouter tool calls dispatching `create_suggestion`/`create_inline_comment` back to `docs_client`.

The fact this whole migration hinges on: `GoogleDocsClient.__init__(self, service, drive_service=None)` already takes a pre-built, already-authenticated Docs/Drive service — it has no OAuth logic of its own. OAuth acquisition lives entirely in the separate `from_local_credentials()` classmethod (`src/verbatim/docs_client.py`). That existing decoupling is what makes this migration a swap of the auth layer rather than a rewrite of the agent.

## 3. Add-on shape decision

Recommended: an **Editor Add-on** — Apps Script-backed, `CardService` sidebar, scoped to Docs as the single host — over a general Workspace Add-on spanning multiple hosts (Gmail/Calendar/Chat). Verbatim is Docs-only; there's no multi-host use case to justify the extra generality.

Design constraint: the Add-on is a thin trigger/UI shell only. Its entire job is:

1. Render a sidebar card with a "Run Verbatim Audit" button (and maybe a brief-ID input or config).
1. On click, call the existing Python backend over HTTPS (`UrlFetchApp`), passing document ID, brief ID, channel, and the Add-on's own OAuth token.
1. Render the JSON response (suggestions/comments made, errors) back into the card.

No Docs/Drive API calls happen in Apps Script itself in this design — all API calls stay in `docs_client.py`, unchanged.

## 4. Auth model swap

This is the crux of the migration. Today's `InstalledAppFlow.from_client_secrets_file(...).run_local_server(port=0)` plus `token.json`/`client_secret.json` assumes a single local user with a browser and a filesystem. None of that holds inside a hosted, multi-user Add-on.

Options considered:

1. **Apps Script calls the Docs/Drive APIs itself**, via the `Docs`/`Drive` Advanced Services and `ScriptApp.getOAuthToken()`, with the backend only ever handling plain text in and suggested edits out. Rejected — this pulls the range-locating/UTF-16-indexing logic (`_locate_document_range`, `_utf16_length`, the suggestion-mode/strikethrough handling) into Apps Script alongside the existing Python implementation, forking it across two languages and violating the thin-shell constraint from §3.
1. **Recommended: the Add-on forwards its own OAuth access token to the backend on each call.** The backend builds `google.oauth2.credentials.Credentials(token=...)` from that token and passes it into the same `build("docs", "v1", credentials=...)` / `build("drive", "v3", credentials=...)` calls used today — i.e. `GoogleDocsClient` gets constructed exactly as it is now, just from a different credential source. This replaces `from_local_credentials()` with a new `from_access_token(token, include_drive)` classmethod. Apps Script's `appsscript.json` declares the needed `oauthScopes` (`documents.readonly`, `documents`, `drive`, plus `script.external_request` for `UrlFetchApp`). No server-side token storage is needed at all — Apps Script re-fetches a fresh token on every invocation, replacing `token.json`'s refresh handling entirely.
1. **Domain-wide delegation / service-account impersonation** — future consideration only, relevant if Verbatim ever needs to run unattended or scheduled rather than user-initiated from an open doc. Rejected for this migration: adds admin-console setup and a broader trust surface for no benefit, since every run today is triggered by a copywriter inside a document they already have open.

Open concern introduced by option 2 that doesn't exist in the CLI today: the backend becomes an internet-reachable HTTP endpoint and must validate that an inbound bearer token is a legitimate Google-issued token for the expected OAuth client (e.g. a tokeninfo check) before trusting it. Resolved in #21 — see `src/verbatim/token_validator.py` and `.knowledge-base/google-oauth2-api/`.

One scope fact carries over unchanged: `WRITE_SCOPES`'s full `drive` scope (not `drive.file`) is already required today, confirmed live and documented in `.knowledge-base/google-drive-api/MAP.md`, because `drive.file` 404s on `comments.create` for docs the app didn't create/open via Picker. That's a Google-classified sensitive/restricted scope, worth flagging early in any OAuth consent-screen discussion.

## 5. What's reusable vs. what changes

| File                                                                | Change                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `docs_client.py`                                                    | No change to any API-calling method (`get_document_content`, `get_campaign_context`, `create_suggestion`, `create_inline_comment`, `list_comments`, range-locating/UTF-16 helpers). Only `_load_credentials`/`from_local_credentials` are replaced by `from_access_token(token, include_drive)`.                                                                                                                                                                 |
| `agent.py`                                                          | No change — `run_agent()` takes an already-constructed `GoogleDocsClient`/`OpenRouterClient` and doesn't care how either was authenticated.                                                                                                                                                                                                                                                                                                                      |
| `llm_client.py`, `prompt.py`, `evaluator.py`, `brand_guidelines.py` | No anticipated change.                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| `cli.py`                                                            | **Retained, not retired** (amended per #24/#20 discussion) — the CLI stays as a first-class local-dev/direct-run entrypoint. A new `http_api.py` module is added alongside it (FastAPI route parsing a JSON request body + `Authorization` bearer token instead of argv, returning JSON instead of printing to stdout), reusing `run_agent()` exactly as `cli.py` does. `[project.scripts]` keeps `verbatim` (CLI) and gains a second entry for the HTTP server. |
| `pyproject.toml`                                                    | New dependency group for the HTTP framework + ASGI/WSGI server; `[project.scripts]` either dropped or kept alongside the new hosted entrypoint for local dev.                                                                                                                                                                                                                                                                                                    |
| `data/brand_guidelines.json`                                        | No change — still a bundled fixture read at request time.                                                                                                                                                                                                                                                                                                                                                                                                        |

Because OAuth acquisition was already isolated from `GoogleDocsClient`'s constructor, this migration is "swap the auth/service-construction layer and the entrypoint," not a rewrite of the agent.

## 6. Hosting

Recommend **Cloud Run** over Cloud Functions: this is already a normal Python app with real dependencies (`google-api-python-client`, `openai`, etc.), and the tool-calling loop can run up to `max_tool_call_rounds=20` LLM round trips, which wants more headroom over request timeout and concurrency than a single function gives. `OPENROUTER_API_KEY` moves to Secret Manager (replacing the local `.env`); the container is built from the existing `src/verbatim` package; no persistent volume is needed since there's no more `token.json` to manage.

Implemented in #23: a multi-stage `Dockerfile` at the repo root builds `verbatim-server` (the HTTP entrypoint, `http_api.py`) via `uv sync --frozen --no-dev`, not the CLI — `cli.py`'s local OAuth consent flow has no meaning inside a container. **Deployed**: `verbatim-backend` on Cloud Run, region `us-east4`, project `verbatim-501715` — `https://verbatim-backend-75857425003.us-east4.run.app`. Confirmed live: `/docs` returns 404 (`VERBATIM_DISABLE_DOCS=1`), `/audit` returns 401 without a valid `BACKEND_SHARED_SECRET`.

`GOOGLE_OAUTH_CLIENT_ID` is now set on the live service, sourced from the standalone Apps Script project (#22, `addon/`) after associating it with `verbatim-501715` via the script editor's Project Settings → Google Cloud Platform (GCP) Project → project number `75857425003`, then reading the auto-created OAuth 2.0 Client ID off that project's [Credentials page](https://console.cloud.google.com/apis/credentials?project=verbatim-501715). Updated via `gcloud run services update verbatim-backend --region=us-east4 --project=verbatim-501715 --update-env-vars=GOOGLE_OAUTH_CLIENT_ID=...` (not `--set-env-vars`, to avoid clobbering `VERBATIM_DISABLE_DOCS`) — confirmed both are still in effect after the update.

Still outstanding: setting the Add-on's Script Properties (`BACKEND_URL`, `BACKEND_SHARED_SECRET`, optional `DEFAULT_BRIEF_ID`/`CHANNEL` — see `addon/README.md`; brief ID itself is a sidebar text field, not a Script Property) and an actual end-to-end run via **Deploy → Test deployments** against a real Google Doc. Both are manual, in-browser steps with no CLI/API path.

The actual command run (`GOOGLE_OAUTH_CLIENT_ID` omitted — see above):

```sh
gcloud run deploy verbatim-backend \
  --image=us-east4-docker.pkg.dev/verbatim-501715/verbatim/verbatim-backend:latest \
  --region=us-east4 \
  --allow-unauthenticated \
  --set-env-vars="VERBATIM_DISABLE_DOCS=1" \
  --set-secrets="OPENROUTER_API_KEY=openrouter-api-key:latest,BACKEND_SHARED_SECRET=backend-shared-secret:latest" \
  --project=verbatim-501715
```

Notes on that command:

- `GOOGLE_OAUTH_CLIENT_ID` is a plain env var, not a Secret Manager secret — it's a public client identifier (not sensitive), unlike `OPENROUTER_API_KEY`.
- `VERBATIM_DISABLE_DOCS=1` turns off FastAPI's `/docs`/`/redoc`/`/openapi.json` — no reason to hand an internet-reachable deployment a free map of its API surface. Left enabled locally (`uv run verbatim-server` with no env override) for dev convenience.
- **On Windows PowerShell**, quote `--set-env-vars`/`--set-secrets` values explicitly (as above) — passing them unquoted through `gcloud`'s `.ps1` wrapper mangles comma-separated key=value lists (observed directly: a two-entry `--set-secrets` list arrived at gcloud with one entry's key dropped and the two joined by a space instead of a comma, crashing with `Invalid secret spec`).
- `--allow-unauthenticated` is a deliberate choice, not an oversight: the real security boundary is the app-level tokeninfo check in `token_validator.py` (#21) plus the `BACKEND_SHARED_SECRET` header check in `http_api.py` (a cheap first-line filter against scanning/probing, checked before that tokeninfo network call even happens), not Cloud Run's own IAM-based invoker auth. Requiring the latter too would mean the Add-on also needs to mint and forward a Google-signed ID token audienced to this specific Cloud Run service — a second, separate auth concern from the OAuth access token `token_validator.py` already checks, and Apps Script has no clean way to produce one without embedding a service-account key. A real fix (an internal auth-proxy Cloud Run service sitting in front of this one, itself requiring IAM auth) is tracked as a deliberate follow-up on [#33](https://github.com/hirekarl/verbatim/issues/33), not solved here.
- `openrouter-api-key` and `backend-shared-secret` must already exist as Secret Manager secrets in the target project (`gcloud secrets create <name> --data-file=-`), and the Cloud Run service's runtime service account needs `roles/secretmanager.secretAccessor` on each.

## 7. Knowledge-base gap

`.knowledge-base/` currently has zero coverage of Apps Script, `CardService`, the Add-on manifest (`appsscript.json`), `UrlFetchApp`, or Workspace Add-on OAuth/publishing — unlike the Docs/Drive/OpenRouter REST APIs already mapped there. Action item for whenever this work is actually picked up (not done as part of this doc): add `.knowledge-base/google-workspace-addons/MAP.md` plus leaves, following the existing map-and-leaf convention in `.knowledge-base/README.md`. Likely leaves: `concept-appsscript-manifest.md`, `concept-cardservice-ui.md`, `concept-oauth-scopes-and-triggers.md`, `concept-urlfetchapp.md`.

## 8. Sizing & risk

Order-of-magnitude only, not a committed estimate, for a two-person team.

- New toolchain neither Karl nor Christina has used: the Apps Script IDE / `clasp`, `appsscript.json`, `CardService` — real ramp-up cost, not just a translation exercise.
- OAuth consent screen / Google Workspace Marketplace SDK configuration is required even for internal, single-domain installation; the full `drive` scope (already required today) is Google-classified as sensitive, which matters more the more visible this becomes.
- New hosted backend deployment (containerize, Secret Manager, Cloud Run service) plus the inbound-token-validation concern from §4.
- Slower dev loop: testing an Editor Add-on means binding to a real test document and using the Apps Script online editor or `clasp push`, rather than `uv run verbatim <document_id> <brief_id>`.

Rough statement: at least a week of focused solo work once actually started, likely more given zero prior team experience with Apps Script/Add-ons. Scope this as its own mini-sprint, not something squeezed into spare post-demo time.

## 9. Open questions

- ~~Exact inbound-token validation mechanism for the backend endpoint.~~ **Resolved** (see #21): a call to Google's tokeninfo endpoint, checking HTTP status, `aud`/`azp` against `GOOGLE_OAUTH_CLIENT_ID`, and required scope, in `src/verbatim/token_validator.py` — see `.knowledge-base/google-oauth2-api/`.
- ~~Single GCP project (Apps Script + backend together) vs. two.~~ **Resolved** (see #24): single project for v1 — simplest for a two-person team, revisit only if it needs to grow.
- ~~Ordering relative to Christina's already-planned post-demo rotation into Docs API/agent-loop territory (`list_comments` work) — does one block the other?~~ **Resolved** (see #24): no blocking relationship — `list_comments` is a separate, orthogonal method in `docs_client.py`; both can proceed independently post-demo.
- ~~Whether v1 needs a brief-ID picker UI in the sidebar, or can start with a hardcoded/config value.~~ **Resolved, then reconsidered**: #24 originally resolved on a hardcoded/config value to keep the shell thin. Before the Add-on was actually tested, Karl decided against hardcoding it after all — `addon/Code.gs` now has a sidebar `TextInput` for the brief ID (a `CardService.TextInput` is still within the "thin shell" widget-catalog constraint from §3, just not a *fixed* value), read fresh via `e.formInput.briefId` on every run. An optional `DEFAULT_BRIEF_ID` Script Property pre-fills the field for convenience without forcing a fixed value. `extractDocId()` in the same file also accepts a full Google Docs share URL, not just a raw document ID, applied to both the brief ID and the currently-open document's ID. See `addon/README.md`.
