"""Multi-agent orchestration: per-specialist dispatch and result merging."""

from typing import Any

from verbatim.agent import AgentRunResult, Finding
from verbatim.docs_client import DocsClientError, GoogleDocsClient
from verbatim.llm_client import AnthropicClient, ToolCall
from verbatim.prompts.shared import validate_category


def _dispatch_tool_call(
    docs_client: GoogleDocsClient,
    document_id: str,
    tool_call: ToolCall,
    seen_spans: set[tuple[str, str]],
    allowed_categories: list[str],
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
        allowed_categories: The calling agent's own category vocabulary --
            the full ``CATEGORIES`` for the legacy single-agent path, or a
            narrower per-specialist list (``STRUCTURAL_CATEGORIES``,
            ``LINE_EDITOR_CATEGORIES``) for the split agents.

    Returns:
        A tuple of (result text for the model, suggestions made, comments
        made, finding). ``finding`` is set on a real successful dispatch, or
        ``None`` on any skip/error/unknown-tool branch. Neither the schema's
        ``required`` list nor its ``category`` ``enum`` is hard-enforced by
        the model's tool-calling, so a dispatched call's ``category`` is run
        through ``validate_category`` against
        ``allowed_categories`` -- missing or not one of the caller's allowed
        categories both fall back to ``"uncategorized"`` -- and a call
        missing ``rationale`` falls back to an empty detail, rather than
        raising. DocsClientError failures are caught and surfaced as result
        text rather than raised, giving the model a chance to retry in the
        same run.
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
                    tool_call.arguments.get("category"), allowed_categories
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
                    tool_call.arguments.get("category"), allowed_categories
                ),
                kind="comment",
                matched_text=matched,
                detail=comment,
            )
            return "Comment created.", 0, 1, finding
        return f"Unknown tool: {tool_call.name}", 0, 0, None
    except DocsClientError as err:
        return f"Error: {err}", 0, 0, None


def _run_single_agent_loop(
    docs_client: GoogleDocsClient,
    llm_client: AnthropicClient,
    document_id: str,
    system_prompt: str,
    tool_schemas: list[dict[str, Any]],
    allowed_categories: list[str],
    max_tool_call_rounds: int = 20,
) -> AgentRunResult:
    """Run one tool-calling conversation for a single specialist agent.

    Generalizes today's ``agent.run_agent`` loop body to take an arbitrary
    system prompt and tool schema set, so both the Structural and
    Line-Editor agents can share one implementation.

    Args:
        docs_client: An authenticated GoogleDocsClient with write access.
        llm_client: An AnthropicClient to run the audit conversation on.
        document_id: The Google Docs document ID being audited.
        system_prompt: The specialist agent's assembled system prompt. Passed
            straight through to the Anthropic Messages API's top-level
            ``system`` parameter -- unlike OpenAI-style chat completions, it
            is never a message in ``messages`` itself.
        tool_schemas: The specialist agent's restricted tool schema set.
        allowed_categories: This agent's own category vocabulary --
            ``STRUCTURAL_CATEGORIES`` or ``LINE_EDITOR_CATEGORIES``, not the
            full 7. Threaded through to ``_dispatch_tool_call`` so a finding
            mistagged with a real category that belongs to the *other*
            specialist agent is caught, not just outright typos. See
            `MULTI_AGENT_PLAN.md`'s "Category validation" section.
        max_tool_call_rounds: The maximum number of model round trips before
            the run is stopped as a safety backstop.

    Returns:
        The outcome of this specialist agent's audit pass.
    """
    # Claude's Messages API rejects an empty `messages` list and requires the
    # first message to have role "user" -- unlike OpenAI-style chat
    # completions, which allowed a request carrying only the system message.
    # All of this agent's actual instructions/context live in system_prompt;
    # this is just the required kickoff turn.
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": "Begin your audit of the document."}
    ]
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
        result = llm_client.complete_chat(
            system=system_prompt, messages=messages, tools=tool_schemas
        )
        messages.append(result.raw_assistant_message)

        if not result.tool_calls:
            stopped_due_to_max_rounds = False
            break

        # All tool_result blocks produced from one assistant turn's tool
        # calls must land in a single user-role message -- returning them
        # across separate messages silently trains Claude to stop making
        # parallel tool calls.
        tool_results: list[dict[str, Any]] = []
        for tool_call in result.tool_calls:
            outcome, made_suggestion, made_comment, finding = _dispatch_tool_call(
                docs_client, document_id, tool_call, seen_spans, allowed_categories
            )
            suggestions_made += made_suggestion
            comments_made += made_comment
            if finding is not None:
                category_counts[finding.category] = (
                    category_counts.get(finding.category, 0) + 1
                )
                findings.append(finding)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call.id,
                    "content": outcome,
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return AgentRunResult(
        suggestions_made=suggestions_made,
        comments_made=comments_made,
        transcript=messages,
        stopped_due_to_max_rounds=stopped_due_to_max_rounds,
        category_counts=category_counts,
        findings=findings,
    )


def _spans_overlap(a: str, b: str) -> bool:
    """True if one matched_text span is a substring of the other (or equal)."""
    return a in b or b in a


def _find_cross_agent_overlaps(
    structural_findings: list[Finding], line_editor_findings: list[Finding]
) -> list[tuple[Finding, Finding]]:
    """Pair up Structural/Line-Editor findings whose matched_text spans overlap.

    Flags, doesn't resolve: see #58, where both specialists independently
    flagged the same three-word CTA with contradictory advice (relocate vs.
    reword in place). There's no way to know which finding should "win"
    without a reconciliation/critic agent -- deferred per
    `MULTI_AGENT_PLAN.md`'s "Why this split" pending more data than one
    adversarial-fixture occurrence. This just surfaces the overlap so a
    copywriter isn't handed silently-contradictory advice, and so future
    Eval Card runs have real data on how often it happens.

    Args:
        structural_findings: The Structural agent's findings.
        line_editor_findings: The Line-Editor agent's findings.

    Returns:
        (structural_finding, line_editor_finding) pairs whose matched_text
        spans overlap, in structural-findings order.
    """
    return [
        (structural_finding, line_editor_finding)
        for structural_finding in structural_findings
        for line_editor_finding in line_editor_findings
        if _spans_overlap(
            structural_finding.matched_text, line_editor_finding.matched_text
        )
    ]


def reconcile_findings(
    structural: AgentRunResult, line_editor: AgentRunResult
) -> AgentRunResult:
    """Merge the Structural and Line-Editor agents' results into one.

    Cross-agent span dedup is a non-issue by construction (the two agents
    never share a tool name), so this is a straight merge, not a dedup pass.
    Deliberately does not re-validate either input's categories: every
    ``Finding`` in ``structural``/``line_editor`` already passed through
    ``_run_single_agent_loop``'s ``validate_category`` call at dispatch
    time, so a category outside either agent's allowed set can't reach this
    function -- re-checking here would be validating data that can't be
    invalid by construction. See `MULTI_AGENT_PLAN.md`'s "Category
    validation" section.

    Cross-agent *content* overlap (both agents flagging the same or
    overlapping text) is a separate, real possibility this function does
    detect -- see ``_find_cross_agent_overlaps``.

    Args:
        structural: The Structural agent's (Info Hierarchy + CTA Cadence) run
            result.
        line_editor: The Line-Editor agent's (Tone Drift + Readability) run
            result.

    Returns:
        One combined ``AgentRunResult`` representing both agents' output.
    """
    category_counts = dict(structural.category_counts)
    for category, count in line_editor.category_counts.items():
        category_counts[category] = category_counts.get(category, 0) + count

    return AgentRunResult(
        suggestions_made=structural.suggestions_made + line_editor.suggestions_made,
        comments_made=structural.comments_made + line_editor.comments_made,
        transcript=structural.transcript + line_editor.transcript,
        stopped_due_to_max_rounds=(
            structural.stopped_due_to_max_rounds
            or line_editor.stopped_due_to_max_rounds
        ),
        category_counts=category_counts,
        findings=structural.findings + line_editor.findings,
        cross_agent_overlaps=_find_cross_agent_overlaps(
            structural.findings, line_editor.findings
        ),
    )
