/**
 * Calls the Python backend's HTTP entrypoint (src/verbatim/http_api.py).
 *
 * Only the backend URL and shared secret are Script Properties -- per
 * Karl's reconsideration of #24's original "hardcoded/config value"
 * resolution, neither the brief ID nor the target channel is baked into
 * the deployment; both come from the sidebar (Code.gs) each run.
 *
 * `UrlFetchApp.fetch()` has a hard, non-configurable 60-second timeout (see
 * .knowledge-base/google-workspace-addons/concept-urlfetchapp.md), and a
 * real audit run routinely exceeds that. So this is a submit-then-poll
 * pair, not one blocking call: submitVerbatimAudit() kicks off a background
 * job on the backend and returns immediately with a job id;
 * pollVerbatimAudit() checks that job's status, itself a fast call well
 * under the timeout.
 */

function _verbatimBackendProps() {
  const props = PropertiesService.getScriptProperties();
  // Script property values are trimmed defensively -- a stray trailing
  // newline/space from copy-pasting into the Script Properties dialog would
  // otherwise silently break the shared-secret comparison or the URL.
  const backendUrl = (props.getProperty('BACKEND_URL') || '').trim();
  const backendSharedSecret = (
    props.getProperty('BACKEND_SHARED_SECRET') || ''
  ).trim();

  if (!backendUrl) {
    throw new Error('Script property BACKEND_URL is not set.');
  }
  if (!backendSharedSecret) {
    throw new Error('Script property BACKEND_SHARED_SECRET is not set.');
  }

  return { backendUrl: backendUrl, backendSharedSecret: backendSharedSecret };
}

function _verbatimBackendErrorMessage(body) {
  // FastAPI's 422 responses carry `detail` as a list of validation-error
  // objects, not a string -- string concatenation on that silently
  // stringifies to "[object Object]"; JSON.stringify it instead so the
  // real validation failure is visible in the error card.
  var detail = body && body.detail;
  return typeof detail === 'string'
    ? detail
    : detail
      ? JSON.stringify(detail)
      : 'unknown error';
}

function submitVerbatimAudit(documentId, briefId, channel) {
  if (!briefId) {
    throw new Error('Enter a Campaign Brief Doc ID before running the audit.');
  }

  const backendProps = _verbatimBackendProps();
  const token = ScriptApp.getOAuthToken();
  const payload = {
    document_id: documentId,
    brief_id: briefId,
  };
  if (channel) {
    payload.channel = channel;
  }

  const response = UrlFetchApp.fetch(backendProps.backendUrl + '/audit', {
    method: 'post',
    contentType: 'application/json',
    headers: {
      Authorization: 'Bearer ' + token,
      'X-Backend-Shared-Secret': backendProps.backendSharedSecret,
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
        _verbatimBackendErrorMessage(body)
    );
  }

  return body.job_id;
}

function pollVerbatimAudit(jobId) {
  const backendProps = _verbatimBackendProps();

  const response = UrlFetchApp.fetch(
    backendProps.backendUrl + '/audit/' + encodeURIComponent(jobId),
    {
      method: 'get',
      headers: {
        'X-Backend-Shared-Secret': backendProps.backendSharedSecret,
      },
      muteHttpExceptions: true,
    }
  );

  const statusCode = response.getResponseCode();

  if (statusCode === 404) {
    return { status: 'not_found' };
  }

  const body = JSON.parse(response.getContentText());

  if (statusCode >= 400) {
    throw new Error(
      'Verbatim backend error (' +
        statusCode +
        '): ' +
        _verbatimBackendErrorMessage(body)
    );
  }

  return body;
}
