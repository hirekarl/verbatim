# Google Docs API

- **Service endpoint:** `https://docs.googleapis.com`
- **API version used:** v1
- **Scopes this project uses:** `https://www.googleapis.com/auth/documents.readonly`
  (read-only, Day 1). Day 2's `create_suggestion` will need the read-write
  `https://www.googleapis.com/auth/documents` scope instead.
- **Official reference:**
  <https://developers.google.com/workspace/docs/api/reference/rest/v1/documents>

## Leaves

- [`resource-documents.md`](resource-documents.md) — the `documents` resource:
  `get`, `batchUpdate`, `create`.
- [`concept-document-structure.md`](concept-document-structure.md) — how a
  document's JSON body is shaped (`StructuralElement`, `Paragraph`, `TextRun`,
  headings).
- [`concept-indices-and-ranges.md`](concept-indices-and-ranges.md) — UTF-16 index
  gotchas that matter for both reading text and (later) making `batchUpdate` edits.

## What this project uses it for

- `get_document_content` (Day 1, `src/verbatim/docs_client.py`) — `documents.get`
  against the audited document's ID.
- `get_campaign_context` (Day 1, same module) — `documents.get` against a *separate*
  campaign brief document's ID. Same endpoint, different document.
- `create_suggestion` (Day 2) — `documents.batchUpdate` with a
  `SuggestChangesRequest`, not built yet.

## Gotcha: comments are NOT a Docs API call

`create_inline_comment` (Day 2) is a **Drive API v3** call
(`POST /drive/v3/files/{fileId}/comments`), not a Docs API call, despite being
conceptually "a Google Docs comment." See
[`../google-drive-api/resource-comments.md`](../google-drive-api/resource-comments.md).
