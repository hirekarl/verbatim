# `CardService`: the sidebar UI

Reference: <https://developers.google.com/apps-script/reference/card-service>, <https://developers.google.com/apps-script/add-ons/concepts/cards>

Editor Add-on UI is built declaratively: a script function returns a `Card` (or array of `Card`s), and the host (Docs) renders it in the sidebar. There's no persistent DOM to manipulate directly — every UI update is "build a new `Card` and return it," including in response to button clicks.

## Minimal shape

```javascript
function onHomepage(e) {
  return buildAuditCard();
}

function buildAuditCard() {
  const button = CardService.newTextButton()
    .setText("Run Verbatim Audit")
    .setOnClickAction(
      CardService.newAction().setFunctionName("runAudit")
    );

  const section = CardService.newCardSection()
    .addWidget(button);

  return CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle("Verbatim"))
    .addSection(section)
    .build();
}

function runAudit(e) {
  // UrlFetchApp call to the backend happens here — see concept-urlfetchapp.md
  const resultText = "Audit complete: 3 suggestions, 1 comment.";

  const resultSection = CardService.newCardSection()
    .addWidget(CardService.newTextParagraph().setText(resultText));

  const resultCard = CardService.newCardBuilder()
    .setHeader(CardService.newCardHeader().setTitle("Verbatim — Results"))
    .addSection(resultSection)
    .build();

  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().pushCard(resultCard))
    .build();
}
```

## Core pieces relevant to Verbatim's shell

- **`CardBuilder` / `CardHeader` / `CardSection`** — a `Card` is one or more sections; each section holds widgets, added top to bottom.
- **`TextButton`** — the "Run Verbatim Audit" trigger. `setOnClickAction` binds it to a named script function via `CardService.newAction()`.
- **`TextInput`** — used in `addon/Code.gs` for the brief-ID field: `CardService.newTextInput().setFieldName("briefId")...`. Field values come back in the click handler's event object as `e.formInput.briefId`. Issue #24's original resolution deferred this to a hardcoded/config value for v1, but Karl reconsidered before the Add-on was actually tested — see `addon/README.md`'s "Brief ID input" section.
- **`ActionResponseBuilder` + `Navigation.pushCard()`** — how a click handler updates the UI: not by mutating the existing card, but by pushing a new one onto the sidebar's navigation stack. `popCard()`/`popToRoot()` exist for going back.
- **`TextParagraph`** — simplest way to render the backend's JSON response (formatted as a summary string) back into the card, per the shell's job #3 in `MAP.md`.

## Gotchas

- **No arbitrary HTML/CSS, but `.setText()` supports a small whitelist.** `CardService` widgets are a fixed catalog (buttons, text inputs, images, decorated text, switches, selection inputs, etc.) — there's no custom markup or styling. The one exception: a widget's main `.setText()` value (not `DecoratedText.setTopLabel()`/`setBottomLabel()`, which are plain-text only) renders a small tag whitelist — `<b>`, `<i>`, `<u>`, `<s>`, `<font color="#rrggbb">`, `<a href>`, `<br>` — enough for bolding/color-coding, not enough to build a custom layout. Escape any live document/user text embedded this way (`&`/`<`/`>`) before wrapping it in tags, or a literal `<`/`>` in the source text gets parsed as markup. `DecoratedText` also takes a `.setStartIcon()`/`.setEndIcon()` built from `CardService.newIconImage().setIcon(CardService.Icon.X)` (a fixed enum of built-in icons) or `.setIconUrl()` for a custom image — useful for a cheap visual category/type marker without needing custom HTML.
- **Click handlers run as a fresh function invocation**, not a live callback closure — any state needed across the click (e.g. the document ID) must be read fresh from `DocumentApp.getActiveDocument().getId()` or passed via hidden form fields, not captured from the homepage-trigger function's scope.
- **`e.docs.id` / `e.docs.title`** are available on the event object inside Docs-hosted trigger functions (populated because the manifest's `addOns.docs` grants document-context access) — this is likely how the Add-on gets the audited document's ID without the user typing it in, distinct from the brief-ID question above.
- **Execution time limit**: Apps Script functions triggered from the UI have a 6-minute cap (30 seconds for simple triggers, but click-handler functions get the longer limit). The backend's own tool-calling loop (`max_tool_call_rounds=20`, per `docs/workspace-addon-migration.md` §6) must complete comfortably inside that window, or the click handler needs to poll rather than block on one long `UrlFetchApp.fetch()` call — worth confirming against real LLM round-trip timing once #20 exists.
