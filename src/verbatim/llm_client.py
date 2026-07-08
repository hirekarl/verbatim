"""OpenRouter LLM client: a thin wrapper around the OpenAI-compatible chat API."""

import json
import os
from dataclasses import dataclass
from typing import Any, cast

from dotenv import load_dotenv
from openai import OpenAI, OpenAIError

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class LLMClientError(Exception):
    """Base exception for all llm_client failures."""


class MissingAPIKeyError(LLMClientError):
    """Raised when OPENROUTER_API_KEY is not set in the environment."""


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


class OpenRouterClient:
    """A chat-completions client targeting OpenRouter via the OpenAI SDK."""

    def __init__(
        self, api_key: str, model: str, base_url: str = DEFAULT_BASE_URL
    ) -> None:
        """Build a client for the given model, authenticated against OpenRouter.

        Args:
            api_key: The OpenRouter API key.
            model: The OpenRouter model identifier to request completions from.
            base_url: The OpenAI-compatible API base URL. Defaults to
                OpenRouter's endpoint.
        """
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model

    @classmethod
    def from_env(cls, model: str) -> "OpenRouterClient":
        """Build a client using the OPENROUTER_API_KEY environment variable.

        Loads a `.env` file first, if one is present (without overriding any
        already-exported environment variable), so OPENROUTER_API_KEY can be
        set either way.

        Args:
            model: The OpenRouter model identifier to request completions from.

        Returns:
            An OpenRouterClient authenticated with the environment's API key.

        Raises:
            MissingAPIKeyError: OPENROUTER_API_KEY is not set.
        """
        load_dotenv()
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise MissingAPIKeyError(
                "OPENROUTER_API_KEY environment variable is not set"
            )
        return cls(api_key=api_key, model=model)

    def complete_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int | None = 4096,
    ) -> ChatCompletionResult:
        """Run one chat-completion request/response round.

        Args:
            messages: The conversation so far, in OpenAI chat message format.
            tools: The function-calling tool schemas the model may invoke.
            max_tokens: The maximum number of tokens to generate. Defaults to 4096.

        Returns:
            The response content (if any) and any tool calls the model made.

        Raises:
            LLMClientError: The request failed, or a tool call's arguments
                weren't valid JSON.
        """
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=cast(Any, messages),
                tools=cast(Any, tools),
                max_tokens=max_tokens,
            )
        except OpenAIError as err:
            raise LLMClientError("OpenRouter chat completion request failed") from err

        message = response.choices[0].message
        tool_calls: list[ToolCall] = []
        # Only function-type tool calls are supported; TOOL_SCHEMAS never
        # declares custom tools, so the SDK's other tool-call variant is
        # never actually returned here.
        for tool_call in cast(list[Any], message.tool_calls or []):
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as err:
                raise LLMClientError(
                    "Model returned malformed tool-call arguments for "
                    f"{tool_call.function.name}"
                ) from err
            tool_calls.append(
                ToolCall(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=arguments,
                )
            )

        return ChatCompletionResult(
            content=message.content,
            tool_calls=tool_calls,
            raw_assistant_message=message.model_dump(exclude_none=True),
        )
