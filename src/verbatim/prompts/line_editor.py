"""System prompt assembly and tool schema for the Line-Editor agent (stub).

Mirrors `verbatim.prompt`'s shape but scoped to Tone Drift + Readability,
suggestion-only (no `create_inline_comment`). Full implementation lands
Mon Jul 13 per `TODO.md`; today only locks the signatures so
`verbatim.orchestrator` has a stable contract to import against.
"""

from typing import Any

from verbatim.docs_client import CampaignContext, DocumentContent
from verbatim.evaluator import Violation

LINE_EDITOR_CATEGORIES: list[str] = ["tone_drift", "readability"]

LINE_EDITOR_SYSTEM_PROMPT_TEMPLATE: str = ""

LINE_EDITOR_TOOL_SCHEMAS: list[dict[str, Any]] = []


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
        The assembled system prompt string.

    Raises:
        NotImplementedError: Stub; implemented Mon Jul 13.
    """
    raise NotImplementedError
