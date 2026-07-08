# OpenRouter API

Reference documentation index for the OpenRouter LLM completions API.

## Service Endpoint

- **Base URL:** `https://openrouter.ai/api/v1`
- **Reference:** <https://openrouter.ai/docs/api-reference>

## Authentication

Authentication is handled via the `Authorization` header containing the bearer token:

```http
Authorization: Bearer <OPENROUTER_API_KEY>
```

The client loads the key from the `OPENROUTER_API_KEY` environment variable (which can be set in a local `.env` file).

## Leaf Files

- [`completions.md`](completions.md) — chat completions endpoint (`POST /chat/completions`), request/response schema, and tool calling integration.
