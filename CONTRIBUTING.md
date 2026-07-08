# Contributing to Verbatim

We want to keep Verbatim's codebase reliable, well-tested, and clean. Please follow these guidelines when contributing.

## Development Workflow & TDD

We practice **Test-Driven Development (TDD)** on this project.

- Always write a failing test in the `tests/` directory before writing the implementation code that makes it pass.
- Keep test coverage at or above **90%**. The CI pipeline will reject pull requests that drop below this threshold.

## Branch Naming

Use descriptive branch names with category prefixes:

- `feat/feature-name` for new features
- `fix/bug-name` for bug fixes
- `chore/task-name` for setup or config changes
- `docs/doc-name` for documentation updates

## Commit Messages

We enforce **Conventional Commits** for all commits on this repository. This allows our release workflow to automatically manage semantic version bumps and generate changelogs.

Format: `<type>(<scope>): <description>`

Common types:

- `feat`: A new feature (bumps minor version pre-1.0)
- `fix`: A bug fix (bumps patch version)
- `docs`: Documentation only changes
- `style`: Changes that do not affect the meaning of the code (white-space, formatting, etc.)
- `refactor`: A code change that neither fixes a bug nor adds a feature
- `test`: Adding missing tests or correcting existing tests
- `chore`: Changes to the build process or auxiliary tools/libraries

Example:

```bash
git commit -m "feat(evaluator): add character count limits check for channels"
```

You can use `uv run cz commit` to run an interactive prompt that helps you craft a valid commit message.

## Pull Requests

1. **Required PR Title Format**: PR titles *must* follow the Conventional Commits format. This is critical because we squash-merge PRs, and the PR title becomes the squash commit message on `main`.

1. **Review & CI Requirements**:

   - At least 1 approving review from another repository CODEOWNER is required before merging.
   - The CI Quality Gates and PR Title Lint must pass completely.

1. **Local Validation**: Before pushing your branch, run the complete local check suite:

   ```bash
   uv run pytest
   uv run ruff check .
   uv run ruff format --check .
   uv run mypy src
   uv run pre-commit run --all-files
   ```

## Code of Conduct

By participating, you are expected to uphold the \[Code of Conduct\](file:///Users/karlsaintlucy/documents/pursuit/l2/verbatim/CODE_OF_CONDUCT.md).
