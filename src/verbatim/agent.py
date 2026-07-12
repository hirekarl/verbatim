"""Single-pass tool-calling agent loop for auditing a Google Doc."""

from dataclasses import dataclass, field
from typing import Any, Literal

from verbatim.brand_guidelines import BrandGuidelines
from verbatim.docs_client import DocsClientError, GoogleDocsClient
from verbatim.evaluator import BrandGuidelinesEvaluator
from verbatim.llm_client import OpenRouterClient, ToolCall
from verbatim.prompt import TOOL_SCHEMAS, build_system_prompt
from verbatim.prompts.shared import CATEGORIES, validate_category


@dataclass(frozen=True)
class Finding:
    """One issue the agent actually posted to the document.

    ``detail`` is the suggestion's ``rationale`` or the comment's own text --
    either way, the human-readable explanation of what was wrong, for
    display on a results screen (CLI summary, Add-on results card).
    """

    category: str
    kind: Literal["suggestion", "comment"]
    matched_text: str
    detail: str


@dataclass(frozen=True)
class AgentRunResult:
    """The outcome of one single-pass audit run."""

    suggestions_made: int
    comments_made: int
    transcript: list[dict[str, Any]]
    stopped_due_to_max_rounds: bool = False
    category_counts: dict[str, int] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)


def _find_anchor_text(body_text: str) -> str | None:
    """Find a unique substring in body_text to anchor a warning comment on."""
    if not body_text:
        return None
    # Try lines/paragraphs first
    paragraphs = [p.strip() for p in body_text.split("\n") if p.strip()]
    for p in paragraphs:
        if body_text.count(p) == 1:
            return p
    # If no whole paragraph is unique, try sentences or words
    words = body_text.split()
    for w in words:
        if body_text.count(w) == 1:
            return w
    # Fallback to the first 20 characters if unique
    if len(body_text) >= 20:
        candidate = body_text[:20]
        if body_text.count(candidate) == 1:
            return candidate
    return None


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

    if not brand_guidelines.is_valid:
        warning_msg = (
            f"Warning: Brand guidelines file "
            f"'{brand_guidelines.filepath.name}' is missing or corrupt "
            f"({brand_guidelines.error_message}). "
            f"Audit conducted using only the Campaign Brief."
        )
        anchor = _find_anchor_text(document.body_text)
        if anchor:
            try:
                docs_client.create_inline_comment(
                    document_id=document_id,
                    matched_text=anchor,
                    comment=warning_msg,
                )
                # Clear cache and refetch because document has been updated
                docs_client.clear_cache(document_id)
                document = docs_client.get_document_content(document_id)
            except Exception:
                pass

        guidelines_block = (
            "=== BRAND VOICE & STYLE GUIDELINES ===\n"
            "[WARNING] Brand voice and style guidelines are unavailable because "
            "the guidelines file is missing or invalid. Evaluate the document "
            "against the Campaign Brief and common-sense copywriting rules only."
        )
        violations = []
    else:
        guidelines_block = brand_guidelines.format_for_llm_prompt(
            target_channel=target_channel
        )
        evaluator = BrandGuidelinesEvaluator(
            guidelines_path=str(brand_guidelines.filepath)
        )
        violations = evaluator.evaluate(
            document.body_text,
            channel=target_channel,
            headings=document.headings,
            title=document.title,
        )

    system_prompt = build_system_prompt(
        guidelines_block, document, campaign, violations=violations
    )

    messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    suggestions_made = 0
    comments_made = 0
    category_counts: dict[str, int] = {}
    findings: list[Finding] = []
    stopped_due_to_max_rounds = True
    # Tracks (tool_name, matched_text) pairs already dispatched, so the model
    # re-flagging the same span in a later round (e.g. once during its
    # overall-structure pass, again during its paragraph-by-paragraph pass)
    # doesn't produce duplicate comments/suggestions on the same text.
    seen_spans: set[tuple[str, str]] = set()

    for _round in range(max_tool_call_rounds):
        result = llm_client.complete_chat(messages=messages, tools=TOOL_SCHEMAS)
        messages.append(result.raw_assistant_message)

        if not result.tool_calls:
            stopped_due_to_max_rounds = False
            break

        for tool_call in result.tool_calls:
            outcome, made_suggestion, made_comment, finding = _dispatch_tool_call(
                docs_client, document_id, tool_call, seen_spans
            )
            suggestions_made += made_suggestion
            comments_made += made_comment
            if finding is not None:
                category_counts[finding.category] = (
                    category_counts.get(finding.category, 0) + 1
                )
                findings.append(finding)
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
        category_counts=category_counts,
        findings=findings,
    )


def _dispatch_tool_call(
    docs_client: GoogleDocsClient,
    document_id: str,
    tool_call: ToolCall,
    seen_spans: set[tuple[str, str]],
) -> tuple[str, int, int, Finding | None]:
    """Dispatch one tool call to GoogleDocsClient, returning a tool-result message.

    Args:
        docs_client: The client to dispatch the write to.
        document_id: The document being audited.
        tool_call: The model's requested tool call.
        seen_spans: (tool_name, matched_text) pairs already dispatched this
            run; a repeat is skipped rather than posted again, since the
            model re-visits the same span across its structure pass and its
            paragraph-by-paragraph pass.

    Returns:
        A tuple of (result text for the model, suggestions made, comments
        made, finding). ``finding`` is set on a real successful dispatch, or
        ``None`` on any skip/error/unknown-tool branch. Neither the schema's
        ``required`` list nor its ``category`` ``enum`` is hard-enforced by
        OpenRouter/OpenAI-style function calling, so a dispatched call's
        ``category`` is run through ``validate_category`` -- missing or not
        one of the 7 known categories both fall back to ``"uncategorized"``
        -- and a call missing ``rationale`` falls back to an empty detail,
        rather than raising. DocsClientError failures are caught and
        surfaced as result text rather than raised, giving the model a
        chance to retry in the same run.
    """
    try:
        if tool_call.name == "create_suggestion":
            matched = tool_call.arguments["matched_text"]
            replacement = tool_call.arguments["replacement_text"]
            if matched == replacement:
                return (
                    "Suggestion matches existing text; no change needed.",
                    0,
                    0,
                    None,
                )
            span_key = (tool_call.name, matched)
            if span_key in seen_spans:
                return "Already flagged this text; skipping duplicate.", 0, 0, None
            docs_client.create_suggestion(
                document_id=document_id,
                matched_text=matched,
                replacement_text=replacement,
            )
            seen_spans.add(span_key)
            finding = Finding(
                category=validate_category(
                    tool_call.arguments.get("category"), CATEGORIES
                ),
                kind="suggestion",
                matched_text=matched,
                detail=tool_call.arguments.get("rationale", ""),
            )
            return "Suggestion created.", 1, 0, finding
        if tool_call.name == "create_inline_comment":
            matched = tool_call.arguments["matched_text"]
            span_key = (tool_call.name, matched)
            if span_key in seen_spans:
                return "Already flagged this text; skipping duplicate.", 0, 0, None
            comment = tool_call.arguments["comment"]
            docs_client.create_inline_comment(
                document_id=document_id,
                matched_text=matched,
                comment=comment,
            )
            seen_spans.add(span_key)
            finding = Finding(
                category=validate_category(
                    tool_call.arguments.get("category"), CATEGORIES
                ),
                kind="comment",
                matched_text=matched,
                detail=comment,
            )
            return "Comment created.", 0, 1, finding
        return f"Unknown tool: {tool_call.name}", 0, 0, None
    except DocsClientError as err:
        return f"Error: {err}", 0, 0, None
