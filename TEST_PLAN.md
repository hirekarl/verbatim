# Test plan: campaign briefs, test documents, and running them against the live app

A practical guide for Karl and Christina to build a reusable set of test campaign briefs and draft documents, and exercise them against Verbatim — locally via the CLI, and against the live Cloud Run backend / Workspace Add-on. This complements (doesn't replace) the demo-document goal in `TODO.md`; that's a single showcase doc, this is a repeatable regression suite.

## 1. Why this doc exists

Verbatim evaluates copy across 7 categories, split across two very different mechanisms (see `TODO.md`'s hybrid-architecture decision):

| Category                       | Judged by                      | Source of truth                                                         |
| ------------------------------ | ------------------------------ | ----------------------------------------------------------------------- |
| `tone_drift`                   | LLM (system prompt)            | `src/verbatim/prompt.py` + `brand_guidelines.json`'s `rules.tone_drift` |
| `information_hierarchy`        | LLM                            | `rules.information_hierarchy`                                           |
| `cta_cadence`                  | LLM                            | `rules.cta_cadence`                                                     |
| `readability`                  | LLM                            | `rules.readability`                                                     |
| `formatting_and_style`         | Deterministic (`evaluator.py`) | `rules.formatting_and_style`                                            |
| `channel_constraints`          | Deterministic (`evaluator.py`) | `rules.channel_constraints`                                             |
| `banned_words_and_competitors` | Deterministic (`evaluator.py`) | `rules.banned_words_and_competitors`                                    |

The deterministic categories are exact and testable the same way every time — a given input either trips a regex/rule or it doesn't. The LLM-judged categories are not deterministic: the model may phrase feedback differently between runs, or occasionally miss something a human would catch. **Testing the LLM categories means checking for reasonable coverage, not exact output matching.** Keep that distinction in mind throughout — it changes what "the test passed" means per category.

Ownership carries over from `README.md`'s split: Christina owns `evaluator.py`'s three deterministic categories and their test documents; Karl owns the LLM-judged categories, the agent loop, and the infrastructure paths (CLI/HTTP/Add-on) documents get run through. Either of you can and should write test *documents* for any category — the ownership split is about who fixes a bug found, not who's allowed to find one.

## 2. Building a test campaign brief

`GoogleDocsClient.get_campaign_context()` doesn't enforce a schema on the brief — it's just injected as raw title + body text into the system prompt (`prompt.py`). But the PRD (`docs/PRD.snapshot.md`) is specific about what a brief should give the agent to reason against: **audience persona, channel, CTA requirements, and campaign goals.** Without those, `information_hierarchy` and `cta_cadence` judgments have nothing concrete to check the draft against.

Recommended brief structure (as a real Google Doc, with real headings so `get_campaign_context`'s heading extraction has something to parse):

```text
# [Campaign Name] Brief

## Target Audience
Who this is for — persona, pain points, what they already know.

## Primary Channel
email | blog | twitter | facebook | instagram
(Match this to the --channel / dropdown value you'll test with.)

## Campaign Goal
What success looks like for this specific piece of copy.

## Key Message
The one thing the reader should walk away understanding.

## Call-to-Action Requirements
What action the reader should take, and any constraints
(single CTA only, must appear after the value prop is established, etc.)
```

One reusable "master" brief covering a generic SaaS product launch is enough for most testing — you don't need a new brief per test document. Make a second brief only if you want to test that the agent actually uses brief content (e.g., a brief stating "single CTA only" against a draft with three CTAs should trigger `cta_cadence`, brief-informed).

## 3. Building test documents

### 3.1 Per-category trigger examples

Copy-paste starting points. Each is written to isolate its category as much as possible, but don't be surprised when one sentence trips more than one category — some rules deliberately overlap (e.g., `tone_drift`'s ageist-language rule and the `young`/`old`/`elderly` entries in `banned_words`). That overlap is by design, not a bug — the deterministic evaluator's findings are an extra signal the LLM can cite (per `TODO.md`'s architecture note), so a well-designed test document will often light up two categories for the same sentence. Note that when it happens; don't file it as a false positive.

**`tone_drift`** (LLM-judged):

- "Freddie says, 'Welcome aboard! We can't wait to see what you build.'" — Freddie doesn't speak, only smiles/winks/high-fives.
- "Make sure the email goes out to your audience once it has confirmed its subscription." — audience referred to as "it," not "they."
- "This template works great for younger users who love bold colors." — ageist descriptor (also trips `banned_words`, see above).

**`information_hierarchy`** (LLM-judged):

- Open a document with the CTA/offer before any context: "Sign up now and save 20%!" as literally the first line, with the actual explanation of what's being offered three paragraphs later.
- An H1 followed directly by an H3, skipping H2.
- Five sequential steps written as one run-on paragraph instead of a numbered list.

**`cta_cadence`** (LLM-judged):

- Competing CTAs in one short piece: "Sign up here! Or check out our blog! Or follow us on Twitter! Or download our app!"
- A CTA as the very first sentence, before any value has been established.

**`readability`** (LLM-judged):

- Passive voice: "The account was logged into by Marti." (the PRD's own example — should become "Marti logged into the account.")
- Negative phrasing: "You can't get a donut if you don't stand in line."
- Jargon: "Optimize your holistic customer journey through omnichannel synergy."
- Disability idiom: "That excuse is pretty lame."

**`formatting_and_style`** (deterministic — `evaluator.py`, category `formatting_and_style`):

- Missing Oxford comma: "We support email, SMS and push notifications."
- Semicolon: "Sign up today; it only takes a minute."
- Double exclamation: "Don't miss out!!"
- Ampersand outside a brand name: "Save time & money with automation."
- Gendered term: "Contact your account waitress for help." (should be "server").
- "Hey guys, check out our new feature!"
- Two spaces after a sentence-ending period (hard to see — literally type two spaces).

**`channel_constraints`** (deterministic — `evaluator.py`, category `channel_constraints`; **only checked when a channel is passed**):

- `twitter`: any text over 280 characters.
- `facebook`: 3+ sentences, e.g. "Our sale starts today. Prices are 50% off. Don't miss it. Shop now before it's gone."
- `instagram`: 2+ sentences, e.g. "New arrivals are here. Shop the collection today."
- `email`: an all-caps subject line ("HUGE SALE THIS WEEK ONLY"), or a too-short/generic one ("Update"), or one over ~60 characters ending mid-word.

**`banned_words_and_competitors`** (deterministic — `evaluator.py`, category `banned_words_and_competitors`; also covers standardized spellings):

- "Let's leverage this funnel to incentivize activation and crush it like a true rockstar ninja." — packs in `leverage`/`funnel`/`incentivize`/`activation`/`crushing it`/`rockstar`/`ninja` in one sentence.
- "Visit our Website or check the drop down menu for e-mail preferences." — `Website` (should be lowercase), `drop down` (should be hyphenated as a noun), `e-mail` (should be unhyphenated `email`) all violate `standardized_spellings`.

### 3.2 The suggested document set

Build these once, reuse them for every regression pass:

1. **Seven focused documents** — one per category above, each built mostly from that category's examples, so a clean run should show violations concentrated in one place. Useful for isolating a regression to a specific rule.
1. **One "kitchen sink" document** — a single realistic-looking marketing draft that intentionally trips all 7 categories at once (this can double as the demo document from `TODO.md`'s original ask). Useful as an end-to-end smoke test after any change to `evaluator.py`, `prompt.py`, or `agent.py`.
1. **One clean control document** — well-formed, on-brand copy with no intentional violations. If this document ever comes back with findings, that's a false positive worth investigating on its own, separate from whether the trigger documents work.

Keep all of these (plus your master brief) in one shared Drive folder, and record each document's ID somewhere durable (a pinned doc, a comment on this file, whatever's easiest) so re-running a pass after a code change is a five-minute task, not a rebuild-from-scratch task.

## 4. Running a test

### 4.1 CLI — the fast loop

The primary way to iterate on `evaluator.py` or `prompt.py` changes locally:

```sh
uv run verbatim <document_id> <brief_id> --channel <channel>
```

Requires local OAuth setup (`client_secret.json`/`token.json`, see `README.md`'s CLI usage section) already done for both of you. This is the only path that doesn't depend on the Cloud Run deployment or the Add-on at all — use it first when chasing down an evaluator or prompt bug.

### 4.2 The Add-on sidebar — the only real end-to-end test

Once Script Properties are set (`BACKEND_URL`, `BACKEND_SHARED_SECRET`, optional `DEFAULT_BRIEF_ID` — see `addon/README.md`), open a test document, run the sidebar's "Run Verbatim Audit" with a brief ID and channel from your test set. This is the only path that exercises the full deployed system: `ScriptApp.getOAuthToken()` → `token_validator.py`'s tokeninfo check → the real Cloud Run container → `run_agent()`.

### 4.3 Direct HTTP against Cloud Run — auth-path testing only

```sh
curl -X POST https://verbatim-backend-75857425003.us-east4.run.app/audit \
  -H "Authorization: Bearer <token>" \
  -H "X-Backend-Shared-Secret: <secret>" \
  -H "Content-Type: application/json" \
  -d '{"document_id": "...", "brief_id": "...", "channel": "email"}'
```

**Caveat, so you don't waste time on this**: `token_validator.py` checks that the bearer token's audience matches `GOOGLE_OAUTH_CLIENT_ID` — the Apps Script project's own OAuth client. A token from the CLI's local OAuth flow (a different, separate OAuth client) will fail that check with a clean 401, not because anything's broken, but because it's the wrong client's token. Use `curl` to verify the *rejection* paths (missing/wrong shared secret → 401, malformed body → 422, missing bearer token → 401) — for the actual success path with real audit results, use the Add-on (§4.2).

## 5. Recording results

For each document in your test set, keep a simple expected-vs-actual note (a comment on the test doc itself is fine — no separate tracking system needed):

- **Deterministic categories**: did the exact violations you built in get flagged? Any you didn't expect (false positive)? Any you built in that didn't get flagged (false negative)?
- **LLM categories**: did the agent's comments/suggestions land in the right general area? Don't expect word-for-word matches to the rule text — judge whether a human reviewer would agree the feedback is on-target.

File a GitHub issue for anything that's actually wrong, same as any other bug — tag it against `evaluator.py` (Christina's domain) or `prompt.py`/`agent.py` (Karl's domain) based on which one is actually responsible, using the deterministic-vs-LLM split in §1 to figure out which.

## 6. When to re-run

Re-run the full document set (or at minimum the categories touched) after:

- Any change to `src/verbatim/evaluator.py`, `brand_guidelines.json`, or `prompt.py`
- Any change to `src/verbatim/agent.py`'s tool-dispatch logic
- Before merging a PR that touches any of the above
- Periodically against the live Cloud Run deployment, since that's a separately-versioned artifact from whatever's on `main` locally (redeployed manually, not on every merge — see `docs/workspace-addon-migration.md` §6)
