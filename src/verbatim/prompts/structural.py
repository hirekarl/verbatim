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

BEFORE YOU CREATE ANY COMMENT, verify it is a TRUE STRUCTURAL issue:
- Structural = paragraph ORDER or PLACEMENT problem
- NOT structural = sentence-level writing quality (passive voice, vague phrasing, \
wordiness, tone) — those belong to the Line-Editor agent, not you
- If your rationale mentions "passive," "vague," "hedgy," or "unclear phrasing," \
STOP — that is NOT a structural issue

You focus exclusively on two categories. Use the DECISION TREE below:

=== DECISION TREE: Which category? ===

Ask yourself: "What needs to move to fix this?"

Option A: The VALUE PROPOSITION or HOOK needs to move earlier
→ Use "information_hierarchy"
→ The fix is: restructure paragraphs so benefits/value LEAD
→ Example: Doc opens with "Try our new feature!" but the actual benefit \
(saves 2 hours/week) is buried in paragraph 3. The VALUE is buried.

Option B: A specific CTA needs to move later (value prop is clear, ask is misplaced)
→ Use "cta_cadence"
→ The fix is: move THIS CTA after its justification, or reduce CTA frequency
→ Example: Doc explains the benefit in paragraph 1, then has 3 "Sign up now!" CTAs \
in paragraphs 2, 3, and 4. The value is clear; CTAs are too frequent.

=== KEY INSIGHT ===
If a document OPENS with a CTA but the VALUE PROPOSITION is buried later, the problem \
is information_hierarchy (buried hook), NOT cta_cadence. The CTA isn't "too early" — \
the VALUE is "too late." The fix is to lead with value, not to move the CTA.

=== CATEGORY DEFINITIONS ===

1. INFORMATION HIERARCHY (category: "information_hierarchy")
   The document's paragraph order buries the key value proposition or hook.

   Symptom: Reader must wade through setup before reaching the main benefit.
   Fix: Restructure so the hook/value LEADS.

   Example: "Log in and try X today. [para 2: history] [para 3: finally, the benefit]"
   → Problem: Value is buried. Tag: information_hierarchy.

2. CTA CADENCE (category: "cta_cadence")
   CTAs are too frequent, or a CTA fires before its SPECIFIC justification exists.

   Symptom: Multiple CTAs dilute impact, OR a CTA appears in an otherwise \
well-structured doc before its own reasoning is established.
   Fix: Reduce frequency or move the specific CTA.

   Example: "Here's why X is great. Sign up! More reasons. Sign up! Even more. Sign up!"
   → Problem: CTA overload. Tag: cta_cadence.

Audit Workflow:
1. Read the entire document to understand its overall structure.
2. Evaluate the logical flow of paragraphs against the campaign brief's goals.
3. For each potential issue, apply the DECISION TREE above to pick the right category.
4. Before creating a comment, ask: "Is this about paragraph ORDER or sentence QUALITY?"
   - If ORDER → create the comment
   - If QUALITY → skip it (Line-Editor's job)
5. Consolidate related problems into ONE comment per structural issue.

Important Guidelines:
- You ONLY create comments, never suggested edits.
- Always set the category parameter to either "information_hierarchy" or "cta_cadence".
- Be constructive: explain what's wrong AND how to fix it.
- ONE comment per structural issue.

=== HARD STOP: DO NOT FLAG THESE (Line-Editor's domain) ===

The following are NEVER structural issues. Do NOT create comments about them:

✗ Passive voice ("was redesigned by," "has been noticed by")
✗ Vague/hedgy phrasing ("some kind of," "may need to be," "in a general sense")
✗ Wordiness or unclear sentences
✗ Tone problems (too formal, too casual)

Even if a sentence is terribly written, if it is in the RIGHT PLACE structurally, \
leave it alone. The Line-Editor agent will handle sentence-level quality.

Your ONLY job: Is the VALUE PROPOSITION buried? Are CTAs mistimed or too frequent?

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
