"""Tests for the Anthropic LLM client module."""

import logging
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from anthropic import APIConnectionError, APIStatusError, RateLimitError
from pytest_mock import MockerFixture

from verbatim.llm_client import (
    AnthropicClient,
    ChatCompletionResult,
    LLMClientError,
    MissingAPIKeyError,
    ToolCall,
    _ipv4_only_http_client,
)

_FAKE_REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def _fake_text_block(text: str) -> SimpleNamespace:
    """Build a fake SDK text content block."""
    return SimpleNamespace(
        type="text",
        text=text,
        model_dump=lambda exclude_none=True: {"type": "text", "text": text},
    )


def _fake_tool_use_block(
    call_id: str, name: str, arguments: dict[str, Any]
) -> SimpleNamespace:
    """Build a fake SDK tool_use content block with already-parsed input."""
    return SimpleNamespace(
        type="tool_use",
        id=call_id,
        name=name,
        input=arguments,
        model_dump=lambda exclude_none=True: {
            "type": "tool_use",
            "id": call_id,
            "name": name,
            "input": arguments,
        },
    )


def _fake_response(content: list[SimpleNamespace]) -> SimpleNamespace:
    """Build a fake SDK Message response with the given content blocks."""
    return SimpleNamespace(content=content)


class TestIpv4OnlyHttpClient:
    """Tests for the IPv4-forcing httpx.Client builder."""

    def test_binds_to_a_literal_ipv4_address_to_force_the_v4_stack(self) -> None:
        """The transport binds to 0.0.0.0 -- httpx's documented IPv4-only trick.

        Cloud Run's default (non-VPC) networking has no outbound IPv6 route,
        but api.anthropic.com resolves to both an A and an AAAA record; left
        alone, httpx can pick the unreachable IPv6 address and fail the
        connection outright instead of falling back to IPv4.
        """
        client = _ipv4_only_http_client()

        transport = client._transport
        assert isinstance(transport, httpx.HTTPTransport)
        assert transport._pool._local_address == "0.0.0.0"


class TestFromEnv:
    """Tests for AnthropicClient.from_env."""

    @pytest.fixture(autouse=True)
    def _mock_load_dotenv(self, mocker: MockerFixture) -> None:
        """Prevent a real .env file on disk from affecting these tests."""
        self.mock_load_dotenv = mocker.patch("verbatim.llm_client.load_dotenv")

    def test_raises_missing_api_key_error_when_env_var_is_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no ANTHROPIC_API_KEY set (and no .env providing one), it raises."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        with pytest.raises(MissingAPIKeyError):
            AnthropicClient.from_env(model="claude-sonnet-5")

    def test_builds_a_client_using_the_env_var(
        self, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
    ) -> None:
        """The Anthropic SDK client is constructed with the env API key."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        mock_anthropic = mocker.patch("verbatim.llm_client.anthropic.Anthropic")

        client = AnthropicClient.from_env(model="claude-sonnet-5")

        assert mock_anthropic.call_count == 1
        kwargs = mock_anthropic.call_args.kwargs
        assert kwargs["api_key"] == "sk-ant-test"
        assert isinstance(kwargs["http_client"], httpx.Client)
        assert client._model == "claude-sonnet-5"

    def test_loads_dotenv_before_reading_the_api_key(
        self, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
    ) -> None:
        """A .env file populating ANTHROPIC_API_KEY is picked up via load_dotenv."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        mock_anthropic = mocker.patch("verbatim.llm_client.anthropic.Anthropic")

        def _fake_load_dotenv(*args: Any, **kwargs: Any) -> bool:
            monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-dotenv")
            return True

        self.mock_load_dotenv.side_effect = _fake_load_dotenv

        AnthropicClient.from_env(model="claude-sonnet-5")

        self.mock_load_dotenv.assert_called_once()
        assert mock_anthropic.call_count == 1
        kwargs = mock_anthropic.call_args.kwargs
        assert kwargs["api_key"] == "sk-ant-from-dotenv"
        assert isinstance(kwargs["http_client"], httpx.Client)


class TestCompleteChat:
    """Tests for AnthropicClient.complete_chat."""

    @pytest.fixture
    def mock_create(self, mocker: MockerFixture) -> Any:
        """The mocked messages.create call on a patched Anthropic client."""
        mock_anthropic = mocker.patch("verbatim.llm_client.anthropic.Anthropic")
        return mock_anthropic.return_value.messages.create

    @pytest.fixture
    def client(self, mock_create: Any) -> AnthropicClient:
        """An AnthropicClient wired to the mocked Anthropic SDK client."""
        return AnthropicClient(api_key="sk-ant-test", model="claude-sonnet-5")

    def test_forwards_system_messages_and_tools_to_the_sdk_call(
        self, client: AnthropicClient, mock_create: Any
    ) -> None:
        """The model, system, messages, and tools are passed straight through."""
        mock_create.return_value = _fake_response([_fake_text_block("Looks good.")])
        messages = [{"role": "user", "content": "Audit this."}]
        tools = [{"name": "create_suggestion", "input_schema": {}}]

        client.complete_chat(system="You are Verbatim.", messages=messages, tools=tools)

        mock_create.assert_called_once_with(
            model="claude-sonnet-5",
            max_tokens=4096,
            system=[
                {
                    "type": "text",
                    "text": "You are Verbatim.",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Audit this.",
                            "cache_control": {"type": "ephemeral"},
                        }
                    ],
                }
            ],
            tools=tools,
            thinking={"type": "disabled"},
        )

    def test_marks_the_system_prompt_as_ephemeral_cacheable(
        self, client: AnthropicClient, mock_create: Any
    ) -> None:
        """The system prompt gets a cache_control breakpoint.

        Every round of an agent's tool-calling loop resends the same system
        prompt (brand guidelines + document, unchanged for the life of the
        loop) -- marking it cacheable means round 2 onward reads it back at
        ~10% of input-token price instead of paying full price every round.
        """
        mock_create.return_value = _fake_response([_fake_text_block("ok")])

        client.complete_chat(system="A" * 5000, messages=[], tools=[])

        sent_system = mock_create.call_args.kwargs["system"]
        assert sent_system == [
            {
                "type": "text",
                "text": "A" * 5000,
                "cache_control": {"type": "ephemeral"},
            }
        ]

    def test_marks_only_the_last_message_blocks_last_entry_as_the_breakpoint(
        self, client: AnthropicClient, mock_create: Any
    ) -> None:
        """Only the newest message's last content block gets cache_control.

        A tool-calling loop resends the whole conversation every round since
        the Messages API is stateless. Moving the single breakpoint to the
        tail each round -- rather than leaving it on the first message --
        lets the read hit everything before it and extends the write to
        cover the newest turn too (the "Multi-turn conversations" placement
        pattern from shared/prompt-caching.md). Earlier messages are
        rendered in the same block-list shape but without cache_control, so
        their bytes stay identical round over round -- see the string vs.
        block-list note in ``test_forwards_system_messages_and_tools_to_the_sdk_call``.
        """
        mock_create.return_value = _fake_response([_fake_text_block("ok")])
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": "Begin your audit of the document."},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "toolu_1", "name": "x", "input": {}}
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_1",
                        "content": "Comment created.",
                    }
                ],
            },
        ]

        client.complete_chat(system="sys", messages=messages, tools=[])

        sent_messages = mock_create.call_args.kwargs["messages"]
        assert sent_messages[0] == {
            "role": "user",
            "content": [{"type": "text", "text": "Begin your audit of the document."}],
        }
        assert sent_messages[1] == {
            "role": "assistant",
            "content": [
                {"type": "tool_use", "id": "toolu_1", "name": "x", "input": {}}
            ],
        }
        assert sent_messages[2] == {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_1",
                    "content": "Comment created.",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }

    def test_does_not_mutate_the_caller_supplied_messages_list(
        self, client: AnthropicClient, mock_create: Any
    ) -> None:
        """The caller's messages list and dicts are left untouched.

        orchestrator.py keeps appending to the same list across rounds and
        returns it as ``AgentRunResult.transcript`` -- mutating it here would
        leak cache_control markers into that transcript.
        """
        mock_create.return_value = _fake_response([_fake_text_block("ok")])
        original: list[dict[str, Any]] = [
            {"role": "user", "content": [{"type": "text", "text": "hi"}]}
        ]

        client.complete_chat(system="sys", messages=original, tools=[])

        assert original == [
            {"role": "user", "content": [{"type": "text", "text": "hi"}]}
        ]

    def test_handles_an_empty_messages_list(
        self, client: AnthropicClient, mock_create: Any
    ) -> None:
        """No breakpoint to place when there's no last message to place it on."""
        mock_create.return_value = _fake_response([_fake_text_block("ok")])

        client.complete_chat(system="sys", messages=[], tools=[])

        assert mock_create.call_args.kwargs["messages"] == []

    def test_forwards_custom_max_tokens_to_the_sdk_call(
        self, client: AnthropicClient, mock_create: Any
    ) -> None:
        """A custom max_tokens limit is passed straight through to the SDK."""
        mock_create.return_value = _fake_response([_fake_text_block("Looks good.")])
        client.complete_chat(system="", messages=[], tools=[], max_tokens=1000)
        mock_create.assert_called_once_with(
            model="claude-sonnet-5",
            max_tokens=1000,
            system=[
                {
                    "type": "text",
                    "text": "",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[],
            tools=[],
            thinking={"type": "disabled"},
        )

    def test_returns_content_only_result_when_the_model_makes_no_tool_calls(
        self, client: AnthropicClient, mock_create: Any
    ) -> None:
        """A plain-text response has no tool calls."""
        mock_create.return_value = _fake_response([_fake_text_block("Looks good.")])

        result = client.complete_chat(system="", messages=[], tools=[])

        assert result == ChatCompletionResult(
            content="Looks good.",
            tool_calls=[],
            raw_assistant_message={
                "role": "assistant",
                "content": [{"type": "text", "text": "Looks good."}],
            },
        )

    def test_parses_a_single_tool_call_with_already_parsed_arguments(
        self, client: AnthropicClient, mock_create: Any
    ) -> None:
        """A single tool_use block's input dict is used directly, no JSON parsing."""
        block = _fake_tool_use_block(
            "toolu_1",
            "create_suggestion",
            {"matched_text": "feature", "replacement_text": "capability"},
        )
        mock_create.return_value = _fake_response([block])

        result = client.complete_chat(system="", messages=[], tools=[])

        assert result.tool_calls == [
            ToolCall(
                id="toolu_1",
                name="create_suggestion",
                arguments={
                    "matched_text": "feature",
                    "replacement_text": "capability",
                },
            )
        ]

    def test_parses_multiple_tool_calls_in_one_response(
        self, client: AnthropicClient, mock_create: Any
    ) -> None:
        """Several tool_use blocks in one response are all parsed and returned."""
        blocks = [
            _fake_tool_use_block("toolu_1", "create_suggestion", {"matched_text": "a"}),
            _fake_tool_use_block(
                "toolu_2", "create_inline_comment", {"matched_text": "b"}
            ),
        ]
        mock_create.return_value = _fake_response(blocks)

        result = client.complete_chat(system="", messages=[], tools=[])

        assert [tc.id for tc in result.tool_calls] == ["toolu_1", "toolu_2"]
        assert [tc.name for tc in result.tool_calls] == [
            "create_suggestion",
            "create_inline_comment",
        ]

    def test_returns_both_content_and_tool_calls_for_mixed_content(
        self, client: AnthropicClient, mock_create: Any
    ) -> None:
        """A response with both a text block and a tool_use block surfaces both."""
        mock_create.return_value = _fake_response(
            [
                _fake_text_block("Here's my suggestion."),
                _fake_tool_use_block(
                    "toolu_1", "create_suggestion", {"matched_text": "a"}
                ),
            ]
        )

        result = client.complete_chat(system="", messages=[], tools=[])

        assert result.content == "Here's my suggestion."
        assert len(result.tool_calls) == 1

    def test_raises_llm_client_error_on_connection_error(
        self, client: AnthropicClient, mock_create: Any
    ) -> None:
        """A network-level connection failure is wrapped as LLMClientError."""
        mock_create.side_effect = APIConnectionError(
            message="connection failed", request=_FAKE_REQUEST
        )

        with pytest.raises(LLMClientError):
            client.complete_chat(system="", messages=[], tools=[])

    def test_logs_the_underlying_exception_on_connection_error(
        self,
        client: AnthropicClient,
        mock_create: Any,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """The raw SDK/httpx error is logged with its traceback before wrapping.

        The wrapped LLMClientError message alone (just str(err)) has been too
        thin to diagnose real network failures -- e.g. distinguishing a DNS/
        IPv6-egress problem from a genuine outage. Logging the original
        exception (exc_info) preserves the full chain, including whatever
        httpx/httpcore attached as __cause__.
        """
        underlying = APIConnectionError(
            message="connection failed", request=_FAKE_REQUEST
        )
        mock_create.side_effect = underlying

        with (
            caplog.at_level(logging.ERROR, logger="verbatim.llm_client"),
            pytest.raises(LLMClientError),
        ):
            client.complete_chat(system="", messages=[], tools=[])

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.exc_info is not None
        assert record.exc_info[1] is underlying

    def test_raises_llm_client_error_on_rate_limit_error(
        self, client: AnthropicClient, mock_create: Any
    ) -> None:
        """A 429 rate-limit error is wrapped as LLMClientError."""
        response = httpx.Response(status_code=429, request=_FAKE_REQUEST)
        mock_create.side_effect = RateLimitError(
            "rate limited", response=response, body=None
        )

        with pytest.raises(LLMClientError):
            client.complete_chat(system="", messages=[], tools=[])

    def test_raises_llm_client_error_on_api_status_error(
        self, client: AnthropicClient, mock_create: Any
    ) -> None:
        """Any other non-2xx API error is wrapped as LLMClientError."""
        response = httpx.Response(status_code=500, request=_FAKE_REQUEST)
        mock_create.side_effect = APIStatusError(
            "server error", response=response, body=None
        )

        with pytest.raises(LLMClientError):
            client.complete_chat(system="", messages=[], tools=[])


class TestNewInstance:
    """Tests for AnthropicClient.new_instance."""

    def test_builds_a_distinct_client_with_the_same_credentials(
        self, mocker: MockerFixture
    ) -> None:
        """A second, independent client is built from the same credentials."""
        mock_anthropic = mocker.patch("verbatim.llm_client.anthropic.Anthropic")
        client = AnthropicClient(api_key="sk-ant-test", model="claude-sonnet-5")

        second = client.new_instance()

        assert second is not client
        assert second._model == client._model
        assert mock_anthropic.call_count == 2
        for call in mock_anthropic.call_args_list:
            assert call.kwargs["api_key"] == "sk-ant-test"
            assert isinstance(call.kwargs["http_client"], httpx.Client)
