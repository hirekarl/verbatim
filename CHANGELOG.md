## v0.12.2 (2026-07-13)

### Fix

- **addon**: whitelist Cloud Run's newer hash-based backend URL (#60)

## v0.12.1 (2026-07-13)

### Fix

- **addon**: add urlFetchWhitelist for Cloud Run backend to manifest (#59)

## v0.12.0 (2026-07-13)

### Feat

- implement multi-agent audit split (Structural + Line-Editor agents) (#46)

## v0.11.2 (2026-07-12)

### Fix

- **evaluator**: add Website capitalization and expand guys pattern (#50)

## v0.11.1 (2026-07-09)

### Fix

- **hooks**: update gitleaks to v8.30.1 for Go 1.24 compatibility (#43)

## v0.11.0 (2026-07-09)

### Feat

- **addon**: richer copy, category breakdown, and real icon (#42)

## v0.10.1 (2026-07-09)

### Fix

- **addon**: fix bugs found during first live end-to-end Add-on test (#41)

## v0.10.0 (2026-07-09)

### Feat

- **evaluator**: add title/sentence case checks for headings and document titles (#40)

## v0.9.0 (2026-07-08)

### Feat

- **addon**: make target channel a dropdown instead of hardcoded (#37)

## v0.8.0 (2026-07-08)

### Feat

- **addon**: make brief ID dynamic and record live Cloud Run/Apps Script setup (#36)

## v0.7.1 (2026-07-08)

### Fix

- **addon**: correct appsscript.json Editor Add-on manifest schema (#35)

## v0.7.0 (2026-07-08)

### Feat

- **http-api**: add shared-secret header and lock down API docs (#32)

## v0.6.0 (2026-07-08)

### Feat

- **infra**: containerize the HTTP backend for Cloud Run (#31)

## v0.5.0 (2026-07-08)

### Feat

- **addon**: build Editor Add-on shell (manifest + CardService + UrlFetchApp) (#30)

## v0.4.0 (2026-07-08)

### Feat

- **http-api**: validate inbound Add-on bearer tokens before trusting them (#29)

## v0.3.0 (2026-07-08)

### Feat

- **http-api**: add HTTP entrypoint wrapping run_agent(), retain CLI (#28)

## v0.2.0 (2026-07-08)

### Feat

- **docs-client**: add from_access_token() auth path for hosted use (#27)

## v0.1.0 (2026-07-08)

### Feat

- **infra**: implement post-demo backlog (#9)
- add remaining formatting/style checks (#7)
- integrate brand evaluator, implement CLI, resolve OpenRouter budget limit, and fix duplicate replacements
- Google Docs API auth + read-side document/campaign-brief tools (#4)
- add email channel constraint check
- add channel constraints check for Twitter, Facebook, and Instagram
- add standardized spellings check
- add four formatting/style checks (semicolons, exclamation points, spaces, links)
- add brand guidelines evaluator with core violation detection
- add CI workflow and MIT license (#1)
- bootstrap Python tooling, pre-commit, and onboarding docs
- add verbatim agent prd, brand guidelines fixture, and python parser

### Fix

- detect non-breaking spaces in double-space check
- dedupe overlapping click-here matches and tighten "here" boundary
- correct oxford comma sentence-boundary and clause-starter heuristics
- stop suppressing banned words that lead a hyphenated compound
- preserve apostrophes when tokenizing ampersand brand names
- address all code review findings from Karl's PR #2 review
- pin pre-commit ruff/mypy hooks to the project's uv-resolved versions
- prevent Oxford comma false positives on two-item conjunctions
- run pre-commit mypy hook unscoped to match pyproject.toml
- pin pre-commit ruff/mypy hooks to the project's uv-resolved versions

### Refactor

- address code review nice-to-have improvements
