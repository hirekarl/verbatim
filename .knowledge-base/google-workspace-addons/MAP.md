# Google Workspace Add-ons (Apps Script)

- **Runtime:** Google Apps Script, not a REST API called from Python — this is JavaScript-like code that runs inside Google's own execution environment, bound to (or installed as) an Add-on. Nothing in this section is called via `googleapiclient.discovery.build(...)`, unlike the `google-docs-api` and `google-drive-api` sections.
- **Editor Add-on type used:** a Docs-only **Editor Add-on** (`CardService` sidebar), not a general Workspace Add-on spanning multiple hosts. See `docs/workspace-addon-migration.md` §3 for why (Verbatim is Docs-only, no multi-host use case).
- **Official reference:** <https://developers.google.com/apps-script/add-ons/editors>

## Leaves

- [`concept-appsscript-manifest.md`](concept-appsscript-manifest.md) — the `appsscript.json` manifest: `oauthScopes`, `addOns.common`/`addOns.editors` config for a Docs Editor Add-on.
- [`concept-cardservice-ui.md`](concept-cardservice-ui.md) — `CardService`: building the sidebar UI (`Card`, `CardHeader`, `CardSection`, widgets, the homepage-trigger pattern).
- [`concept-oauth-scopes-and-triggers.md`](concept-oauth-scopes-and-triggers.md) — the Add-on OAuth model (`ScriptApp.getOAuthToken()`, install/runtime triggers) and how it differs from the installed-app flow `src/verbatim/docs_client.py` uses today.
- [`concept-urlfetchapp.md`](concept-urlfetchapp.md) — `UrlFetchApp.fetch()`: how the Add-on shell calls out to Verbatim's Python backend over HTTPS.

## What this project uses it for

Per `docs/workspace-addon-migration.md` §3, the Add-on is a **thin trigger/UI shell only** — no Docs/Drive API calls happen in Apps Script itself:

1. Render a sidebar card (`CardService`) with a "Run Verbatim Audit" button.
1. On click, `UrlFetchApp.fetch()` the backend (issue #20's HTTP entrypoint), passing document ID, brief ID, channel, and the Add-on's own OAuth access token (`ScriptApp.getOAuthToken()`).
1. Render the JSON response (suggestions/comments made, errors) back into the card.

All the actual Docs/Drive API work (range-locating, UTF-16 indexing, suggestion/comment creation) stays in `src/verbatim/docs_client.py`, unchanged — see `google-docs-api/MAP.md` and `google-drive-api/MAP.md`. The access token forwarded by `UrlFetchApp` is what issue #19's `GoogleDocsClient.from_access_token()` consumes on the backend.

## Scope note

Issue #22 ("Build Editor Add-on shell") has landed the actual source at `addon/` (`appsscript.json`, `Code.gs`, `Backend.gs`) — see `addon/README.md` for what's there and the `clasp` setup steps to actually deploy it. It hasn't been pushed to a real Apps Script project or exercised against a live Docs sidebar yet, so treat the leaves here as accurate against Google's current docs as of this writing, and verify against the linked references before relying on anything load-bearing beyond what `addon/` already reflects.
