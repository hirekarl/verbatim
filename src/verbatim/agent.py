"""Single-pass tool-calling agent loop for auditing a Google Doc."""

from dataclasses import dataclass
from typing import Any

from verbatim.brand_guidelines import BrandGuidelines
from verbatim.docs_client import DocsClientError, GoogleDocsClient
from verbatim.llm_client import OpenRouterClient, ToolCall
from verbatim.prompt import TOOL_SCHEMAS, build_system_prompt


@dataclass(frozen=True)
class AgentRunResult:
    """The outcome of one single-pass audit run."""

    suggestions_made: int
    comments_made: int
    transcript: list[dict[str, Any]]
    stopped_due_to_max_rounds: bool = False


def run_agent(
    docs_client: GoogleDocsClient,
    llm_client: OpenRouterClient,
    document_id: str,
    brief_id: str,
    brand_guidelines: BrandGuidelines,
    target_channel: str | None = None,
    max_tool_call_rounds: int = 20,
) -> AgentRunResult:
    """Run one single-pass audit conversation over a document.

    Fetches the document, campaign brief, and brand guidelines exactly once,
    then runs a tool-calling conversation until the model stops requesting
    tools (or ``max_tool_call_rounds`` is exhausted, as a backstop against a
    non-terminating conversation).

    Args:
        docs_client: An authenticated GoogleDocsClient with write access.
        llm_client: An OpenRouterClient to run the audit conversation on.
        document_id: The Google Docs document ID to audit.
        brief_id: The Google Docs document ID of the campaign brief.
        brand_guidelines: The brand guidelines to inject into the prompt.
        target_channel: Optional channel (e.g. "email", "blog") to filter
            channel-specific brand guidelines by.
        max_tool_call_rounds: The maximum number of model round trips before
            the run is stopped as a safety backstop.

    Returns:
        The number of suggestions/comments posted and the full transcript.
    """
    document = docs_client.get_document_content(document_id)
    campaign = docs_client.get_campaign_context(brief_id)
    guidelines_block = brand_guidelines.format_for_llm_prompt(
        target_channel=target_channel
    )
    system_prompt = build_system_prompt(guidelines_block, document, campaign)

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    suggestions_made = 0
    comments_made = 0
    stopped_due_to_max_rounds = True

    for _round in range(max_tool_call_rounds):
        result = llm_client.complete_chat(messages=messages, tools=TOOL_SCHEMAS)
        messages.append(result.raw_assistant_message)

        if not result.tool_calls:
            stopped_due_to_max_rounds = False
            break

        for tool_call in result.tool_calls:
            outcome, made_suggestion, made_comment = _dispatch_tool_call(
                docs_client, document_id, tool_call
            )
            suggestions_made += made_suggestion
            comments_made += made_comment
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": outcome,
                }
            )

    return AgentRunResult(
        suggestions_made=suggestions_made,
        comments_made=comments_made,
        transcript=messages,
        stopped_due_to_max_rounds=stopped_due_to_max_rounds,
    )


def _dispatch_tool_call(
    docs_client: GoogleDocsClient, document_id: str, tool_call: ToolCall
) -> tuple[str, int, int]:
    """Dispatch one tool call to GoogleDocsClient, returning a tool-result message.

    Args:
        docs_client: The client to dispatch the write to.
        document_id: The document being audited.
        tool_call: The model's requested tool call.

    Returns:
        A tuple of (result text for the model, suggestions made, comments made).
        DocsClientError failures are caught and surfaced as result text rather
        than raised, giving the model a chance to retry in the same run.
    """
    try:
        if tool_call.name == "create_suggestion":
            docs_client.create_suggestion(
                document_id=document_id,
                matched_text=tool_call.arguments["matched_text"],
                replacement_text=tool_call.arguments["replacement_text"],
            )
            return "Suggestion created.", 1, 0
        if tool_call.name == "create_inline_comment":
            docs_client.create_inline_comment(
                document_id=document_id,
                matched_text=tool_call.arguments["matched_text"],
                comment=tool_call.arguments["comment"],
            )
            return "Comment created.", 0, 1
        return f"Unknown tool: {tool_call.name}", 0, 0
    except DocsClientError as err:
        return f"Error: {err}", 0, 0
