# Verbatim

Verbatim is an AI agent that reviews draft marketing copy inside Google Docs against a brand's voice, style, and structural guidelines and a campaign brief. It runs on-demand when a copywriter starts a check, then flags mechanical issues — tone drift, information hierarchy, CTA cadence, readability, formatting/style, channel constraints, and banned words — as inline comments and suggested edits directly in the document.

## Table of contents

- [Current sprint](#current-sprint)
- [Prerequisites](#prerequisites)
- [macOS setup](#macos-setup)
- [Windows setup](#windows-setup)
- [Clone & bootstrap](#clone--bootstrap)
- [Common commands](#common-commands)
- [Development workflow](#development-workflow)
- [Google Docs API setup](#google-docs-api-setup)
- [Project structure](#project-structure)
- [Versioning](#versioning)
- [License](#license)

## Current sprint

See [`TODO.md`](TODO.md) for the active sprint plan — the current deadline, the day-by-day work split between Karl and Christina, and which files/components each of them (and their coding agents) should be working in.

## Prerequisites

This project is managed end-to-end by [`uv`](https://docs.astral.sh/uv/), which installs and pins the right Python version for you — you do not need to install Python separately. You do need `git` and `uv` themselves; setup steps for each OS are below.

## macOS setup

1. Install [Homebrew](https://brew.sh) if you don't already have it.

1. Install git:

   ```sh
   brew install git
   ```

1. Install `uv`:

   ```sh
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

1. Restart your terminal, then install the project's Python version:

   ```sh
   uv python install 3.12
   ```

## Windows setup

1. Install git via [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/):

   ```powershell
   winget install --id Git.Git -e --source winget
   ```

1. Install `uv` (official PowerShell installer):

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

1. Restart your terminal, then install the project's Python version:

   ```powershell
   uv python install 3.12
   ```

## Clone & bootstrap

```sh
git clone <repo-url>
cd verbatim
uv sync
uv run pre-commit install
```

`uv sync` creates a `.venv` and installs every dependency pinned in `uv.lock`. `uv run pre-commit install` wires up the local git hooks (code quality checks on every commit, commit message format checks on every commit message).

## Common commands

Run everything through `uv run` — there's no separate virtualenv to activate.

| Command                             | What it does                                                        |
| ----------------------------------- | ------------------------------------------------------------------- |
| `uv run pytest`                     | Run the test suite with coverage                                    |
| `uv run ruff check .`               | Lint the code                                                       |
| `uv run ruff format .`              | Auto-format the code                                                |
| `uv run mypy`                       | Type-check the code                                                 |
| `uv run pre-commit run --all-files` | Run every pre-commit hook against the whole repo                    |
| `uv run cz commit`                  | Build a Conventional Commits-formatted commit message interactively |

## Development workflow

This project follows **test-driven development**: write a failing test before writing the implementation code that makes it pass. Commit messages (and PR titles once this repo is on GitHub) follow the [Conventional Commits](https://www.conventionalcommits.org/) format (`feat: ...`, `fix: ...`, `chore: ...`, `docs: ...`) — the `commitizen` pre-commit hook enforces this locally, and `uv run cz commit` will build a properly formatted message for you.

## Google Docs API setup

`src/verbatim/docs_client.py` reads documents via the Google Docs API using an
OAuth installed-app flow (not a service account — the copywriter checks their own
currently-open document, so there's nothing to pre-share). One-time setup to run it
locally:

1. Create or select a project in the
   [Google Cloud Console](https://console.cloud.google.com/).
2. Enable the **Google Docs API** for that project (the Drive API will be needed
   later, for Day 2's inline comments — not required yet).
3. Configure the OAuth consent screen as **External**, in **Testing** mode, and add
   your own Google account as a test user.
4. Create an OAuth Client ID of type **Desktop app** — this matters, since the
   installed-app flow's local redirect handling
   (`InstalledAppFlow.run_local_server`) only works with this client type, not "Web
   application."
5. Download the client ID's JSON and save it as `client_secret.json` at the repo
   root (already git-ignored — never commit it).
6. Run anything that calls `GoogleDocsClient.from_local_credentials()`. The first
   run opens a browser consent prompt; afterward, a `token.json` is cached locally
   (also git-ignored) so you won't be prompted again until it expires or the
   requested scopes change.

See `.knowledge-base/google-docs-api/` and `.knowledge-base/google-drive-api/` for
decomposed reference docs on the underlying REST APIs.

## Project structure

```text
verbatim/
├── .github/
│   ├── CODEOWNERS
│   └── workflows/
│       └── ci.yml          # lint, type-check, and test on every PR and push to main
├── src/verbatim/           # the installable package
│   ├── __init__.py
│   ├── py.typed
│   ├── evaluator.py        # BrandGuidelinesEvaluator: checks text against brand rules
│   ├── brand_guidelines.py # loader for brand_guidelines.json
│   ├── docs_client.py      # Google Docs API auth + read-side tool wrappers
│   └── data/
│       └── brand_guidelines.json  # brand voice/style rules fixture
├── tests/                  # pytest suite
│   └── test_docs_client.py
├── .knowledge-base/        # decomposed reference docs for external APIs (map-and-leaf)
├── docs/                   # PRD and research reference docs (.docx + Markdown snapshots)
├── BOOTSTRAPPING.md        # scaffolding rationale and remaining setup work
├── CLAUDE.md               # project context for AI coding agents
├── LICENSE                 # MIT
├── pyproject.toml          # project metadata + all tool configuration
└── uv.lock                 # pinned dependency versions
```

## Versioning

Versioning will become fully automatic (semver bump + changelog + GitHub Release on every merge to `main`) once this repo's CI/CD is set up — see `BOOTSTRAPPING.md` for that plan. Until then, there's no manual version bump step to worry about.

## License

[MIT](LICENSE).
