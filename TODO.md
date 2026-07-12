# TODO: sprint plan

## Timeline

**Sprint 1** (Tue Jul 7 – Sat Jul 11) shipped the single-agent pipeline and demoed successfully Sat Jul 11 morning. Full narrative: see "Sprint 1 (complete)" below.

**Sprint 2** (Sat Jul 11 – Sat Jul 18) is in progress now: evolving the single-agent pipeline into a multi-agent workflow. **Full architecture, rationale, and file/module plan: see `MULTI_AGENT_PLAN.md`.** This document is the actionable day-by-day checklist; `MULTI_AGENT_PLAN.md` is where the "why" lives, so the two don't need to stay in lockstep beyond the schedule itself.

Feature work should be substantially complete by **Thu Jul 16**, leaving **Fri Jul 17** as a dedicated demo-prep/rehearsal day (mirroring Sprint 1's rhythm). Demo is **Sat Jul 18**.

## Sprint 2 day-by-day plan

### Sat Jul 11 (today, Karl)

- [x] Write `MULTI_AGENT_PLAN.md` (architecture, rationale, file/module plan, schedule).
- [x] Create `multi-agent-plan` branch.
- [x] Commit `MULTI_AGENT_PLAN.md`, push the branch, open a PR.
- [x] Write failing contract tests for `prompts/structural.py` (category list, tool schema shape, system-prompt template contents) and for `orchestrator.reconcile_findings()`.
- [x] Stub `prompts/line_editor.py` and `orchestrator.py` signatures so imports resolve.

### Sun Jul 12 (Christina, solo — Karl out)

- [x] Implement `src/verbatim/prompts/structural.py` against the pre-written failing tests. (This is the "Christina's rotation into Docs API/agent territory" backlog item from Sprint 1 — see below — now actually underway.)

### Sun Jul 12 (Karl, out-of-band)

Christina's exploration of `shared.py` while starting her `structural.py` work surfaced a real validation gap — category tags aren't hard-enforced against the 7-category vocabulary, only advisory via a JSON-schema `enum`. Full writeup: `MULTI_AGENT_PLAN.md`'s "Category validation" section. Done entirely in Karl-owned files, no collision with Christina's `structural.py` task above.

- [x] Implement `src/verbatim/prompts/shared.py` (`CATEGORIES` relocated from `prompt.py`, new `validate_category()`).
- [x] Wire `validate_category` into `agent.py`'s `_dispatch_tool_call` (closes the gap in the currently-deployed Sprint-1 path).
- [x] Lock `orchestrator._run_single_agent_loop`'s new `allowed_categories` parameter (signature/docstring only — body still stubbed for Monday).

### Mon Jul 13 (Karl back)

- [ ] Implement `prompts/line_editor.py` and `orchestrator.py` Phase 1 (sequential dispatch + `reconcile_findings`).
- [ ] Wire `_run_single_agent_loop`'s `allowed_categories` param (`STRUCTURAL_CATEGORIES`/`LINE_EDITOR_CATEGORIES`) through `validate_category` at both specialist call sites — contract locked Sun Jul 12.
- [ ] Retarget `tests/test_agent.py`'s dispatch/dedup/error-handling tests onto `_run_single_agent_loop`.
- [ ] Wire `run_agent()` to the new split behind `run_agent_legacy`.

### Tue Jul 14 — Eval Card validation, split by agent ownership

- [ ] **Christina**: run golden/edge/adversarial fixtures (+ `presentation/demo/*`) against the Structural agent (Info Hierarchy + CTA Cadence); fix anything found in `prompts/structural.py`.
- [ ] **Karl**: same for the Line-Editor agent (Tone Drift + Readability) in `prompts/line_editor.py`.
- [ ] **Both**: end-of-day sync — go/no-go call on flipping `run_agent()`'s default to the new split.

### Wed Jul 15

- [ ] **Karl**: Phase 2 concurrency — `ThreadPoolExecutor` dispatch, `docs_client.py` write lock, two independent `OpenRouterClient` instances, concurrency test.
- [ ] **Christina**: unassigned/TBD. Her originally-planned task here (the `formatting_and_style` title/sentence-case check, [#11](https://github.com/hirekarl/verbatim/issues/11)) already shipped in PR #40 on Jul 9, before this sprint plan was written — caught during PR #46 review. Revisit after Tue Jul 14's Eval Card sync, once there's real signal on what needs work.

### Thu Jul 16 — buffer/polish, feature-complete

- [ ] **Karl**: full regression (`pytest`, `ruff`, `mypy`, `--cov-fail-under=90`).
- [ ] **Karl**: merge `multi-agent-plan` into `main`.
- [ ] **Christina**: CHANGELOG/README updates for the new architecture.
- [ ] **Christina**: final coverage pass on `tests/test_prompts_structural.py`.

### Fri Jul 17 — demo prep only (not a sprint day)

- [ ] **Christina**: prep structural-category demo fixtures/triggers.
- [ ] **Karl**: prep line-editor-category triggers plus deck mechanics (`presentation/build_deck.py` / `PRESENTATION_PLAN.md`).
- [ ] **Both**: rehearse end to end.

### Sat Jul 18 — demo (both)

## Sprint 2 file/component ownership map

See `MULTI_AGENT_PLAN.md`'s "File/module plan" for the authoritative version; summarized here for quick reference:

| Component                              | Files                                            | Owner     |
| -------------------------------------- | ------------------------------------------------ | --------- |
| Shared prompt scaffolding              | `src/verbatim/prompts/shared.py`                 | Karl      |
| Structural agent (Info Hierarchy, CTA) | `src/verbatim/prompts/structural.py`, its tests  | Christina |
| Line-Editor agent (Tone, Readability)  | `src/verbatim/prompts/line_editor.py`, its tests | Karl      |
| Orchestrator + result merging          | `src/verbatim/orchestrator.py` (new)             | Karl      |
| Docs API write-serialization (Phase 2) | `src/verbatim/docs_client.py`                    | Karl      |
| Legacy single-agent validation         | `src/verbatim/agent.py`                          | Karl      |

Untouched this sprint: `src/verbatim/evaluator.py`, `brand_guidelines.py`/`.json`, `tests/test_evaluator.py`, `http_api.py`, `cli.py`, `addon/` — unless Christina's still-TBD Wed Jul 15 slot (see day-by-day above) ends up landing in `evaluator.py`.

Non-file tasks (Eval Card validation) are split by day above rather than in this table, since they're not tied one-to-one to a file.

## Deferred backlog (carried over from Sprint 1)

- [ ] `BOOTSTRAPPING.md`'s verification checklist walkthrough (optional sanity pass — every actual governance item it covers is already live).
- [x] Christina's rotation into Docs API/agent-loop territory — now underway as Sprint 2's Sun Jul 12 task (see above), no longer a separate backlog item.
- [x] `formatting_and_style` general title/sentence-case check for body copy — [#11](https://github.com/hirekarl/verbatim/issues/11) *(merged in #40, Jul 9, ahead of this backlog list being written)*.
- [ ] [#33](https://github.com/hirekarl/verbatim/issues/33) Front the Cloud Run backend with an internal auth-proxy to drop `--allow-unauthenticated` — deliberately deferred, not part of the initial deploy.

## Workspace Add-on migration backlog

Tracked as [milestone "Workspace Add-on Migration"](https://github.com/hirekarl/verbatim/milestone/1), labeled `workspace-addon`. Filed in dependency order — see `docs/workspace-addon-migration.md` for the full direction/feasibility writeup each issue is drawn from. All shipped ahead of schedule except #33 (tracked above).

- [x] [#18](https://github.com/hirekarl/verbatim/issues/18) Add knowledge-base coverage for Apps Script / CardService / Add-on OAuth *(merged in #26)*
- [x] [#19](https://github.com/hirekarl/verbatim/issues/19) `docs_client`: add `from_access_token()` auth path for hosted use — depends on #18 *(merged in #27)*
- [x] [#24](https://github.com/hirekarl/verbatim/issues/24) Resolve open sequencing questions before starting the migration — resolved as a comment on the issue and in `docs/workspace-addon-migration.md` §9
- [x] [#20](https://github.com/hirekarl/verbatim/issues/20) Stand up HTTP entrypoint wrapping `run_agent()` — depends on #19; CLI-retention amendment recorded as a comment on the issue *(merged in #28)*
- [x] [#21](https://github.com/hirekarl/verbatim/issues/21) Validate inbound Add-on bearer tokens before trusting them — depends on #20 *(merged in #29)*
- [x] [#22](https://github.com/hirekarl/verbatim/issues/22) Build Editor Add-on shell: manifest + CardService sidebar + UrlFetchApp call — depends on #20, #21. Pushed to a real standalone Apps Script project via `clasp` (manifest schema bug found and fixed, #35) and associated with `verbatim-501715`. Brief ID and target channel both reconsidered from #24's original hardcoded-value resolution to sidebar inputs (a text field accepting a doc ID or full share URL; a dropdown limited to channels the evaluator has rules for) — see `addon/README.md`.
- [x] [#23](https://github.com/hirekarl/verbatim/issues/23) Containerize backend and deploy to Cloud Run — depends on #20. Deployed: `verbatim-backend` on `us-east4`, project `verbatim-501715` — `https://verbatim-backend-75857425003.us-east4.run.app`. `GOOGLE_OAUTH_CLIENT_ID` is now set (sourced from the associated Apps Script project's OAuth client).
- [ ] [#33](https://github.com/hirekarl/verbatim/issues/33) Front the Cloud Run backend with an internal auth-proxy to drop `--allow-unauthenticated` — deliberately deferred, not part of the initial deploy.

## Sprint 1 (complete)

Shipped the single-agent pipeline and the Workspace Add-on migration, ahead of the original scope. Kept here for reference; `CHANGELOG.md` has the authoritative shipped-feature record.

### Context

`BOOTSTRAPPING.md`'s local tooling scaffold and GitHub-governance checklist (release.yml/RELEASE_PAT, dependabot, PR/issue templates, CONTRIBUTING/SECURITY/CODE_OF_CONDUCT, CODEOWNERS, branch protection, squash-only merge settings) were done ahead of the demo. Christina built a deterministic `BrandGuidelinesEvaluator` (banned words, formatting/style, channel constraints) TDD-style against `tests/test_evaluator.py`; Karl built the Docs API client, LLM agent orchestration, and CLI/HTTP entrypoints. The engineering split kept the two of them off the same files at the same time: Karl on infra/CI/Docs-API/agent, Christina on the evaluator/rules logic.

Architecture decision made so it wouldn't get re-litigated mid-sprint: **hybrid architecture** — `evaluator.py` stays deterministic/regex-based and only covers the mechanically-checkable categories (banned words, formatting/style, channel constraints); the four subjective categories (tone drift, information hierarchy, CTA cadence, readability) are handled by one LLM agent via the system prompt, using the evaluator's output as injected context rather than something the LLM needs to reproduce.

### Day 1 — Tue Jul 7: merge the core, start Docs plumbing

- [x] **Karl**: stand up Google Docs API auth + `get_document_content` + `get_campaign_context` tool wrappers, isolated from `evaluator.py`. *(merged in #4)*
- [x] **Christina**: get `feat/brand-guidelines-evaluator` merged into `main`. *(merged in #2)*
- [x] **Christina**: add the standardized-spellings check.
- [x] **Christina**: build out the `channel_constraints` category — covers Twitter, Facebook, Instagram, and email subject-line checks.

### Day 2 — Wed Jul 8: comment/suggestion posting + system prompt

- [x] **Karl**: implement `create_suggestion` / `create_inline_comment` (Docs API `batchUpdate` + comments POST).
- [x] **Karl**: draft the PRD's "System Prompt v0" and wire `BrandGuidelines.format_for_llm_prompt()` into `prompt.py`.
- [x] **Christina**: flesh out `formatting_and_style` — semicolons, exclamation points, quotation-mark placement, gender-neutral terms, capitalization, link/button copy rules, number formatting. *(merged in #7)*
- [x] **Christina**: `brand_guidelines.py`/`.json` migration into `src/verbatim/` — done ahead of schedule.

### Day 3 — Thu Jul 9: wire it all together, integration-test

- [x] **Karl**: build `cli.py`, tying evaluator + LLM + comment/suggestion posting into one on-demand run.
- [x] **Karl**: run it end to end against a real Doc + brief, fix bugs. *(OpenRouter budget-limit handling, duplicate suggestion replacements)*
- [x] **Christina**: shake out evaluator false positives/negatives against real copy. *(non-breaking-space detection, overlapping click-here-link matches)*
- [x] **Christina**: assemble the demo document.

### Fri Jul 10 — buffer day

- [x] Rehearsed the demo end to end and prepared a fallback.

### Sat Jul 11 morning — demo

Demoed successfully.
