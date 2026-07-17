# Week 2 presentation plan — Verbatim

A tight ~4:30 spoken script plus a live run, built to the Sprint 2 rubric (screenshots in the repo root, "Agent Level-Up Presentation Structure, due 07/18"): Role & Pain Point (0:30), Week 5 Agent (0:30), Week 6 Complexity Addition (1:00), Eval Evidence (0:30), Live Demo (2:00). Same style tokens as last week's deck — both now come from `presentation/deck_common.py`, so the palette, type, and icon geometry are identical, not just similar.

Speaking time is split evenly between Karl and Christina — not by slide count, but by seconds: 75s apiece across the spoken script (0:30 Role & Pain Point split 15/15, Karl's 0:30 solo Week 5 recap, the 1:00 Week 6 section split 30/30, and Eval Evidence's 0:30 going to Christina to balance the ledger), then the 2:00 live demo alternating roughly 60/60. Every claim in the Week 6 section is a real, merged PR or a real production incident — see `TODO.md`'s Sprint 2 day-by-day log and each PR number cited below.

Eval Card evidence (Slide 5) is now filled in from real runs — all 6 eval card pairs (`presentation/demo/eval-card-links.md`) were run against the current multi-agent split; full output in `presentation/demo/eval-card-run-results.md` (both kept local/uncommitted). The live demo's expected output (Slide 6) stays a bracketed placeholder on purpose — same honesty convention as last week's plan, since that output is read live off whatever the run actually produces, not predicted in advance.

## A. Slide outline (≈4:30 budget + live run)

| #   | Slide                          | Speaker              | Time            |
| --- | ------------------------------ | -------------------- | --------------- |
| 1   | Role & Pain Point              | Christina, then Karl | 0:30            |
| 2   | Week 5 — The Original Agent    | Karl                 | 0:30            |
| 3   | Week 6 — Two Specialist Agents | Karl                 | 0:30            |
| 4   | Week 6 — Now Covering All 7    | Christina            | 0:30            |
| 5   | Eval Evidence                  | Christina            | 0:30            |
| 6   | Live Demo (via the Add-on)     | Both (alternating)   | 0:30 + live run |

(Slide 6's own script runs ~0:30 read aloud, same as last week's slide 7 — the remaining 1:30 of the "Live Demo" bucket is the actual live run, not more spoken script.)

**1. Role & Pain Point** — same grounding as last week: copywriters, and the 20-30% of editing time spent policing mechanical voice/tone instead of strategy (`docs/research-notes.snapshot.md`). Unchanged this week, so no new content to write — just said fast.

**2. Week 5 — The Original Agent** — kept deliberately tight per the rubric. One LLM tool-calling loop judging all 4 subjective categories (tone drift, information hierarchy, CTA cadence, readability), backed by Christina's deterministic evaluator for the 3 mechanical ones. Human-in-the-loop checkpoint: every output a suggestion or comment, nothing lands without an explicit accept in Google Docs.

**3. Week 6 — Two Specialist Agents (Karl)** — the architecture pattern: single agent → Structural agent (information hierarchy, CTA cadence; `create_inline_comment` only) + Line-Editor agent (tone drift, readability; originally `create_suggestion` only), dispatched concurrently on a `ThreadPoolExecutor`, merged by `orchestrator.reconcile_findings` (#46, #62). Restricting each agent to one tool turned a soft per-category preference into a hard constraint. `reconcile_findings` also flags — without resolving — cross-agent span overlaps (#65). Real false positives this fixed: #61 (tone_drift/readability false positives in Line-Editor), #64 (structural category fragmentation). Real resilience this bought: #66 — one specialist's already-posted output now survives even if the other's thread raises; previously a fail-fast crash discarded a completed result.

**4. Week 6 — Now Covering All 7 (Christina)** — Christina's rotation this sprint, in order: building `structural.py` from scratch, solo, against a failing-test contract Karl wrote before going out for the day (Sun Jul 12 — her first time in the agent/prompt layer, not the evaluator); her own Eval Card fixes in it (#64); then, in the back half of the week, PRs landing directly in what had been Karl-only files — `shared.py` (#80, case- insensitive category validation), `orchestrator.py` (#79, malformed-tool-call handling), and `llm_client.py` (#85). The headline one: #83, expanding the Line-Editor agent so the evaluator's deterministic findings (formatting/ style, banned words, channel constraints) aren't just injected as system- prompt context anymore — the agent transcribes each one into a real `create_suggestion`/`create_inline_comment` call. All 7 categories reach the document today; in Week 5 it was 4.

**5. Eval Evidence** — filled in from real runs against all 6 eval card pairs (`presentation/demo/eval-card-run-results.md` has full output). Golden path: **Mobile App Launch** — a clean run, no errors, no round cap, that correctly caught a banned competitor comparison as both a structural information-hierarchy issue and a line-editor banned-words hit (with the cross-agent-overlap flag firing correctly), plus real tone-drift and readability fixes — 7 findings across 5 categories. Adversarial input: **Feature Sunset** — a deliberately dense draft (a banned word repeated 5+ times, ageist language, two separate CTA stacks, heavy passive voice) that made the agent hit its round cap and stop early, but it still returned 14 valid, correctly-categorized findings across all 7 categories rather than crashing or returning a partial/corrupt result.

**6. Live Demo (via the Add-on)** — same mechanism as last week: sidebar → Run Verbatim Audit → Check Status → review inline. Input switches to **Eval Card 3 — Integration Announcement** (`presentation/demo/eval-card-links.md`), chosen over last week's proven `draft-copy.txt`/`campaign-brief.txt` pair because it ties the demo directly to this week's real eval-card work and its catches read well live (triple exclamation points, four stacked "click here" links) — a real, deliberate risk trade vs. the untouched, already-proven pair.

- **Action required before Saturday**: this doc was already directly edited once during evidence-gathering (`presentation/demo/eval-card-run- results.md`, run #3) — it's shared Editor, not Suggester, so that run landed as silent edits, not reviewable suggestions. Restore it to pristine text via Google Docs **File → Version history → See version history → restore the pre-audit version** before rehearsing or running this live.
- Input: draft doc `Eval Card 3 - Draft - Integration Announcement` (`1NLHA7W3QFNkgTpLWZIhP6v-_7Hn9QYeHt4rMNhgwJXQ`), campaign brief `Eval Card 3 - Brief - Integration Announcement` (`1ICj1ITPe3fv6spNmeu2Mt2nSIEavPSOMc87PYT_jEVk`), channel = Blog.
- Expected: **[placeholder — read off whatever categories/counts the results card actually shows; the evidence-gathering run found 10 findings across 5 categories (info hierarchy, CTA cadence, formatting/style, tone drift, readability), but this is a live, non-deterministic re-run against restored text, not a scripted repeat]**.
- Backup: a recorded run from rehearsal, same fallback rationale as last week (`UrlFetchApp.fetch()`'s 60s timeout, submit-then-poll flow — see `addon/README.md`).

Total ≈ 4:30 on the spoken script, before the live run itself.

## B. Speaker script

Each line is its own list item on purpose, same convention as last week's plan — a plain line break collapses into one run-on paragraph in rendered Markdown. Parenthetical text is a stage direction, not something to say out loud.

**[Slide 1 — 0:00–0:30, Christina then Karl]**

- CHRISTINA: "We're Karl and Christina, and Verbatim is still for copywriters — the people who write a company's marketing copy."
- KARL: "The pain point hasn't changed either: twenty to thirty percent of editing time goes to policing mechanical stuff instead of real writing. This week was about making the agent that gets that time back actually hold up under real use."

**[Slide 2 — 0:30–1:00, Karl]**

- KARL: "Quick recap of where we started. Week 5's agent was one tool-calling loop, judging all four subjective categories at once, backed by a deterministic evaluator for the mechanical ones. It read the doc and the brief, decided what to flag, and posted suggestions or comments — nothing landed without an explicit accept in Google Docs."

**[Slide 3 — 1:00–1:30, Karl]**

- KARL: "This week, one agent became two. The Structural agent judges information hierarchy and CTA cadence and can only leave comments; the Line-Editor agent judges tone and readability and can only propose rewrites — restricting each one to a single tool turned a soft preference into a hard constraint. They run concurrently on separate threads, and an orchestrator merges what they find — flagging, not resolving, any spot where both agents independently raise an issue. Narrower prompts fixed real false positives in each agent, and we made sure one agent's crash doesn't silently swallow the other's already-posted work."

**[Slide 4 — 1:30–2:00, Christina]**

- CHRISTINA: "My half of this: I built the Structural agent from scratch, solo, against failing tests Karl wrote before he went out for a day — my first time in the agent code instead of the evaluator. By the back half of the week I was shipping fixes directly into files that used to be Karl- only — the orchestrator, the shared category validation, even the LLM client — because the split held up well enough to work across. The biggest one: the Line-Editor agent doesn't just read the evaluator's findings as context anymore, it transcribes them into real suggestions and comments. All seven categories reach the doc now, not four."

**[Slide 5 — 2:00–2:30, Christina]**

- CHRISTINA: "We ran all six eval cards against this week's split. On the clean one — a mobile app launch email — it caught a banned competitor comparison from two angles at once: a structural hierarchy issue and a line-editor banned-words hit, flagged as the same overlapping span, plus real tone and readability fixes."
- CHRISTINA: "On the messiest one — a feature-sunset notice with a banned word repeated five times, ageist language, and two separate stacks of CTAs — it actually hit its round cap and had to stop early. But it still came back with fourteen valid, correctly-categorized findings instead of crashing or returning something broken."

**[Slide 6 — 2:30–3:00, alternating, then live]**

- KARL: "Let's run it — this is one of the six eval cards we just used to score the split." (open the Verbatim sidebar on the draft; the campaign brief link is already filled in)
- CHRISTINA: "Blog channel this time." (pick Blog, click "Run Verbatim Audit")
- KARL: "Two agents means two threads doing this at once now — we'll check status until both come back." (click "Check Status" once or twice until the results card appears)
- CHRISTINA: "Here's the breakdown." (read off the category counts — call out whatever actually shows up)
- KARL: "And here's what actually landed in the doc." (point at 2-3 of the real suggestions or comments that landed)

## C. Readiness self-check

### The agent

- [x] Week 5 agent recap accurate to what actually shipped and demoed Sat Jul 11.
- [x] Week 6 complexity addition is real, merged code — every PR cited above (#46, #61, #62, #64, #65, #66, #79, #80, #83, #85) is on `main`.
- [x] **Eval Card evidence** — all 6 eval card pairs run against the current agent split (`presentation/demo/eval-card-run-results.md`); golden-path and adversarial-input evidence sourced from real output.
- [x] Live demo mechanism unchanged from last week and already proven end-to-end (see `PRESENTATION_PLAN.md`'s own checklist).
- [ ] **Live demo input reset** — Eval Card 3's draft (`1NLHA7W3QFNkgTpLWZIhP6v-_7Hn9QYeHt4rMNhgwJXQ`) was already directly edited once during evidence-gathering; restore it to pristine text via Google Docs version history before rehearsing or presenting.
- [ ] **Live demo rehearsed against Eval Card 3** — this specific draft/brief/channel combination hasn't been run live yet (only once, during evidence-gathering, before the switch).

### The presentation

- [x] Speaking time balanced by seconds (75s/75s spoken script, ~60/60 alternating live-demo lines), not just by slide count.
- [x] Every Week 6 claim traceable to a real PR or incident, not invented for the talk.
- [x] Eval Card section filled in from real runs, not invented.
- [ ] **Full run-through timed** — draft script above is budgeted to 4:30, not yet rehearsed aloud against a clock.

The deck mechanism, script, and Eval Card evidence are all done. Two real gaps remain: resetting Eval Card 3's draft doc back to pristine text, and rehearsing/timing the full run-through — including this new live-demo input — against a clock.
