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

  const introParagraph = CardService.newTextParagraph().setText(
    'Verbatim checks this document for tone drift, information hierarchy, ' +
      'CTA cadence, readability, formatting/style, channel constraints, ' +
      'and banned words. Running it posts inline comments for structural ' +
      'issues and suggested edits directly in this doc — nothing changes ' +
      'outright.'
  );

  const briefIdInput = CardService.newTextInput()
    .setFieldName('briefId')
    .setTitle('Campaign Brief (Doc ID or share link)')
    .setHint('Paste a Doc ID or a full Google Docs/Drive share link — either works.')
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
    .addWidget(introParagraph)
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
    const jobId = submitVerbatimAudit(documentId, briefId, channel);
    return CardService.newActionResponseBuilder()
      .setNavigation(
        CardService.newNavigation().pushCard(buildInProgressCard(jobId))
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

function checkAuditStatus(e) {
  const jobId = e.formInput.jobId;

  try {
    const status = pollVerbatimAudit(jobId);
    var nextCard;
    if (status.status === 'done') {
      nextCard = buildResultCard(status.result);
    } else if (status.status === 'error') {
      nextCard = buildErrorCard({ message: status.error || 'unknown error' });
    } else if (status.status === 'not_found') {
      nextCard = buildErrorCard({
        message:
          'Job not found — the backend may have restarted. Please run the audit again.',
      });
    } else {
      // 'queued' or 'running' -- still going, offer the same check-status
      // card again. CardService has no client-side timer, so re-checking is
      // always a deliberate click, never automatic.
      nextCard = buildInProgressCard(jobId);
    }
    return CardService.newActionResponseBuilder()
      .setNavigation(CardService.newNavigation().pushCard(nextCard))
      .build();
  } catch (err) {
    return CardService.newActionResponseBuilder()
      .setNavigation(
        CardService.newNavigation().pushCard(buildErrorCard(err))
      )
      .build();
  }
}

function buildInProgressCard(jobId) {
  const introParagraph = CardService.newTextParagraph().setText(
    'Audit running — this can take a few minutes (the model works through ' +
      'up to 20 rounds of checks). Click "Check Status" to see whether ' +
      'it’s finished.'
  );

  // Hidden-form-field pattern: click handlers are fresh invocations with no
  // closures, so jobId has to round-trip through the next click's
  // e.formInput the same way briefId/channel already do in buildAuditCard.
  const jobIdInput = CardService.newTextInput()
    .setFieldName('jobId')
    .setTitle('Job ID')
    .setValue(jobId);

  const button = CardService.newTextButton()
    .setText('Check Status')
    .setOnClickAction(
      CardService.newAction().setFunctionName('checkAuditStatus')
    );

  const section = CardService.newCardSection()
    .addWidget(introParagraph)
    .addWidget(jobIdInput)
    .addWidget(button);

  return CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle('Verbatim — Running'))
    .addSection(section)
    .build();
}

// Fixed order matching src/verbatim/prompt.py's CATEGORIES -- rendered in
// this order regardless of the response's key order, so the breakdown
// always reads in the same sequence the pre-audit card describes.
var CATEGORY_ORDER = [
  'tone_drift',
  'information_hierarchy',
  'cta_cadence',
  'readability',
  'formatting_and_style',
  'channel_constraints',
  'banned_words_and_competitors',
];

var CATEGORY_LABELS = {
  tone_drift: 'Tone Drift',
  information_hierarchy: 'Information Hierarchy',
  cta_cadence: 'CTA Cadence',
  readability: 'Readability',
  formatting_and_style: 'Formatting & Style',
  channel_constraints: 'Channel Constraints',
  banned_words_and_competitors: 'Banned Words & Competitors',
  uncategorized: 'Uncategorized',
};

// One color per category, reused for both the count in "Breakdown by
// category" and the quoted matched text in "Findings" below, so the two
// sections read as one coordinated system rather than two plain lists.
// CardService widgets only support this small HTML subset (<b>, <i>, <u>,
// <s>, <font color>, <a>, <br>) and only in .setText() -- setTopLabel()/
// setBottomLabel() are plain-text only, per
// .knowledge-base/google-workspace-addons/concept-cardservice-ui.md.
var CATEGORY_COLORS = {
  tone_drift: '#8E24AA',
  information_hierarchy: '#1E88E5',
  cta_cadence: '#00897B',
  readability: '#F4511E',
  formatting_and_style: '#6D4C41',
  channel_constraints: '#3949AB',
  banned_words_and_competitors: '#C62828',
  uncategorized: '#616161',
};

var DISCLAIMER_TEXT =
  'Disclaimer: All findings above were generated by an AI system and may ' +
  'contain errors or omissions. Human review and approval is required ' +
  'prior to publication.';

// Widget text has practical length limits in the sidebar's fixed-width
// card -- truncate long matched spans/details to keep each finding
// scannable rather than wrapping into a wall of text.
function _truncate(text, maxLength) {
  if (!text) {
    return text;
  }
  return text.length > maxLength
    ? text.slice(0, maxLength - 1) + '…'
    : text;
}

// .setText() is the only widget field that renders CardService's small HTML
// subset -- a literal "&"/"<"/">" from real document text (e.g. "Save 20%
// & More" or "Revenue < Cost") would otherwise be parsed as markup and
// break or hide the rest of the string.
function _escapeHtml(text) {
  if (!text) {
    return text;
  }
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function _findingIcon(kind) {
  return CardService.newIconImage().setIcon(
    kind === 'suggestion' ? CardService.Icon.STAR : CardService.Icon.DESCRIPTION
  );
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

  const counts = result.category_counts || {};
  const nonzero = CATEGORY_ORDER.filter(function (key) {
    return counts[key] > 0;
  });

  if (nonzero.length > 0) {
    section.addWidget(
      CardService.newTextParagraph().setText('Breakdown by category:')
    );
    nonzero.forEach(function (key) {
      const color = CATEGORY_COLORS[key] || CATEGORY_COLORS.uncategorized;
      section.addWidget(
        CardService.newDecoratedText()
          .setTopLabel(CATEGORY_LABELS[key])
          .setText(
            '<font color="' + color + '"><b>' + counts[key] + '</b></font>'
          )
      );
    });
  }

  const findings = result.findings || [];
  if (findings.length > 0) {
    section.addWidget(CardService.newTextParagraph().setText('Findings:'));
    // Listed in the order categories first appear in `findings`, which is
    // dispatch order from the agent loop -- not re-sorted by CATEGORY_ORDER,
    // so this reads as "what the agent found, in the order it found it."
    findings.forEach(function (finding) {
      const color =
        CATEGORY_COLORS[finding.category] || CATEGORY_COLORS.uncategorized;
      const quotedText =
        '<font color="' +
        color +
        '"><b>“' +
        _escapeHtml(_truncate(finding.matched_text, 80)) +
        '”</b></font>';
      section.addWidget(
        CardService.newDecoratedText()
          .setStartIcon(_findingIcon(finding.kind))
          .setTopLabel(CATEGORY_LABELS[finding.category] || finding.category)
          .setText(quotedText)
          .setBottomLabel(_truncate(finding.detail, 100))
          .setWrapText(true)
      );
    });
  }

  section.addWidget(CardService.newTextParagraph().setText(DISCLAIMER_TEXT));

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
