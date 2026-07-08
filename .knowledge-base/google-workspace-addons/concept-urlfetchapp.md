# `UrlFetchApp`: calling the Python backend

Reference: <https://developers.google.com/apps-script/reference/url-fetch/url-fetch-app>

`UrlFetchApp` is Apps Script's HTTP client — the only way the Add-on shell reaches outside Google's own services. This is what carries the click handler's request to the hosted backend (issue #20's HTTP entrypoint) and brings the JSON response back into the card.

## Minimal shape

```javascript
function callVerbatimBackend(documentId, briefId, channel) {
  const token = ScriptApp.getOAuthToken();
  const payload = {
    document_id: documentId,
    brief_id: briefId,
    channel: channel,
  };

  const response = UrlFetchApp.fetch("https://verbatim-backend.example.run.app/audit", {
    method: "post",
    contentType: "application/json",
    headers: {
      Authorization: "Bearer " + token,
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });

  const statusCode = response.getResponseCode();
  const body = JSON.parse(response.getContentText());

  if (statusCode >= 400) {
    throw new Error("Verbatim backend error: " + (body.error || statusCode));
  }

  return body;
}
```

## Fields that matter for this call

- **`method`** — `"post"`, matching issue #20's HTTP entrypoint accepting a JSON request body (document ID, brief ID, channel, bearer token) rather than a GET with query params.
- **`headers.Authorization`** — carries the `ScriptApp.getOAuthToken()` result as a standard bearer token, which issue #21's inbound-token validation checks before the backend trusts it.
- **`payload` + `contentType: "application/json"`** — `UrlFetchApp` doesn't auto-serialize JS objects; `payload` must be a `JSON.stringify`'d string with `contentType` set explicitly, or the backend receives a form-encoded body instead of JSON.
- **`muteHttpExceptions: true`** — without this, `UrlFetchApp.fetch()` throws on any non-2xx response *before* the script gets a chance to read the response body, which would swallow whatever error detail the backend put in a JSON error response. Setting this makes 4xx/5xx responses come back as a normal `HTTPResponse` to inspect via `getResponseCode()`.

## Gotchas

- **Requires `script.external_request` in `appsscript.json`.** Without that scope declared (see `concept-appsscript-manifest.md`), any `UrlFetchApp` call to a non-Google host throws at runtime, not at deploy time — this is easy to miss until the click handler is actually exercised.
- **No streaming / long-poll support.** `UrlFetchApp.fetch()` blocks until the response completes or the request times out; it can't consume a streaming response incrementally. If the backend's tool-calling loop (`max_tool_call_rounds=20`) runs long, the Add-on has no way to show incremental progress — it's a single blocking call from the script's perspective, tying back into the execution-time-limit gotcha in `concept-cardservice-ui.md`.
- **Default request timeout is roughly 30–60 seconds** unless increased at the Apps Script project level, and Apps Script doesn't otherwise expose a per-call timeout override the way many HTTP client libraries do. Confirm this against real end-to-end LLM audit latency before assuming the synchronous request/response shape in the minimal example above will hold up — a genuinely long-running audit may need the backend to return immediately with a job ID and have the Add-on poll a second endpoint instead.
- **`muteHttpExceptions` still doesn't suppress network-level failures** (DNS resolution, connection refused, Cloud Run cold-start timeout) — those still throw. Wrap the call in `try`/`catch` in the click handler so a backend outage renders an error card instead of an unhandled exception breaking the sidebar.
