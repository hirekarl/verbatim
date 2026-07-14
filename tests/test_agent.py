from typing import Any
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockerFixture

from verbatim.agent import (
    AgentRunResult,
    Finding,
    _find_anchor_text,
    run_agent,
    run_agent_legacy,
)
from verbatim.brand_guidelines import BrandGuidelines
from verbatim.docs_client import (
    CampaignContext,
    DocumentContent,
    GoogleDocsClient,
    TextNotFoundError,
)
from verbatim.llm_client import AnthropicClient, ChatCompletionResult, ToolCall
from verbatim.orchestrator import _run_single_agent_loop
from verbatim.prompts.line_editor import LINE_EDITOR_CATEGORIES
from verbatim.prompts.shared import CATEGORIES
from verbatim.prompts.structural import STRUCTURAL_CATEGORIES, STRUCTURAL_TOOL_SCHEMAS

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
    """A fake AnthropicClient; tests configure complete_chat's side effects."""
    return MagicMock(spec=AnthropicClient)


@pytest.fixture
def brand_guidelines() -> BrandGuidelines:
    """The real BrandGuidelines loaded from the repo's fixture file."""
    return BrandGuidelines()


def _no_tool_calls_result(content: str = "Audit complete.") -> ChatCompletionResult:
    return ChatCompletionResult(
        content=content,
        tool_calls=[],
        raw_assistant_message={
            "role": "assistant",
            "content": [{"type": "text", "text": content}],
        },
    )


def _tool_call_result(*tool_calls: ToolCall) -> ChatCompletionResult:
    return ChatCompletionResult(
        content=None,
        tool_calls=list(tool_calls),
        raw_assistant_message={
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": tc.id,
                    "name": tc.name,
                    "input": tc.arguments,
                }
                for tc in tool_calls
            ],
        },
    )


class TestRunSingleAgentLoop:
    """Tests for orchestrator._run_single_agent_loop's tool-calling conversation.

    Retargeted Mon Jul 13 from run_agent's inline loop (now extracted into
    this shared, per-specialist function) per `TODO.md`. Uses the legacy
    `TOOL_SCHEMAS`/`CATEGORIES` since these behaviors (dispatch, dedup,
    error-handling, loop-control) are generic to the loop itself, not
    specific to either specialist agent.
    """

    def test_seeds_the_conversation_with_an_initial_user_message(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
    ) -> None:
        """The first API call includes a user-role kickoff message.

        Claude's Messages API rejects an empty `messages` list and requires
        the first message to have role "user" -- unlike OpenAI's chat
        completions, which allowed a request containing only the system
        message. All conversational content still lives in `system_prompt`;
        this is just the required kickoff turn. Caught by a live smoke test
        against the real API, not by any pre-existing unit test, since
        `complete_chat` is mocked everywhere else.
        """
        llm_client.complete_chat.return_value = _no_tool_calls_result()

        _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=CATEGORIES,
        )

        first_call_messages = llm_client.complete_chat.call_args_list[0].kwargs[
            "messages"
        ]
        assert len(first_call_messages) >= 1
        assert first_call_messages[0]["role"] == "user"

    def test_stops_immediately_when_the_model_makes_no_tool_calls(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
    ) -> None:
        """A content-only first response ends the run with nothing posted."""
        llm_client.complete_chat.return_value = _no_tool_calls_result()

        result = _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=CATEGORIES,
        )

        assert result == AgentRunResult(
            suggestions_made=0,
            comments_made=0,
            transcript=result.transcript,
            stopped_due_to_max_rounds=False,
        )
        llm_client.complete_chat.assert_called_once()

    def test_dispatches_a_single_create_suggestion_call_then_stops(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
    ) -> None:
        """A single suggestion tool call is dispatched and counted."""
        suggestion_call = ToolCall(
            id="call_1",
            name="create_suggestion",
            arguments={
                "matched_text": "Feature",
                "replacement_text": "Capability",
                "rationale": "Simplify the noun.",
                "category": "readability",
            },
        )
        llm_client.complete_chat.side_effect = [
            _tool_call_result(suggestion_call),
            _no_tool_calls_result(),
        ]

        result = _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=CATEGORIES,
        )

        docs_client.create_suggestion.assert_called_once_with(
            document_id="doc-id",
            matched_text="Feature",
            replacement_text="Capability",
        )
        assert result.suggestions_made == 1
        assert result.comments_made == 0
        assert result.category_counts == {"readability": 1}
        assert result.findings == [
            Finding(
                category="readability",
                kind="suggestion",
                matched_text="Feature",
                detail="Simplify the noun.",
            )
        ]

    def test_skips_redundant_suggestion_when_matched_and_replacement_are_identical(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
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

        result = _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=CATEGORIES,
        )

        docs_client.create_suggestion.assert_not_called()
        assert result.suggestions_made == 0
        assert result.comments_made == 0
        assert result.findings == []

    def test_dispatches_a_single_create_inline_comment_call_then_stops(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
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

        result = _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=CATEGORIES,
        )

        docs_client.create_inline_comment.assert_called_once_with(
            document_id="doc-id",
            matched_text="Big News!",
            comment="Lead with value instead.",
        )
        assert result.suggestions_made == 0
        assert result.comments_made == 1
        assert result.category_counts == {"information_hierarchy": 1}
        assert result.findings == [
            Finding(
                category="information_hierarchy",
                kind="comment",
                matched_text="Big News!",
                detail="Lead with value instead.",
            )
        ]

    def test_dispatches_multiple_tool_calls_returned_in_one_round(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
    ) -> None:
        """Several tool calls in one model response are all dispatched."""
        suggestion_call = ToolCall(
            id="call_1",
            name="create_suggestion",
            arguments={
                "matched_text": "Feature",
                "replacement_text": "Capability",
                "rationale": "Simplify the noun.",
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

        result = _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=CATEGORIES,
        )

        assert result.suggestions_made == 1
        assert result.comments_made == 1
        assert result.category_counts == {
            "readability": 1,
            "information_hierarchy": 1,
        }
        assert result.findings == [
            Finding(
                category="readability",
                kind="suggestion",
                matched_text="Feature",
                detail="Simplify the noun.",
            ),
            Finding(
                category="information_hierarchy",
                kind="comment",
                matched_text="Big News!",
                detail="Reorder this.",
            ),
        ]

    def test_missing_category_falls_back_to_uncategorized(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
    ) -> None:
        """A tool call omitting category still counts, under 'uncategorized'.

        The model isn't guaranteed to honor the schema's `required` list --
        the model's tool-calling doesn't hard-enforce it -- so a dispatched
        call missing `category` shouldn't crash or vanish from the tally."""
        suggestion_call = ToolCall(
            id="call_1",
            name="create_suggestion",
            arguments={"matched_text": "Feature", "replacement_text": "Capability"},
        )
        llm_client.complete_chat.side_effect = [
            _tool_call_result(suggestion_call),
            _no_tool_calls_result(),
        ]

        result = _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=CATEGORIES,
        )

        assert result.suggestions_made == 1
        assert result.category_counts == {"uncategorized": 1}
        assert result.findings == [
            Finding(
                category="uncategorized",
                kind="suggestion",
                matched_text="Feature",
                detail="",
            )
        ]

    def test_unrecognized_category_falls_back_to_uncategorized(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
    ) -> None:
        """A tool call with an out-of-vocabulary category still counts, under
        'uncategorized' -- not as a new, silent category_counts key.

        Same reasoning as the missing-category fallback above, but for the
        case where the model *does* type a category, just not one of the
        caller's ``allowed_categories`` (a typo like 'info_hierarchy', wrong
        casing, or a real category borrowed from the wrong specialist
        agent -- see the narrower-``allowed_categories`` tests below)."""
        suggestion_call = ToolCall(
            id="call_1",
            name="create_suggestion",
            arguments={
                "matched_text": "Feature",
                "replacement_text": "Capability",
                "category": "info_hierarchy",
            },
        )
        llm_client.complete_chat.side_effect = [
            _tool_call_result(suggestion_call),
            _no_tool_calls_result(),
        ]

        result = _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=CATEGORIES,
        )

        assert result.suggestions_made == 1
        assert result.category_counts == {"uncategorized": 1}
        assert result.findings == [
            Finding(
                category="uncategorized",
                kind="suggestion",
                matched_text="Feature",
                detail="",
            )
        ]

    def test_category_from_the_other_specialist_agent_falls_back_to_uncategorized(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
    ) -> None:
        """A real category outside this call's narrower allowed_categories
        is caught too, not just outright typos -- the scenario
        `allowed_categories` exists for once the specialist split lands."""
        suggestion_call = ToolCall(
            id="call_1",
            name="create_suggestion",
            arguments={
                "matched_text": "Feature",
                "replacement_text": "Capability",
                "category": "information_hierarchy",
            },
        )
        llm_client.complete_chat.side_effect = [
            _tool_call_result(suggestion_call),
            _no_tool_calls_result(),
        ]

        result = _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=["tone_drift", "readability"],
        )

        assert result.category_counts == {"uncategorized": 1}

    def test_missing_rationale_falls_back_to_empty_detail(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
    ) -> None:
        """A suggestion tool call omitting rationale still creates a Finding.

        Same reasoning as the missing-category fallback above: the model
        isn't guaranteed to honor the schema's `required` list."""
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

        result = _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=CATEGORIES,
        )

        assert result.findings == [
            Finding(
                category="readability",
                kind="suggestion",
                matched_text="Feature",
                detail="",
            )
        ]

    def test_skips_duplicate_inline_comment_on_same_matched_text_across_rounds(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
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

        result = _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=CATEGORIES,
        )

        docs_client.create_inline_comment.assert_called_once_with(
            document_id="doc-id",
            matched_text="Big News!",
            comment="Reorder this.",
        )
        assert result.comments_made == 1
        assert len(result.findings) == 1

    def test_skips_duplicate_suggestion_on_same_matched_text_across_rounds(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
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

        result = _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=CATEGORIES,
        )

        docs_client.create_suggestion.assert_called_once_with(
            document_id="doc-id",
            matched_text="Feature",
            replacement_text="Capability",
        )
        assert result.suggestions_made == 1
        assert len(result.findings) == 1

    def test_docs_client_error_is_fed_back_as_a_tool_result_not_raised(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
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

        result = _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=CATEGORIES,
        )

        assert result.suggestions_made == 0
        assert result.category_counts == {}
        assert result.findings == []
        second_call_messages = llm_client.complete_chat.call_args_list[1].kwargs[
            "messages"
        ]
        tool_result_blocks = [
            block
            for message in second_call_messages
            if message.get("role") == "user" and isinstance(message["content"], list)
            for block in message["content"]
            if block.get("type") == "tool_result"
        ]
        assert any("not found" in block["content"] for block in tool_result_blocks)

    def test_unknown_tool_name_is_surfaced_to_the_model_without_crashing(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
    ) -> None:
        """A tool call for an unrecognized tool name doesn't raise or dispatch."""
        unknown_call = ToolCall(id="call_1", name="delete_document", arguments={})
        llm_client.complete_chat.side_effect = [
            _tool_call_result(unknown_call),
            _no_tool_calls_result(),
        ]

        result = _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=CATEGORIES,
        )

        assert result.suggestions_made == 0
        assert result.comments_made == 0
        docs_client.create_suggestion.assert_not_called()
        docs_client.create_inline_comment.assert_not_called()

    def test_stops_after_max_rounds_when_the_model_never_stops_calling_tools(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
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

        result = _run_single_agent_loop(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            system_prompt="System Prompt",
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=CATEGORIES,
            max_tool_call_rounds=3,
        )

        assert result.stopped_due_to_max_rounds is True
        assert llm_client.complete_chat.call_count == 3
        assert result.suggestions_made == 3


class TestFindAnchorText:
    """Tests for _find_anchor_text's unique-substring search.

    Only two tiers are reachable: whole-paragraph match, then a first-20-
    characters fallback. A word-level tier used to sit between them but was
    dead code -- any paragraph containing a textually-unique word is itself
    unique, so the paragraph loop always returns first. Removed Jul 13.
    """

    def test_returns_none_for_empty_body_text(self) -> None:
        assert _find_anchor_text("") is None

    def test_returns_a_unique_paragraph(self) -> None:
        assert _find_anchor_text("Big News! Feature helps you.") == (
            "Big News! Feature helps you."
        )

    def test_skips_non_unique_paragraphs_to_find_a_unique_one(self) -> None:
        """Repeated paragraphs are skipped in favor of one that's unique."""
        text = "dup\ndup\nfoo bar unique_word baz"

        assert _find_anchor_text(text) == "foo bar unique_word baz"

    def test_falls_back_to_first_20_characters_when_no_paragraph_is_unique(
        self,
    ) -> None:
        text = "same paragraph line\nsame paragraph line"

        assert _find_anchor_text(text) == text[:20]

    def test_returns_none_when_nothing_is_unique_and_body_is_short(self) -> None:
        """Repeated, short content leaves no paragraph or 20-char anchor."""
        assert _find_anchor_text("hi\nhi") is None

    def test_returns_none_when_the_20_char_candidate_is_also_not_unique(
        self,
    ) -> None:
        """Long but repetitive content exhausts every fallback tier."""
        text = "this is a duplicated line\nthis is a duplicated line"

        assert _find_anchor_text(text) is None


class TestRunAgentLegacy:
    """Tests for run_agent_legacy's single-pass tool-calling conversation.

    Renamed Mon Jul 13 from `TestRunAgent` -- these orchestration-level
    behaviors (fetch once, run the evaluator once, fall back gracefully on
    invalid guidelines) live on the pre-split legacy path now, kept for the
    Tue Jul 14 before/after Eval Card comparison. Dispatch/dedup/error-
    handling behaviors moved to `TestRunSingleAgentLoop` above.
    """

    def test_stops_immediately_when_the_model_makes_no_tool_calls(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
    ) -> None:
        """A content-only first response ends the run with nothing posted."""
        llm_client.complete_chat.return_value = _no_tool_calls_result()

        result = run_agent_legacy(
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

        run_agent_legacy(
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

        run_agent_legacy(
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

        result = run_agent_legacy(
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

    def test_skips_warning_comment_when_document_has_no_anchor_text(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """If no unique anchor exists in the doc, don't post a comment at all."""
        docs_client.get_document_content.return_value = DocumentContent(
            document_id="doc-id", title="Draft", body_text="hi\nhi", headings=[]
        )
        bad_guidelines = MagicMock(spec=BrandGuidelines)
        bad_guidelines.is_valid = False
        bad_guidelines.error_message = "File is corrupt"
        bad_guidelines.filepath = MagicMock()
        bad_guidelines.filepath.name = "brand_guidelines.json"

        mocker.patch("verbatim.agent.build_system_prompt", return_value="Prompt")
        llm_client.complete_chat.return_value = _no_tool_calls_result()

        run_agent_legacy(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=bad_guidelines,
        )

        docs_client.create_inline_comment.assert_not_called()
        docs_client.clear_cache.assert_not_called()

    def test_swallows_a_failed_warning_comment_and_keeps_going(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        mocker: MockerFixture,
    ) -> None:
        """A create_inline_comment failure while warning shouldn't abort the run."""
        docs_client.create_inline_comment.side_effect = RuntimeError("Docs API down")
        bad_guidelines = MagicMock(spec=BrandGuidelines)
        bad_guidelines.is_valid = False
        bad_guidelines.error_message = "File is corrupt"
        bad_guidelines.filepath = MagicMock()
        bad_guidelines.filepath.name = "brand_guidelines.json"

        mock_build = mocker.patch(
            "verbatim.agent.build_system_prompt", return_value="Prompt"
        )
        llm_client.complete_chat.return_value = _no_tool_calls_result()

        result = run_agent_legacy(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=bad_guidelines,
        )

        assert result.suggestions_made == 0
        assert result.comments_made == 0
        docs_client.clear_cache.assert_not_called()
        mock_build.assert_called_once()


class TestRunAgentSpecialistDispatch:
    """Tests for the new run_agent's wiring: both specialists, then reconcile.

    Unlike `TestRunSingleAgentLoop`/`TestRunAgentLegacy` above, these mock
    out `orchestrator._run_single_agent_loop` and
    `orchestrator.reconcile_findings` entirely -- the goal here is only to
    verify `run_agent` assembles and dispatches to both specialist agents
    correctly, not to re-exercise the loop or merge logic those other test
    classes already cover.
    """

    def test_calls_structural_then_line_editor_then_reconciles(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
        mocker: MockerFixture,
    ) -> None:
        """Both specialist agents run concurrently and their results are merged.

        Dispatch happens on separate threads (Phase 2), so submission order
        doesn't guarantee call order for these near-instant mocks -- assert
        by each call's ``allowed_categories`` rather than list position.
        """
        structural_result = AgentRunResult(
            suggestions_made=0, comments_made=1, transcript=[]
        )
        line_editor_result = AgentRunResult(
            suggestions_made=1, comments_made=0, transcript=[]
        )

        def fake_run_single_agent_loop(
            **kwargs: Any,
        ) -> AgentRunResult:
            if kwargs["allowed_categories"] == STRUCTURAL_CATEGORIES:
                return structural_result
            return line_editor_result

        mock_loop = mocker.patch(
            "verbatim.orchestrator._run_single_agent_loop",
            side_effect=fake_run_single_agent_loop,
        )
        merged_result = AgentRunResult(
            suggestions_made=1, comments_made=1, transcript=[]
        )
        mock_reconcile = mocker.patch(
            "verbatim.orchestrator.reconcile_findings", return_value=merged_result
        )

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        assert result is merged_result
        assert mock_loop.call_count == 2
        all_kwargs = [call.kwargs for call in mock_loop.call_args_list]
        structural_kwargs = next(
            kw for kw in all_kwargs if kw["allowed_categories"] == STRUCTURAL_CATEGORIES
        )
        line_editor_kwargs = next(
            kw
            for kw in all_kwargs
            if kw["allowed_categories"] == LINE_EDITOR_CATEGORIES
        )
        assert structural_kwargs["llm_client"] is llm_client
        assert line_editor_kwargs["llm_client"] is llm_client.new_instance.return_value
        llm_client.new_instance.assert_called_once()
        mock_reconcile.assert_called_once_with(structural_result, line_editor_result)

    def test_fetches_document_and_campaign_exactly_once(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
        mocker: MockerFixture,
    ) -> None:
        """Reads happen once up front, shared by both specialist prompts."""
        mocker.patch(
            "verbatim.orchestrator._run_single_agent_loop",
            return_value=AgentRunResult(
                suggestions_made=0, comments_made=0, transcript=[]
            ),
        )
        mocker.patch(
            "verbatim.orchestrator.reconcile_findings",
            return_value=AgentRunResult(
                suggestions_made=0, comments_made=0, transcript=[]
            ),
        )

        run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        docs_client.get_document_content.assert_called_once_with("doc-id")
        docs_client.get_campaign_context.assert_called_once_with("brief-id")


class TestRunAgentLineEditorResilience:
    """Coverage for the Line-Editor agent returning zero tool calls.

    Simulates a transient LLM failure/empty response -- the adversarial Eval
    Card fixture's forced-failure scenario (see
    `presentation/demo/eval-card-expected-output.md`): the Structural agent
    finds something, the Line-Editor agent's only round returns no tool
    calls at all. Unlike `TestRunAgentSpecialistDispatch` above, this runs
    the real `_run_single_agent_loop` for both specialists (only
    `llm_client.complete_chat` is mocked), so it also confirms `run_agent`
    doesn't crash on this path.
    """

    def test_returns_valid_result_when_line_editor_finds_nothing(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
    ) -> None:
        """Structural's finding survives; Line-Editor's zero is a clean gap."""
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
            _tool_call_result(comment_call),  # Structural round 1: one comment
            _no_tool_calls_result(),  # Structural round 2: done
        ]
        # Line-Editor runs concurrently on its own AnthropicClient instance
        # (agent.py's run_agent calls llm_client.new_instance() for it), not
        # the shared mock above -- its "nothing at all" response has to be
        # configured on that instance, or the default MagicMock stub's
        # truthy .tool_calls never breaks the loop and it spins to the round
        # cap instead.
        llm_client.new_instance.return_value.complete_chat.return_value = (
            _no_tool_calls_result()
        )

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        assert result.comments_made == 1
        assert result.suggestions_made == 0
        assert result.category_counts == {"information_hierarchy": 1}
        assert "readability" not in result.category_counts
        assert "tone_drift" not in result.category_counts
        assert result.stopped_due_to_max_rounds is False


class TestRunAgentSpecialistFailure:
    """Coverage for #63: one specialist's thread raising after the other's

    completed successfully -- its writes are already live in the doc, so
    discarding its result via unconditional fail-fast would misreport a
    doc-touching run as a total failure. See #63 for the full writeup.
    """

    def test_returns_partial_result_when_one_specialist_fails(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
        mocker: MockerFixture,
    ) -> None:
        """The surviving specialist's result is still returned, annotated."""
        line_editor_result = AgentRunResult(
            suggestions_made=1, comments_made=0, transcript=[]
        )

        def fake_run_single_agent_loop(**kwargs: Any) -> AgentRunResult:
            if kwargs["allowed_categories"] == STRUCTURAL_CATEGORIES:
                raise RuntimeError("structural boom")
            return line_editor_result

        mocker.patch(
            "verbatim.orchestrator._run_single_agent_loop",
            side_effect=fake_run_single_agent_loop,
        )
        mock_reconcile = mocker.patch("verbatim.orchestrator.reconcile_findings")

        result = run_agent(
            docs_client=docs_client,
            llm_client=llm_client,
            document_id="doc-id",
            brief_id="brief-id",
            brand_guidelines=brand_guidelines,
        )

        mock_reconcile.assert_not_called()
        assert result.suggestions_made == 1
        assert result.comments_made == 0
        assert result.specialist_errors == {"structural": "structural boom"}

    def test_raises_when_both_specialists_fail(
        self,
        docs_client: MagicMock,
        llm_client: MagicMock,
        brand_guidelines: BrandGuidelines,
        mocker: MockerFixture,
    ) -> None:
        """No partial result is possible; the run failed outright."""

        def fake_run_single_agent_loop(**kwargs: Any) -> AgentRunResult:
            if kwargs["allowed_categories"] == STRUCTURAL_CATEGORIES:
                raise RuntimeError("structural boom")
            raise RuntimeError("line-editor boom")

        mocker.patch(
            "verbatim.orchestrator._run_single_agent_loop",
            side_effect=fake_run_single_agent_loop,
        )

        with pytest.raises(RuntimeError) as exc_info:
            run_agent(
                docs_client=docs_client,
                llm_client=llm_client,
                document_id="doc-id",
                brief_id="brief-id",
                brand_guidelines=brand_guidelines,
            )

        assert "structural boom" in str(exc_info.value)
        assert "line-editor boom" in str(exc_info.value)
