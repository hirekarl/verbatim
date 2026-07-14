# Messages

Reference documentation for the Anthropic Messages API.

## `POST /v1/messages`

Creates a model response for the given conversation.

Reference: <https://platform.claude.com/docs/en/api/messages>

### Request

```json
{
  "model": "claude-sonnet-5",
  "max_tokens": 4096,
  "system": "...",
  "messages": [
    {
      "role": "user",
      "content": "..."
    }
  ],
  "tools": [
    {
      "name": "create_suggestion",
      "description": "...",
      "input_schema": {
        "type": "object",
        "properties": {
          "matched_text": { "type": "string" },
          "replacement_text": { "type": "string" }
        },
        "required": ["matched_text", "replacement_text"]
      }
    }
  ]
}
```

### Response

```json
{
  "id": "msg_...",
  "role": "assistant",
  "stop_reason": "tool_use",
  "content": [
    {
      "type": "tool_use",
      "id": "toolu_...",
      "name": "create_suggestion",
      "input": {
        "matched_text": "old text",
        "replacement_text": "new text"
      }
    }
  ]
}
```

### Tool results

Tool results are sent back as a `user`-role message with `tool_result` content blocks -- **all** tool_result blocks from one assistant turn must be batched into a single user message, not sent as separate messages:

```json
{
  "role": "user",
  "content": [
    {
      "type": "tool_result",
      "tool_use_id": "toolu_...",
      "content": "Suggestion created."
    }
  ]
}
```

### Gotchas

- **Parsed Tool Arguments:** Unlike OpenRouter/OpenAI, Anthropic's `tool_use` content blocks already expose `input` as a parsed JSON object, not a stringified value -- no `json.loads` needed.
- **System prompt is a top-level parameter, not a message:** `system` is passed as its own request field, not as a `{"role": "system", ...}` entry in `messages`.
- **Tool schema shape:** flat `{"name", "description", "input_schema"}` -- no `{"type": "function", "function": {...}}` wrapper like OpenAI-compatible APIs use.
- **Batched tool results:** all `tool_result` blocks produced from a single assistant turn's tool calls must be returned in one `user` message, not one message per tool call -- returning them separately silently trains the model to stop making parallel tool calls.
- **Exception hierarchy:** `anthropic.APIConnectionError` is a sibling of `anthropic.APIStatusError`, not a subclass -- catch it separately (it has no HTTP status to log). `anthropic.RateLimitError` is a subclass of `APIStatusError` but the SDK already retries 429s automatically (`max_retries=2` default) before it ever surfaces to calling code.
- **API Key Loading:** The SDK expects `ANTHROPIC_API_KEY` to be set in the environment or passed to the initializer. In this project, `python-dotenv` loads this from a local `.env` file first.
