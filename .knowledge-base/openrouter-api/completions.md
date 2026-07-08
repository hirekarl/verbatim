# Chat Completions

Reference documentation for the OpenRouter chat completions endpoint.

## `POST /chat/completions`

Creates a model response for the given chat conversation.

Reference: <https://openrouter.ai/docs/api-reference/parameters>

### Request

The request body follows the standard OpenAI chat completions parameters.

```json
{
  "model": "google/gemini-2.5-flash",
  "messages": [
    {
      "role": "system",
      "content": "..."
    },
    {
      "role": "user",
      "content": "..."
    }
  ],
  "tools": [
    {
      "type": "function",
      "function": {
        "name": "create_suggestion",
        "description": "...",
        "parameters": {
          "type": "object",
          "properties": {
            "matched_text": { "type": "string" },
            "replacement_text": { "type": "string" }
          },
          "required": ["matched_text", "replacement_text"]
        }
      }
    }
  ],
  "max_tokens": 4096
}
```

### Response

The response format returns the model's text answer and/or any requested tool calls.

```json
{
  "id": "gen-...",
  "choices": [
    {
      "finish_reason": "tool_calls",
      "message": {
        "role": "assistant",
        "content": null,
        "tool_calls": [
          {
            "id": "call_...",
            "type": "function",
            "function": {
              "name": "create_suggestion",
              "arguments": "{\"matched_text\": \"old text\", \"replacement_text\": \"new text\"}"
            }
          }
        ]
      }
    }
  ]
}
```

### Gotchas

- **JSON Tool Arguments:** OpenRouter/OpenAI returns tool arguments as a stringified JSON value under `function.arguments` rather than a parsed object. The client must parse this string with `json.loads` before executing the tool.
- **Model Names:** Model IDs must be prefixed with the provider prefix on OpenRouter (e.g. `google/gemini-2.5-flash` instead of just `gemini-2.5-flash`).
- **OpenAI Client Base URL:** When using the `openai` Python SDK, the `base_url` must be explicitly overridden to `https://openrouter.ai/api/v1` to redirect requests to OpenRouter instead of OpenAI's default endpoints.
- **API Key Loading:** The SDK expects `OPENROUTER_API_KEY` to be set in the environment or passed to the initializer. In this project, `python-dotenv` loads this from a local `.env` file first.
