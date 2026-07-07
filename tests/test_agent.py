"""Tests for the single-pass tool-calling agent loop."""

from unittest.mock import MagicMock

import pytest

from brand_guidelines import BrandGuidelines
from verbatim.agent import AgentRunResult, run_agent
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
    return BrandGuidelines("brand_guidelines.json")


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

        docs_client.create_suggestion.assert_called_once_with(
            document_id="doc-id",
            matched_text="Feature",
            replacement_text="Capability",
        )
        assert result.suggestions_made == 1
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
            arguments={"matched_text": "Feature", "replacement_text": "Capability"},
        )
        comment_call = ToolCall(
            id="call_2",
            name="create_inline_comment",
            arguments={"matched_text": "Big News!", "comment": "Reorder this."},
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
            arguments={"matched_text": "nowhere", "replacement_text": "x"},
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
        never_ending_call = ToolCall(
            id="call_1",
            name="create_suggestion",
            arguments={"matched_text": "Feature", "replacement_text": "Capability"},
        )
        llm_client.complete_chat.return_value = _tool_call_result(never_ending_call)

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
