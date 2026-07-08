# `documents` resource

Reference: <https://developers.google.com/workspace/docs/api/reference/rest/v1/documents>

## `documents.get`

`GET /v1/documents/{documentId}`

Gets the latest version of the specified document.

- **Used by:** `get_document_content` and `get_campaign_context` (Day 1) — same call, two different document IDs (the audited doc vs. the campaign brief doc).
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

See [`concept-document-structure.md`](concept-document-structure.md) for what the full range of `body.content` element types looks like, and [`concept-indices-and-ranges.md`](concept-indices-and-ranges.md) for what `startIndex`/`endIndex` actually mean.

### Gotchas

- The document doesn't come back as plain text — you get a structural tree. Getting "body text" out means walking `body.content` and concatenating every `paragraph.elements[].textRun.content`, not reading a single string field.
- Headings aren't a separate list — they're paragraphs whose `paragraphStyle.namedStyleType` happens to be `HEADING_1`..`HEADING_6`. You have to inspect every paragraph's style to find them.
- 404 means the document ID doesn't exist (or isn't a Docs file); 403 means it exists but isn't shared with the authenticated account. Both are common failure modes worth distinguishing in error handling rather than surfacing one generic "couldn't read document" message.

## `documents.batchUpdate` (Day 2 — not used yet)

`POST /v1/documents/{documentId}:batchUpdate`

Applies one or more update requests atomically. This is how `create_suggestion` works — via a plain `deleteContentRange` + `insertText` pair, same as a direct edit would use. **There is no `SuggestChangesRequest` type or any other suggestion-mode flag in the Docs API v1** (an earlier version of this note claimed otherwise; that was wrong). Whether the edit lands as a reviewable "Suggested edit" instead of a silent direct edit is entirely a side effect of the OAuth principal's sharing role on the document — Commenter/Suggester gets converted to a suggestion, Editor applies directly — confirmed against the live API, not just inferred from docs.

- **Scope:** requires the read-write `documents` scope, not `documents.readonly`.
- **Gotcha (forward-looking):** every request in a batch references text by `startIndex`/`endIndex`. If a batch contains multiple edits, earlier edits shift the indices that later edits in the *same batch* need to target — ordering and index math matters. See [`concept-indices-and-ranges.md`](concept-indices-and-ranges.md).

### Confirmed: `updateTextStyle` for Editor-role "editor marks"

For accounts with Editor access (where `batchUpdate` can't produce a native suggestion), `create_suggestion`/`create_inline_comment` fall back to manual in-text marks via `updateTextStyle`, confirmed live against a real doc:

```json
{
  "updateTextStyle": {
    "range": { "startIndex": 19, "endIndex": 26 },
    "textStyle": { "strikethrough": true },
    "fields": "strikethrough"
  }
}
```

- `fields` is a comma-separated `FieldMask` naming exactly which `textStyle` properties to write (`"strikethrough"`, `"bold,strikethrough"`, `"backgroundColor"`, ...) — properties present in `textStyle` but absent from `fields` are silently ignored, not applied.
- `backgroundColor` (highlighting) and `foregroundColor` (used to color the bold-inserted replacement text green, distinguishing it from the struck-through original) are both `OptionalColor`, nested as `{"color": {"rgbColor": {"red": ..., "green": ..., "blue": ...}}}` (floats 0.0–1.0) — not a bare `{"red": ...}`. Zero-valued channels are omitted from the API's echoed-back response (e.g. pure green comes back as `{"rgbColor": {"green": 0.6}}`, not `{"red": 0.0, "green": 0.6, "blue": 0.0}`) — don't mistake that for the color having been dropped.
- **Gotcha, confirmed live:** `insertText` inherits the text style of the character immediately preceding the insertion point. Inserting a bold replacement right after a struck-through original therefore requires explicitly setting `"strikethrough": false` (not just omitting it) in the replacement's own `updateTextStyle` request — confirmed live that the explicit override wins over inheritance.
- No index-shift compensation is needed for a single contiguous edit region (strikethrough the original → insert the replacement → restyle the newly inserted range) — see the confirmation in [`concept-indices-and-ranges.md`](concept-indices-and-ranges.md).

## `documents.create` (not used — Verbatim never creates documents)

`POST /v1/documents`

Creates a blank document. Verbatim only ever reads/annotates existing copywriter drafts and campaign briefs, so this method has no planned use — listed here only for completeness of the resource.
