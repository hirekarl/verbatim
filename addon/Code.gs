/**
 * Verbatim Editor Add-on: sidebar UI (CardService) and the homepage trigger.
 *
 * Thin shell only -- no Docs/Drive API calls happen here. All actual audit
 * logic (evaluator, LLM agent loop, Docs/Drive writes) lives in the Python
 * backend (src/verbatim/http_api.py); this script's only job is to trigger
 * a run and render its result. See docs/workspace-addon-migration.md and
 * .knowledge-base/google-workspace-addons/.
 */

function onHomepage(e) {
  return buildAuditCard(e);
}

function buildAuditCard(e) {
  const defaultBriefId =
    PropertiesService.getScriptProperties().getProperty('DEFAULT_BRIEF_ID') ||
    '';

  const briefIdInput = CardService.newTextInput()
    .setFieldName('briefId')
    .setTitle('Campaign Brief (Doc ID or share link)')
    .setValue(defaultBriefId);

  // Only channels the evaluator actually has rules for (see
  // src/verbatim/evaluator.py's _check_channel_constraints) -- other values
  // are accepted by the backend but silently trigger no channel-specific
  // checks, so there's no reason to offer them here.
  const channelInput = CardService.newSelectionInput()
    .setType(CardService.SelectionInputType.DROPDOWN)
    .setFieldName('channel')
    .setTitle('Target Channel (optional)')
    .addItem('None', '', true)
    .addItem('Email', 'email', false)
    .addItem('Twitter', 'twitter', false)
    .addItem('Facebook', 'facebook', false)
    .addItem('Instagram', 'instagram', false);

  const button = CardService.newTextButton()
    .setText('Run Verbatim Audit')
    .setOnClickAction(
      CardService.newAction().setFunctionName('runAudit')
    );

  const section = CardService.newCardSection()
    .addWidget(briefIdInput)
    .addWidget(channelInput)
    .addWidget(button);

  return CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle('Verbatim'))
    .addSection(section)
    .build();
}

function runAudit(e) {
  // e.docs.id (the event object's doc-context field) was not reliably
  // populated in testing, even at click time -- DocumentApp.getActiveDocument()
  // reads the current doc directly from the active editor session instead
  // of depending on that event object field.
  const documentId = DocumentApp.getActiveDocument().getId();
  const briefId = extractDocId(e.formInput.briefId);
  const channel = e.formInput.channel;

  try {
    const result = callVerbatimBackend(documentId, briefId, channel);
    return CardService.newActionResponseBuilder()
      .setNavigation(
        CardService.newNavigation().pushCard(buildResultCard(result))
      )
      .build();
  } catch (err) {
    return CardService.newActionResponseBuilder()
      .setNavigation(
        CardService.newNavigation().pushCard(buildErrorCard(err))
      )
      .build();
  }
}

function buildResultCard(result) {
  const summary =
    'Suggestions posted: ' +
    result.suggestions_made +
    '\nComments posted: ' +
    result.comments_made +
    '\n' +
    (result.stopped_due_to_max_rounds
      ? 'Stopped early (max rounds reached).'
      : 'Completed.');

  const section = CardService.newCardSection().addWidget(
    CardService.newTextParagraph().setText(summary)
  );

  return CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle('Verbatim — Results'))
    .addSection(section)
    .build();
}

function extractDocId(input) {
  if (!input) {
    return input;
  }
  var trimmed = input.trim();
  // Google Docs/Sheets/Slides/Drive share URLs all carry the ID as the
  // path segment right after "/d/" (e.g. .../document/d/<ID>/edit).
  var match = trimmed.match(/\/d\/([a-zA-Z0-9_-]+)/);
  return match ? match[1] : trimmed;
}

function buildErrorCard(err) {
  const section = CardService.newCardSection().addWidget(
    CardService.newTextParagraph().setText('Audit failed: ' + err.message)
  );

  return CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle('Verbatim — Error'))
    .addSection(section)
    .build();
}
