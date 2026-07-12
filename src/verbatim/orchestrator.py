"""Multi-agent orchestration: per-specialist dispatch and result merging.

Phase 1 (sequential dispatch: Structural agent, then Line-Editor agent) lands
Mon Jul 13 per `TODO.md`. Today only locks the signatures below so
`reconcile_findings` has a stable contract to write tests against, and so
Christina's Sun Jul 12 work on `prompts/structural.py` isn't blocked on
anything in this file.
"""

from typing import Any

from verbatim.agent import AgentRunResult
from verbatim.docs_client import GoogleDocsClient
from verbatim.llm_client import OpenRouterClient


def _run_single_agent_loop(
    docs_client: GoogleDocsClient,
    llm_client: OpenRouterClient,
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
        llm_client: An OpenRouterClient to run the audit conversation on.
        document_id: The Google Docs document ID being audited.
        system_prompt: The specialist agent's assembled system prompt.
        tool_schemas: The specialist agent's restricted tool schema set.
        allowed_categories: This agent's own category vocabulary --
            ``STRUCTURAL_CATEGORIES`` or ``LINE_EDITOR_CATEGORIES``, not the
            full 7. The implementation must run each dispatched tool call's
            ``category`` argument through
            ``verbatim.prompts.shared.validate_category(category,
            allowed_categories)`` before constructing a ``Finding`` --
            mirroring ``agent.py``'s ``_dispatch_tool_call`` -- so a finding
            mistagged with a real category that belongs to the *other*
            specialist agent is caught, not just outright typos. See
            `MULTI_AGENT_PLAN.md`'s "Category validation" section.
        max_tool_call_rounds: The maximum number of model round trips before
            the run is stopped as a safety backstop.

    Returns:
        The outcome of this specialist agent's audit pass.

    Raises:
        NotImplementedError: Stub; implemented Mon Jul 13.
    """
    raise NotImplementedError


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

    Args:
        structural: The Structural agent's (Info Hierarchy + CTA Cadence) run
            result.
        line_editor: The Line-Editor agent's (Tone Drift + Readability) run
            result.

    Returns:
        One combined ``AgentRunResult`` representing both agents' output.

    Raises:
        NotImplementedError: Stub; implemented Mon Jul 13.
    """
    raise NotImplementedError
