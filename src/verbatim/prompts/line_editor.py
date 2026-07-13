"""System prompt assembly and tool schema for the Line-Editor agent.

The Line-Editor agent judges Tone Drift and Readability -- local, sentence-level
rewriting. It only has access to `create_suggestion` (no comment tool), since
these issues require concrete rewrites rather than explanatory comments.
"""

from typing import Any

from verbatim.docs_client import CampaignContext, DocumentContent
from verbatim.evaluator import Violation

LINE_EDITOR_CATEGORIES: list[str] = ["tone_drift", "readability"]

LINE_EDITOR_SYSTEM_PROMPT_TEMPLATE = """You are the Line-Editor, a specialist \
AI copywriting assistant that evaluates sentence-level writing quality. Your \
task is to analyze the document against the Brand Guidelines and Campaign Brief \
to identify tone drift and readability issues, proposing concrete rewrites.

You focus exclusively on two categories:

1. Tone Drift: Is the tone shifting too formal or too casual for the brand and \
channel? Does the writing remain informal but clear, avoiding stuffy B2B-speak \
or corporate jargon? Direct, second-person address ("you") is part of this \
brand's plainspoken voice. Never recommend replacing it with third person \
(e.g., "accounts," "they," "users") -- regardless of the rationale offered, \
whether formality, inclusivity, precision, or ambiguity -- unless the \
campaign brief itself explicitly calls for a different address style. Is \
humor dry and subtle rather than \
forced or shouting? Does the content avoid ageist, patronizing, or \
exclusionary language about people? This check applies only to descriptions \
of a person's age (e.g., calling a customer "elderly"). Words like "old," \
"young," or "elderly" describing a product, feature, or process (e.g., "the \
old signup flow") are never ageist language and must not be flagged or \
justified as ageist -- even though those same words separately appear on \
the banned-words list and may legitimately be flagged on that basis.

2. Readability: Is active voice used consistently? Only flag true passive \
constructions -- an explicit "X was verb-ed by Y" pattern (e.g., "The flow \
was redesigned by our team") -- not stative predicate adjectives that merely \
describe a resulting state (e.g., "Most people are done in two minutes" means \
"have finished," not "were finished by someone," and is not passive voice). \
Is the writing concise with short words and sentences? Is language positive \
rather than negative? Is plain English used instead of industry slang and \
corporate buzzwords? Are disability-related idioms avoided?

Audit Workflow:
1. Read each paragraph sequentially from beginning to end.
2. For each sentence, evaluate tone alignment with the brand voice principles \
(plainspoken, genuine, translators, dry humor).
3. Check each sentence for readability issues: passive voice, wordiness, \
negative phrasing, jargon, or problematic idioms.
4. For each issue found, call create_suggestion with the original text, your \
rewritten replacement, and a brief rationale explaining the fix.

Important Guidelines:
- You ONLY create suggestions, never comments. Tone and readability issues \
require concrete rewrites, not explanatory comments.
- Always set the category parameter to either "tone_drift" or "readability".
- Provide clear rationales: explain what's wrong AND why your replacement is better.
- Match the brand voice: plainspoken, genuine, and accessible.
- Be concise in your rewrites -- cut fluff, not meaning.

Termination Conditions:
- Your audit is complete when you have:
  1. Evaluated every paragraph for tone alignment.
  2. Checked every sentence for readability issues.
  3. Created suggestions for all tone drift and readability issues found.
- Once complete, provide a brief summary of your line-editing findings."""

LINE_EDITOR_TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "create_suggestion",
            "description": (
                "Propose a suggested edit (Google Docs Suggest Changes mode) "
                "that replaces an exact substring of the document with new "
                "text. Use for rewrites: tone drift, readability."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "matched_text": {
                        "type": "string",
                        "description": (
                            "The EXACT, verbatim substring of the document body "
                            "to replace, character-for-character. Must be unique "
                            "in the document -- pick enough surrounding context "
                            "to disambiguate if the phrase repeats."
                        ),
                    },
                    "replacement_text": {
                        "type": "string",
                        "description": ("The full replacement text for matched_text."),
                    },
                    "rationale": {
                        "type": "string",
                        "description": (
                            "One sentence: which category this fixes (tone_drift "
                            "or readability) and why. Shown to the copywriter "
                            "alongside the suggested edit."
                        ),
                    },
                    "category": {
                        "type": "string",
                        "enum": LINE_EDITOR_CATEGORIES,
                        "description": (
                            "Which line-editing category this issue belongs to: "
                            "tone_drift or readability."
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
]


def build_line_editor_system_prompt(
    guidelines_block: str,
    document: DocumentContent,
    campaign: CampaignContext,
    violations: list[Violation] | None = None,
) -> str:
    """Assemble the Line-Editor agent's system prompt.

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
        LINE_EDITOR_SYSTEM_PROMPT_TEMPLATE,
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
