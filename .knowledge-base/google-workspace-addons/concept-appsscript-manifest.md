# The `appsscript.json` manifest

Reference: <https://developers.google.com/apps-script/manifest>, <https://developers.google.com/apps-script/add-ons/editors/manifest>

Every Apps Script project has one `appsscript.json` manifest file. For an Editor Add-on it declares the runtime, the OAuth scopes the script needs, and where/how the Add-on attaches to the Docs UI.

## Minimal shape for a Docs Editor Add-on

```json
{
  "timeZone": "America/New_York",
  "runtimeVersion": "V8",
  "oauthScopes": [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/script.external_request"
  ],
  "addOns": {
    "common": {
      "name": "Verbatim",
      "logoUrl": "https://example.com/logo.png",
      "layoutProperties": {
        "primaryColor": "#4285F4"
      }
    },
    "docs": {
      "homepageTrigger": {
        "runFunction": "onHomepage"
      }
    }
  }
}
```

**Verified live** against a real standalone Apps Script project (`clasp push`) while building #22: `addOns.docs.homepageTrigger` is correct; the previously-documented `addOns.editors.docs.homepageTrigger` nesting is wrong and gets rejected by `clasp`/the Apps Script API with `"appsscript.json" has errors: Invalid manifest: unknown fields: [addOns.editors]`. Docs-editor config sits directly under `addOns`, a sibling of `addOns.common`, not nested under an `editors` wrapper.

## `oauthScopes`

Per `docs/workspace-addon-migration.md` §4, the recommended auth model has Apps Script forward its own OAuth access token to the Python backend rather than calling the Docs/Drive APIs itself — but the scopes still need to be declared here, because `ScriptApp.getOAuthToken()` (see `concept-oauth-scopes-and-triggers.md`) can only mint a token for scopes the manifest lists. Needed scopes carried over from `src/verbatim/docs_client.py`'s `WRITE_SCOPES`:

- `documents.readonly` / `documents` — same scopes `docs_client.py` already requests for read/write document access.
- `drive` — same full-`drive` scope already required today (confirmed live, documented in `../google-drive-api/MAP.md`) for `comments.create` to work on documents the app didn't create/open itself.
- `script.external_request` — required for `UrlFetchApp` to call any non-Google host (the Python backend). Without this scope, `UrlFetchApp.fetch()` throws at runtime.

## `addOns.docs`

Scopes the Add-on to Docs only (as opposed to `addOns.common` alone, which would make it a general Workspace Add-on offered across multiple hosts). `homepageTrigger.runFunction` names the function that builds and returns the sidebar's initial `Card` — see `concept-cardservice-ui.md`.

## Gotchas

- **Sensitive/restricted scopes trigger extra review.** The full `drive` scope is Google-classified as sensitive; publishing an Add-on (even for internal single-domain use) that requests it goes through OAuth consent-screen verification, not just a manifest change. Flagged already in `docs/workspace-addon-migration.md` §4 and §8 — budget calendar time, not just implementation time, for this step.
- **`runtimeVersion: "V8"` is not optional in practice.** The legacy Rhino runtime is deprecated; all new Add-on development should target V8 from the start.
- **The manifest is a separate file from script source**, pushed/pulled alongside `.gs`/`.js` files via `clasp` (the Apps Script CLI) if this project manages Add-on source outside the online IDE — worth deciding before #22 starts, since `clasp` needs its own auth setup distinct from anything `docs_client.py` uses.
