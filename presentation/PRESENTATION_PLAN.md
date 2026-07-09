# Saturday presentation plan — Verbatim

5-minute live demo, built to the assignment rubric in this folder's screenshots: **Role + Pain Point**, **Loop + Checkpoint**, **Live Demo**, plus the "Agent Checklist" / "Presentation Checklist" self-check. Speaking time is split roughly evenly between Karl and Christina, each covering the part of the system they actually built (per `TODO.md`'s ownership split). The live demo runs through the real Workspace Add-on sidebar in Google Docs — not the CLI — since that's the actual target experience. Demo assets live in `presentation/demo/`.

Audience assumption: not everyone in the room knows what a CTA is, let alone "CTA cadence" or "information hierarchy." The opening two slides spend real time on plain-language context — who this is for, and why a brand style guide and a campaign brief are two different things that both matter — before any jargon shows up. Every technical term gets defined in the same breath it's introduced, not assumed.

Output honesty: the model's findings are not deterministic — the same draft can surface a different mix of suggestions/comments on different runs. Nothing below states an exact expected result; anywhere the live demo's actual output would go, there's a bracketed placeholder and an instruction to read off whatever the run actually produces.

## A. Slide outline (≈5:00 budget)

| #   | Slide                                           | Speaker              | Time            |
| --- | ----------------------------------------------- | -------------------- | --------------- |
| 1   | Title / who this is for                         | Both                 | 0:35            |
| 2   | Why two documents                               | Christina, then Karl | 0:50            |
| 3   | Loop — Observe                                  | Karl, then Christina | 0:40            |
| 4   | Loop — Decide (with plain-language definitions) | Christina, then Karl | 0:55            |
| 5   | Loop — Act                                      | Karl                 | 0:20            |
| 6   | Checkpoint                                      | Karl, then Christina | 0:35            |
| 7   | Live demo (via the Add-on)                      | Both (alternating)   | 0:50 + live run |
| 8   | Close                                           | Karl, then Christina | 0:15            |

**1. Title / who this is for** — Verbatim is built for copywriters — the people who write a company's marketing emails, social posts, and web copy. Grounds the pain point in a real number from the project's own research notes (`docs/research-notes.snapshot.md`): marketing leads spend 20-30% of their editing time policing mechanical voice/tone corrections instead of doing actual strategy work. That's the time Verbatim is trying to get back.

**2. Why two documents** — every piece of copy gets checked against two different things: a brand style guide (the company's permanent voice and rules) and a campaign brief (what's specific to this one piece — audience, ask, deadline). Names the demo's brand guide explicitly as a synthesis of Mailchimp's publicly published content style guide — realistic reference data, not a claim about Mailchimp's actual internal rules (see README's design notes). Both documents matter: on-brand-but-off-target copy is useless, on-target-but-off-brand copy confuses readers. Doing this check by hand, against both, is slow and inconsistent between reviewers — that's the gap Verbatim closes.

**3. Loop — Observe** — Karl: a copywriter clicks "Run Verbatim Audit" in the Add-on sidebar (brief + channel already filled in), and Verbatim fetches the draft and brief via the Docs/Drive API, no copy-pasting into another tool. Christina: her deterministic evaluator runs in parallel over what's black-and-white — banned words, formatting mechanics, channel limits (defined concretely, e.g. Twitter's character cap) — via regex, no model call.

**4. Loop — Decide** — Christina: her evaluator's findings get fed straight into the model's system prompt as citable evidence rather than something it has to re-derive. Karl: that same system prompt is what makes the model judge the four things that need actual judgment, each given a plain-language gloss in the same breath: tone drift (does it still sound like the brand), information hierarchy (is the important stuff said first, not buried), CTA cadence (CTA = "call to action," the part of the copy telling someone what to do next — is there a clear one, and does it show up at the right time, not too often), and readability.

**5. Loop — Act** — Karl: the model calls `create_suggestion` (Docs API `batchUpdate`) for rewrites or `create_inline_comment` (Drive API) for structural issues, loops until done or capped, prints a run summary.

**6. Checkpoint** — kept at the "what and why" level, not the API-permission mechanics. Karl: nothing Verbatim does gets applied outright — every output is something reviewable (a suggested edit or a comment), never a silent change to the doc. Christina: why it matters and what happens next — copy headed for sign-off can't be silently rewritten, so the copywriter accepts/rejects every item inline, and only accepted changes move forward.

**7. Live demo (via the Add-on)** — open the Verbatim sidebar on the draft doc, paste in the campaign brief (doc ID or share link), pick a channel from the dropdown, click "Run Verbatim Audit." It's one blocking call to the backend — evaluator and model both run server-side before anything comes back — then the sidebar shows a results card (suggestions/comments posted, broken down by category) and the actual suggestions/comments land inline in the doc.

- Input: draft doc pre-loaded with `presentation/demo/draft-copy.txt`, campaign brief `presentation/demo/campaign-brief.txt`, channel = Email.
- Expected: **[placeholder — read off whatever categories/counts the results card actually shows, and point at 2-3 real suggestions/comments in the doc]**. `presentation/demo/expected-output.md` is a backstage rehearsal reference for what the seeded draft is designed to exercise (verified against the real evaluator) — not a script to recite live, since the model's half is never guaranteed to repeat exactly.
- Backup: a recorded run from Friday's rehearsal, in case the live call is slow or times out — `addon/README.md` flags that Apps Script's blocking call may run close to its own timeout on a long tool-calling loop.

**8. Close** — Karl: what was just demoed is running for real (Cloud Run backend, live Add-on), not a mockup. Christina: closes it out.

Total ≈ 5:00 on the spoken script, before the live run itself.

## B. Speaker script

Each line is its own list item on purpose — a plain line break collapses into one run-on paragraph in rendered Markdown, and this needs to stay readable line-by-line while presenting. Parenthetical text is a stage direction, not something to say out loud.

**[Slide 1 — 0:00–0:35, both]**

- KARL: "I'm Karl."
- CHRISTINA: "I'm Christina. We built Verbatim for copywriters — the people who write a company's marketing emails, social posts, and web copy."
- KARL: "On a lot of marketing teams, the lead editor spends twenty to thirty percent of their editing time just policing mechanical stuff — voice, tone, formatting — instead of the actual writing and strategy. Right before a piece goes out, it needs that check. Verbatim automates it, so that time comes back."

**[Slide 2 — 0:35–1:25, Christina then Karl]**

- CHRISTINA: "Every piece of copy gets checked against two different things. First, a brand style guide — a company's permanent voice and rules. Always sounds like this, never says that. The one we're demoing with today is built from Mailchimp's publicly published content style guide, so it's realistic, not made up."
- KARL: "Second, the campaign brief — what's specific to just this one piece. Who it's going to, what we want the reader to do, and by when."
- CHRISTINA: "You need both. Copy that's perfectly on-brand but ignores what this campaign needs is useless. Copy that nails the ask but doesn't sound anything like the company is going to confuse people."
- KARL: "Checking both by hand means one person holding a style guide in one hand and a brief in the other, line by line. Two reviewers won't always catch the same things, and it's slow. That's the gap Verbatim closes."

**[Slide 3 — 1:25–2:05, Karl then Christina]**

- KARL: "My half is getting the actual content onto the page. When a copywriter clicks 'Run Verbatim Audit' in the sidebar, with the brief and channel already filled in, Verbatim pulls the draft and the brief straight out of Google Docs — no copying and pasting into another tool."
- CHRISTINA: "While that's happening, my evaluator runs over the text — a rules engine I built and tested against real sample copy. It checks what's black-and-white: banned words, formatting details like commas and quotation marks, and channel limits — things like Twitter's character cap, or an email subject line that's too long or too generic. None of that touches the model, it's just pattern matching."

**[Slide 4 — 2:05–3:00, Christina then Karl]**

- CHRISTINA: "Whatever my evaluator flags gets fed straight into the model's system prompt — the instructions that shape everything it does — as evidence it can point to, instead of guessing at the same rules a second time."
- KARL: "That same system prompt is what makes the model judge the four things that actually need judgment, not pattern matching. Does the writing still sound like the brand, or has the tone drifted. Is the important information said first, or is it buried three paragraphs down — that's what we call information hierarchy. Is there a clear ask, and does it show up at the right moment and not too often — that's CTA cadence. CTA means 'call to action' — the part of the copy that tells someone what to actually do next, like 'sign up' or 'buy now.' And is it actually easy to read. Christina's findings, the brand guidelines, the document, and the brief all go into that one system prompt, and the model decides what to flag."

**[Slide 5 — 3:00–3:20, Karl]**

- KARL: "From there the model has two moves: propose a suggested edit for a rewrite, or leave a comment for anything more structural than a simple text swap. It keeps going until it's out of things to flag or hits a round limit, then prints a summary of what it posted."

**[Slide 6 — 3:20–3:55, Karl then Christina]**

- KARL: "This part matters most: nothing Verbatim does gets applied outright. Everything shows up as something reviewable — a suggested edit or a comment — never a silent change to the doc."
- CHRISTINA: "That's because this copy is headed for a final sign-off — nobody wants their draft rewritten out from under them. The copywriter goes through every suggestion and comment one at a time and accepts or rejects each. Only what they accept moves forward."

**[Slide 7 — 3:55–4:45, alternating, then live]**

- KARL: "Let's see it in the doc." (open the Verbatim sidebar on the draft; the campaign brief link is already filled in)
- CHRISTINA: "We'll run it against Email." (pick Email from the channel dropdown, click "Run Verbatim Audit") "This is one call to our backend — the evaluator and the model both run behind the scenes, so there's a short wait."
- KARL: "Here's what came back." (read off the sidebar's category breakdown and counts — call out whatever actually shows up, not a fixed number)
- CHRISTINA: "And here in the doc—" (point at 2-3 of the actual suggestions or comments that landed, whatever they turn out to be)
- KARL: "If the live call is slow or times out, we've got a recording of a clean run from rehearsal as backup."

**[Slide 8 — 4:45–5:00, Karl then Christina]**

- KARL: "What you just saw is running for real — the same backend, the same Add-on, live in this doc. Not a mockup."
- CHRISTINA: "That's Verbatim."

## C. Readiness self-check

### The agent

- [x] System prompt specifies tool call sequence, output format, termination condition — `prompt.py`.
- [x] At least one tool calls a real API and returns real data — `docs_client.py` hits the live Docs/Drive APIs, not mocks.
- [x] Full observe-decide-act loop runs end-to-end — exercised in integration testing per `TODO.md` Day 3.
- [x] Human-in-the-loop checkpoint pauses before highest-risk action — every write is suggestion/comment-only; nothing reaches the draft without an explicit accept in Google Docs.
- [x] Output is something the target role would actually act on — inline suggestions/comments a copywriter reviews directly in their own doc.
- [x] Code committed to GitHub.
- [ ] **Add-on end-to-end path actually verified** — this is the biggest open risk now that the demo runs through the Add-on instead of the CLI. Per `addon/README.md`, the Apps Script project's Script Properties (`BACKEND_URL`, `BACKEND_SHARED_SECRET`, optionally `DEFAULT_BRIEF_ID`) still need confirming as set, and there has not yet been a real end-to-end run via **Deploy → Test deployments**. The CLI path is fully tested; the Add-on path is not, and it's now the one being demoed live.

### The presentation

- [x] Role and pain point explained in plain language, grounded in a real number (20-30% of editing time) rather than an assertion.
- [x] Each step of observe-decide-act walkable for audience, described as it will actually appear in the Add-on (sidebar click, not a terminal command).
- [x] Checkpoint explained: where, why, what happens on yes/no — kept at the plain "reviewable, never silent" level, without the underlying API-permission mechanics.
- [x] Live demo planned: specific input and backup, with expected output deliberately left as a live placeholder rather than a predicted result, since the model's output isn't deterministic.
- [ ] **Demo tested at least 3 times before Saturday** — content is ready; still need to (1) paste `campaign-brief.txt` / `draft-copy.txt` into two real Google Docs, share the draft appropriately, (2) confirm the Add-on's Script Properties and run a real end-to-end test via Deploy → Test deployments (see above — not yet done at all), (3) record the rehearsal-day fallback video. All scheduled for Friday's buffer day per `TODO.md`.

The content, script, and mechanism are done. The real remaining risk is that the Add-on path — Script Properties plus one real end-to-end run — hasn't been exercised yet at all, and it's now what Saturday's live demo depends on.
