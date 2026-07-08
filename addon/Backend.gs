/**
 * Calls the Python backend's HTTP entrypoint (src/verbatim/http_api.py).
 *
 * Backend URL and target channel are read from Script Properties, so a
 * deployment can be pointed at a given backend/channel without editing
 * source. Brief ID is NOT a Script Property -- per Karl's reconsideration
 * of #24's original "hardcoded/config value" resolution, it comes from the
 * sidebar's text input (Code.gs) each run, so nothing about which campaign
 * brief to audit against is baked into the deployment.
 */

function callVerbatimBackend(documentId, briefId) {
  const props = PropertiesService.getScriptProperties();
  const backendUrl = props.getProperty('BACKEND_URL');
  const channel = props.getProperty('CHANNEL'); // optional
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
