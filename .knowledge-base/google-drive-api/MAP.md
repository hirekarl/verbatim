# Google Drive API

- **Service endpoint:** `https://www.googleapis.com` (Drive-specific paths under
  `/drive/v3/...`)
- **API version used:** v3
- **Scopes this project uses:** none yet (Day 1 only touches the Docs API). Day 2's
  `create_inline_comment` will need `https://www.googleapis.com/auth/drive.file` (or
  broader `drive`, scoped down as far as it'll work) to post comments.
- **Official reference:**
  <https://developers.google.com/workspace/drive/api/reference/rest/v3>

## Leaves

- [`resource-files.md`](resource-files.md) — `files.get`/`files.list`: field masks,
  scopes, pagination.
- [`resource-comments.md`](resource-comments.md) — `comments.create`/`list`/`get`:
  what `create_inline_comment` (Day 2) actually calls, and why it's here and not in
  the Docs API knowledge base.
- [`resource-permissions.md`](resource-permissions.md) — `permissions.get`/`list`:
  useful for diagnosing "why did I get a 403" rather than for anything Verbatim
  calls directly today.

## Scope note

Drive API v3 has many more resources than listed here (`replies`, `changes`,
`revisions`, `drives`, `about`, `apps`, `operations`, `channels`,
`accessproposals`, `approvals`). None of those are used or planned for Verbatim, so
they're deliberately not decomposed here — see the top-level
[`.knowledge-base/README.md`](../README.md)'s scope note. Add a leaf if/when one
becomes relevant.
