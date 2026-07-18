"""Anthropic LLM client: a thin wrapper around the native Anthropic SDK."""

import logging
import os
from dataclasses import dataclass
from typing import Any, cast

import anthropic
import httpx
from dotenv import load_dotenv

DEFAULT_MODEL = "claude-sonnet-5"

logger = logging.getLogger(__name__)


def _render_message_content(
    content: str | list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Render a message's content in the API's canonical block-list form.

    A plain string is shorthand for a single text block. Normalizing every
    message to the list form -- not just the ones that already use it --
    keeps a given message's rendered bytes identical across rounds
    regardless of which message currently holds the cache breakpoint (see
    ``_with_cache_breakpoint``); a string one round and an equivalent block
    list the next would look like a changed prefix and silently miss the
    cache.
    """
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return [dict(block) for block in content]


def _with_cache_breakpoint(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Copy ``messages`` with an ephemeral cache breakpoint on the newest block.

    Each round of an agent's tool-calling loop resends the full conversation
    so far -- the Messages API is stateless. Moving the single breakpoint to
    the last block of the last message every round means round N reads back
    everything through round N-1's tail from cache (the shared prefix
    renders identically every time, per ``_render_message_content``) and
    only pays full price for what's new since then -- the "Multi-turn
    conversations" placement pattern from shared/prompt-caching.md. Returns a
    copy rather than mutating in place: ``orchestrator._run_single_agent_loop``
    keeps appending to and eventually returns this same list as
    ``AgentRunResult.transcript``, so mutating it here would leak
    cache_control markers into that transcript.
    """
    if not messages:
        return []
    rendered = [
        {**message, "content": _render_message_content(message["content"])}
        for message in messages
    ]
    last_content = rendered[-1]["content"]
    if last_content:
        last_content[-1] = {
            **last_content[-1],
            "cache_control": {"type": "ephemeral"},
        }
    return rendered


def _ipv4_only_http_client() -> httpx.Client:
    """Build an httpx.Client that only ever binds to an IPv4 local address.

    Hosted deployments (Cloud Run without a VPC connector) have no outbound
    IPv6 route, but api.anthropic.com resolves to both an A and an AAAA
    record. Left alone, httpx/httpcore can select the unreachable IPv6
    address and fail the connection outright rather than falling back to
    IPv4. Binding the transport to the literal address "0.0.0.0" is httpx's
    documented trick to force the IPv4 stack. See
    https://www.python-httpx.org/advanced/#binding-to-network-interfaces.
    """
    return httpx.Client(transport=httpx.HTTPTransport(local_address="0.0.0.0"))


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
        self._client = anthropic.Anthropic(
            api_key=api_key, http_client=_ipv4_only_http_client()
        )
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
                format (``role`` of "user"/"assistant" only). Sent with an
                ephemeral cache breakpoint on the newest message's last
                block -- see ``_with_cache_breakpoint``.
            tools: The tool schemas the model may invoke, in Anthropic's flat
                ``input_schema`` shape.
            max_tokens: The maximum number of tokens to generate. Defaults to
                4096.

        Returns:
            The response content (if any) and any tool calls the model made.

        Raises:
            LLMClientError: The request failed.
        """
        # Every round of an agent's tool-calling loop resends this same
        # system prompt (brand guidelines + document, unchanged for the life
        # of the loop) since the API is stateless -- marking it as an
        # ephemeral cache breakpoint means round 2 onward reads it back at
        # ~10% of input-token price instead of paying full price every round.
        cacheable_system: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        cacheable_messages = _with_cache_breakpoint(messages)
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=cast(Any, cacheable_system),
                messages=cast(Any, cacheable_messages),
                tools=cast(Any, tools),
                # Disable extended thinking for reliable tool use
                thinking={"type": "disabled"},
            )
        except anthropic.APIConnectionError as err:
            logger.exception("Anthropic chat completion request failed: network error")
            raise LLMClientError(
                f"Anthropic chat completion request failed: network error: {err}"
            ) from err
        except anthropic.RateLimitError as err:
            logger.exception("Anthropic chat completion request failed: rate limited")
            raise LLMClientError(
                f"Anthropic chat completion request failed: rate limited: {err}"
            ) from err
        except anthropic.APIStatusError as err:
            logger.exception(
                "Anthropic chat completion request failed: API status error"
            )
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
