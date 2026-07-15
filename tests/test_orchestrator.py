"""Contract tests for orchestrator.reconcile_findings and _dispatch_tool_call.

Written against the `orchestrator.py` stub (`orchestrator.py`'s functions
currently `raise NotImplementedError`) as the TDD red step for Mon Jul 13's
Phase 1 implementation -- see `TODO.md` and `MULTI_AGENT_PLAN.md`.
"""

from unittest.mock import MagicMock

from verbatim.agent import AgentRunResult, Finding
from verbatim.llm_client import ToolCall
from verbatim.orchestrator import _dispatch_tool_call, reconcile_findings

_EMPTY = AgentRunResult(suggestions_made=0, comments_made=0, transcript=[])


class TestReconcileFindings:
    """Tests for reconcile_findings' merge of two AgentRunResults."""

    def test_sums_suggestions_made_across_both_agents(self) -> None:
        """Line-Editor's suggestions and Structural's (zero) are summed."""
        structural = AgentRunResult(suggestions_made=0, comments_made=2, transcript=[])
        line_editor = AgentRunResult(suggestions_made=3, comments_made=0, transcript=[])

        result = reconcile_findings(structural, line_editor)

        assert result.suggestions_made == 3

    def test_sums_comments_made_across_both_agents(self) -> None:
        """Structural's comments and Line-Editor's (zero) are summed."""
        structural = AgentRunResult(suggestions_made=0, comments_made=2, transcript=[])
        line_editor = AgentRunResult(suggestions_made=3, comments_made=0, transcript=[])

        result = reconcile_findings(structural, line_editor)

        assert result.comments_made == 2

    def test_merges_category_counts_by_summing_shared_keys(self) -> None:
        """Overlapping category keys are summed, not overwritten."""
        structural = AgentRunResult(
            suggestions_made=0,
            comments_made=2,
            transcript=[],
            category_counts={"information_hierarchy": 1, "cta_cadence": 1},
        )
        line_editor = AgentRunResult(
            suggestions_made=2,
            comments_made=0,
            transcript=[],
            category_counts={"tone_drift": 1, "cta_cadence": 1},
        )

        result = reconcile_findings(structural, line_editor)

        assert result.category_counts == {
            "information_hierarchy": 1,
            "cta_cadence": 2,
            "tone_drift": 1,
        }

    def test_concatenates_findings_structural_before_line_editor(self) -> None:
        """Findings are ordered structural-first, matching Phase 1's sequencing."""
        structural_finding = Finding(
            category="cta_cadence",
            kind="comment",
            matched_text="Buy now",
            detail="CTA appears before the value proposition.",
        )
        line_editor_finding = Finding(
            category="tone_drift",
            kind="suggestion",
            matched_text="ain't",
            detail="Too casual for this brand voice.",
        )
        structural = AgentRunResult(
            suggestions_made=0,
            comments_made=1,
            transcript=[],
            findings=[structural_finding],
        )
        line_editor = AgentRunResult(
            suggestions_made=1,
            comments_made=0,
            transcript=[],
            findings=[line_editor_finding],
        )

        result = reconcile_findings(structural, line_editor)

        assert result.findings == [structural_finding, line_editor_finding]

    def test_concatenates_transcripts_structural_before_line_editor(self) -> None:
        """Transcripts are ordered structural-first, matching Phase 1's sequencing."""
        structural = AgentRunResult(
            suggestions_made=0,
            comments_made=0,
            transcript=[{"role": "system", "content": "STRUCTURAL"}],
        )
        line_editor = AgentRunResult(
            suggestions_made=0,
            comments_made=0,
            transcript=[{"role": "system", "content": "LINE_EDITOR"}],
        )

        result = reconcile_findings(structural, line_editor)

        assert result.transcript == [
            {"role": "system", "content": "STRUCTURAL"},
            {"role": "system", "content": "LINE_EDITOR"},
        ]

    def test_stopped_due_to_max_rounds_true_when_structural_hit_the_cap(self) -> None:
        """Either agent hitting the round cap marks the merged result too."""
        structural = AgentRunResult(
            suggestions_made=0,
            comments_made=0,
            transcript=[],
            stopped_due_to_max_rounds=True,
        )
        line_editor = AgentRunResult(
            suggestions_made=0,
            comments_made=0,
            transcript=[],
            stopped_due_to_max_rounds=False,
        )

        result = reconcile_findings(structural, line_editor)

        assert result.stopped_due_to_max_rounds is True

    def test_stopped_due_to_max_rounds_true_when_line_editor_hit_the_cap(self) -> None:
        """Either agent hitting the round cap marks the merged result too."""
        structural = AgentRunResult(
            suggestions_made=0,
            comments_made=0,
            transcript=[],
            stopped_due_to_max_rounds=False,
        )
        line_editor = AgentRunResult(
            suggestions_made=0,
            comments_made=0,
            transcript=[],
            stopped_due_to_max_rounds=True,
        )

        result = reconcile_findings(structural, line_editor)

        assert result.stopped_due_to_max_rounds is True

    def test_stopped_due_to_max_rounds_false_when_neither_hit_the_cap(self) -> None:
        """Only False when both agents terminated cleanly."""
        structural = AgentRunResult(
            suggestions_made=0,
            comments_made=0,
            transcript=[],
            stopped_due_to_max_rounds=False,
        )
        line_editor = AgentRunResult(
            suggestions_made=0,
            comments_made=0,
            transcript=[],
            stopped_due_to_max_rounds=False,
        )

        result = reconcile_findings(structural, line_editor)

        assert result.stopped_due_to_max_rounds is False

    def test_merging_two_empty_results_yields_an_empty_result(self) -> None:
        """Baseline: nothing in, nothing out."""
        result = reconcile_findings(_EMPTY, _EMPTY)

        assert result.suggestions_made == 0
        assert result.comments_made == 0
        assert result.transcript == []
        assert result.category_counts == {}
        assert result.findings == []
        assert result.stopped_due_to_max_rounds is False
        assert result.cross_agent_overlaps == []

    def test_flags_identical_matched_text_across_agents_as_an_overlap(self) -> None:
        """Both agents flagging the exact same span is surfaced, not resolved.

        See #58: Structural and Line-Editor independently flagged the same
        three words with conflicting advice (relocate vs. reword in place).
        reconcile_findings doesn't adjudicate which one "wins" -- it just
        surfaces the overlap so a copywriter (or a future Eval Card pass)
        can see it happened.
        """
        structural_finding = Finding(
            category="cta_cadence",
            kind="comment",
            matched_text="Upgrade your plan.",
            detail="This CTA is premature.",
        )
        line_editor_finding = Finding(
            category="tone_drift",
            kind="suggestion",
            matched_text="Upgrade your plan.",
            detail="Soften the abrupt command.",
        )
        structural = AgentRunResult(
            suggestions_made=0,
            comments_made=1,
            transcript=[],
            findings=[structural_finding],
        )
        line_editor = AgentRunResult(
            suggestions_made=1,
            comments_made=0,
            transcript=[],
            findings=[line_editor_finding],
        )

        result = reconcile_findings(structural, line_editor)

        assert result.cross_agent_overlaps == [
            (structural_finding, line_editor_finding)
        ]

    def test_flags_one_matched_text_containing_the_other_as_an_overlap(self) -> None:
        """A span overlap doesn't require an exact match, just containment."""
        structural_finding = Finding(
            category="information_hierarchy",
            kind="comment",
            matched_text="Upgrade your plan. Explore your options today.",
            detail="Reorder this paragraph.",
        )
        line_editor_finding = Finding(
            category="tone_drift",
            kind="suggestion",
            matched_text="Upgrade your plan.",
            detail="Soften the abrupt command.",
        )
        structural = AgentRunResult(
            suggestions_made=0,
            comments_made=1,
            transcript=[],
            findings=[structural_finding],
        )
        line_editor = AgentRunResult(
            suggestions_made=1,
            comments_made=0,
            transcript=[],
            findings=[line_editor_finding],
        )

        result = reconcile_findings(structural, line_editor)

        assert result.cross_agent_overlaps == [
            (structural_finding, line_editor_finding)
        ]

    def test_does_not_flag_disjoint_spans_as_an_overlap(self) -> None:
        """Findings on unrelated text aren't reported as overlapping."""
        structural_finding = Finding(
            category="cta_cadence",
            kind="comment",
            matched_text="Buy now",
            detail="CTA appears before the value proposition.",
        )
        line_editor_finding = Finding(
            category="tone_drift",
            kind="suggestion",
            matched_text="ain't",
            detail="Too casual for this brand voice.",
        )
        structural = AgentRunResult(
            suggestions_made=0,
            comments_made=1,
            transcript=[],
            findings=[structural_finding],
        )
        line_editor = AgentRunResult(
            suggestions_made=1,
            comments_made=0,
            transcript=[],
            findings=[line_editor_finding],
        )

        result = reconcile_findings(structural, line_editor)

        assert result.cross_agent_overlaps == []


class TestDispatchToolCall:
    """Tests for _dispatch_tool_call's error handling."""

    def test_returns_error_message_when_matched_text_missing_from_suggestion(
        self,
    ) -> None:
        """A malformed create_suggestion call missing matched_text returns an error."""
        docs_client = MagicMock()
        tool_call = ToolCall(
            id="call_1",
            name="create_suggestion",
            # missing matched_text
            arguments={"replacement_text": "new text", "rationale": "fix"},
        )

        result, suggestions, comments, finding = _dispatch_tool_call(
            docs_client=docs_client,
            document_id="doc-id",
            tool_call=tool_call,
            seen_spans=set(),
            allowed_categories=["tone_drift", "readability"],
        )

        assert "Missing required field" in result
        assert "'matched_text'" in result
        assert suggestions == 0
        assert comments == 0
        assert finding is None
        docs_client.create_suggestion.assert_not_called()

    def test_returns_error_message_when_replacement_text_missing_from_suggestion(
        self,
    ) -> None:
        """Malformed create_suggestion missing replacement_text returns an error."""
        docs_client = MagicMock()
        tool_call = ToolCall(
            id="call_1",
            name="create_suggestion",
            # missing replacement_text
            arguments={"matched_text": "old text", "rationale": "fix"},
        )

        result, suggestions, comments, finding = _dispatch_tool_call(
            docs_client=docs_client,
            document_id="doc-id",
            tool_call=tool_call,
            seen_spans=set(),
            allowed_categories=["tone_drift", "readability"],
        )

        assert "Missing required field" in result
        assert "'replacement_text'" in result
        assert suggestions == 0
        assert comments == 0
        assert finding is None
        docs_client.create_suggestion.assert_not_called()

    def test_returns_error_message_when_matched_text_missing_from_comment(
        self,
    ) -> None:
        """Malformed create_inline_comment missing matched_text returns an error."""
        docs_client = MagicMock()
        tool_call = ToolCall(
            id="call_1",
            name="create_inline_comment",
            arguments={"comment": "This is wrong"},  # no matched_text
        )

        result, suggestions, comments, finding = _dispatch_tool_call(
            docs_client=docs_client,
            document_id="doc-id",
            tool_call=tool_call,
            seen_spans=set(),
            allowed_categories=["information_hierarchy", "cta_cadence"],
        )

        assert "Missing required field" in result
        assert "'matched_text'" in result
        assert suggestions == 0
        assert comments == 0
        assert finding is None
        docs_client.create_inline_comment.assert_not_called()

    def test_returns_error_message_when_comment_missing_from_comment(self) -> None:
        """Malformed create_inline_comment missing comment returns an error."""
        docs_client = MagicMock()
        tool_call = ToolCall(
            id="call_1",
            name="create_inline_comment",
            arguments={"matched_text": "old text"},  # no comment
        )

        result, suggestions, comments, finding = _dispatch_tool_call(
            docs_client=docs_client,
            document_id="doc-id",
            tool_call=tool_call,
            seen_spans=set(),
            allowed_categories=["information_hierarchy", "cta_cadence"],
        )

        assert "Missing required field" in result
        assert "'comment'" in result
        assert suggestions == 0
        assert comments == 0
        assert finding is None
        docs_client.create_inline_comment.assert_not_called()
