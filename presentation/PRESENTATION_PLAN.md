# Saturday presentation plan — Verbatim

5-minute live demo, built to the assignment rubric in this folder's screenshots: **Role + Pain Point**, **Loop + Checkpoint**, **Live Demo**, plus the "Agent Checklist" / "Presentation Checklist" self-check. Speaking time is split roughly evenly between Karl and Christina, each covering the part of the system they actually built (per `TODO.md`'s ownership split), and demo assets live in `presentation/demo/`.

## A. Slide outline (≈4:50 budget)

| #   | Slide                     | Speaker              | Time            |
| --- | ------------------------- | -------------------- | --------------- |
| 1   | Title / Role + Pain Point | Both                 | 0:25            |
| 2   | Loop — Observe            | Karl, then Christina | 0:50            |
| 3   | Loop — Decide             | Christina, then Karl | 0:50            |
| 4   | Loop — Act                | Karl                 | 0:30            |
| 5   | Checkpoint                | Karl, then Christina | 0:50            |
| 6   | Live demo                 | Both (alternating)   | 1:05 + live run |
| 7   | Close                     | Karl, then Christina | 0:20            |

**1. Title / Role + Pain Point** — Verbatim audits marketing copy in Google Docs against brand guidelines and a campaign brief, for copywriters, across 7 categories: tone drift, information hierarchy, CTA cadence, readability, formatting/style, channel constraints, banned words.

**2. Loop — Observe** — Karl: auth + fetch the draft and brief via the Docs/Drive API. Christina: her deterministic evaluator runs in parallel over the mechanically-checkable categories (banned words, formatting mechanics, channel limits) via regex, no model call.

**3. Loop — Decide** — Christina: her evaluator's findings get handed to the model as citable evidence rather than something it has to re-derive. Karl: the LLM tool-calling loop judges the four categories that need actual judgment — tone drift, hierarchy, CTA cadence, readability.

**4. Loop — Act** — Karl: the model calls `create_suggestion` (Docs API `batchUpdate`) for rewrites or `create_inline_comment` (Drive API) for structural issues, loops until done or capped, prints a run summary.

**5. Checkpoint** — Karl: mechanism — suggestions only land as reviewable because the account has Suggester, not Editor, access (tested against a live doc; Editor access makes the same call apply silently). Christina: why it matters and what happens next — copy headed for sign-off can't be silently rewritten, so the copywriter accepts/rejects every item inline, and only accepted changes move forward.

**6. Live demo** — input, expected output, and backup are all pre-built in `presentation/demo/`:

- Input: `campaign-brief.txt` and `draft-copy.txt` (paste each into its own Google Doc), run `uv run verbatim <draft_doc_id> <brief_doc_id> --channel email`.
- Expected: full breakdown in `presentation/demo/expected-output.md` — roughly 20 evaluator hits (banned words, formatting, the all-caps subject line) plus four LLM-judged flags (audience called "it", buried lede, three competing CTAs, negative/passive phrasing).
- Backup: a recorded run from Friday's rehearsal, in case the live Docs API call is flaky.

**7. Close** — Karl: the Add-on + Cloud Run backend are already deployed, ahead of the original plan. Christina: one formatting rule (general body-copy title case) is a known, tracked gap, not a miss — everything else in the loop is done and tested.

Total ≈ 4:50, leaving slack.

## B. Speaker script

Each line is its own list item on purpose — a plain line break collapses into one run-on paragraph in rendered Markdown, and this needs to stay readable line-by-line while presenting.

**[Slide 1 — 0:00–0:25, both]**

- KARL: "I'm Karl."
- CHRISTINA: "I'm Christina. Together we built Verbatim. It checks marketing copy in Google Docs against brand guidelines and a campaign brief, before a draft goes out for sign-off."
- KARL: "Right now that check happens by hand, and it means holding seven different rules in your head at once — tone, hierarchy, how often the CTA shows up, readability, banned words, formatting, channel limits. It's easy to miss one, and two reviewers won't always catch the same things."

**[Slide 2 — 0:25–1:15, Karl then Christina]**

- KARL: "My half is getting the actual content. A copywriter runs one command with a doc ID and a brief ID, and Verbatim authenticates to the Docs and Drive APIs and pulls both straight out of Google Docs — no copy-pasting into some other tool."
- CHRISTINA: "While that's happening, my evaluator runs over the text. It's a regex rules engine I built and tested against real sample copy — banned words, formatting details like the Oxford comma and semicolons, gender-neutral language, channel limits like a Twitter character count or an email subject line. None of that touches the model."

**[Slide 3 — 1:15–2:05, Christina then Karl]**

- CHRISTINA: "Whatever my evaluator flags gets handed to the model as evidence it can point to, instead of the model guessing at the same rules a second time."
- KARL: "Then the model takes the four categories that actually need judgment instead of pattern matching — tone drift, information hierarchy, CTA cadence, readability. It gets Christina's findings, the brand guidelines, the document, and the brief in one prompt, and decides what to flag."

**[Slide 4 — 2:05–2:35, Karl]**

- KARL: "From there it has two tools: propose a suggested edit through the Docs API, or leave an inline comment through the Drive API for anything more structural than a simple rewrite. It keeps going until it's out of things to flag or hits a round limit, then prints a summary of what it posted."

**[Slide 5 — 2:35–3:25, Karl then Christina]**

- KARL: "This part is worth slowing down on. Suggestions only show up as a reviewable 'Suggested edit' because the account has Suggester access, not Editor — I checked this against a live doc, and the identical API call will silently rewrite the document under Editor access instead. So the permission level is doing real work here, not just the code."
- CHRISTINA: "That matters because this copy is headed for strategic sign-off — nobody wants their draft rewritten out from under them. The copywriter opens the doc, goes through every suggestion and comment one at a time, and accepts or rejects each. Only what they accept moves forward."

**[Slide 6 — 3:25–4:30, alternating, then live]**

- KARL: "Let's run it." — run `uv run verbatim <draft_doc_id> <brief_doc_id> --channel email`
- CHRISTINA: "Watch the evaluator catches land first — those come back fast. Banned words, a missing Oxford comma, that all-caps subject line."
- KARL: "Then the model's suggestions land after — the audience gets called 'it' instead of 'they,' the actual price-change deadline is buried two paragraphs in, and there are three different CTAs competing with each other." (call out specifics as they appear)
- CHRISTINA: "If the live call has any trouble, we've got a recording of a clean run from rehearsal as backup."

**[Slide 7 — 4:30–4:50, Karl then Christina]**

- KARL: "On my end, the Add-on and its Cloud Run backend are already live — that was originally a post-demo item, and we got to it early."
- CHRISTINA: "On mine, there's one formatting rule still open — general title case for body copy — it's tracked, and it's deliberately not today's problem. Everything else in the loop is done and tested."
- CHRISTINA: "That's Verbatim."

## C. Readiness self-check

### The agent

- [x] System prompt specifies tool call sequence, output format, termination condition — `prompt.py`.
- [x] At least one tool calls a real API and returns real data — `docs_client.py` hits the live Docs/Drive APIs, not mocks.
- [x] Full observe-decide-act loop runs end-to-end — exercised in integration testing per `TODO.md` Day 3.
- [x] Human-in-the-loop checkpoint pauses before highest-risk action — every write is suggestion/comment-only; nothing reaches the draft without an explicit accept in Google Docs.
- [x] Output is something the target role would actually act on — inline suggestions/comments a copywriter reviews directly in their own doc.
- [x] Code committed to GitHub.

### The presentation

- [x] Role and pain point explained in plain language.
- [x] Each step of observe-decide-act walkable for audience.
- [x] Checkpoint explained: where, why, what happens on yes/no.
- [x] Live demo planned: specific input, expected output, backup if it fails — seeded copy in `presentation/demo/draft-copy.txt` + `campaign-brief.txt`, expected hits enumerated in `presentation/demo/expected-output.md`.
- [ ] **Demo tested at least 3 times before Saturday** — content is ready; still need to (1) actually paste `campaign-brief.txt` / `draft-copy.txt` into two real Google Docs, share the draft with Suggester access, (2) run the CLI against them and confirm the expected-output sheet holds up against real model output, (3) record the rehearsal-day fallback video. All scheduled for Friday's buffer day per `TODO.md`.

The only remaining gap is turning the two seeded text files into real Google Docs and rehearsing against them — the content, mechanism, and script are all done.
