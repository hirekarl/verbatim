# Verbatim

An AI agent that audits marketing copy in Google Docs against brand guidelines and a campaign brief. It runs on-demand when a copywriter starts a check, reads the document and its campaign brief via the Google Docs API, and evaluates the text across 7 categories — tone drift, information hierarchy, CTA cadence, readability, formatting/style, channel constraints, and banned words. Issues surface as inline comments (structural problems) or suggested edits (rewrites), which the copywriter accepts or rejects in Google Docs before sending the draft on for strategic sign-off. Full detail: `Verbatim PRD.docx` and `Marketing Role Research Notes_ Automated Copy Review.docx`.

**Before starting any work, read `TODO.md`.** It has the current sprint's day-by-day plan and, critically, which files/components are Karl's vs. Christina's to touch — staying inside that split is what keeps the two of them from colliding on the same files.

## Stack & tooling

Python 3.12, fully managed by `uv` (no manual venv/pip). Build backend: hatchling. Quality gates: ruff (strict lint + format), mypy (strict), pytest/pytest-cov (`--cov-fail-under=90`), pre-commit, commitizen. Always invoke tools through `uv run ...` — see the command table in `README.md`, which this mirrors:

- `uv run pytest`
- `uv run ruff check .` / `uv run ruff format .`
- `uv run mypy`
- `uv run pre-commit run --all-files`
- `uv run cz commit`

## Repo layout

- `src/verbatim/` — the installable package (currently just version plumbing).
- `tests/` — pytest suite.
- `brand_guidelines.json` / `brand_guidelines.py` — brand voice/style rules fixture and loader. These intentionally stay at the repo root for now, not `src/verbatim/`; that migration is deliberately deferred (see BOOTSTRAPPING.md's Follow-up section). Because of that, both are excluded from `mypy` (`files = ["src", "tests"]` in `pyproject.toml`) and `ruff` (`extend-exclude` in `pyproject.toml`) — don't be surprised that lint/type-check gates don't touch them, and don't pre-emptively move or reformat them as part of unrelated work.
- `BOOTSTRAPPING.md` — the full scaffolding runbook and rationale (branch protection, CI/CD, versioning, governance). Local tooling (this package, pre-commit, ruff/mypy config) is done; GitHub-side setup (repo creation, branch protection, CI/CD workflows, CODEOWNERS, issue/PR templates) is still outstanding — check there before assuming any of it exists.
- `TODO.md` — the live sprint plan: current deadline, the day-by-day Karl/Christina work split, file/component ownership, and what's been deliberately deferred. Check it before picking up new work so you don't duplicate or collide with the other person's in-flight work.

## Process norms

- **TDD**: write a failing test before the implementation code that makes it pass.
- **Conventional Commits** for commit messages (`feat:`, `fix:`, `chore:`, `docs:`) — enforced locally by the commitizen pre-commit hook; `uv run cz commit` builds one interactively.
- Never add a Claude/Anthropic `Co-Authored-By` trailer to commits in this repo.
- Don't regenerate `.gitignore` — the existing macOS/Windows/Python composite is correct as-is.
- Markdown files are linted by `markdownlint-cli2` (config in `.markdownlint-cli2.jsonc`; line-length (MD013) is disabled since these are prose docs, not hard-wrapped).
