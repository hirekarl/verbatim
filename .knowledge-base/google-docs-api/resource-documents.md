# `documents` resource

Reference: <https://developers.google.com/workspace/docs/api/reference/rest/v1/documents>

## `documents.get`

`GET /v1/documents/{documentId}`

Gets the latest version of the specified document.

- **Used by:** `get_document_content` and `get_campaign_context` (Day 1) — same
  call, two different document IDs (the audited doc vs. the campaign brief doc).
- **Scope:** `documents.readonly` is sufficient — this is a read-only call.

Minimal example response shape (trimmed):

```json
{
  "documentId": "1AbCdEf...",
  "title": "Q3 Launch Blog Draft",
  "body": {
    "content": [
      {
        "startIndex": 1,
        "endIndex": 15,
        "paragraph": {
          "elements": [
            { "startIndex": 1, "endIndex": 15, "textRun": { "content": "Big News!\n" } }
          ],
          "paragraphStyle": { "namedStyleType": "HEADING_1" }
        }
      },
      {
        "startIndex": 15,
        "endIndex": 60,
        "paragraph": {
          "elements": [
            { "startIndex": 15, "endIndex": 60, "textRun": { "content": "Our new feature helps you...\n" } }
          ],
          "paragraphStyle": { "namedStyleType": "NORMAL_TEXT" }
        }
      }
    ]
  }
}
```

See [`concept-document-structure.md`](concept-document-structure.md) for what the
full range of `body.content` element types looks like, and
[`concept-indices-and-ranges.md`](concept-indices-and-ranges.md) for what
`startIndex`/`endIndex` actually mean.

### Gotchas

- The document doesn't come back as plain text — you get a structural tree. Getting
  "body text" out means walking `body.content` and concatenating every
  `paragraph.elements[].textRun.content`, not reading a single string field.
- Headings aren't a separate list — they're paragraphs whose
  `paragraphStyle.namedStyleType` happens to be `HEADING_1`..`HEADING_6`. You have to
  inspect every paragraph's style to find them.
- 404 means the document ID doesn't exist (or isn't a Docs file); 403 means it
  exists but isn't shared with the authenticated account. Both are common failure
  modes worth distinguishing in error handling rather than surfacing one generic
  "couldn't read document" message.

## `documents.batchUpdate` (Day 2 — not used yet)

`POST /v1/documents/{documentId}:batchUpdate`

Applies one or more update requests atomically. This is how `create_suggestion`
will work — via a `SuggestChangesRequest`-flavored update inside the request body,
so the edit shows up as a Google Docs "suggestion" (Suggest Changes mode) rather
than a direct silent edit.

- **Scope:** requires the read-write `documents` scope, not `documents.readonly`.
- **Gotcha (forward-looking):** every request in a batch references text by
  `startIndex`/`endIndex`. If a batch contains multiple edits, earlier edits shift
  the indices that later edits in the *same batch* need to target — ordering and
  index math matters. See
  [`concept-indices-and-ranges.md`](concept-indices-and-ranges.md).

## `documents.create` (not used — Verbatim never creates documents)

`POST /v1/documents`

Creates a blank document. Verbatim only ever reads/annotates existing copywriter
drafts and campaign briefs, so this method has no planned use — listed here only for
completeness of the resource.
