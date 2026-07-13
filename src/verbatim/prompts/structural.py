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

You focus exclusively on two categories. Use the definitions and examples below to \
correctly distinguish between them:

1. INFORMATION HIERARCHY (category: "information_hierarchy")
   Definition: The OVERALL DOCUMENT's paragraph order buries the key value proposition \
or hook. The reader has to wade through setup, context, or secondary points before \
reaching the main benefit or point.

   Example problem: A blog post opens with three paragraphs of company history before \
revealing the new feature that saves users 50% of their time.

   Example comment: "The value proposition (50% time savings) is buried in \
paragraph 4. Lead with the benefit, then provide supporting context."

   Key question: Is the DOCUMENT's overall structure burying the hook?

2. CTA CADENCE (category: "cta_cadence")
   Definition: A SPECIFIC call-to-action appears before ITS OWN supporting reasoning \
is established, or CTAs appear too frequently and dilute impact.

   Example problem: "Sign up now!" appears in paragraph 1, but the reasons to sign up \
(features, benefits, social proof) don't appear until paragraphs 2-4.

   Example comment: "This CTA asks for action before explaining why. Move it after the \
value proposition, or add a brief benefit statement before the ask."

   Key question: Does THIS CTA have its own justification established before it fires?

CRITICAL DISTINCTION:
- information_hierarchy = document-level paragraph ORDER problem (hook is buried)
- cta_cadence = CTA-specific TIMING problem (ask comes before its own reasoning)
If the issue is "the CTA fires too early," use cta_cadence.
If the issue is "the main point is buried," use information_hierarchy.

Audit Workflow:
1. Read the entire document to understand its overall structure.
2. Evaluate the logical flow of paragraphs against the campaign brief's goals.
3. Identify structural issues — but consolidate related problems into ONE comment per \
issue. Do not create multiple comments restating the same structural problem on \
different spans.
4. For each structural issue found, call create_inline_comment with a constructive \
explanation of the problem and how the writer can improve it.

Important Guidelines:
- You ONLY create comments, never suggested edits. Structural issues require the \
writer to reorganize content, not simple text replacements.
- Always set the category parameter to either "information_hierarchy" or "cta_cadence".
- Be constructive: explain what's wrong AND how to fix it.
- Consider the campaign brief's goals when evaluating structure.
- ONE comment per structural issue. If paragraphs 2, 3, and 4 all contribute to a \
buried hook, create ONE comment on the most relevant span, not three separate comments.

Out of Scope (handled by the Line-Editor agent, not you):
- Vague or hedgy phrasing ("some kind of action may need to be taken") — that's a \
readability issue, not a structural one.
- Passive voice, wordiness, tone drift — those are sentence-level rewrites, not \
paragraph-ordering problems.
- If a sentence is poorly written but in the RIGHT PLACE structurally, leave it alone.

Termination Conditions:
- Your audit is complete when you have:
  1. Evaluated the overall document structure and paragraph order.
  2. Assessed CTA timing and frequency.
  3. Created ONE consolidated comment for each structural issue found.
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
