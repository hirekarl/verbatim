# `comments` resource

Reference: <https://developers.google.com/workspace/drive/api/reference/rest/v3/comments>

## Gotcha: this is what `create_inline_comment` actually calls

The PRD (`docs/Verbatim PRD.docx`, Section 3a) lists `create_inline_comment`'s API
as "Google Docs API — POST /documents/{id}/comments." **That path doesn't exist on
the Docs API.** Comments on a Drive-hosted file (including Google Docs) are a
**Drive API v3** resource, keyed by the same file ID a Docs API call would use:

`POST /drive/v3/files/{fileId}/comments`

This matters concretely for Day 2: posting an inline comment needs a second
discovery service (`build("drive", "v3", credentials=...)`), not just the `docs` v1
service Day 1 builds. Budget for wiring up both services, not one.

## `comments.create`

`POST /drive/v3/files/{fileId}/comments`

Request body includes `content` (the comment's plain-text body — Verbatim's
rationale for the flag) and an `anchor` field describing what text range the
comment attaches to. The anchor format is Drive's own JSON micro-schema (region +
revision-scoped), not the same `startIndex`/`endIndex` pairs the Docs API uses —
don't assume Docs API ranges can be passed straight through.

## `comments.list` / `comments.get`

`GET /drive/v3/files/{fileId}/comments` / `GET /drive/v3/files/{fileId}/comments/{commentId}`

Not used by any planned Verbatim tool (Verbatim only ever creates comments, never
reads existing ones back), but useful for manual verification during Day 2
development — list a file's comments after a test run to confirm
`create_inline_comment` actually posted what was expected.

### Gotcha

Like `files.get`, comment fields may need an explicit `fields` mask to get back
more than the default subset.
