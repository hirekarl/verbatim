"""Vocabulary shared by every specialist agent's prompt/tool schema module.

`CATEGORIES` is the single source of truth for the 7 audit categories --
`prompt.py` re-exports it rather than duplicating the list, and each
specialist agent module (`prompts/structural.py`, `prompts/line_editor.py`)
defines its own narrower subset for its own tool schema's `category` enum.

`validate_category` closes the gap where a tool call's `category` argument
isn't hard-enforced: OpenRouter/OpenAI-style function calling doesn't
validate a JSON-schema `enum` server-side, so a model can still return a
`category` string that's missing, misspelled, or -- once split by
specialist agent -- borrowed from the wrong agent's own allowed set. See
`MULTI_AGENT_PLAN.md`'s "Category validation" section for the full
rationale, including why this is enforced only at dispatch time and not
duplicated in `orchestrator.reconcile_findings`.
"""

# Matches brand_guidelines.json's `rules` keys exactly -- the same convention
# evaluator.py's Violation.category already uses for its 3 deterministic
# categories, extended here to all 7 so every tool call can be tagged.
CATEGORIES: list[str] = [
    "tone_drift",
    "information_hierarchy",
    "cta_cadence",
    "readability",
    "formatting_and_style",
    "channel_constraints",
    "banned_words_and_competitors",
]

UNCATEGORIZED_CATEGORY = "uncategorized"


def validate_category(category: str | None, allowed: list[str]) -> str:
    """Validate a tool call's category argument against an agent's allowed set.

    Handles both failure modes a tool call's arguments can arrive in: the
    ``category`` key missing entirely (``category`` is ``None``) and the key
    present but holding a value outside ``allowed`` -- misspelled, wrong
    casing, or borrowed from a different specialist agent's category set.
    Neither failure mode is enforced server-side by OpenRouter/OpenAI-style
    function calling's JSON-schema ``enum``, so this is the actual
    enforcement point.

    Args:
        category: The raw ``category`` argument from the tool call, or
            ``None`` if the key was missing.
        allowed: The calling agent's own allowed category list -- the full
            ``CATEGORIES`` for the legacy single-agent path, or a narrower
            per-specialist list (``STRUCTURAL_CATEGORIES``,
            ``LINE_EDITOR_CATEGORIES``) for the split agents.

    Returns:
        ``category`` unchanged if it's a member of ``allowed``, otherwise
        ``UNCATEGORIZED_CATEGORY``.
    """
    if category is None or category not in allowed:
        return UNCATEGORIZED_CATEGORY
    return category
