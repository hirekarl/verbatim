# TODO: sprint plan to the Sat Jul 11 demo

## Timeline

Today is **Tue Jul 7, 2026**. The demo is **Saturday Jul 11 morning**. Feature work should be substantially complete by **Thursday Jul 9 evening**, leaving Friday Jul 10 as a buffer/rehearsal day rather than a work day. That's really only **three working days**. `BOOTSTRAPPING.md`'s GitHub governance checklist is now fully done as of Jul 8 (release.yml + RELEASE_PAT, dependabot, PR/issue templates, CONTRIBUTING/SECURITY/CODE_OF_CONDUCT, CODEOWNERS, branch protection, and squash-only merge settings are all live) — only that document's verification checklist walkthrough remains, which is optional/non-blocking and deferred to the post-demo backlog below so both people's time stays against feature completion.

## Context

Verbatim's local tooling scaffold from `BOOTSTRAPPING.md` is done, and so is that runbook's GitHub-governance checklist (release.yml/RELEASE_PAT, dependabot, PR/issue templates, CONTRIBUTING/SECURITY/CODE_OF_CONDUCT, CODEOWNERS, branch protection, squash-only merge settings). Separately, real feature work has already started: Christina opened `feat/brand-guidelines-evaluator` (not yet merged) implementing a deterministic `BrandGuidelinesEvaluator` that covers 3 of the 7 audit categories (banned words, and two formatting/style checks — ampersands, Oxford comma) via regex, built TDD-style against `tests/test_evaluator.py`. Karl has been making small infra-fixup commits on top of her branch (pinning pre-commit hook versions to match CI).

The engineering split below formalizes what's already fallen out of who's touched what so far: Karl owns infra/CI/tooling and the Docs API/agent side, Christina owns the evaluator/rules logic. Karl is more technical; the goal is to keep the two of them off the same files at the same time while giving Christina genuine, substantive ownership rather than docs/config busywork.

Two architecture/process decisions, made so they don't get re-litigated mid-sprint:

1. **Hybrid architecture**: `evaluator.py` stays a deterministic, regex/rule-based checker and only ever needs to cover the *mechanically-checkable* categories — banned words, formatting/style mechanics, channel character/sentence limits, standardized spellings. The four categories requiring subjective judgment (tone drift, information hierarchy, CTA cadence, readability) are handled by the LLM agent itself via the system prompt described in the PRD, using `BrandGuidelines.format_for_llm_prompt()` as injected context — the evaluator's deterministic violations become an extra signal the agent can cite, not something it needs to reproduce with regex.
1. **Christina's scope**: stays concentrated in the evaluator/rules domain through Thursday (where she already has traction and it's lower-risk given the time pressure), with rotation into Docs API/agent-loop territory explicitly deferred to the post-demo backlog.

## File/component ownership map (why the work doesn't collide)

| Component                                | Files                                                                         | Owner                                                     |
| ---------------------------------------- | ----------------------------------------------------------------------------- | --------------------------------------------------------- |
| Deterministic rule evaluator             | `src/verbatim/evaluator.py`, `tests/test_evaluator.py`                        | Christina                                                 |
| Brand guidelines loader (post-migration) | `src/verbatim/brand_guidelines.py`, `src/verbatim/data/brand_guidelines.json` | Christina (migration), then a shared read-only dependency |
| Google Docs API client + tool wrappers   | new `src/verbatim/docs_client.py` (or similar)                                | Karl (Christina rotates in post-demo)                     |
| LLM system prompt + agent orchestration  | new `src/verbatim/agent.py` / `src/verbatim/prompt.py`                        | Karl                                                      |

Karl and Christina work in disjoint files every day through the demo — no shared-file edits to coordinate.

## Day-by-day plan

### Day 1 — Tue Jul 7 (today, remainder of day): merge the core, start Docs plumbing

- [x] **Karl**: stand up Google Docs API auth + `get_document_content` + `get_campaign_context` tool wrappers in a new module, isolated from `evaluator.py`; read a real Google Doc's content and a campaign brief doc programmatically, end to end. *(merged in #4)*
- [x] **Christina**: get `feat/brand-guidelines-evaluator` merged into `main`. *(merged in #2)*
- [x] **Christina**: add the standardized-spellings check (`get_standardized_spellings()` wired into `evaluator.py`).
- [x] **Christina**: start the `channel_constraints` category (character/sentence-count limits per channel) — went beyond "start," fully covers Twitter, Facebook, Instagram, and email subject-line checks.

### Day 2 — Wed Jul 8: comment/suggestion posting + system prompt, rest of formatting rules

- [x] **Karl**: implement `create_suggestion` / `create_inline_comment` (Docs API `batchUpdate` + comments POST).
- [x] **Karl**: draft the PRD's "System Prompt v0" and wire `BrandGuidelines.format_for_llm_prompt()` into a prompt-assembly module (`prompt.py`) covering the four LLM-judged categories (tone drift, information hierarchy, CTA cadence, readability); agent loop is one pass over the document, as scoped.
- [x] **Christina**: flesh out `formatting_and_style` — semicolons, exclamation points, quotation-mark placement, gender-neutral terms, capitalization standardization, link/button copy rules, number formatting. *(merged in #7)*
- [ ] **Christina**: general title/sentence-case check for body copy — the one `formatting_and_style` rule PR #7 didn't cover (email-subject sentence case is handled, general body copy isn't). Deliberately deferred, not a regression — tracked as [#11](https://github.com/hirekarl/verbatim/issues/11).
- [x] **Christina**: `brand_guidelines.py`/`.json` → `src/verbatim/` migration — done ahead of the "if time remains" contingency.

### Day 3 — Thu Jul 9 (finish by evening): wire it all together, integration-test

- [x] **Karl**: build the single orchestration entrypoint/CLI (`cli.py`) that ties evaluator output + LLM output + comment/suggestion posting into one on-demand run.
- [x] **Karl**: run it end to end against a real Google Doc + campaign brief and fix Docs API/orchestration bugs as they surface. *(evidenced by fix commits: OpenRouter budget-limit handling, duplicate suggestion replacements)*
- [x] **Christina**: feed real/sample marketing copy through the evaluator to shake out false positives/negatives and fix evaluator/rule bugs found during integration testing. *(evidenced by fix commits: non-breaking-space detection, overlapping click-here-link matches)*
- [ ] **Christina**: help assemble the demo document so it visibly triggers a representative spread across all 7 categories — lives in Google Docs itself, not verifiable from the repo; confirm directly with Christina.

### Fri Jul 10 — buffer day (not a sprint)

- [ ] Rehearse the demo end to end.
- [ ] Fix anything that broke during rehearsal.
- [ ] Prepare a recorded fallback in case the live Docs API demo is flaky.

### Sat Jul 11 morning — demo

## Post-demo backlog (deliberately deferred, not due Thursday)

- [ ] `BOOTSTRAPPING.md`'s verification checklist walkthrough (optional sanity pass — every actual governance item it covers, including squash-only merge settings, is already live as of Jul 8).
- [x] Failure-mode safeguards from PRD 3c not essential to the demo: session cache for Docs API rate-limit resilience (`GoogleDocsClient._doc_cache`, tested), graceful in-doc warning if `brand_guidelines.json` is missing/corrupt (`agent.py`, tested). *(shipped early in #9, ahead of the demo)*
- [ ] Christina's rotation into Docs API/agent-loop territory (one self-contained tool wrapper, reviewed by Karl) — `GoogleDocsClient.list_comments()` exists as a stub raising `NotImplementedError`, with a stub test asserting that; the real implementation is still outstanding. *(scaffolded in #9)*
- [ ] Any `formatting_and_style` rules not finished by Wednesday — just the general title/sentence-case check for body copy, tracked as [#11](https://github.com/hirekarl/verbatim/issues/11).
- [ ] Workspace Add-on migration (fulfills the original production target from `docs/research-notes.snapshot.md` — `cli.py` is retained as a permanent local-dev/direct-run entrypoint alongside it, not replaced): see `docs/workspace-addon-migration.md` for the direction/feasibility writeup and the checklist below. Sized as its own mini-sprint, not a quick follow-on. Started ahead of schedule (Karl-solo) on Jul 8.

## Workspace Add-on migration backlog

Tracked as [milestone "Workspace Add-on Migration"](https://github.com/hirekarl/verbatim/milestone/1), labeled `workspace-addon`. Filed in dependency order — see `docs/workspace-addon-migration.md` for the full direction/feasibility writeup each issue is drawn from.

- [x] [#18](https://github.com/hirekarl/verbatim/issues/18) Add knowledge-base coverage for Apps Script / CardService / Add-on OAuth *(merged in #26)*
- [x] [#19](https://github.com/hirekarl/verbatim/issues/19) `docs_client`: add `from_access_token()` auth path for hosted use — depends on #18 *(merged in #27)*
- [x] [#24](https://github.com/hirekarl/verbatim/issues/24) Resolve open sequencing questions before starting the migration — resolved as a comment on the issue and in `docs/workspace-addon-migration.md` §9
- [x] [#20](https://github.com/hirekarl/verbatim/issues/20) Stand up HTTP entrypoint wrapping `run_agent()` — depends on #19; CLI-retention amendment recorded as a comment on the issue *(merged in #28)*
- [x] [#21](https://github.com/hirekarl/verbatim/issues/21) Validate inbound Add-on bearer tokens before trusting them — depends on #20 *(merged in #29)*
- [x] [#22](https://github.com/hirekarl/verbatim/issues/22) Build Editor Add-on shell: manifest + CardService sidebar + UrlFetchApp call — depends on #20, #21. Pushed to a real standalone Apps Script project via `clasp` (manifest schema bug found and fixed, #35) and associated with `verbatim-501715`. Brief ID and target channel both reconsidered from #24's original hardcoded-value resolution to sidebar inputs (a text field accepting a doc ID or full share URL; a dropdown limited to channels the evaluator has rules for) — see `addon/README.md`. Still outstanding: Script Properties (`BACKEND_URL`/`BACKEND_SHARED_SECRET`/optional `DEFAULT_BRIEF_ID`) and a real end-to-end test via Deploy → Test deployments — both manual, in-browser steps.
- [x] [#23](https://github.com/hirekarl/verbatim/issues/23) Containerize backend and deploy to Cloud Run — depends on #20. Deployed: `verbatim-backend` on `us-east4`, project `verbatim-501715` — `https://verbatim-backend-75857425003.us-east4.run.app`. `GOOGLE_OAUTH_CLIENT_ID` is now set (sourced from the associated Apps Script project's OAuth client).
- [ ] [#33](https://github.com/hirekarl/verbatim/issues/33) Front the Cloud Run backend with an internal auth-proxy to drop `--allow-unauthenticated` — deliberately deferred, not part of the initial deploy
