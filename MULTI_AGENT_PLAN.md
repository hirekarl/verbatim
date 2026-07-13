# Multi-Agent Evolution Plan

Build week 2's goal: evolve Verbatim's single-agent pipeline into a multi-agent workflow. The single-agent build (one LLM tool-calling loop judging all 4 subjective categories, backed by a deterministic evaluator for the 3 mechanical ones) just demoed successfully. This document is the sprint plan for the next step — architecture, rationale, file/module ownership, and a day-by-day split between Karl and Christina, written specifically because **Karl is out the day after this plan is written and Christina works solo that day**. Every decision below is made concrete enough that her solo day doesn't block on him.

## Current architecture (recap)

`cli.py` / `http_api.py` → `agent.run_agent()` → fetch doc + brief once → run `BrandGuidelinesEvaluator.evaluate()` once (3 deterministic categories: banned words, formatting/style, channel constraints) → build one system prompt covering all 4 subjective categories (tone drift, information hierarchy, CTA cadence, readability) → one tool-calling loop against two tools (`create_suggestion`, `create_inline_comment`) → return `AgentRunResult`.

The weak point this plan addresses: today's single prompt only *instructs* the model which tool to prefer per category — it's a soft constraint the model can (and sometimes does) ignore. And a single prompt asks one model to hold instructions and reasoning for 4 different kinds of judgment (structural, whole-document reasoning vs. local, sentence-level rewriting) in one context.

## Target architecture

**Two specialist LLM agents + one thin code orchestrator**, replacing the single 4-category loop:

- **Structural agent** — judges Information Hierarchy + CTA Cadence. Only has `create_inline_comment` available (no suggestion tool). Whole-document, paragraph-ordering reasoning.
- **Line-Editor agent** — judges Tone Drift + Readability. Only has `create_suggestion` available (no comment tool). Local, sentence-level rewrite reasoning.
- **Orchestrator** — plain Python, not an LLM. Builds the shared context once (fetch doc/brief, run the deterministic evaluator exactly as today, unfiltered, passed identically to both agents), dispatches both sub-agents, **blocks until both return** (no streaming or partial synthesis), then calls an isolated `reconcile_findings(structural, line_editor) -> AgentRunResult` function to merge. This seam is deliberately code-only for now, but shaped so a future LLM "lead agent" — one that reconciles conflicting or redundant findings before write-out — can drop in later without changing anything upstream or downstream of it.

### Delivery is phased, not one leap

1. **Phase 1 (sequential).** Orchestrator calls Structural then Line-Editor in sequence, merges. No concurrency, no lock needed. This isolates and validates the actually-unproven variable — does narrowing the prompt/tool surface per category improve output? — from any concurrency risk.
1. **Phase 2 (concurrent).** Once Phase 1 is validated (see Validation below), swap the sequential calls for `ThreadPoolExecutor`-based concurrent dispatch. Requires a `threading.Lock` around `GoogleDocsClient.create_suggestion` / `create_inline_comment` — their locate-range + batchUpdate + cache-clear sequence isn't thread-safe today — and two independent `OpenRouterClient` instances. Cross-agent span dedup is a non-issue by construction: the existing dedup key is `(tool_name, matched_text)`, and Structural/Line-Editor never share a tool name, so their local `seen_spans` sets can never collide. Concurrency also breaks the "no partial synthesis" assumption above: once both specialists' writes can land in the doc independently, an exception in one thread can no longer be treated as "the doc is untouched" the way Phase 1's sequential fail-fast could assume. `run_agent()` awaits both futures and returns the surviving specialist's real result (annotated via `AgentRunResult.specialist_errors`) rather than discarding it, only raising if both fail — see #63.

`run_agent()`'s signature and `AgentRunResult`'s shape stay exactly as they are today — `http_api.py`, `cli.py`, and the Workspace Add-on's submit/poll contract need zero changes either phase. The old single-agent path is kept around as `run_agent_legacy` (not deleted) so a before/after comparison stays possible.

## Why this split

- The comment-vs-suggestion boundary is already a hard product requirement in the PRD (`docs/PRD.snapshot.md`), not an invented abstraction — Tone/Readability → suggestions, Info Hierarchy/CTA Cadence → comments. Splitting along it is the least arbitrary cut available, and turns a soft per-category tool preference into a hard constraint each sub-agent literally cannot violate.
- CTA cadence and information hierarchy both depend on reasoning about paragraph order across the whole document; tone and readability are both local rewrite judgments. A 4-way fan-out (one agent per category) would separate categories that plausibly need shared context — rejected for that reason, plus it would be 4x the prompts to maintain and 4x the write contention for no added product justification.
- A reviewer/critic third agent (a drafting agent plus an adjudicator that dedupes before write-out) is deferred, not rejected outright — worth it only if the Eval Card comparison below turns up a specific false-positive/noise problem, which there's no data on yet.

## Validation

Before flipping the default from `run_agent_legacy` to the new split, run the PRD's Eval Card golden / edge-case / adversarial fixtures — plus the existing `presentation/demo/*` fixtures — through both paths against the same seeded document and manually diff per-category finding coverage. `TEST_PLAN.md` already treats LLM-judged categories as "reasonable coverage, not exact match," so this is a semi-manual comparison, not a new CI gate, which is the appropriately-scoped bar for a one-week, two-person sprint.

## File/module plan

To keep Karl/Christina ownership disjoint (an existing, explicit design goal), `prompt.py` becomes a package rather than one shared file both of them would need to touch:

- `src/verbatim/prompts/shared.py` (Karl) — `CATEGORIES`, `validate_category()`, the prompt-assembly helper, the deterministic-findings block. Logic relocated from `prompt.py` unchanged.
- `src/verbatim/prompts/structural.py` (**Christina**) — `STRUCTURAL_CATEGORIES`, its system prompt template, `build_structural_system_prompt()`, `STRUCTURAL_TOOL_SCHEMAS` (comment-only, category enum restricted to `["information_hierarchy", "cta_cadence"]`).
- `src/verbatim/prompts/line_editor.py` (Karl) — mirror of the above for Tone Drift + Readability, suggestion-only.
- `src/verbatim/orchestrator.py` (Karl, new file) — `_run_single_agent_loop()` (extracted from today's `agent.py` loop body, takes an `allowed_categories` param and validates each dispatched finding's category against it — see "Category validation" below), `reconcile_findings()`, and the rewritten `run_agent()` entrypoint (Phase 1 sequential; Phase 2 swaps in `ThreadPoolExecutor`).
- `src/verbatim/docs_client.py` (Karl) — add `threading.Lock`, Phase 2 only.
- Tests: `tests/test_prompts_structural.py` (**Christina**), `tests/test_prompts_line_editor.py` plus a retargeted `tests/test_agent.py` (Karl).

**Untouched:** `src/verbatim/evaluator.py`, `brand_guidelines.py`/`.json`, `tests/test_evaluator.py` (Christina's existing files — `evaluate()` is still called exactly once, unfiltered, by the orchestrator), `http_api.py`, `cli.py`, `addon/Backend.gs`, `addon/Code.gs`.

## Category validation

Christina, while working through where the category vocabulary should live for `prompts/structural.py` (Sun Jul 12), surfaced a gap: the 7 category tags are just strings the model has to type correctly into every tool call. The only existing enforcement is a JSON-schema `enum` on the `category` parameter (`prompt.py`'s `TOOL_SCHEMAS`), but OpenRouter/OpenAI-style function calling doesn't hard-enforce a schema `enum` or `required` server-side — a model can still return `category` missing, misspelled (`"info_hierarchy"`), differently cased, or — once the specialist split lands — a real category that belongs to the *other* agent (e.g. Structural tagging a finding `tone_drift`). That silently fragments `AgentRunResult.category_counts`, which is indistinguishable from a genuine zero-findings case and feeds directly into the PRD's Eval Card per-category coverage comparison. This is the same "soft instruction vs. hard constraint" gap the comment-vs-suggestion tool split above closes for tool *choice* — just one layer down, on the tag string itself.

**Fix:** `src/verbatim/prompts/shared.py` exposes `validate_category(category, allowed) -> str`, which returns `category` unchanged if it's in the caller's `allowed` list, else falls back to `"uncategorized"` — the same fallback value and philosophy `agent.py` already uses (and is tested) for a missing `category`, just now also covering "present but not allowed." Each caller passes its *own* allowed set: the full `CATEGORIES` for the legacy single-agent path (`agent.py`, wired Sun Jul 12), and each specialist's own narrower list (`STRUCTURAL_CATEGORIES`, `LINE_EDITOR_CATEGORIES`) once `orchestrator._run_single_agent_loop` is implemented Mon Jul 13 — so a Structural finding mistagged `tone_drift` is caught too, not just outright typos.

**Enforced at dispatch time only** (`agent.py`'s `_dispatch_tool_call` today; `orchestrator._run_single_agent_loop` Monday) — deliberately **not** duplicated in `reconcile_findings`. Every `Finding` is constructed at dispatch, so by the time two `AgentRunResult`s reach `reconcile_findings` their categories are already valid; re-checking there would validate data that can't be invalid by construction, which is exactly the unneeded defense this project's process norms (see `CLAUDE.md`) say to avoid. `reconcile_findings` also has no way to know which agent's narrower allowed-list a given merged key should be checked against, since it merges both into one union.

No logging was added (a first for this codebase would need its own convention decision) — silent fallback matches the existing tested precedent exactly. Worth revisiting once the Tue Jul 14 Eval Card runs give real data on how often `uncategorized` actually fires.

## Sprint schedule (Sat Jul 11 – Sat Jul 18)

Sprint 1 demoed today, Sat Jul 11. This is the build-week-2 sprint: implementation runs through Thu Jul 16, Fri Jul 17 is dedicated demo-prep (no new feature work), and the week-2 demo is Sat Jul 18 — mirroring sprint 1's own implement-then-buffer-then-demo rhythm, shifted one week.

- **Sat Jul 11 (today, Karl):** Finalize this document and the `multi-agent-plan` branch. Write the **failing contract tests** for `prompts/structural.py` (category list, tool schema shape, system-prompt template contents) and for `orchestrator.reconcile_findings()` — the TDD red step, and critically, it locks the interface so Christina isn't making open design calls alone tomorrow, she's turning pre-written red tests green. Stub `prompts/line_editor.py` and `orchestrator.py` signatures (not full implementations) so imports resolve.
- **Sun Jul 12 (Christina, solo — Karl out):** Implement `src/verbatim/prompts/structural.py` against the pre-written failing tests. Doubles as the "Christina's rotation into Docs API/agent territory" item already sitting in `TODO.md`'s post-demo backlog — this sprint is where that rotation actually starts, on a piece scoped tightly enough not to need Karl live. Stays out of `agent.py`/`orchestrator.py`/`docs_client.py` entirely — no concurrent-editing risk, no blocked-on-Karl risk.
- **Mon Jul 13 (Karl back):** Implement `prompts/line_editor.py` and `orchestrator.py` Phase 1 (sequential dispatch + `reconcile_findings`), retarget `tests/test_agent.py`'s dispatch/dedup/error-handling tests onto `_run_single_agent_loop`, wire `run_agent()` to the new split behind `run_agent_legacy`.
- **Tue Jul 14 — Eval Card validation, split by agent ownership:** **Christina** runs the golden/edge-case/adversarial fixtures plus `presentation/demo/*` against the Structural agent (Information Hierarchy + CTA Cadence) and fixes anything found in `prompts/structural.py`; **Karl** does the same for the Line-Editor agent (Tone Drift + Readability) in `prompts/line_editor.py`. Each stays in their own file — no collision. Short joint sync at day's end for the go/no-go call on flipping the default.
- **Wed Jul 15:** **Karl** — Phase 2 concurrency: `ThreadPoolExecutor` dispatch, `docs_client.py` write lock, two independent `OpenRouterClient` instances, concurrency test (all files already his). **Christina** — unassigned/TBD; her originally-planned task (`formatting_and_style` title/sentence-case check, [#11](https://github.com/hirekarl/verbatim/issues/11)) already shipped in PR #40 on Jul 9, before this document was written. Revisit after Tue Jul 14's Eval Card sync.
- **Thu Jul 16 — buffer/polish, feature-complete ("more or less done"):** **Karl** — full regression (`pytest`, `ruff`, `mypy`, `--cov-fail-under=90`), merge `multi-agent-plan` into `main`. **Christina** — CHANGELOG/README updates for the new architecture, final coverage pass on `tests/test_prompts_structural.py`. Any Mon–Wed spillover gets absorbed here, not into Friday.
- **Fri Jul 17 — demo prep only:** No new feature work. **Christina** preps structural-category demo fixtures/triggers; **Karl** preps line-editor-category triggers plus deck mechanics (`presentation/build_deck.py`, `PRESENTATION_PLAN.md`). Rehearse together end to end.
- **Sat Jul 18 — demo (both).**
