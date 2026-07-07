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

### Confirmed dead end: anchored comments on Google Docs specifically

`anchor` is built for non-Google file formats (video/text files, third-party
integrations) — passing it on a Google Doc returns 200 but the Docs web UI shows
the comment unanchored with an "Original content deleted" flag. Real Docs
selection anchors use a closed, internal `kix.`-prefixed format not exposed by
either the Docs or Drive API. `create_inline_comment`'s approach (quote
`matched_text` in the comment body) is the correct, standard workaround, not a
placeholder for something better — don't revisit this.

Also confirmed live: setting `quotedFileContent` (`{"mimeType": ..., "value":
...}`, a separate field from `anchor`) instead of/alongside omitting `anchor`
does **not** avoid the "Original content deleted" flag either. And the flag
isn't actually about deletion — it appeared on a comment whose target text
(`"MySchools portal"`) was never deleted, only highlighted, ruling out the
hypothesis that it's triggered by this project's own `deleteContentRange`
calls elsewhere in the document. It's Docs' generic fallback for "no
UI-recognized anchor," full stop, regardless of `quotedFileContent` or whether
the referenced text still exists. Not fixable from either API — don't revisit.

A tempting-looking alternative, **also a dead end for Verbatim**: Docs bookmarks.
The REST API can *link to* an existing bookmark (`updateTextStyle` with a
`textStyle.link.bookmark.id`/`tabId` payload), but there's no
`createBookmark`/`insertBookmark` `batchUpdate` request type — creating one is
only possible via Apps Script (`Body.newPosition` + `Document.addBookmark`),
which would mean standing up a second execution surface (an Apps Script web
app/Execution API) purely to plant anchors. Not worth it for what it buys.

**The actual workaround shipped:** for Editor-role documents (where
`create_suggestion` also can't get a native suggestion — see
[`resource-documents.md`](../google-docs-api/resource-documents.md)'s
`batchUpdate` section), `create_inline_comment` pairs the comment with a Docs
API (not Drive) `updateTextStyle` `backgroundColor` highlight over the matched
range, applied after the comment is posted. This doesn't use Drive's `anchor`
at all — it's a real, visible highlight in the document body — so it's a
different mechanism from the comment call itself, despite living right next to
it in `create_inline_comment`.

## `comments.list` / `comments.get`

`GET /drive/v3/files/{fileId}/comments` / `GET /drive/v3/files/{fileId}/comments/{commentId}`

Not used by any planned Verbatim tool (Verbatim only ever creates comments, never
reads existing ones back), but useful for manual verification during Day 2
development — list a file's comments after a test run to confirm
`create_inline_comment` actually posted what was expected.

### Gotcha

Like `files.get`, comment fields may need an explicit `fields` mask to get back
more than the default subset.
