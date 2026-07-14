"""Anthropic LLM client: a thin wrapper around the native Anthropic SDK."""

import os
from dataclasses import dataclass
from typing import Any, cast

import anthropic
from dotenv import load_dotenv

DEFAULT_MODEL = "claude-sonnet-5"


class LLMClientError(Exception):
    """Base exception for all llm_client failures."""


class MissingAPIKeyError(LLMClientError):
    """Raised when ANTHROPIC_API_KEY is not set in the environment."""


@dataclass(frozen=True)
class ToolCall:
    """A single tool call requested by the model, with parsed arguments."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ChatCompletionResult:
    """The parsed result of one chat-completion round."""

    content: str | None
    tool_calls: list[ToolCall]
    raw_assistant_message: dict[str, Any]


class AnthropicClient:
    """A chat-completions client targeting the native Anthropic Messages API."""

    def __init__(self, api_key: str, model: str) -> None:
        """Build a client for the given model, authenticated against Anthropic.

        Args:
            api_key: The Anthropic API key.
            model: The Claude model identifier to request completions from.
        """
        self._api_key = api_key
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    @classmethod
    def from_env(cls, model: str) -> "AnthropicClient":
        """Build a client using the ANTHROPIC_API_KEY environment variable.

        Loads a `.env` file first, if one is present (without overriding any
        already-exported environment variable), so ANTHROPIC_API_KEY can be
        set either way.

        Args:
            model: The Claude model identifier to request completions from.

        Returns:
            An AnthropicClient authenticated with the environment's API key.

        Raises:
            MissingAPIKeyError: ANTHROPIC_API_KEY is not set.
        """
        load_dotenv()
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise MissingAPIKeyError(
                "ANTHROPIC_API_KEY environment variable is not set"
            )
        return cls(api_key=api_key, model=model)

    def new_instance(self) -> "AnthropicClient":
        """Build a second, independent client sharing this one's credentials.

        Phase 2 concurrent dispatch runs the Structural and Line-Editor
        specialist agents on separate threads; each gets its own SDK client
        object rather than sharing one across threads.
        """
        return AnthropicClient(api_key=self._api_key, model=self._model)

    def complete_chat(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int = 4096,
    ) -> ChatCompletionResult:
        """Run one chat-completion request/response round.

        Args:
            system: The system prompt for this conversation. Anthropic takes
                this as a top-level request parameter, not a message with
                role "system" -- see orchestrator.py's message-building.
            messages: The conversation so far, in Anthropic Messages API
                format (``role`` of "user"/"assistant" only).
            tools: The tool schemas the model may invoke, in Anthropic's flat
                ``input_schema`` shape.
            max_tokens: The maximum number of tokens to generate. Defaults to
                4096.

        Returns:
            The response content (if any) and any tool calls the model made.

        Raises:
            LLMClientError: The request failed.
        """
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=cast(Any, messages),
                tools=cast(Any, tools),
            )
        except anthropic.APIConnectionError as err:
            raise LLMClientError(
                f"Anthropic chat completion request failed: network error: {err}"
            ) from err
        except anthropic.RateLimitError as err:
            raise LLMClientError(
                f"Anthropic chat completion request failed: rate limited: {err}"
            ) from err
        except anthropic.APIStatusError as err:
            raise LLMClientError(
                f"Anthropic chat completion request failed: {err}"
            ) from err

        content: str | None = None
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=cast(dict[str, Any], block.input),
                    )
                )

        return ChatCompletionResult(
            content=content,
            tool_calls=tool_calls,
            raw_assistant_message={
                "role": "assistant",
                "content": [
                    block.model_dump(exclude_none=True) for block in response.content
                ],
            },
        )
