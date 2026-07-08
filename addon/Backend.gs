/**
 * Calls the Python backend's HTTP entrypoint (src/verbatim/http_api.py).
 *
 * Backend URL, brief ID, and target channel are read from Script
 * Properties rather than hardcoded, so a deployment can be pointed at a
 * given campaign brief/channel without editing source. Per #24's
 * resolution, v1 uses a config value here rather than a sidebar picker.
 */

function callVerbatimBackend(documentId) {
  const props = PropertiesService.getScriptProperties();
  const backendUrl = props.getProperty('BACKEND_URL');
  const briefId = props.getProperty('BRIEF_ID');
  const channel = props.getProperty('CHANNEL'); // optional
  const backendSharedSecret = props.getProperty('BACKEND_SHARED_SECRET');

  if (!backendUrl) {
    throw new Error('Script property BACKEND_URL is not set.');
  }
  if (!briefId) {
    throw new Error('Script property BRIEF_ID is not set.');
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
