# `files` resource

Reference: <https://developers.google.com/workspace/drive/api/reference/rest/v3/files>

## `files.get`

`GET /drive/v3/files/{fileId}`

Retrieves a file's metadata (not its Docs-API content — that's
`documents.get`, see the Docs API knowledge base). Not used by Day 1, but relevant
if Verbatim ever needs to confirm a document's `mimeType`, sharing status, or
`modifiedTime` before/instead of fetching its full content.

### Gotcha: field masks

Drive API responses are **empty by default beyond an `id`/`kind`/`name` core** —
you must explicitly request fields via the `fields` query parameter (e.g.
`fields=id,name,mimeType,modifiedTime`) or you'll silently get back less than you
expect. This is a common surprise coming from the Docs API, which doesn't require
field masks the same way.

## `files.list`

`GET /drive/v3/files`

Lists/searches files. Supports a `q` query-string mini-language (e.g.
`mimeType='application/vnd.google-apps.document'`) and cursor-based pagination via
`pageToken`. **Not currently used or planned** — the PRD's tool contracts
(`get_document_content`, `get_campaign_context`) both take a document ID directly,
with no doc-discovery/search step. Listed here for completeness in case that
assumption changes.

### Gotcha: pagination

`list` responses return a `nextPageToken` when more results exist — a single call
is not guaranteed to return everything. Irrelevant today since nothing calls
`files.list`, but worth remembering if a future "search my drive for the campaign
brief" feature gets built.
