"""Entrypoints for auditing a Google Doc: the multi-agent split and its legacy path."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Literal

from verbatim.brand_guidelines import BrandGuidelines
from verbatim.docs_client import CampaignContext, DocumentContent, GoogleDocsClient
from verbatim.evaluator import BrandGuidelinesEvaluator, Violation
from verbatim.llm_client import OpenRouterClient
from verbatim.prompt import TOOL_SCHEMAS, build_system_prompt
from verbatim.prompts.line_editor import (
    LINE_EDITOR_CATEGORIES,
    LINE_EDITOR_TOOL_SCHEMAS,
    build_line_editor_system_prompt,
)
from verbatim.prompts.shared import CATEGORIES
from verbatim.prompts.structural import (
    STRUCTURAL_CATEGORIES,
    STRUCTURAL_TOOL_SCHEMAS,
    build_structural_system_prompt,
)


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
    cross_agent_overlaps: list[tuple[Finding, Finding]] = field(default_factory=list)


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


def _fetch_shared_context(
    docs_client: GoogleDocsClient,
    document_id: str,
    brief_id: str,
    brand_guidelines: BrandGuidelines,
    target_channel: str | None,
) -> tuple[DocumentContent, CampaignContext, str, list[Violation]]:
    """Fetch the document/campaign and run the evaluator, exactly once.

    Shared by ``run_agent_legacy``'s single system prompt and ``run_agent``'s
    two specialist prompts -- both need the identical document, campaign,
    guidelines block, and deterministic violations list, per
    `MULTI_AGENT_PLAN.md`'s "Builds the shared context once" design.

    Returns:
        The (possibly refreshed, if a guidelines-missing warning comment was
        posted) document, the campaign context, the guidelines block to
        embed in a system prompt, and the deterministic violations list.
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
        violations: list[Violation] = []
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

    return document, campaign, guidelines_block, violations


def run_agent(
    docs_client: GoogleDocsClient,
    llm_client: OpenRouterClient,
    document_id: str,
    brief_id: str,
    brand_guidelines: BrandGuidelines,
    target_channel: str | None = None,
    max_tool_call_rounds: int = 20,
) -> AgentRunResult:
    """Run one audit as two concurrent specialist agents, then reconcile.

    Fetches the document, campaign brief, and brand guidelines exactly once,
    then dispatches the Structural agent (Information Hierarchy + CTA
    Cadence, comment-only) and the Line-Editor agent (Tone Drift +
    Readability, suggestion-only) concurrently on separate threads -- Phase
    2's dispatch per `MULTI_AGENT_PLAN.md`. Each specialist gets its own
    ``OpenRouterClient`` instance; ``docs_client``'s write methods hold their
    own lock, so it's safe to share across both. If either specialist's
    thread raises, that exception propagates immediately and the other's
    result is discarded without reconciling -- fail-fast, matching Phase 1's
    existing implicit behavior (a Structural failure already prevented
    Line-Editor from ever running).

    Args:
        docs_client: An authenticated GoogleDocsClient with write access.
        llm_client: An OpenRouterClient to run the Structural agent's
            conversation on; the Line-Editor agent gets its own via
            ``llm_client.new_instance()``.
        document_id: The Google Docs document ID to audit.
        brief_id: The Google Docs document ID of the campaign brief.
        brand_guidelines: The brand guidelines to inject into both prompts.
        target_channel: Optional channel (e.g. "email", "blog") to filter
            channel-specific brand guidelines by.
        max_tool_call_rounds: The maximum number of model round trips per
            specialist agent before that agent's run is stopped as a safety
            backstop.

    Returns:
        The merged outcome of both specialist agents' audit passes.
    """
    document, campaign, guidelines_block, violations = _fetch_shared_context(
        docs_client, document_id, brief_id, brand_guidelines, target_channel
    )

    structural_prompt = build_structural_system_prompt(
        guidelines_block, document, campaign, violations=violations
    )
    line_editor_prompt = build_line_editor_system_prompt(
        guidelines_block, document, campaign, violations=violations
    )
    line_editor_llm_client = llm_client.new_instance()

    # Deferred import: orchestrator.py imports Finding/AgentRunResult from
    # this module at load time, so importing it back at module level here
    # would be circular.
    from verbatim.orchestrator import _run_single_agent_loop, reconcile_findings

    with ThreadPoolExecutor(max_workers=2) as executor:
        structural_future = executor.submit(
            _run_single_agent_loop,
            docs_client=docs_client,
            llm_client=llm_client,
            document_id=document_id,
            system_prompt=structural_prompt,
            tool_schemas=STRUCTURAL_TOOL_SCHEMAS,
            allowed_categories=STRUCTURAL_CATEGORIES,
            max_tool_call_rounds=max_tool_call_rounds,
        )
        line_editor_future = executor.submit(
            _run_single_agent_loop,
            docs_client=docs_client,
            llm_client=line_editor_llm_client,
            document_id=document_id,
            system_prompt=line_editor_prompt,
            tool_schemas=LINE_EDITOR_TOOL_SCHEMAS,
            allowed_categories=LINE_EDITOR_CATEGORIES,
            max_tool_call_rounds=max_tool_call_rounds,
        )
        structural_result = structural_future.result()
        line_editor_result = line_editor_future.result()

    return reconcile_findings(structural_result, line_editor_result)


def run_agent_legacy(
    docs_client: GoogleDocsClient,
    llm_client: OpenRouterClient,
    document_id: str,
    brief_id: str,
    brand_guidelines: BrandGuidelines,
    target_channel: str | None = None,
    max_tool_call_rounds: int = 20,
) -> AgentRunResult:
    """Run one single-pass audit conversation over a document (pre-split).

    The original single-agent path: one system prompt covering all 4
    subjective categories, one tool-calling loop against both
    ``create_suggestion`` and ``create_inline_comment``. Kept alongside the
    new ``run_agent`` (not deleted) so the Tue Jul 14 Eval Card validation
    can compare the two paths' output before flipping the default -- see
    `MULTI_AGENT_PLAN.md`.

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
    document, campaign, guidelines_block, violations = _fetch_shared_context(
        docs_client, document_id, brief_id, brand_guidelines, target_channel
    )
    system_prompt = build_system_prompt(
        guidelines_block, document, campaign, violations=violations
    )

    from verbatim.orchestrator import _run_single_agent_loop

    return _run_single_agent_loop(
        docs_client=docs_client,
        llm_client=llm_client,
        document_id=document_id,
        system_prompt=system_prompt,
        tool_schemas=TOOL_SCHEMAS,
        allowed_categories=CATEGORIES,
        max_tool_call_rounds=max_tool_call_rounds,
    )
