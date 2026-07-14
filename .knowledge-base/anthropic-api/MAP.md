# Anthropic API

Reference documentation index for the native Anthropic Messages API.

## Service Endpoint

- **Base URL:** `https://api.anthropic.com`
- **Reference:** <https://platform.claude.com/docs/en/api/messages>

## Authentication

Authentication is handled via the `x-api-key` header (set automatically by the `anthropic` Python SDK from the constructor's `api_key` argument):

```http
x-api-key: <ANTHROPIC_API_KEY>
anthropic-version: 2023-06-01
```

The client loads the key from the `ANTHROPIC_API_KEY` environment variable (which can be set in a local `.env` file).

## Leaf Files

- [`messages.md`](messages.md) — the Messages API endpoint (`POST /v1/messages`), request/response schema, and tool calling (`tool_use`/`tool_result`) integration.
