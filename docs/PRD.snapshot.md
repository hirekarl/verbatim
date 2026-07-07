> **Snapshot notice:** Markdown snapshot of `Verbatim PRD.docx`, generated 2026-07-07 via `pandoc -f docx -t gfm`. The docx remains the authoritative source — don't hand-edit this file; regenerate it with the same command if the docx changes.

**Verbatim**

*Product Requirements Document: Agent Build*

**Agent name:** Verbatim

**Owner(s):** Karl Johnson and Christina Ruiz

**Date:** July 6, 2026

# <span class="smallcaps">1. PROBLEM</span>

Marketing Leads and Content Managers experience a critical review bottleneck in the copywriting pipeline because brand guidelines exist as static documents (PDFs/wikis) that require manual, subjective self-policing by writers, resulting in 20% to 30% of editing time spent on repetitive mechanical corrections and delays of hours or days before drafts are ready for approval.

### Supporting Context (optional)

- **Repetitive Micro-Decisions:** Marketing Leads must repeatedly police the same mechanical issues (Tone Drift, Info Hierarchy, CTA Cadence, Readability, Style Mechanics, Channel Constraints, and Banned Words) on every single block of copy.

- **Operational Burden:** Marketing Leads spend 20% to 30% of their total editing time policing these mechanical corrections rather than refining structural narrative or messaging strategy.

- **Static Guidelines:** Static PDFs/wikis lead to subjective interpretations, meaning writers inconsistently implement style guidelines.

## **1a. Opportunity**

Create an automated review checker that flags these 7 categories of micro-decisions during the drafting stage, recovering 20% to 30% of the Marketing Lead's review time and speeding up the approval pipeline.

### Size of the Opportunity

- **Time Savings:** 20% to 30% reduction in total editing time spent on mechanical reviews by the Marketing Lead.

- **Velocity:** Accelerating the transition from initial draft to final approval by eliminating manual review loops.

- **Supporting Analysis:** [<u>Marketing Role Research Notes: Automated Copy Review</u>](https://docs.google.com/document/d/1I-PdEyZfzk0-ihQsBB94WZ-xg5lkBoK20lpsPVEWyPM/edit?usp=sharing)

## **1b. Users & Needs**

**Primary user(s):** Marketing Lead / Content Manager (managing 5–10 active campaigns; wants to guard brand integrity and scale content production without getting bogged down in line-by-line mechanical edits)

**Secondary users:** Internal Copywriters and Freelancers (wanting to draft copy and quickly check compliance with style guidelines)

### Key User Needs

As a Marketing Lead, I need copy to be pre-screened for mechanical compliance (tone, hierarchy, style, CTAs, constraints) before it reaches my desk, so that I can focus my time on high-level strategy and final sign-off.

As a Copywriter, I need to check my drafts against brand guidelines directly inside my writing workspace (Google Docs) before submission, so that I can self-correct immediately and avoid back-and-forth review loops.

# <span class="smallcaps">2. PROPOSED SOLUTION</span>

Verbatim is an AI agent for Marketing Leads and Copywriters that evaluates draft copy against brand voice, structural hierarchy, and style guidelines. It runs on-demand when a copywriter initiates a check in Google Docs, uses its tools to ingest the campaign brief and evaluate the text against a brand voice configuration and style rules, and delivers inline comments flagging discrepancies alongside suggested edits to the Copywriter. The Copywriter then reviews the suggestions, applies the fixes, and submits a pre-screened draft to the Marketing Lead for final strategic sign-off.

## **2a. Value Proposition**

Marketing Leads and Copywriters who struggle with slow draft approval cycles caused by manual style guide reviews use Verbatim, an AI agent that intercepts drafts inside Google Docs and audits them against brand guidelines. Unlike generic AI writing assistants, it evaluates copy contextually against specific campaign briefs and brand models, generating inline comments and suggested edits, helping them cut review turnaround times and publish on-brand content faster.

## **2b. Top 3 MVP Value Props**

**The Vitamin (must-have baseline):** Every paragraph is scanned for the 7 key style and brand guidelines, ensuring no mechanical violations slip through to the reviewer.

**The Painkiller (solves the core pain):** Feedback is delivered inline inside Google Docs as comments and suggested edits, eliminating manual review loops.

**The Steroid (the magic moment):** Verbatim generates high-quality alternative rewrites inline for any flagged issue, allowing copywriters to resolve warnings with a single click in Google Docs' Suggest Changes mode.

## **2c. Success Metrics**

| **Goal**                                   | **Signal**                                                           | **Metric**                                                      | **Target**                                                                     |
| ------------------------------------------ | -------------------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Reduce review overhead for Marketing Leads | Marketing Leads spend less time editing drafts for basic compliance  | Average editing time spent per draft by the Marketing Lead      | < 10% of total editing time spent on mechanical corrections (down from 20-30%) |
| Accelerate review loops                    | Copywriters submit cleaner first drafts that require fewer revisions | Average number of review rounds per asset before final approval | ≤ 1 review round per asset                                                     |
| Trustworthy suggestions                    | Copywriters accept the agent's suggested rewrites                    | Acceptance rate of inline suggestions by copywriters            | ≥ 70% acceptance rate                                                          |

# <span class="smallcaps">3. AGENT REQUIREMENTS</span>

## **3a. Tools**

| **Tool name**         | **What it does**                                                                            | **API it calls**                                      | **Data it returns**                                                             |
| --------------------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------- |
| get_document_content  | Pulls the active document's text and structural headers.                                    | Google Docs API — GET /documents/{id}                 | Document title, body text, structural headers                                   |
| get_campaign_context  | Retrieves target audience, channel constraints, and goals from the campaign brief doc.      | Google Docs API — GET /documents/{brief_id}           | Audience persona, channel (email/blog/social), CTA requirements, campaign goals |
| get_brand_guidelines  | Retrieves brand voice guidelines, style mechanics, and banned words list from a local file. | Read local config — brand_guidelines.json             | Brand voice definition, casing rules, Oxford comma rule, banned words list      |
| create_suggestion     | Proposes inline suggested edits (adds/deletes) directly in the active doc.                  | Google Docs API — batchUpdate (SuggestChangesRequest) | Target text range, replacement text                                             |
| create_inline_comment | Places explanatory feedback comments linked to specific text ranges.                        | Google Docs API — POST /documents/{id}/comments       | Comment body (rationale for the flag), linked text range                        |

## **3b. System Prompt v0**

You are Verbatim, an AI copywriting assistant built to review drafts in Google Docs. Your task is to evaluate the document against the Brand Guidelines and the Campaign Brief to identify mechanical, stylistic, and structural issues.

First, check the overall Document Structure:

1. Audit the higher-order information hierarchy. Does the paragraph order make logical sense based on the campaign brief (e.g., introduction/hook -> problem/opportunity -> solution -> CTA)?
1. If paragraphs are out of order, use create_inline_comment to flag the structural issue and explain the logical flow.

Second, audit each text block / paragraph for these 7 categories:

- Tone Drift: Tone shifting too formal or too casual for the brand and channel.
- Information Hierarchy: The hook being buried instead of leading with the value proposition.
- CTA Cadence: Premature or poorly timed CTAs.
- Readability: Passive voice, heavy jargon, or run-on sentences.
- Formatting: Violating casing, punctuation, or brand spelling rules (e.g., Oxford commas).
- Channel Constraints: Exceeding character counts or length guidelines for the targeted channel.
- Banned Words: Using prohibited phrases or competitor names.

When an issue is identified:

- For rewrites (Tone, Readability, Formatting, Banned Words): Call create_suggestion with the replacement text.
- For structural issues (Paragraph Order, CTA Cadence, Information Hierarchy): Call create_inline_comment with a constructive explanation of the issue and how the writer can improve it.

## **3c. Blast Radius**

**Worst-case scenario:** The agent suggests incorrect style changes or deletes valid text in Google Docs. Since the agent runs in Google Docs' Suggest Changes mode, the changes are advisory and must be accepted by a human. The impact is minimal (10-15 minutes of the copywriter's time to reject the changes) and fully reversible.

### Failure Modes & Safeguards

| **Failure mode**                                                  | **Worst-case impact**                                                  | **Safeguard**                                                                                                  |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| Agent gives incorrect rewrite suggestions.                        | Writer wastes time rejecting changes; potential confusion.             | Suggest Changes Mode: The copywriter must review and manually accept any suggested edit; changes are not live. |
| Guidelines fixture (brand_guidelines.json) is missing or corrupt. | Agent cannot run or runs on generic rules, producing inaccurate flags. | Graceful Fallback: Agent stops and warns the writer that the brand guidelines fixture could not be loaded.     |
| Google Docs API rate limits are exceeded during document scan.    | Scanning fails mid-document, leading to incomplete reviews.            | Local Session Cache: Guidelines are cached; user is warned of partial scan completion.                         |

## **3d. Eval Card**

<table>
<colgroup>
<col style="width: 23%" />
<col style="width: 36%" />
<col style="width: 40%" />
</colgroup>
<thead>
<tr>
<th><strong>Case</strong></th>
<th><strong>Input</strong></th>
<th><strong>Expected output — written before you run</strong></th>
</tr>
<tr>
<th>1 — Golden example (normal input)</th>
<th>Input: A draft blog intro containing passive voice: 'The new feature
is launched by our team to help users.'<br />
Brief: B2B blog post, helpful/active tone.</th>
<th>Expected: A suggested edit replacing the text with: 'Today, we
launch our new feature to help you...' and a comment flagging
'Readability (passive voice).'</th>
</tr>
<tr>
<th>2 — Golden example (edge case)</th>
<th>Input: A draft blog where the CTA is the first paragraph and the
hook is in paragraph 3.<br />
Brief: B2B blog post.</th>
<th>Expected: An inline comment flagging 'Document Structure' and
recommending that the hook be moved to paragraph 1 and the CTA moved to
the end.</th>
</tr>
<tr>
<th>3 — Adversarial input</th>
<th>Input: The local brand_guidelines.json file is missing.</th>
<th>Expected: A warning comment at the top of the document: 'Verbatim
could not load the brand guidelines fixture (brand_guidelines.json).
Please check your configuration.'</th>
</tr>
</thead>
<tbody>
</tbody>
</table>
