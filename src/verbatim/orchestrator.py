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
