"""System prompt assembly and tool schemas for the Verbatim audit agent."""

from typing import Any

from verbatim.docs_client import CampaignContext, DocumentContent
from verbatim.evaluator import Violation
from verbatim.prompts.shared import CATEGORIES as CATEGORIES

# Display labels for CATEGORIES, matching addon/Code.gs's CATEGORY_LABELS --
# kept in sync by hand since Apps Script and Python can't share a module.
CATEGORY_LABELS: dict[str, str] = {
    "tone_drift": "Tone Drift",
    "information_hierarchy": "Information Hierarchy",
    "cta_cadence": "CTA Cadence",
    "readability": "Readability",
    "formatting_and_style": "Formatting & Style",
    "channel_constraints": "Channel Constraints",
    "banned_words_and_competitors": "Banned Words & Competitors",
    "uncategorized": "Uncategorized",
}

SYSTEM_PROMPT_TEMPLATE = """You are Verbatim, an AI copywriting assistant built to \
review drafts in Google Docs. Your task is to evaluate the document against the \
Brand Guidelines and the Campaign Brief to identify mechanical, stylistic, and \
structural issues.

First, check the overall Document Structure:

1. Audit the higher-order information hierarchy. Does the paragraph order make \
logical sense based on the campaign brief (e.g., introduction/hook -> \
problem/opportunity -> solution -> CTA)?
2. If paragraphs are out of order, use create_inline_comment to flag the \
structural issue and explain the logical flow.

Second, audit each text block / paragraph for these 7 categories:

- Tone Drift: Tone shifting too formal or too casual for the brand and channel.
- Information Hierarchy: The hook being buried instead of leading with the value \
proposition.
- CTA Cadence: Premature or poorly timed CTAs.
- Readability: Passive voice, heavy jargon, or run-on sentences.
- Formatting: Violating casing, punctuation, or brand spelling rules (e.g., \
Oxford commas).
- Channel Constraints: Exceeding character counts or length guidelines for the \
targeted channel.
- Banned Words: Using prohibited phrases or competitor names.

When an issue is identified:

- For rewrites (Tone, Readability, Formatting, Banned Words): Call \
create_suggestion with the replacement text.
- For structural issues (Paragraph Order, CTA Cadence, Information Hierarchy): \
Call create_inline_comment with a constructive explanation of the issue and how \
the writer can improve it.
- Always set the category parameter on every tool call to the single one of \
the 7 categories above that issue belongs to.

Audit Workflow & Sequence:
1. First, analyze the overall document structure (paragraph order, logical flow, \
CTA timing) and create any structural inline comments using create_inline_comment \
before proposing paragraph-specific edits.
2. Second, audit each paragraph sequentially from the beginning to the end \
of the document, checking them against the 7 category criteria. Propose \
inline suggestions or comments as you locate them. You may request multiple \
tool calls in parallel.

Termination Conditions:
- Your audit is complete when:
  1. You have fully reviewed the overall document structure.
  2. You have evaluated every paragraph against all 7 categories.
  3. You have made all necessary tool calls to suggest rewrites or flag \
structural issues.
- Once those conditions are met and you have no further suggestions or \
comments, do NOT call any more tools.
- Provide a brief, professional summary of your audit findings in your final \
text response to signal that you are finished."""

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "create_suggestion",
            "description": (
                "Propose a suggested edit (Google Docs Suggest Changes mode) that "
                "replaces an exact substring of the document with new text. Use "
                "for rewrites: tone drift, readability, formatting/style, banned "
                "words."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "matched_text": {
                        "type": "string",
                        "description": (
                            "The EXACT, verbatim substring of the document body "
                            "to replace, character-for-character. Must be unique "
                            "in the document - pick enough surrounding context "
                            "to disambiguate if the phrase repeats."
                        ),
                    },
                    "replacement_text": {
                        "type": "string",
                        "description": "The full replacement text for matched_text.",
                    },
                    "rationale": {
                        "type": "string",
                        "description": (
                            "One sentence: which of the 7 categories this fixes "
                            "and why. Shown to the copywriter alongside the "
                            "suggested edit."
                        ),
                    },
                    "category": {
                        "type": "string",
                        "enum": CATEGORIES,
                        "description": (
                            "Which of the 7 audit categories this issue belongs to."
                        ),
                    },
                },
                "required": [
                    "matched_text",
                    "replacement_text",
                    "rationale",
                    "category",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_inline_comment",
            "description": (
                "Attach an explanatory comment to an exact substring of the "
                "document without proposing a specific rewrite. Use for "
                "structural issues: paragraph order, CTA cadence, information "
                "hierarchy."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "matched_text": {
                        "type": "string",
                        "description": (
                            "The EXACT, verbatim substring this comment refers "
                            "to. Must be unique in the document."
                        ),
                    },
                    "comment": {
                        "type": "string",
                        "description": (
                            "Constructive explanation shown to the copywriter: "
                            "what the issue is and how to improve it."
                        ),
                    },
                    "category": {
                        "type": "string",
                        "enum": CATEGORIES,
                        "description": (
                            "Which of the 7 audit categories this issue belongs to."
                        ),
                    },
                },
                "required": ["matched_text", "comment", "category"],
            },
        },
    },
]


def build_system_prompt(
    guidelines_block: str,
    document: DocumentContent,
    campaign: CampaignContext,
    violations: list[Violation] | None = None,
) -> str:
    """Assemble the full system prompt for one audit run.

    Args:
        guidelines_block: The pre-rendered output of
            ``BrandGuidelines.format_for_llm_prompt()``.
        document: The parsed content of the document being audited.
        campaign: The parsed content of the campaign brief.
        violations: Optional list of deterministic violations found in the
            document.

    Returns:
        The persona/process instructions, brand guidelines, campaign brief,
        document body, and optional deterministic findings, joined into a
        single system prompt string.
    """
    sections = [
        SYSTEM_PROMPT_TEMPLATE,
        guidelines_block,
        f"=== CAMPAIGN BRIEF: {campaign.title} ===\n{campaign.body_text}",
        f"=== DOCUMENT UNDER AUDIT: {document.title} ===\n{document.body_text}",
    ]
    if violations:
        findings_lines = ["=== DETERMINISTIC FINDINGS ==="]
        for v in violations:
            line = (
                f"- [{v.category}] {v.severity.upper()}: {v.message} "
                f"(matched: '{v.matched_text}')"
            )
            if v.suggestion:
                line += f" -> Suggestion: '{v.suggestion}'"
            findings_lines.append(line)
        sections.append("\n".join(findings_lines))

    return "\n\n".join(sections)
