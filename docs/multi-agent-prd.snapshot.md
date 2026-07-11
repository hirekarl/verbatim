> **Snapshot notice:** Markdown snapshot of `Multi-Agent Category Split PRD.docx`, generated 2026-07-11 via `pandoc -f docx -t gfm`. The docx remains the authoritative source — don't hand-edit this file; regenerate it with the same command if the docx changes.

**Multi-Agent Category Split**

*Product Requirements Document: Agent Improvement*

**Agent:** Verbatim

**Owner(s):** Karl Johnson and Christina Ruiz

**Date:** July 11, 2026

# <span class="smallcaps">1. PROBLEM</span>

Copywriters and Marketing Leads get inline comments and suggested edits from Verbatim’s single audit agent today, but occasionally see a structural issue land as a suggested rewrite (or a rewrite-worthy issue land as an unactionable comment) because the agent’s one system prompt only instructs — never enforces — which of its two tools (create_suggestion, create_inline_comment) fits each of the 4 LLM-judged categories, and that same single prompt has to hold both whole-document structural reasoning and local, sentence-level rewrite reasoning in one context at once.

## **1a. Background & Dependencies**

- Verbatim PRD (v1) — docs/PRD.snapshot.md (source: Verbatim PRD.docx); architecture rationale and phased rollout plan for this improvement: MULTI_AGENT_PLAN.md.

- Current state: v1 is one LLM tool-calling loop (agent.py’s run_agent()) judging all 4 subjective categories against both create_suggestion and create_inline_comment, backed by a deterministic evaluator (evaluator.py) for the other 3 categories — demoed successfully once, Sat Jul 11, with no live production usage yet.

- Dependency: none new. Both tools already call the same GoogleDocsClient.create_suggestion / create_inline_comment methods granted in v1 — this improvement only re-scopes which agent’s schema offers which tool; no new API scope, endpoint, or credential is required.

## **1b. Current Agent Behavior**

- cli.py and http_api.py both call agent.run_agent() once per audit; it fetches the document and campaign brief exactly once, then runs BrandGuidelinesEvaluator.evaluate() once for the 3 deterministic categories (banned words, formatting/style, channel constraints).

- It builds one system prompt (prompt.py’s SYSTEM_PROMPT_TEMPLATE) asking a single model to judge all 4 LLM-judged categories — tone drift, information hierarchy, CTA cadence, readability — and instructs it, in prose, which of its two tools (create_suggestion or create_inline_comment) fits each category.

- **→ Problem:** That tool choice is a soft prompt instruction, not an enforced constraint — the model can, and per MULTI_AGENT_PLAN.md’s own framing sometimes does, call create_suggestion for a structural issue or create_inline_comment for a rewrite-worthy one.

- It runs one tool-calling loop (agent.py’s round-robin over max_tool_call_rounds) until the model stops requesting tools; \_dispatch_tool_call deduplicates repeat spans by the (tool_name, matched_text) key and aggregates every dispatched call into one AgentRunResult.

- **→ Problem:** That same single model context has to hold instructions and reasoning for two very different judgment types at once — whole-document, paragraph-ordering reasoning for Info Hierarchy/CTA Cadence, and local, sentence-level rewrite reasoning for Tone/Readability — raising the odds either one gets shortchanged.

See TEST_PLAN.md §1 for the full category-to-mechanism table this problem stems from, and MULTI_AGENT_PLAN.md’s “Current architecture (recap)” section for the fuller version of this recap.

# <span class="smallcaps">2. PROPOSED SOLUTION</span>

Split the single 4-category loop into two specialist agents — a Structural agent (Information Hierarchy + CTA Cadence, comment-tool-only) and a Line-Editor agent (Tone Drift + Readability, suggestion-tool-only) — each hard-restricted at the tool-schema level to the one tool that matches its categories.

**How it works:** A new plain-Python orchestrator builds the shared context once (same document/brief fetch, same evaluator.evaluate() call, unchanged), dispatches both sub-agents — sequentially in Phase 1, concurrently via ThreadPoolExecutor in Phase 2 — blocks until both return, then merges their output with reconcile_findings() into the same AgentRunResult shape v1 already returns. cli.py, http_api.py, and the Workspace Add-on’s submit/poll contract all stay unchanged.

## **2a. Value Proposition**

Copywriters and Marketing Leads who occasionally see a structural note land as a suggested rewrite — or a rewrite-worthy issue land as an unactionable comment — because v1’s single prompt only asks the model nicely to pick the right tool use the Multi-Agent Category Split to get a hard guarantee instead. Unlike v1, each specialist agent’s tool schema physically excludes the wrong tool for its categories — helping copywriters trust that every comment is a structural note and every suggestion is a one-click-acceptable rewrite, with zero regression to the categories v1 already covered well.

## **2b. Goals & Out-of-Scope**

### Goals

- Convert the comment-vs-suggestion boundary from a soft prompt instruction into a hard, tool-schema-level constraint — measured via the cross-category tool-misuse rate in 2c.

- Reduce single-context overload by giving each specialist agent only the categories and the one tool relevant to its judgment type, structural vs. line-level.

- Protect v1: all 3 existing Eval Card cases (docs/PRD.snapshot.md §3d) still pass, and cli.py/http_api.py/the Add-on’s submit-poll contract require zero changes.

### Out-of-Scope

- Phase 2 concurrency (ThreadPoolExecutor dispatch, the docs_client.py write lock) is deferred until Phase 1’s narrower-prompt hypothesis is validated against the Eval Card — not part of this improvement’s initial ship.

- A third reviewer/adjudicator agent that reconciles conflicting or redundant findings via an LLM (rather than the plain-Python reconcile_findings()) is deferred, and only worth building if the Eval Card comparison in 3d turns up a specific false-positive/noise problem — there’s no data yet that it’s needed.

- No new tools, no new API scopes, and no change to the deterministic evaluator’s 3 categories (evaluator.py, brand_guidelines.py/.json stay untouched).

## **2c. Measurable Outcomes**

| **Metric**                                                                                      | **How it’s measured**                                                                                                                                     | **Baseline**                                                                                                                          | **Target**                                                                                                            |
| ----------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| Cross-category tool-misuse rate (suggestion tool used for a structural category, or vice versa) | Manual diff of per-category finding coverage across TEST_PLAN.md’s 7 focused + kitchen-sink + control test documents, old single-agent path vs. new split | Not previously measured or logged in v1 — nonzero by construction, since v1’s tool choice is a soft instruction the model can violate | 0% — schema-level impossibility once each agent only has one tool                                                     |
| Per-category finding coverage on TEST_PLAN.md’s per-category trigger documents                  | Manual expected-vs-actual note per TEST_PLAN.md §5, one pass per sub-agent (Christina: Structural; Karl: Line-Editor)                                     | v1’s current coverage — not yet formally logged; this is the first formal comparison pass                                             | At least as good as v1, on the theory that a narrower per-category prompt improves focus rather than costing coverage |
| Eval Card pass rate (docs/PRD.snapshot.md §3d, 3 cases)                                         | Same 3 fixtures re-run against the new split before flipping the default                                                                                  | 3/3 passing on v1 (demoed Sat Jul 11)                                                                                                 | 3/3 passing — no regression                                                                                           |

# <span class="smallcaps">3. AGENT REQUIREMENTS</span>

## **3a. Tools**

| **Tool name**         | **Change**                | **What it does**                                                                                                                               | **API it calls**                                      | **Data it returns**                 |
| --------------------- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------- | ----------------------------------- |
| create_suggestion     | Modified (scope narrowed) | Unchanged Docs API call, but now only ever offered to the Line-Editor agent’s tool schema (Tone Drift + Readability) — never to Structural     | Google Docs API — batchUpdate (SuggestChangesRequest) | Target text range, replacement text |
| create_inline_comment | Modified (scope narrowed) | Unchanged Docs API call, but now only ever offered to the Structural agent’s tool schema (Info Hierarchy + CTA Cadence) — never to Line-Editor | Google Docs API — POST /documents/{id}/comments       | Comment body, linked text range     |

## **3b. System Prompt Changes**

**What’s changing and why:** prompt.py splits into prompts/shared.py (common assembly helpers, deterministic-findings block), prompts/structural.py (Christina), and prompts/line_editor.py (Karl). Each new template is a narrowed subset of today’s SYSTEM_PROMPT_TEMPLATE: Structural keeps the whole-document structure pass and only ever mentions create_inline_comment; Line-Editor keeps the paragraph-by-paragraph rewrite instructions and only ever mentions create_suggestion. Both still receive the same campaign brief, document body, and deterministic-findings block, unchanged.

[STRUCTURAL AGENT — prompts/structural.py, narrowed from prompt.py:34–88] “You are Verbatim’s Structural agent... First, audit the overall Document Structure... Second, audit each text block for \[only 2 of the original 7 categories\]: Information Hierarchy and CTA Cadence. When an issue is identified: [always call create_inline_comment with a constructive explanation — create_suggestion is not offered in this agent’s tool schema, so it cannot be called].” [LINE-EDITOR AGENT — prompts/line_editor.py, narrowed from prompt.py:34–88] “You are Verbatim’s Line-Editor agent... Audit each paragraph sequentially for \[only 2 of the original 7 categories\]: Tone Drift and Readability. When an issue is identified: [always call create_suggestion with the replacement text — create_inline_comment is not offered in this agent’s tool schema, so it cannot be called].” Both templates keep the shared termination-condition and category-tagging instructions verbatim from prompt.py, moved unchanged into prompts/shared.py.

## **3c. Blast Radius**

**Radius change:** Unchanged, arguably shrinks per agent: no new tools, no new API scopes, no new write surface — the Structural agent’s schema now literally excludes create_suggestion and the Line-Editor agent’s schema literally excludes create_inline_comment, which is strictly more contained than v1’s one agent holding both.

**Worst-case scenario:** Same worst case as v1 (docs/PRD.snapshot.md §3c): an agent posts an incorrect suggested edit or comment. Google Docs’ Suggest Changes mode keeps it advisory and human-reviewed — fully reversible. Phase 2 concurrency adds one new, contained worst case (see the failure-mode table below), gated behind its own concurrency test before it ships.

### New Failure Modes & Safeguards

| **Failure mode**                                                                                                                                                   | **Worst-case impact**                                                                                    | **Safeguard**                                                                                                                                                                                                                                                                  |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| reconcile_findings() mishandles or duplicates a finding when merging the Structural and Line-Editor agents’ output                                                 | Copywriter sees a duplicate comment/suggestion on the same span, or one agent’s finding silently dropped | Cross-agent dedup is a non-issue by construction — the dedup key is (tool_name, matched_text), and the two agents never share a tool name — plus reconcile_findings() gets its own contract tests written before either sub-agent is implemented (the Sat Jul 11 TDD red step) |
| (Phase 2 only) concurrent ThreadPoolExecutor dispatch races on GoogleDocsClient’s locate-range + batchUpdate + cache-clear sequence, which isn’t thread-safe today | A write is lost, corrupted, or applied against a stale cached document range                             | A threading.Lock around both GoogleDocsClient write methods, added specifically for Phase 2, plus a dedicated concurrency test before Phase 2 ships                                                                                                                            |
| A sub-agent’s narrower prompt misses a case v1’s single, broader prompt used to catch                                                                              | A real issue that v1 would have flagged goes unflagged in the new split                                  | Explicit validation gate before flipping the default: full Eval Card + TEST_PLAN.md fixture re-run against both paths (see 3d); run_agent_legacy is kept, not deleted, so rollback is a one-line default flip                                                                  |

## **3d. Eval Card**

**Regression check:** The 3 existing Eval Card cases in docs/PRD.snapshot.md §3d — golden (passive-voice blog intro → suggested rewrite), golden edge case (buried hook / late CTA → structural comment), and adversarial (missing brand_guidelines.json → warning comment) — all three must still pass, unchanged, against the new split before flipping run_agent()’s default off run_agent_legacy.

### New Cases

| **Case**                          | **Input**                                                                                                                                                                                | **Expected output — written before you run**                                                                                                                                                                                                                                   |
| --------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1 — Golden example (normal input) | A single document containing one clear line-level issue (a passive-voice sentence) and one clear structural issue (a buried hook, CTA in paragraph 1) at the same time.                  | The Line-Editor agent posts a create_suggestion for the passive-voice sentence; the Structural agent posts a create_inline_comment for the buried hook; reconcile_findings() merges both into one AgentRunResult with correct per-category counts and no cross-tool misfire.   |
| 2 — Golden example (edge case)    | A single sentence that plausibly trips both a structural and a line-level category at once — e.g. a CTA that is both premature (CTA Cadence) and written in passive voice (Readability). | The Structural agent flags the CTA-cadence problem via create_inline_comment; the Line-Editor agent independently flags the passive voice via create_suggestion on the same or overlapping span. Both findings land — one agent must not silently absorb the other’s category. |
| 3 — Adversarial input             | The Line-Editor agent returns zero tool calls on a document that clearly has readability issues (simulating a transient LLM failure or an empty response).                               | The orchestrator still returns a valid AgentRunResult built from whatever the Structural agent found; the run does not crash. The gap is visible as zero readability findings in category_counts, not silently dropped.                                                        |
