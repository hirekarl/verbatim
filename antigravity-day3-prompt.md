# Prompt for Antigravity: Verbatim Day 3 (Karl's tasks)

Copy everything below the line into Antigravity as the task prompt.

______________________________________________________________________

## Context

You're working in **Verbatim**, an AI agent that audits marketing copy in Google Docs against brand guidelines and a campaign brief. It's a Python 3.12 project managed entirely by `uv` (no manual venv/pip), with hatchling as the build backend. Read `CLAUDE.md` and `TODO.md` at the repo root first — `TODO.md` has the full sprint plan and file-ownership split; `CLAUDE.md` has stack/tooling conventions.

**The demo is Saturday morning.** Today (in the sprint plan) is Day 3, the last feature day before a Friday rehearsal buffer. Feature work needs to be substantially complete by end of day.

### Two people work this repo — stay in your lane

Karl (that's you, for this task) owns infra/CI/tooling and the Docs API/agent side. Christina owns the deterministic rule evaluator. **Do not touch these files** — they're Christina's Day 3 scope (shaking out evaluator false positives/negatives, assembling the demo doc):

- `src/verbatim/evaluator.py`
- `tests/test_evaluator.py`
- `src/verbatim/brand_guidelines.py` / `src/verbatim/data/brand_guidelines.json` (read from these freely, don't edit them)

You may need to *call* `BrandGuidelinesEvaluator` and read its `Violation` dataclass shape (in `evaluator.py`) to wire its output in, but don't modify evaluator logic itself. If you find an evaluator bug, note it rather than fixing it directly — that's Christina's file.

### What's already built (Days 1–2, done)

- `src/verbatim/docs_client.py` — `GoogleDocsClient` with `get_document_content(document_id)`, `get_campaign_context(brief_id)`, `create_suggestion(document_id, matched_text, replacement_text)`, and `create_inline_comment(document_id, matched_text, comment)`. Auth via `GoogleDocsClient.from_local_credentials(include_drive=True)` (needs `client_secret.json` at repo root, write scopes for suggestion/comment support — see README "Google Docs API setup").
- `src/verbatim/llm_client.py` — `OpenRouterClient.from_env(model)` (reads `OPENROUTER_API_KEY` from env/`.env`), `complete_chat(messages, tools)` returning a `ChatCompletionResult` with `.content`, `.tool_calls` (list of `ToolCall(id, name, arguments)`), `.raw_assistant_message`.
- `src/verbatim/prompt.py` — `SYSTEM_PROMPT_TEMPLATE` (System Prompt v0, covers all 7 audit categories), `TOOL_SCHEMAS` (function schemas for `create_suggestion`/`create_inline_comment`), and `build_system_prompt(guidelines_block, document, campaign)` which joins the template with `BrandGuidelines.format_for_llm_prompt()` output, the campaign brief body, and the document body.
- `src/verbatim/agent.py` — `run_agent(docs_client, llm_client, document_id, brief_id, brand_guidelines, target_channel=None, max_tool_call_rounds=20)`. Runs a single-pass tool-calling conversation loop: fetches document + campaign brief once, builds the system prompt, then loops `complete_chat` → dispatch any `create_suggestion`/`create_inline_comment` tool calls against `docs_client` → feed results back as tool messages — until the model stops calling tools or `max_tool_call_rounds` is hit. Returns an `AgentRunResult(suggestions_made, comments_made, transcript, stopped_due_to_max_rounds)`.
- `src/verbatim/evaluator.py` — `BrandGuidelinesEvaluator(guidelines_path=None)` with `.evaluate(text, channel=None) -> list[Violation]`. `Violation` has `category`, `severity` (`"error"|"warning"|"info"`), `message`, `matched_text`, `suggestion: str | None`. Covers the mechanically-checkable categories: banned words, standardized spellings, formatting/style (ampersands, Oxford comma, semicolons, exclamation points, double spaces, "click here" links), and channel constraints.

All of this is merged to `main`. 129 tests pass, 97% coverage. Run `uv run pytest` to confirm before you start.

### Architecture decision already made (don't relitigate)

`evaluator.py` stays deterministic/regex-based and only covers mechanically-checkable categories. The four subjective categories (tone drift, information hierarchy, CTA cadence, readability) are judged by the LLM via the system prompt. **The evaluator's violations are meant to be an extra signal the LLM agent can cite — not something the agent reproduces with regex, and not a separate posting path.** Concretely: run the evaluator over the document body text before/alongside the agent loop, and fold its violations into the system prompt (or an early user/system message) as a pre-computed findings list, so the model can corroborate, cite, or act on them via the same `create_suggestion`/`create_inline_comment` tool calls — don't have the CLI post evaluator violations directly to Docs itself, since that would bypass the LLM's judgment about phrasing/relevance and double up with whatever the model independently finds.

## Your task (Day 3, Karl's scope)

> Build the single orchestration entrypoint/CLI that ties evaluator output + LLM output + comment/suggestion posting into one on-demand run; run it end to end against a real Google Doc + campaign brief and fix Docs API/ orchestration bugs as they surface.

Concretely:

1. **Wire evaluator output into the agent loop as an extra signal.** In `agent.py` (or a small new module if that reads cleaner — your call), run `BrandGuidelinesEvaluator(...).evaluate(document.body_text, channel=target_channel)` before the LLM conversation starts, and pass the resulting violations into `build_system_prompt` (extend its signature) so they're rendered into the system prompt as a labeled "Deterministic findings" section the model can reference. Keep `evaluator.py` itself untouched — only consume its public `evaluate`/`Violation` API from `prompt.py`/`agent.py`.
1. **Build a CLI entrypoint** (e.g. `src/verbatim/cli.py`, wired up as a `[project.scripts]` entry in `pyproject.toml`, or a runnable `python -m verbatim` — pick whichever is more idiomatic for this repo and is consistent with existing module layout). It should take a document ID, a campaign brief ID, and an optional target channel, construct `GoogleDocsClient.from_local_credentials(include_drive=True)` and `OpenRouterClient.from_env(model)`, load `BrandGuidelines`, call `run_agent(...)`, and print a run summary (suggestions made, comments made, whether it hit the round cap).
1. **Follow TDD**: write failing tests first (`tests/test_cli.py` and updates to `tests/test_agent.py`/`tests/test_prompt.py` for the evaluator wiring), then implement. Mock `GoogleDocsClient`/`OpenRouterClient`/Google API calls in tests — don't hit real network/API in the test suite.
1. **Run it end to end against a real Google Doc + campaign brief.** You'll need a `client_secret.json` (OAuth client secret from Google Cloud, see README "Google Docs API setup") and `OPENROUTER_API_KEY` set (see README "Agent (OpenRouter) setup" / `.env.example`) — ask the user for these or for a real document ID / campaign brief ID to test against if you don't have them. Fix any Docs API/orchestration bugs that surface during this real run (auth edge cases, rate limits, malformed tool-call args, etc.) — this is explicitly part of the task, not a stretch goal.
1. Everything must pass the existing quality gates before you're done:
   - `uv run pytest` (coverage must stay ≥ 90%, currently 97%)
   - `uv run ruff check .` and `uv run ruff format .`
   - `uv run mypy` (strict mode — no untyped defs, no incomplete defs)
   - `uv run pre-commit run --all-files`

## Explicitly out of scope for you right now

- GitHub governance scaffolding (`release.yml`, `dependabot.yml`, issue/PR templates, `CONTRIBUTING.md`, etc.) — deferred post-demo per `TODO.md`.
- Session caching / rate-limit resilience for the Docs API, and a graceful in-doc warning if `brand_guidelines.json` is missing/corrupt — both deferred post-demo per `TODO.md`.
- Anything in `evaluator.py` / `tests/test_evaluator.py` — Christina's file, even if you spot a bug in it. Note it instead.

## Commit conventions

- **Conventional Commits** format: `feat: ...`, `fix: ...`, `chore: ...`, `docs: ...`. Use `uv run cz commit` to build one interactively if unsure.
- **Never add a Claude/Anthropic `Co-Authored-By` trailer to commits in this repo** — a commit-msg hook blocks it.
- Prefer several focused commits over one giant one (that's the existing pattern in this repo's history — check `git log --oneline` for style).

## When you're done

Report: what you built, what you ran it against (real doc/brief IDs or "couldn't get real credentials, tested with mocks only — here's what's still unverified"), any bugs you hit and fixed, and current test/coverage numbers.
