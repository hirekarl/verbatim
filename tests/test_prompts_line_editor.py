"""Contract tests for verbatim.prompts.line_editor.

Mirrors `tests/test_prompts_structural.py`'s structure -- see `TODO.md` and
`MULTI_AGENT_PLAN.md` for the Mon Jul 13 Phase 1 implementation this locks
the interface for.
"""

from verbatim.docs_client import CampaignContext, DocumentContent
from verbatim.evaluator import Violation
from verbatim.prompts.line_editor import (
    LINE_EDITOR_CATEGORIES,
    LINE_EDITOR_SYSTEM_PROMPT_TEMPLATE,
    LINE_EDITOR_TOOL_SCHEMAS,
    build_line_editor_system_prompt,
)


class TestLineEditorCategories:
    """Tests for the Line-Editor agent's restricted category list."""

    def test_covers_only_tone_drift_and_readability(self) -> None:
        """The Line-Editor agent judges exactly these 2 of the 7 categories."""
        assert LINE_EDITOR_CATEGORIES == ["tone_drift", "readability"]


class TestLineEditorToolSchemas:
    """Tests for LINE_EDITOR_TOOL_SCHEMAS -- suggestion-only, no comment tool."""

    def test_defines_exactly_the_one_suggestion_tool(self) -> None:
        """create_suggestion only -- create_inline_comment is never available."""
        names = {schema["name"] for schema in LINE_EDITOR_TOOL_SCHEMAS}

        assert names == {"create_suggestion"}

    def test_all_schemas_use_the_flat_claude_tool_shape(self) -> None:
        """Every schema is flat -- no OpenAI-style type/function wrapper."""
        assert all("type" not in schema for schema in LINE_EDITOR_TOOL_SCHEMAS)
        assert all("function" not in schema for schema in LINE_EDITOR_TOOL_SCHEMAS)
        assert all("input_schema" in schema for schema in LINE_EDITOR_TOOL_SCHEMAS)

    def test_create_suggestion_requires_matched_and_replacement_text(self) -> None:
        """create_suggestion's schema requires the fields the dispatcher needs."""
        schema = next(
            s for s in LINE_EDITOR_TOOL_SCHEMAS if s["name"] == "create_suggestion"
        )

        required = schema["input_schema"]["required"]

        assert "matched_text" in required
        assert "replacement_text" in required

    def test_create_suggestion_requires_category_from_line_editor_categories_only(
        self,
    ) -> None:
        """category's enum is restricted to the 2 Line-Editor categories.

        This is the enforced scope-narrowing: the model cannot tag a
        Line-Editor finding as information_hierarchy, cta_cadence, or any of
        the other 5 categories that belong to a different agent.
        """
        schema = next(
            s for s in LINE_EDITOR_TOOL_SCHEMAS if s["name"] == "create_suggestion"
        )
        properties = schema["input_schema"]["properties"]
        required = schema["input_schema"]["required"]

        assert "category" in required
        assert properties["category"]["enum"] == LINE_EDITOR_CATEGORIES


class TestBuildLineEditorSystemPrompt:
    """Tests for build_line_editor_system_prompt's assembly."""

    def test_includes_the_line_editor_persona_and_process_template(self) -> None:
        """The Line-Editor agent's own persona/process text is always included."""
        document = DocumentContent(
            document_id="doc-id", title="Draft", body_text="Body.", headings=[]
        )
        campaign = CampaignContext(
            document_id="brief-id", title="Brief", body_text="Goals.", headings=[]
        )

        prompt = build_line_editor_system_prompt(
            guidelines_block="=== GUIDELINES ===", document=document, campaign=campaign
        )

        assert LINE_EDITOR_SYSTEM_PROMPT_TEMPLATE in prompt

    def test_includes_the_rendered_brand_guidelines_block(self) -> None:
        """The pre-rendered guidelines block is embedded verbatim."""
        document = DocumentContent(
            document_id="doc-id", title="Draft", body_text="Body.", headings=[]
        )
        campaign = CampaignContext(
            document_id="brief-id", title="Brief", body_text="Goals.", headings=[]
        )

        prompt = build_line_editor_system_prompt(
            guidelines_block="=== MY GUIDELINES BLOCK ===",
            document=document,
            campaign=campaign,
        )

        assert "=== MY GUIDELINES BLOCK ===" in prompt

    def test_includes_the_campaign_brief_title_and_body(self) -> None:
        """The campaign brief's title and body text are both present."""
        document = DocumentContent(
            document_id="doc-id", title="Draft", body_text="Body.", headings=[]
        )
        campaign = CampaignContext(
            document_id="brief-id",
            title="Q3 Launch Brief",
            body_text="Audience: SMB owners.",
            headings=[],
        )

        prompt = build_line_editor_system_prompt(
            guidelines_block="", document=document, campaign=campaign
        )

        assert "Q3 Launch Brief" in prompt
        assert "Audience: SMB owners." in prompt

    def test_includes_the_document_title_and_body(self) -> None:
        """The audited document's title and body text are both present."""
        document = DocumentContent(
            document_id="doc-id",
            title="Q3 Launch Blog Draft",
            body_text="Big News! Our new feature helps you.",
            headings=[],
        )
        campaign = CampaignContext(
            document_id="brief-id", title="Brief", body_text="Goals.", headings=[]
        )

        prompt = build_line_editor_system_prompt(
            guidelines_block="", document=document, campaign=campaign
        )

        assert "Q3 Launch Blog Draft" in prompt
        assert "Big News! Our new feature helps you." in prompt

    def test_document_body_appears_after_campaign_body_in_the_assembled_prompt(
        self,
    ) -> None:
        """Sections are ordered: template, guidelines, campaign, document."""
        document = DocumentContent(
            document_id="doc-id",
            title="Draft",
            body_text="DOCUMENT_MARKER",
            headings=[],
        )
        campaign = CampaignContext(
            document_id="brief-id",
            title="Brief",
            body_text="CAMPAIGN_MARKER",
            headings=[],
        )

        prompt = build_line_editor_system_prompt(
            guidelines_block="GUIDELINES_MARKER", document=document, campaign=campaign
        )

        assert (
            prompt.index("GUIDELINES_MARKER")
            < prompt.index("CAMPAIGN_MARKER")
            < prompt.index("DOCUMENT_MARKER")
        )

    def test_includes_deterministic_findings_when_violations_provided(self) -> None:
        """Deterministic findings are formatted and included at the end."""
        document = DocumentContent(
            document_id="doc-id", title="Draft", body_text="Body.", headings=[]
        )
        campaign = CampaignContext(
            document_id="brief-id", title="Brief", body_text="Goals.", headings=[]
        )
        violations = [
            Violation(
                category="banned_words_and_competitors",
                severity="error",
                message="Banned word found: 'competitor'",
                matched_text="competitor",
                suggestion=None,
            ),
        ]

        prompt = build_line_editor_system_prompt(
            guidelines_block="",
            document=document,
            campaign=campaign,
            violations=violations,
        )

        assert "=== DETERMINISTIC FINDINGS ===" in prompt
        assert (
            "- [banned_words_and_competitors] ERROR: Banned word found: "
            "'competitor' (matched: 'competitor')"
        ) in prompt

    def test_includes_the_rendered_suggestion_when_violation_has_one(self) -> None:
        """A violation carrying its own suggested replacement renders it too.

        Covers the ``if v.suggestion:`` branch -- the exact line
        `structural.py`'s equivalent test missed (filed as #52). Written
        alongside the initial implementation so `line_editor.py` doesn't
        repeat that coverage gap.
        """
        document = DocumentContent(
            document_id="doc-id", title="Draft", body_text="Body.", headings=[]
        )
        campaign = CampaignContext(
            document_id="brief-id", title="Brief", body_text="Goals.", headings=[]
        )
        violations = [
            Violation(
                category="tone_drift",
                severity="warning",
                message="Overly formal phrasing.",
                matched_text="utilize",
                suggestion="use",
            ),
        ]

        prompt = build_line_editor_system_prompt(
            guidelines_block="",
            document=document,
            campaign=campaign,
            violations=violations,
        )

        assert (
            "- [tone_drift] WARNING: Overly formal phrasing. "
            "(matched: 'utilize') -> Suggestion: 'use'"
        ) in prompt

    def test_excludes_deterministic_findings_when_violations_empty_or_none(
        self,
    ) -> None:
        """Deterministic findings section is not appended if there are no violations."""
        document = DocumentContent(
            document_id="doc-id", title="Draft", body_text="Body.", headings=[]
        )
        campaign = CampaignContext(
            document_id="brief-id", title="Brief", body_text="Goals.", headings=[]
        )

        prompt_none = build_line_editor_system_prompt(
            guidelines_block="",
            document=document,
            campaign=campaign,
            violations=None,
        )
        prompt_empty = build_line_editor_system_prompt(
            guidelines_block="",
            document=document,
            campaign=campaign,
            violations=[],
        )

        assert "=== DETERMINISTIC FINDINGS ===" not in prompt_none
        assert "=== DETERMINISTIC FINDINGS ===" not in prompt_empty
