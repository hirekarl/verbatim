# Comment-triggering demo assets

The original `campaign-brief.txt` / `draft-copy.txt` pair is seeded to exercise all 7 categories, but in practice its structural issues (CTA cadence, information hierarchy) have been subtle enough that the model sometimes resolves them as suggestions or skips them, so a rehearsal run can come back with zero `create_inline_comment` calls. Per `prompt.py`, comments only fire for three categories: paragraph order / information hierarchy and CTA cadence (plus any other structural call the model judges isn't a clean text-for-text rewrite). The three pairs below make those issues blatant and un-rewritable as a single substring swap, so a comment is the only sane tool call.

Each pair is standalone — paste the brief into one Google Doc, the draft into another, grant Suggester/Commenter access on the draft, and run:

```sh
uv run verbatim <draft_doc_id> <brief_doc_id> --channel <channel>
```

## 1. `campaign-brief-order.txt` / `draft-copy-order.txt` — channel: none needed (omit `--channel`, or pass any)

Six paragraphs, deliberately out of order: opens with the CTA before any context, follows with a testimonial and a pricing paragraph, and only gets to the actual hook ("If you're still exporting spreadsheets...") in paragraph four — with the solution and a second CTA after that. There's no single substring to replace here; fixing it means reordering whole paragraphs, which only `create_inline_comment` can express. Expect a structural comment on the opening CTA paragraph (fires before any value prop) and another on/near the buried hook paragraph (information hierarchy).

## 2. `campaign-brief-cta.txt` / `draft-copy-cta.txt` — channel: twitter

Four sentences, three of which are a "download" CTA — first sentence, third sentence, and fourth sentence — with the brief explicitly calling for exactly one. This is the CTA-cadence category by design: too many asks, and the first one lands before the sync-bug/folders value prop that follows it. Expect at least one comment flagging the repeated/premature CTAs; the sync bug and folders sentence in the middle may separately get a suggestion for readability/wording.

## 3. `campaign-brief-mixed.txt` / `draft-copy-mixed.txt` — channel: facebook

Combines both failure modes to raise the odds at least one comment lands even on an off run: opens with the CTA, follows with an unrelated milestone-celebration paragraph, buries the actual "why invite a friend" hook in paragraph three, then closes with two more soft CTAs ("invite someone today," "reply and tell us who you're inviting"). Also long enough to trip the evaluator's Facebook 1-2-sentence channel-constraint check, so the deterministic findings panel won't be empty either. Expect comments on the opening CTA (information hierarchy) and on the CTA repetition (CTA cadence).

## Rehearsal note

Run each pair at least once before Saturday and confirm a comment actually lands — the model's exact wording and which paragraph it anchors to will vary, but the tool-call choice (comment vs. suggestion) shouldn't, given how unrewritable-as-a-swap these are by construction. If a run still comes back with zero comments, that's worth flagging as a real behavior gap in the system prompt (`prompt.py`), not just an unlucky sample.
