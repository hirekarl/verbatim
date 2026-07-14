# Multi-agent Eval Card fixtures

The three cases in `docs/multi-agent-prd.snapshot.md` §3d, as concrete documents. These are new fixtures for the multi-agent split's own validation gate — separate from `docs/PRD.snapshot.md` §3d's original single-agent Eval Card and from the comment-triggering pairs in `comment-triggers-expected-output.md`. Run each pair against both `run_agent_legacy` and the new split before flipping the default (Tue Jul 14, per `TODO.md`).

Each pair is standalone — paste the brief into one Google Doc, the draft into another, grant Suggester/Commenter access on the draft, and run:

```sh
uv run verbatim <draft_doc_id> <brief_doc_id> --channel <channel>
```

## 1. `campaign-brief-golden.txt` / `draft-copy-golden.txt` — channel: none needed

Golden example, normal input. Paragraph 1 is a bare CTA ("Log in and try the new onboarding today") that fires before the actual value prop — the nine-to-three-step cut, under two minutes — shows up in paragraphs 2–3. That's the structural issue: information hierarchy, buried hook. Paragraph 3 also has one isolated, cleanly-rewritable passive-voice sentence: "The entire flow was redesigned by our product team..." That's the line-level issue.

Expect the Line-Editor agent to post a `create_suggestion` on the passive-voice sentence, and the Structural agent to post a `create_inline_comment` on the opening CTA paragraph. `reconcile_findings()` should merge both into one `AgentRunResult` with `category_counts` showing exactly one hit each for `readability` and `information_hierarchy`, no cross-tool misfire (no comment where a suggestion belongs or vice versa).

## 2. `campaign-brief-golden-edge.txt` / `draft-copy-golden-edge.txt` — channel: email

Golden example, edge case. The opening sentence — "Two-factor authentication should be turned on by every account today." — trips two categories at once on the same span: it's a premature CTA (fires before the warning-banner/compromise-risk reasoning that follows), which is CTA cadence, and it's passive voice, which is readability.

Expect the Structural agent to flag the CTA-cadence problem via `create_inline_comment` on that sentence, and the Line-Editor agent to independently flag the passive voice via `create_suggestion` on the same or an overlapping span. Both findings should land — this is the case that catches one agent silently absorbing the other's category instead of both firing independently.

## 3. `campaign-brief-adversarial.txt` / `draft-copy-adversarial.txt` — channel: blog

Adversarial input. The draft is written to have obvious, dense readability problems throughout paragraphs 1–2 (passive, hedgy, vague — "it has been noticed," "may need to be taken," "in a general sense") plus one clean structural issue: a bare "Upgrade your plan." CTA dropped in paragraph 3, before the limit and pricing land in paragraph 4.

This fixture can't produce the adversarial condition on its own — the PRD scenario is the Line-Editor agent returning zero tool calls entirely (simulating a transient LLM failure or empty response), which has to be forced rather than triggered by document content. Use this doc for two separate runs:

- A normal run, to confirm the Line-Editor agent's readability findings look reasonable against genuinely bad prose (this is also the Tue Jul 14 validation input for `prompts/line_editor.py`).
- A mocked run with the Line-Editor agent's tool-calling loop forced to return zero tool calls (patch `AnthropicClient`/the loop's response at the `orchestrator` boundary), to confirm the orchestrator still returns a valid `AgentRunResult` built from whatever the Structural agent found (the paragraph-3 CTA comment), the run doesn't crash, and the gap shows up as zero `readability` findings in `category_counts` rather than being silently dropped.

## Rehearsal note

These are validation fixtures for the Tue Jul 14 go/no-go call on flipping `run_agent()`'s default off `run_agent_legacy`, not demo-day assets — they don't need to survive into `PRESENTATION_PLAN.md`'s rehearsal flow unless one turns out to double well as a Fri Jul 17 trigger doc.
