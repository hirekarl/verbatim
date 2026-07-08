/**
 * Calls the Python backend's HTTP entrypoint (src/verbatim/http_api.py).
 *
 * Only the backend URL and shared secret are Script Properties -- per
 * Karl's reconsideration of #24's original "hardcoded/config value"
 * resolution, neither the brief ID nor the target channel is baked into
 * the deployment; both come from the sidebar (Code.gs) each run.
 */

function callVerbatimBackend(documentId, briefId, channel) {
  const props = PropertiesService.getScriptProperties();
  const backendUrl = props.getProperty('BACKEND_URL');
  const backendSharedSecret = props.getProperty('BACKEND_SHARED_SECRET');

  if (!backendUrl) {
    throw new Error('Script property BACKEND_URL is not set.');
  }
  if (!briefId) {
    throw new Error('Enter a Campaign Brief Doc ID before running the audit.');
  }
  if (!backendSharedSecret) {
    throw new Error('Script property BACKEND_SHARED_SECRET is not set.');
  }

  const token = ScriptApp.getOAuthToken();
  const payload = {
    document_id: documentId,
    brief_id: briefId,
  };
  if (channel) {
    payload.channel = channel;
  }

  const response = UrlFetchApp.fetch(backendUrl + '/audit', {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer ' + token,
      'X-Backend-Shared-Secret': backendSharedSecret,
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  });

  const statusCode = response.getResponseCode();
  const body = JSON.parse(response.getContentText());

  if (statusCode >= 400) {
    throw new Error(
      'Verbatim backend error (' +
        statusCode +
        '): ' +
        (body.detail || 'unknown error')
    );
  }

  return body;
}
