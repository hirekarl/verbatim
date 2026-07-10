# Demo expected output

**This is a backstage rehearsal reference, not a live script.** The live demo runs through the Workspace Add-on sidebar (see `PRESENTATION_PLAN.md` slide 7), and the model's half of the output isn't deterministic — don't recite this table or the LLM bullets below as if they're guaranteed. Use this to sanity-check a rehearsal run and to know roughly what to expect, then narrate whatever the actual run produces on Saturday.

CLI equivalent, useful for offstage spot-checks: `uv run verbatim <draft_doc_id> <brief_doc_id> --channel email`

Input docs: paste `campaign-brief.txt` into one Google Doc, `draft-copy.txt` into another (first line of the draft is the email subject line), grant the demo Google account Suggester/Commenter access on the draft, then swap in the real doc IDs above. Both files are seeded on purpose so every one of the 7 categories fires at least once.

## Evaluator (Christina's side — deterministic, fires first)

| Category                | Matched text                                                                         | Why                                                 |
| ----------------------- | ------------------------------------------------------------------------------------ | --------------------------------------------------- |
| Banned words            | crazy, insane, leverage, funnel, rockstar, thought leader, ninja, incentivize, young | 9 separate hits from the banned-words list          |
| Banned words (spelling) | e-mail                                                                               | should be `email`                                   |
| Formatting/style        | `&` in "tips & tricks"                                                               | ampersand outside an allowed brand name             |
| Formatting/style        | "templates, automation and analytics"                                                | missing Oxford comma                                |
| Formatting/style        | `;` after "your stack"                                                               | semicolons aren't used                              |
| Formatting/style        | `!!` after "too late"                                                                | more than one exclamation point                     |
| Formatting/style        | double space after "guys,"                                                           | should be a single space                            |
| Formatting/style        | "Click here to turn on..."                                                           | non-descriptive link text                           |
| Formatting/style        | `"tips & tricks",`                                                                   | comma should sit inside the closing quote           |
| Formatting/style        | "Hey guys,"                                                                          | not gender-neutral                                  |
| Formatting/style        | "Mail Chimp"                                                                         | should be one word, "Mailchimp"                     |
| Formatting/style        | "5000"                                                                               | needs a comma: 5,000                                |
| Formatting/style        | "3pm"                                                                                | needs a space + lowercase: 3 pm                     |
| Channel constraints     | subject line "HUGE UPDATE INSIDE"                                                    | email subject should be sentence case, not all caps |

~20 individual regex hits — call out a handful live rather than reading all of them.

## LLM (Karl's side — judgment calls, fires second)

- **Tone drift**: the copy calls the audience/list "it" twice ("it just needs the right nudge... gives it exactly that") instead of "they/them"; the tone reads as forced/shouty rather than the brief's plainspoken, dry-humor voice.
- **Information hierarchy**: opens with a bare CTA before any context; the actual value prop (time saved) and the July 15 price-change deadline — the whole point of the brief — don't show up until the second and fourth paragraphs; the feature list is a run-on clause instead of a structured list.
- **CTA cadence**: three separate CTAs in one short newsletter (the opening line, the "click here" in the middle, "don't wait" at the close) — the brief calls for one focused CTA, and the first one fires before any value is established.
- **Readability**: passive, hedgy phrasing ("was built to leverage"); negative framing ("won't last," "once it's gone, it's gone," "don't wait"); vague filler ("serious results," "focus on strategy instead of grunt work").

Exact model wording will vary run to run — these are the themes to expect, not a literal transcript.

## Backup if the live run is flaky

Record one full successful run ahead of time (`asciinema` or screen recording) and keep it ready to play instead. Take this during Friday's rehearsal pass, per `TODO.md`'s buffer-day plan.
