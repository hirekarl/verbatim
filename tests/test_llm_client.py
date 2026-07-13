"""Tests for the OpenRouter LLM client module."""

from types import SimpleNamespace
from typing import Any

import pytest
from openai import OpenAIError
from pytest_mock import MockerFixture

from verbatim.llm_client import (
    ChatCompletionResult,
    LLMClientError,
    MissingAPIKeyError,
    OpenRouterClient,
    ToolCall,
)


def _fake_tool_call(call_id: str, name: str, arguments: str) -> SimpleNamespace:
    """Build a fake SDK tool-call object with the given raw JSON arguments string."""
    return SimpleNamespace(
        id=call_id, function=SimpleNamespace(name=name, arguments=arguments)
    )


def _fake_response(
    content: str | None,
    tool_calls: list[SimpleNamespace] | None,
    dumped: dict[str, Any],
) -> SimpleNamespace:
    """Build a fake SDK ChatCompletion response with one choice/message."""
    message = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
        model_dump=lambda exclude_none=True: dumped,
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class TestFromEnv:
    """Tests for OpenRouterClient.from_env."""

    @pytest.fixture(autouse=True)
    def _mock_load_dotenv(self, mocker: MockerFixture) -> None:
        """Prevent a real .env file on disk from affecting these tests."""
        self.mock_load_dotenv = mocker.patch("verbatim.llm_client.load_dotenv")

    def test_raises_missing_api_key_error_when_env_var_is_unset(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no OPENROUTER_API_KEY set (and no .env providing one), it raises."""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        with pytest.raises(MissingAPIKeyError):
            OpenRouterClient.from_env(model="some/model")

    def test_builds_a_client_using_the_env_var_and_default_base_url(
        self, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
    ) -> None:
        """The OpenAI SDK client uses the env API key and OpenRouter's base URL."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        mock_openai = mocker.patch("verbatim.llm_client.OpenAI")

        client = OpenRouterClient.from_env(model="some/model")

        mock_openai.assert_called_once_with(
            api_key="sk-test", base_url="https://openrouter.ai/api/v1"
        )
        assert client._model == "some/model"

    def test_loads_dotenv_before_reading_the_api_key(
        self, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture
    ) -> None:
        """A .env file populating OPENROUTER_API_KEY is picked up via load_dotenv."""
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        mock_openai = mocker.patch("verbatim.llm_client.OpenAI")

        def _fake_load_dotenv(*args: Any, **kwargs: Any) -> bool:
            monkeypatch.setenv("OPENROUTER_API_KEY", "sk-from-dotenv")
            return True

        self.mock_load_dotenv.side_effect = _fake_load_dotenv

        OpenRouterClient.from_env(model="some/model")

        self.mock_load_dotenv.assert_called_once()
        mock_openai.assert_called_once_with(
            api_key="sk-from-dotenv", base_url="https://openrouter.ai/api/v1"
        )


class TestCompleteChat:
    """Tests for OpenRouterClient.complete_chat."""

    @pytest.fixture
    def mock_create(self, mocker: MockerFixture) -> Any:
        """The mocked chat.completions.create call on a patched OpenAI client."""
        mock_openai = mocker.patch("verbatim.llm_client.OpenAI")
        return mock_openai.return_value.chat.completions.create

    @pytest.fixture
    def client(self, mock_create: Any) -> OpenRouterClient:
        """An OpenRouterClient wired to the mocked OpenAI SDK client."""
        return OpenRouterClient(api_key="sk-test", model="some/model")

    def test_forwards_model_messages_and_tools_to_the_sdk_call(
        self, client: OpenRouterClient, mock_create: Any
    ) -> None:
        """The model, messages, and tools are passed straight through."""
        mock_create.return_value = _fake_response("Looks good.", None, {})
        messages = [{"role": "system", "content": "You are Verbatim."}]
        tools = [{"type": "function", "function": {"name": "create_suggestion"}}]

        client.complete_chat(messages=messages, tools=tools)

        mock_create.assert_called_once_with(
            model="some/model", messages=messages, tools=tools, max_tokens=4096
        )

    def test_forwards_custom_max_tokens_to_the_sdk_call(
        self, client: OpenRouterClient, mock_create: Any
    ) -> None:
        """A custom max_tokens limit is passed straight through to the SDK."""
        mock_create.return_value = _fake_response("Looks good.", None, {})
        client.complete_chat(messages=[], tools=[], max_tokens=1000)
        mock_create.assert_called_once_with(
            model="some/model", messages=[], tools=[], max_tokens=1000
        )

    def test_returns_content_only_result_when_the_model_makes_no_tool_calls(
        self, client: OpenRouterClient, mock_create: Any
    ) -> None:
        """A plain-text response has no tool calls."""
        mock_create.return_value = _fake_response(
            "Looks good.", None, {"role": "assistant", "content": "Looks good."}
        )

        result = client.complete_chat(messages=[], tools=[])

        assert result == ChatCompletionResult(
            content="Looks good.",
            tool_calls=[],
            raw_assistant_message={"role": "assistant", "content": "Looks good."},
        )

    def test_parses_a_single_tool_call_with_json_arguments(
        self, client: OpenRouterClient, mock_create: Any
    ) -> None:
        """A single tool call's JSON-string arguments are parsed into a dict."""
        tool_call = _fake_tool_call(
            "call_1",
            "create_suggestion",
            '{"matched_text": "feature", "replacement_text": "capability"}',
        )
        mock_create.return_value = _fake_response(None, [tool_call], {})

        result = client.complete_chat(messages=[], tools=[])

        assert result.tool_calls == [
            ToolCall(
                id="call_1",
                name="create_suggestion",
                arguments={
                    "matched_text": "feature",
                    "replacement_text": "capability",
                },
            )
        ]

    def test_parses_multiple_tool_calls_in_one_response(
        self, client: OpenRouterClient, mock_create: Any
    ) -> None:
        """Several tool calls in one response are all parsed and returned."""
        tool_calls = [
            _fake_tool_call("call_1", "create_suggestion", '{"matched_text": "a"}'),
            _fake_tool_call("call_2", "create_inline_comment", '{"matched_text": "b"}'),
        ]
        mock_create.return_value = _fake_response(None, tool_calls, {})

        result = client.complete_chat(messages=[], tools=[])

        assert [tc.id for tc in result.tool_calls] == ["call_1", "call_2"]
        assert [tc.name for tc in result.tool_calls] == [
            "create_suggestion",
            "create_inline_comment",
        ]

    def test_raises_llm_client_error_when_the_sdk_call_fails(
        self, client: OpenRouterClient, mock_create: Any
    ) -> None:
        """An OpenAI SDK error is wrapped as LLMClientError."""
        mock_create.side_effect = OpenAIError("request failed")

        with pytest.raises(LLMClientError):
            client.complete_chat(messages=[], tools=[])

    def test_raises_llm_client_error_on_malformed_tool_call_arguments(
        self, client: OpenRouterClient, mock_create: Any
    ) -> None:
        """Non-JSON tool-call arguments raise LLMClientError rather than crashing."""
        tool_call = _fake_tool_call("call_1", "create_suggestion", "{not valid json")
        mock_create.return_value = _fake_response(None, [tool_call], {})

        with pytest.raises(LLMClientError):
            client.complete_chat(messages=[], tools=[])


class TestNewInstance:
    """Tests for OpenRouterClient.new_instance."""

    def test_builds_a_distinct_client_with_the_same_credentials(
        self, mocker: MockerFixture
    ) -> None:
        """A second, independent client is built from the same credentials."""
        mock_openai = mocker.patch("verbatim.llm_client.OpenAI")
        client = OpenRouterClient(
            api_key="sk-test", model="some/model", base_url="https://example.test"
        )

        second = client.new_instance()

        assert second is not client
        assert second._model == client._model
        assert mock_openai.call_args_list == [
            mocker.call(api_key="sk-test", base_url="https://example.test"),
            mocker.call(api_key="sk-test", base_url="https://example.test"),
        ]
