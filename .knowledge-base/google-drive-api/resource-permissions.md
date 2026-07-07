# `permissions` resource

Reference: <https://developers.google.com/workspace/drive/api/reference/rest/v3/permissions>

## `permissions.get` / `permissions.list`

`GET /drive/v3/files/{fileId}/permissions/{permissionId}` /
`GET /drive/v3/files/{fileId}/permissions`

Not called by any planned Verbatim tool. Documented here purely as a diagnostic
aid: if `documents.get` or a Drive call comes back `403 PERMISSION_DENIED`, these
endpoints (called with the *account owner's* credentials, not the OAuth-authenticated
copywriter's) are how you'd check whether the document is actually shared with the
authenticated account, rather than guessing.

### Gotcha

You need `documents.readonly`/Drive read scope on the *requesting* account, but you
also need the target document to have actually been shared with (or owned by) that
same account — a valid OAuth token doesn't imply access to an arbitrary document ID.
A 403 during Day 1 development most likely means "this test document isn't shared
with whichever Google account the OAuth consent flow was run as," not a code bug.
