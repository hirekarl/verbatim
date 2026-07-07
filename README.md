# Verbatim

Verbatim is an AI agent that reviews draft marketing copy inside Google Docs against a
brand's voice, style, and structural guidelines and a campaign brief. It runs on-demand
when a copywriter starts a check, then flags mechanical issues — tone drift,
information hierarchy, CTA cadence, readability, formatting/style, channel constraints,
and banned words — as inline comments and suggested edits directly in the document.

## Table of contents

- [Prerequisites](#prerequisites)
- [macOS setup](#macos-setup)
- [Windows setup](#windows-setup)
- [Clone & bootstrap](#clone--bootstrap)
- [Common commands](#common-commands)
- [Development workflow](#development-workflow)
- [Project structure](#project-structure)
- [Versioning](#versioning)
- [License](#license)
- [Security](#security)

## Prerequisites

This project is managed end-to-end by [`uv`](https://docs.astral.sh/uv/), which
installs and pins the right Python version for you — you do not need to install Python
separately. You do need `git` and `uv` themselves; setup steps for each OS are below.

## macOS setup

1. Install [Homebrew](https://brew.sh) if you don't already have it.
2. Install git:

   ```sh
   brew install git
   ```

3. Install `uv`:

   ```sh
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

4. Restart your terminal, then install the project's Python version:

   ```sh
   uv python install 3.12
   ```

## Windows setup

1. Install git via [winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/):

   ```powershell
   winget install --id Git.Git -e --source winget
   ```

2. Install `uv` (official PowerShell installer):

   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```

3. Restart your terminal, then install the project's Python version:

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

`uv sync` creates a `.venv` and installs every dependency pinned in `uv.lock`.
`uv run pre-commit install` wires up the local git hooks (code quality checks on every
commit, commit message format checks on every commit message).

## Common commands

Run everything through `uv run` — there's no separate virtualenv to activate.

| Command | What it does |
| --- | --- |
| `uv run pytest` | Run the test suite with coverage |
| `uv run ruff check .` | Lint the code |
| `uv run ruff format .` | Auto-format the code |
| `uv run mypy src` | Type-check the code |
| `uv run pre-commit run --all-files` | Run every pre-commit hook against the whole repo |
| `uv run cz commit` | Build a Conventional Commits-formatted commit message interactively |

## Development workflow

This project follows **test-driven development**: write a failing test before writing
the implementation code that makes it pass. Commit messages (and PR titles once this
repo is on GitHub) follow the
[Conventional Commits](https://www.conventionalcommits.org/) format (`feat: ...`,
`fix: ...`, `chore: ...`, `docs: ...`) — the `commitizen` pre-commit hook enforces this
locally, and `uv run cz commit` will build a properly formatted message for you.

## Project structure

```text
verbatim/
├── src/verbatim/           # the installable package
│   ├── __init__.py
│   └── py.typed
├── tests/                  # pytest suite
├── brand_guidelines.json   # brand voice/style rules fixture
├── brand_guidelines.py     # loader for brand_guidelines.json
├── BOOTSTRAPPING.md        # scaffolding rationale and remaining setup work
├── pyproject.toml          # project metadata + all tool configuration
└── uv.lock                 # pinned dependency versions
```

## Versioning

Versioning will become fully automatic (semver bump + changelog + GitHub Release on
every merge to `main`) once this repo's CI/CD is set up — see `BOOTSTRAPPING.md` for
that plan. Until then, there's no manual version bump step to worry about.

## License

MIT.

## Security

To report a security concern, email <[email redacted]>.
