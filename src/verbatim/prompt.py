"""System prompt assembly and tool schemas for the Verbatim audit agent."""

from typing import Any

from verbatim.docs_client import CampaignContext, DocumentContent
from verbatim.evaluator import Violation

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
the writer can improve it."""

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
                            "and why. For logging only, not shown to the "
                            "copywriter."
                        ),
                    },
                },
                "required": ["matched_text", "replacement_text", "rationale"],
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
                },
                "required": ["matched_text", "comment"],
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
