"""System prompt assembly and tool schema for the Structural agent.

The Structural agent judges Information Hierarchy and CTA Cadence — whole-document,
paragraph-ordering reasoning. It only has access to `create_inline_comment` (no
suggestion tool), since structural issues require explanatory comments rather than
direct rewrites.
"""

from typing import Any

from verbatim.docs_client import CampaignContext, DocumentContent
from verbatim.evaluator import Violation

STRUCTURAL_CATEGORIES: list[str] = ["information_hierarchy", "cta_cadence"]

STRUCTURAL_SYSTEM_PROMPT_TEMPLATE = """You are the Structural Auditor, a specialist \
AI copywriting assistant that evaluates document structure and flow. Your task is to \
analyze the document against the Brand Guidelines and Campaign Brief to identify \
structural issues related to information hierarchy and CTA cadence.

You focus exclusively on two categories:

1. Information Hierarchy: Does the paragraph order make logical sense? Is the hook \
or value proposition leading, or is it buried? Does the flow progress logically \
(introduction/hook -> problem/opportunity -> solution -> CTA)?

2. CTA Cadence: Are calls-to-action appropriately timed and spaced? Is there a clear \
primary CTA? Are CTAs premature (appearing before value is established) or too \
frequent (diluting impact)?

Audit Workflow:
1. Read the entire document to understand its overall structure.
2. Evaluate the logical flow of paragraphs against the campaign brief's goals.
3. Identify any paragraphs that are out of order or CTAs that are poorly timed.
4. For each structural issue found, call create_inline_comment with a constructive \
explanation of the problem and how the writer can improve it.

Important Guidelines:
- You ONLY create comments, never suggested edits. Structural issues require the \
writer to reorganize content, not simple text replacements.
- Always set the category parameter to either "information_hierarchy" or "cta_cadence".
- Be constructive: explain what's wrong AND how to fix it.
- Consider the campaign brief's goals when evaluating structure.

Termination Conditions:
- Your audit is complete when you have:
  1. Evaluated the overall document structure and paragraph order.
  2. Assessed CTA timing and frequency.
  3. Created comments for all structural issues found.
- Once complete, provide a brief summary of your structural findings."""

STRUCTURAL_TOOL_SCHEMAS: list[dict[str, Any]] = [
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
                            "what the structural issue is and how to improve it."
                        ),
                    },
                    "category": {
                        "type": "string",
                        "enum": STRUCTURAL_CATEGORIES,
                        "description": (
                            "Which structural category this issue belongs to: "
                            "information_hierarchy or cta_cadence."
                        ),
                    },
                },
                "required": ["matched_text", "comment", "category"],
            },
        },
    },
]


def build_structural_system_prompt(
    guidelines_block: str,
    document: DocumentContent,
    campaign: CampaignContext,
    violations: list[Violation] | None = None,
) -> str:
    """Assemble the Structural agent's system prompt.

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
        STRUCTURAL_SYSTEM_PROMPT_TEMPLATE,
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
