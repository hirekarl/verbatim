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
  const documentId = extractDocId(e && e.docs && e.docs.id);
  const defaultBriefId =
    PropertiesService.getScriptProperties().getProperty('DEFAULT_BRIEF_ID') ||
    '';

  const briefIdInput = CardService.newTextInput()
    .setFieldName('briefId')
    .setTitle('Campaign Brief (Doc ID or share link)')
    .setValue(defaultBriefId);

  const button = CardService.newTextButton()
    .setText('Run Verbatim Audit')
    .setOnClickAction(
      CardService.newAction()
        .setFunctionName('runAudit')
        .setParameters({ documentId: documentId })
    );

  const section = CardService.newCardSection()
    .addWidget(briefIdInput)
    .addWidget(button);

  return CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle('Verbatim'))
    .addSection(section)
    .build();
}

function runAudit(e) {
  const documentId = e.parameters.documentId;
  const briefId = extractDocId(e.formInput.briefId);

  try {
    const result = callVerbatimBackend(documentId, briefId);
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
