"""Contract tests for verbatim.prompts.structural.

Written before `prompts/structural.py` exists, as the TDD red step locking
the interface for Christina's Sun Jul 12 solo implementation -- see
`TODO.md` and `MULTI_AGENT_PLAN.md`. This suite is expected to fail at
collection (`ModuleNotFoundError`) until that module is created.
"""

from verbatim.prompts.structural import (  # type: ignore[import-not-found]
    STRUCTURAL_CATEGORIES,
    STRUCTURAL_SYSTEM_PROMPT_TEMPLATE,
    STRUCTURAL_TOOL_SCHEMAS,
    build_structural_system_prompt,
)

from verbatim.docs_client import CampaignContext, DocumentContent
from verbatim.evaluator import Violation


class TestStructuralCategories:
    """Tests for the Structural agent's restricted category list."""

    def test_covers_only_information_hierarchy_and_cta_cadence(self) -> None:
        """The Structural agent judges exactly these 2 of the 7 categories."""
        assert STRUCTURAL_CATEGORIES == ["information_hierarchy", "cta_cadence"]


class TestStructuralToolSchemas:
    """Tests for STRUCTURAL_TOOL_SCHEMAS -- comment-only, no suggestion tool."""

    def test_defines_exactly_the_one_comment_tool(self) -> None:
        """create_inline_comment only -- create_suggestion is never available."""
        names = {schema["function"]["name"] for schema in STRUCTURAL_TOOL_SCHEMAS}

        assert names == {"create_inline_comment"}

    def test_all_schemas_are_type_function(self) -> None:
        """Every schema uses the OpenAI function-calling tool type."""
        assert all(schema["type"] == "function" for schema in STRUCTURAL_TOOL_SCHEMAS)

    def test_create_inline_comment_requires_matched_text_and_comment(self) -> None:
        """create_inline_comment's schema requires the fields the dispatcher needs."""
        schema = next(
            s
            for s in STRUCTURAL_TOOL_SCHEMAS
            if s["function"]["name"] == "create_inline_comment"
        )

        required = schema["function"]["parameters"]["required"]

        assert "matched_text" in required
        assert "comment" in required

    def test_create_inline_comment_requires_category_from_structural_categories_only(
        self,
    ) -> None:
        """category's enum is restricted to the 2 Structural categories.

        This is the enforced scope-narrowing: the model cannot tag a
        Structural finding as tone_drift, readability, or any of the other
        5 categories that belong to a different agent.
        """
        schema = next(
            s
            for s in STRUCTURAL_TOOL_SCHEMAS
            if s["function"]["name"] == "create_inline_comment"
        )
        properties = schema["function"]["parameters"]["properties"]
        required = schema["function"]["parameters"]["required"]

        assert "category" in required
        assert properties["category"]["enum"] == STRUCTURAL_CATEGORIES


class TestBuildStructuralSystemPrompt:
    """Tests for build_structural_system_prompt's assembly."""

    def test_includes_the_structural_persona_and_process_template(self) -> None:
        """The Structural agent's own persona/process text is always included."""
        document = DocumentContent(
            document_id="doc-id", title="Draft", body_text="Body.", headings=[]
        )
        campaign = CampaignContext(
            document_id="brief-id", title="Brief", body_text="Goals.", headings=[]
        )

        prompt = build_structural_system_prompt(
            guidelines_block="=== GUIDELINES ===", document=document, campaign=campaign
        )

        assert STRUCTURAL_SYSTEM_PROMPT_TEMPLATE in prompt

    def test_includes_the_rendered_brand_guidelines_block(self) -> None:
        """The pre-rendered guidelines block is embedded verbatim."""
        document = DocumentContent(
            document_id="doc-id", title="Draft", body_text="Body.", headings=[]
        )
        campaign = CampaignContext(
            document_id="brief-id", title="Brief", body_text="Goals.", headings=[]
        )

        prompt = build_structural_system_prompt(
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

        prompt = build_structural_system_prompt(
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

        prompt = build_structural_system_prompt(
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

        prompt = build_structural_system_prompt(
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

        prompt = build_structural_system_prompt(
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

        prompt_none = build_structural_system_prompt(
            guidelines_block="",
            document=document,
            campaign=campaign,
            violations=None,
        )
        prompt_empty = build_structural_system_prompt(
            guidelines_block="",
            document=document,
            campaign=campaign,
            violations=[],
        )

        assert "=== DETERMINISTIC FINDINGS ===" not in prompt_none
        assert "=== DETERMINISTIC FINDINGS ===" not in prompt_empty
