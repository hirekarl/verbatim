# Knowledge base

Decomposed reference documentation for the external APIs Verbatim depends on. This exists so implementation work doesn't require re-fetching or re-reading Google's REST reference pages from scratch every session.

## Structure: map-and-leaf

Each external API gets its own subdirectory containing:

- **`MAP.md`** — the index for that API: service endpoint, auth scopes this project uses, and links to every leaf file underneath. Start here.
- **Leaf files** — one focused file per resource or concept (e.g. `resource-documents.md`, `concept-indices-and-ranges.md`). Each leaf covers an endpoint's signature, a minimal realistic request/response example, and a "Gotchas" section for anything that has bitten (or would bite) implementation work.

This mirrors the index-plus-detail-file pattern used elsewhere for fast lookup without re-deriving context each time.

## Scope

Coverage is intentionally scoped to the resources and methods Verbatim actually calls or has concretely planned to call (see `TODO.md`'s day-by-day plan), not an exhaustive dump of every resource in Google's Docs/Drive REST references. If a new endpoint gets used, add a leaf for it rather than reaching for the live docs cold.

## Available APIs

- [`google-docs-api/`](google-docs-api/MAP.md) — reading/writing Google Docs content (`get_document_content`, `get_campaign_context`, and Day 2's `create_suggestion`).
- [`google-drive-api/`](google-drive-api/MAP.md) — file metadata and comments (Day 2's `create_inline_comment` is a Drive API call, not a Docs API call — see that API's `resource-comments.md` for why).
- [`openrouter-api/`](openrouter-api/MAP.md) — OpenRouter chat completions API used for LLM audits.

## Keeping this current

These are hand-maintained, not auto-generated. When a leaf's content might have drifted from Google's live docs (new API version, changed field names), verify against the linked reference page before trusting it for anything load-bearing.
