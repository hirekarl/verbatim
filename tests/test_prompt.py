"""Tests for the system prompt assembly module."""

from verbatim.docs_client import CampaignContext, DocumentContent
from verbatim.prompt import SYSTEM_PROMPT_TEMPLATE, TOOL_SCHEMAS, build_system_prompt


class TestBuildSystemPrompt:
    """Tests for build_system_prompt."""

    def test_includes_the_base_persona_and_process_template(self) -> None:
        """The PRD's System Prompt v0 persona/process text is always included."""
        document = DocumentContent(
            document_id="doc-id", title="Draft", body_text="Body.", headings=[]
        )
        campaign = CampaignContext(
            document_id="brief-id", title="Brief", body_text="Goals.", headings=[]
        )

        prompt = build_system_prompt(
            guidelines_block="=== GUIDELINES ===", document=document, campaign=campaign
        )

        assert SYSTEM_PROMPT_TEMPLATE in prompt

    def test_includes_the_rendered_brand_guidelines_block(self) -> None:
        """The pre-rendered guidelines block is embedded verbatim."""
        document = DocumentContent(
            document_id="doc-id", title="Draft", body_text="Body.", headings=[]
        )
        campaign = CampaignContext(
            document_id="brief-id", title="Brief", body_text="Goals.", headings=[]
        )

        prompt = build_system_prompt(
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

        prompt = build_system_prompt(
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

        prompt = build_system_prompt(
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

        prompt = build_system_prompt(
            guidelines_block="GUIDELINES_MARKER", document=document, campaign=campaign
        )

        assert (
            prompt.index("GUIDELINES_MARKER")
            < prompt.index("CAMPAIGN_MARKER")
            < prompt.index("DOCUMENT_MARKER")
        )


class TestToolSchemas:
    """Tests for the TOOL_SCHEMAS function-calling definitions."""

    def test_defines_exactly_the_two_write_tools(self) -> None:
        """Only create_suggestion and create_inline_comment are exposed."""
        names = {schema["function"]["name"] for schema in TOOL_SCHEMAS}

        assert names == {"create_suggestion", "create_inline_comment"}

    def test_create_suggestion_requires_matched_text_and_replacement_text(self) -> None:
        """create_suggestion's schema requires the fields the dispatcher needs."""
        schema = next(
            s for s in TOOL_SCHEMAS if s["function"]["name"] == "create_suggestion"
        )

        required = schema["function"]["parameters"]["required"]

        assert "matched_text" in required
        assert "replacement_text" in required

    def test_create_inline_comment_requires_matched_text_and_comment(self) -> None:
        """create_inline_comment's schema requires the fields the dispatcher needs."""
        schema = next(
            s for s in TOOL_SCHEMAS if s["function"]["name"] == "create_inline_comment"
        )

        required = schema["function"]["parameters"]["required"]

        assert "matched_text" in required
        assert "comment" in required

    def test_all_schemas_are_type_function(self) -> None:
        """Every schema uses the OpenAI function-calling tool type."""
        assert all(schema["type"] == "function" for schema in TOOL_SCHEMAS)
