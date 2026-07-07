"""Tests for the BrandGuidelinesEvaluator."""

import pytest

from verbatim.evaluator import BrandGuidelinesEvaluator


class TestBrandGuidelinesEvaluator:
    """Test suite for the BrandGuidelinesEvaluator class."""

    @pytest.fixture
    def evaluator(self) -> BrandGuidelinesEvaluator:
        """Create an evaluator instance with the default guidelines."""
        return BrandGuidelinesEvaluator("brand_guidelines.json")

    def test_evaluator_loads_successfully(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that the evaluator loads brand guidelines without error."""
        assert evaluator is not None
        assert evaluator.guidelines is not None

    def test_detect_banned_word_single(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of a single banned word."""
        text = "We need to leverage our synergy to incentivize growth."
        violations = evaluator.evaluate(text)

        # Should find 'leverage' and 'incentivize'
        banned_violations = [
            v for v in violations if v.category == "banned_words_and_competitors"
        ]
        assert len(banned_violations) == 2
        assert any("leverage" in v.message.lower() for v in banned_violations)
        assert any("incentivize" in v.message.lower() for v in banned_violations)

    def test_no_violations_for_clean_text(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that clean text produces no violations."""
        text = "Send better email with our marketing platform."
        violations = evaluator.evaluate(text)

        banned_violations = [
            v for v in violations if v.category == "banned_words_and_competitors"
        ]
        assert len(banned_violations) == 0

    def test_detect_ampersand_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of improper ampersand usage."""
        text = "Check out our templates & automation features."
        violations = evaluator.evaluate(text)

        ampersand_violations = [
            v
            for v in violations
            if v.category == "formatting_and_style" and "ampersand" in v.message.lower()
        ]
        assert len(ampersand_violations) > 0

    def test_ampersand_allowed_in_brand_name(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that ampersands in brand names are allowed."""
        text = "We integrate with AT&T and Procter & Gamble."
        violations = evaluator.evaluate(text)

        # Should not flag ampersands in known brand names
        # For now, we'll implement simple heuristic: uppercase before & after
        ampersand_violations = [
            v
            for v in violations
            if v.category == "formatting_and_style" and "ampersand" in v.message.lower()
        ]
        assert len(ampersand_violations) == 0

    def test_detect_oxford_comma_missing(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of missing Oxford comma."""
        text = "We offer templates, automation and analytics."
        violations = evaluator.evaluate(text)

        oxford_violations = [
            v
            for v in violations
            if v.category == "formatting_and_style"
            and "oxford comma" in v.message.lower()
        ]
        assert len(oxford_violations) > 0

    def test_oxford_comma_present_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that proper Oxford comma usage produces no violation."""
        text = "We offer templates, automation, and analytics."
        violations = evaluator.evaluate(text)

        oxford_violations = [
            v
            for v in violations
            if v.category == "formatting_and_style"
            and "oxford comma" in v.message.lower()
        ]
        assert len(oxford_violations) == 0

    def test_violation_structure(self, evaluator: BrandGuidelinesEvaluator) -> None:
        """Test that violations have the expected structure."""
        text = "We leverage our platform."
        violations = evaluator.evaluate(text)

        assert len(violations) > 0
        violation = violations[0]

        # Check required fields
        assert hasattr(violation, "category")
        assert hasattr(violation, "severity")
        assert hasattr(violation, "message")
        assert hasattr(violation, "matched_text")
        assert hasattr(violation, "suggestion")

        # Check types
        assert isinstance(violation.category, str)
        assert violation.severity in ["error", "warning", "info"]
        assert isinstance(violation.message, str)
        assert isinstance(violation.matched_text, str)
        assert violation.suggestion is None or isinstance(violation.suggestion, str)

    def test_case_insensitive_banned_word_detection(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that banned word detection is case-insensitive."""
        text = "We need to LEVERAGE our SYNERGY."
        violations = evaluator.evaluate(text)

        banned_violations = [
            v for v in violations if v.category == "banned_words_and_competitors"
        ]
        assert len(banned_violations) > 0
        assert any("leverage" in v.message.lower() for v in banned_violations)

    def test_word_boundary_detection(self, evaluator: BrandGuidelinesEvaluator) -> None:
        """Test that banned word detection respects word boundaries."""
        # 'delivered' contains 'lever' but isn't 'leverage'
        text = "We delivered great results."
        violations = evaluator.evaluate(text)

        banned_violations = [
            v
            for v in violations
            if v.category == "banned_words_and_competitors"
            and "leverage" in v.message.lower()
        ]
        assert len(banned_violations) == 0
