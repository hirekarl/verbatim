from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from verbatim.agent import AgentRunResult, run_agent
from verbatim.brand_guidelines import BrandGuidelines
from verbatim.docs_client import (
    CampaignContext,
    DocumentContent,
    GoogleDocsClient,
    TextNotFoundError,
)
from verbatim.llm_client import ChatCompletionResult, OpenRouterClient, ToolCall

_DOCUMENT = DocumentContent(
    document_id="doc-id",
    title="Draft",
    body_text="Big News! Feature helps you.",
    headings=[],
)
_CAMPAIGN = CampaignContext(
    document_id="brief-id", title="Brief", body_text="Audience: SMBs.", headings=[]
)


@pytest.fixture
def docs_client() -> MagicMock:
    """A fake GoogleDocsClient returning fixed document/campaign content."""
    client = MagicMock(spec=GoogleDocsClient)
    client.get_document_content.return_value = _DOCUMENT
    client.get_campaign_context.return_value = _CAMPAIGN
    return client


@pytest.fixture
def llm_client() -> MagicMock:
    """A fake OpenRouterClient; tests configure complete_chat's side effects."""
    return MagicMock(spec=OpenRouterClient)


@pytest.fixture
def brand_guidelines() -> BrandGuidelines:
    """The real BrandGuidelines loaded from the repo's fixture file."""
    return BrandGuidelines()


def _no_tool_calls_result(content: str = "Audit complete.") -> ChatCompletionResult:
    return ChatCompletionResult(
        content=content,
        tool_calls=[],
        raw_assistant_message={"role": "assistant", "content": content},
    )


def _tool_call_result(*tool_calls: ToolCall) -> ChatCompletionResult:
    return ChatCompletionResult(
        content=None,
        tool_calls=list(tool_calls),
        raw_assistant_message={"role": "assistant", "tool_calls": []},
    )


class TestRunAgent:
    """Tests for run_agent's single-pass tool-calling conversation."""

    def test_stops_immediately_when_the_model_makes_no_tool_calls(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
    ) -> None:
        """A content-only first response ends the run with nothing posted."""
        llm_client.complete_chat.return_value = _no_tool_calls_result()

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        assert result == AgentRunResult(
            suggestions_made=0,
            comments_made=0,
            transcript=result.transcript,
            stopped_due_to_max_rounds=False,
        )
        llm_client.complete_chat.assert_called_once()

    def test_fetches_document_and_campaign_exactly_once(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
    ) -> None:
        """Reads happen once up front, regardless of how many tool-call rounds run."""
        llm_client.complete_chat.return_value = _no_tool_calls_result()

        run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        docs_client.get_document_content.assert_called_once_with("doc-id")
        docs_client.get_campaign_context.assert_called_once_with("brief-id")

    def test_runs_evaluator_and_passes_violations_to_prompt(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
        mocker: MockerFixture,
    ) -> None:
        """The agent runs evaluator and passes findings to prompt builder."""
        mock_evaluator = mocker.patch("verbatim.agent.BrandGuidelinesEvaluator")
        mock_instance = mock_evaluator.return_value
        fake_violations = [MagicMock()]
        mock_instance.evaluate.return_value = fake_violations

        mock_build = mocker.patch("verbatim.agent.build_system_prompt")
        mock_build.return_value = "System Prompt Content"

        llm_client.complete_chat.return_value = _no_tool_calls_result()

        run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
            target_channel="email",
        )

        mock_evaluator.assert_called_once_with(
            guidelines_path=str(brand_guidelines.filepath)
        )
        mock_instance.evaluate.assert_called_once_with(
            _DOCUMENT.body_text,
            channel="email",
            headings=_DOCUMENT.headings,
            title=_DOCUMENT.title,
        )
        mock_build.assert_called_once_with(
            brand_guidelines.format_for_llm_prompt(target_channel="email"),
            _DOCUMENT,
            _CAMPAIGN,
            violations=fake_violations,
        )

    def test_dispatches_a_single_create_suggestion_call_then_stops(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
    ) -> None:
        """A single suggestion tool call is dispatched and counted."""
        suggestion_call = ToolCall(
            id="call_1",
            name="create_suggestion",
            arguments={
                "matched_text": "Feature",
                "replacement_text": "Capability",
                "category": "readability",
            },
        )
        llm_client.complete_chat.side_effect = [
            _tool_call_result(suggestion_call),
            _no_tool_calls_result(),
        ]

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        docs_client.create_suggestion.assert_called_once_with(
            document_id="doc-id",
            matched_text="Feature",
            replacement_text="Capability",
        )
        assert result.suggestions_made == 1
        assert result.comments_made == 0
        assert result.category_counts == {"readability": 1}

    def test_skips_redundant_suggestion_when_matched_and_replacement_are_identical(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
    ) -> None:
        """A redundant suggestion tool call is skipped and not counted."""
        suggestion_call = ToolCall(
            id="call_1",
            name="create_suggestion",
            arguments={"matched_text": "Same text", "replacement_text": "Same text"},
        )
        llm_client.complete_chat.side_effect = [
            _tool_call_result(suggestion_call),
            _no_tool_calls_result(),
        ]

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        docs_client.create_suggestion.assert_not_called()
        assert result.suggestions_made == 0
        assert result.comments_made == 0

    def test_dispatches_a_single_create_inline_comment_call_then_stops(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
    ) -> None:
        """A single comment tool call is dispatched and counted."""
        comment_call = ToolCall(
            id="call_1",
            name="create_inline_comment",
            arguments={
                "matched_text": "Big News!",
                "comment": "Lead with value instead.",
                "category": "information_hierarchy",
            },
        )
        llm_client.complete_chat.side_effect = [
            _tool_call_result(comment_call),
            _no_tool_calls_result(),
        ]

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        docs_client.create_inline_comment.assert_called_once_with(
            document_id="doc-id",
            matched_text="Big News!",
            comment="Lead with value instead.",
        )
        assert result.suggestions_made == 0
        assert result.comments_made == 1
        assert result.category_counts == {"information_hierarchy": 1}

    def test_dispatches_multiple_tool_calls_returned_in_one_round(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
    ) -> None:
        """Several tool calls in one model response are all dispatched."""
        suggestion_call = ToolCall(
            id="call_1",
            name="create_suggestion",
            arguments={
                "matched_text": "Feature",
                "replacement_text": "Capability",
                "category": "readability",
            },
        )
        comment_call = ToolCall(
            id="call_2",
            name="create_inline_comment",
            arguments={
                "matched_text": "Big News!",
                "comment": "Reorder this.",
                "category": "information_hierarchy",
            },
        )
        llm_client.complete_chat.side_effect = [
            _tool_call_result(suggestion_call, comment_call),
            _no_tool_calls_result(),
        ]

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        assert result.suggestions_made == 1
        assert result.comments_made == 1
        assert result.category_counts == {
            "readability": 1,
            "information_hierarchy": 1,
        }

    def test_missing_category_falls_back_to_uncategorized(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
    ) -> None:
        """A tool call omitting category still counts, under 'uncategorized'.

        The model isn't guaranteed to honor the schema's `required` list --
        OpenRouter/OpenAI-style function calling doesn't hard-enforce it --
        so a dispatched call missing `category` shouldn't crash or vanish
        from the tally."""
        suggestion_call = ToolCall(
            id="call_1",
            name="create_suggestion",
            arguments={"matched_text": "Feature", "replacement_text": "Capability"},
        )
        llm_client.complete_chat.side_effect = [
            _tool_call_result(suggestion_call),
            _no_tool_calls_result(),
        ]

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        assert result.suggestions_made == 1
        assert result.category_counts == {"uncategorized": 1}

    def test_skips_duplicate_inline_comment_on_same_matched_text_across_rounds(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
    ) -> None:
        """A repeat create_inline_comment on the same span in a later round is
        skipped rather than posted again -- the model re-flagging the same
        structural issue during both its overall-structure pass and its
        paragraph-by-paragraph pass shouldn't duplicate the comment."""
        first_call = ToolCall(
            id="call_1",
            name="create_inline_comment",
            arguments={"matched_text": "Big News!", "comment": "Reorder this."},
        )
        second_call = ToolCall(
            id="call_2",
            name="create_inline_comment",
            arguments={
                "matched_text": "Big News!",
                "comment": "Lead with value instead.",
            },
        )
        llm_client.complete_chat.side_effect = [
            _tool_call_result(first_call),
            _tool_call_result(second_call),
            _no_tool_calls_result(),
        ]

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        docs_client.create_inline_comment.assert_called_once_with(
            document_id="doc-id",
            matched_text="Big News!",
            comment="Reorder this.",
        )
        assert result.comments_made == 1

    def test_skips_duplicate_suggestion_on_same_matched_text_across_rounds(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
    ) -> None:
        """A repeat create_suggestion on the same span in a later round is
        skipped rather than posted again."""
        first_call = ToolCall(
            id="call_1",
            name="create_suggestion",
            arguments={"matched_text": "Feature", "replacement_text": "Capability"},
        )
        second_call = ToolCall(
            id="call_2",
            name="create_suggestion",
            arguments={"matched_text": "Feature", "replacement_text": "Tool"},
        )
        llm_client.complete_chat.side_effect = [
            _tool_call_result(first_call),
            _tool_call_result(second_call),
            _no_tool_calls_result(),
        ]

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        docs_client.create_suggestion.assert_called_once_with(
            document_id="doc-id",
            matched_text="Feature",
            replacement_text="Capability",
        )
        assert result.suggestions_made == 1

    def test_docs_client_error_is_fed_back_as_a_tool_result_not_raised(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
    ) -> None:
        """A DocsClientError from dispatch surfaces to the model, not the caller."""
        suggestion_call = ToolCall(
            id="call_1",
            name="create_suggestion",
            arguments={
                "matched_text": "nowhere",
                "replacement_text": "x",
                "category": "readability",
            },
        )
        docs_client.create_suggestion.side_effect = TextNotFoundError("not found")
        llm_client.complete_chat.side_effect = [
            _tool_call_result(suggestion_call),
            _no_tool_calls_result(),
        ]

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        assert result.suggestions_made == 0
        assert result.category_counts == {}
        second_call_messages = llm_client.complete_chat.call_args_list[1].kwargs[
            "messages"
        ]
        tool_messages = [m for m in second_call_messages if m.get("role") == "tool"]
        assert any("not found" in m["content"] for m in tool_messages)

    def test_unknown_tool_name_is_surfaced_to_the_model_without_crashing(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
    ) -> None:
        """A tool call for an unrecognized tool name doesn't raise or dispatch."""
        unknown_call = ToolCall(id="call_1", name="delete_document", arguments={})
        llm_client.complete_chat.side_effect = [
            _tool_call_result(unknown_call),
            _no_tool_calls_result(),
        ]

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        assert result.suggestions_made == 0
        assert result.comments_made == 0
        docs_client.create_suggestion.assert_not_called()
        docs_client.create_inline_comment.assert_not_called()

    def test_stops_after_max_rounds_when_the_model_never_stops_calling_tools(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
    ) -> None:
        """A non-terminating conversation is capped by max_tool_call_rounds."""
        # Distinct matched_text per round -- a repeated identical tool call
        # would be collapsed by duplicate-span skipping, confounding this
        # test's assertion that the round cap itself is what stops the loop.
        llm_client.complete_chat.side_effect = [
            _tool_call_result(
                ToolCall(
                    id=f"call_{i}",
                    name="create_suggestion",
                    arguments={
                        "matched_text": f"Feature {i}",
                        "replacement_text": f"Capability {i}",
                    },
                )
            )
            for i in range(3)
        ]

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
            max_tool_call_rounds=3,
        )

        assert result.stopped_due_to_max_rounds is True
        assert llm_client.complete_chat.call_count == 3
        assert result.suggestions_made == 3

    def test_handles_invalid_brand_guidelines_gracefully(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """If guidelines are invalid, warn in-doc and fall back."""
        bad_guidelines = MagicMock(spec=BrandGuidelines)
        bad_guidelines.is_valid = False
        bad_guidelines.error_message = "File is corrupt"
        bad_guidelines.filepath = MagicMock()
        bad_guidelines.filepath.name = "brand_guidelines.json"

        # Mock build_system_prompt to verify the block
        mock_build = mocker.patch("verbatim.agent.build_system_prompt")
        mock_build.return_value = "System Prompt Content"

        llm_client.complete_chat.return_value = _no_tool_calls_result()

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=bad_guidelines,
        )

        assert result.suggestions_made == 0
        assert result.comments_made == 0

        # Verify comment creation for warning
        expected_comment = (
            "Warning: Brand guidelines file 'brand_guidelines.json' "
            "is missing or corrupt (File is corrupt). "
            "Audit conducted using only the Campaign Brief."
        )
        docs_client.create_inline_comment.assert_called_once_with(
            document_id="doc-id",
            matched_text="Big News! Feature helps you.",
            comment=expected_comment,
        )
        docs_client.clear_cache.assert_called_once_with("doc-id")

        # Verify prompt builder call uses fallback block
        mock_build.assert_called_once()
        args = mock_build.call_args.args
        kwargs = mock_build.call_args.kwargs
        assert "[WARNING] Brand voice and style guidelines are unavailable" in args[0]
        assert kwargs.get("violations") == []
