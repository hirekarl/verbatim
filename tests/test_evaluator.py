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

    def test_oxford_comma_two_item_conjunction_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that two-item conjunctions don't trigger false positive."""
        # These are normal two-item conjunctions, not 3+ item lists
        test_cases = [
            "In 2020, mobile and desktop usage grew rapidly.",
            "After launch, sales and marketing teams collaborate.",
            "For iOS, tap and hold the icon.",
            "By default, templates and automation are enabled.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            oxford_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "oxford comma" in v.message.lower()
            ]
            assert len(oxford_violations) == 0, (
                f"False positive for two-item conjunction: '{text}'"
            )

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

    def test_multi_word_banned_phrase_whitespace_normalization(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that multi-word banned phrases match with varied whitespace."""
        # Test with different whitespace variations (newlines, multiple spaces)
        test_cases = [
            "We're crushing it with sales!",  # Normal space
            "We're crushing  it with sales!",  # Multiple spaces
            "We're crushing\nit with sales!",  # Newline
            "We're crushing\t it with sales!",  # Tab + space
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            banned_violations = [
                v
                for v in violations
                if v.category == "banned_words_and_competitors"
                and "crushing it" in v.message.lower()
            ]
            assert len(banned_violations) == 1, (
                f"Failed to detect 'crushing it' with varied whitespace: {text!r}"
            )

    def test_detect_semicolon(self, evaluator: BrandGuidelinesEvaluator) -> None:
        """Test detection of semicolons."""
        text = "We offer templates; they help you grow your business."
        violations = evaluator.evaluate(text)

        semicolon_violations = [
            v
            for v in violations
            if v.category == "formatting_and_style" and "semicolon" in v.message.lower()
        ]
        assert len(semicolon_violations) > 0
        assert semicolon_violations[0].matched_text == ";"

    def test_no_semicolon_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that text without semicolons produces no semicolon violations."""
        text = "We offer templates. They help you grow your business."
        violations = evaluator.evaluate(text)

        semicolon_violations = [
            v
            for v in violations
            if v.category == "formatting_and_style" and "semicolon" in v.message.lower()
        ]
        assert len(semicolon_violations) == 0

    def test_detect_multiple_exclamation_points(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of multiple consecutive exclamation points."""
        test_cases = [
            ("Great work!!", 1),  # Two exclamation points
            ("Amazing!!!", 1),  # Three exclamation points
            ("Wow!! This is great!!", 2),  # Multiple violations
        ]

        for text, expected_count in test_cases:
            violations = evaluator.evaluate(text)
            exclamation_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "exclamation" in v.message.lower()
            ]
            assert len(exclamation_violations) == expected_count, (
                f"Expected {expected_count} violations for {text!r}, "
                f"got {len(exclamation_violations)}"
            )

    def test_single_exclamation_point_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that single exclamation points are allowed."""
        text = "Great work! We're excited to launch this feature!"
        violations = evaluator.evaluate(text)

        exclamation_violations = [
            v
            for v in violations
            if v.category == "formatting_and_style"
            and "exclamation" in v.message.lower()
        ]
        assert len(exclamation_violations) == 0

    def test_detect_double_spaces(self, evaluator: BrandGuidelinesEvaluator) -> None:
        """Test detection of multiple consecutive spaces."""
        test_cases = [
            ("One sentence.  Another sentence.", 1),  # Double space
            ("Text with   triple spaces.", 1),  # Triple space
            ("Multiple  issues  here.", 2),  # Two violations
        ]

        for text, expected_count in test_cases:
            violations = evaluator.evaluate(text)
            space_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style" and "space" in v.message.lower()
            ]
            assert len(space_violations) == expected_count, (
                f"Expected {expected_count} violations for {text!r}, "
                f"got {len(space_violations)}"
            )

    def test_single_space_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that single spaces between words are allowed."""
        text = "This is normal text. It has proper spacing."
        violations = evaluator.evaluate(text)

        space_violations = [
            v
            for v in violations
            if v.category == "formatting_and_style" and "space" in v.message.lower()
        ]
        assert len(space_violations) == 0

    def test_detect_click_here_links(self, evaluator: BrandGuidelinesEvaluator) -> None:
        """Test detection of non-descriptive link text."""
        test_cases = [
            "Click here to learn more",
            "Read more here about our features",
            "Check out this link for details",
            "Click this to get started",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            link_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style" and "link" in v.message.lower()
            ]
            assert len(link_violations) > 0, (
                f"Expected to detect non-descriptive link in {text!r}"
            )

    def test_descriptive_link_text_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that descriptive link text produces no violations."""
        text = "Read our documentation to learn about templates and automation."
        violations = evaluator.evaluate(text)

        link_violations = [
            v
            for v in violations
            if v.category == "formatting_and_style" and "link" in v.message.lower()
        ]
        assert len(link_violations) == 0

    def test_detect_non_standard_spellings(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of non-standard spellings."""
        test_cases = [
            ("Send us an e-mail", "e-mail", "email"),
            ("Check our Web site", "Web site", "website"),
            ("The Internet is great", "Internet", "internet"),
            ("Buy Online today", "Online", "online"),
            ("Our co-worker helps", "co-worker", "coworker"),
            ("Visit the home page", "home page", "homepage"),
            ("Click ok to continue", "ok", "OK"),
            ("Connect to wifi", "wifi", "WiFi"),
        ]

        for text, wrong_form, correct_form in test_cases:
            violations = evaluator.evaluate(text)
            spelling_violations = [
                v
                for v in violations
                if v.category == "banned_words_and_competitors"
                and "spelling" in v.message.lower()
            ]
            assert len(spelling_violations) > 0, (
                f"Expected to detect non-standard spelling '{wrong_form}' in {text!r}"
            )
            # Check that suggestion contains correct form
            violation = spelling_violations[0]
            assert (
                violation.suggestion and correct_form in violation.suggestion
            ) or correct_form in violation.message

    def test_standard_spellings_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that standard spellings produce no violations."""
        text = "Send us an email about our website. Connect to WiFi and click OK."
        violations = evaluator.evaluate(text)

        spelling_violations = [
            v
            for v in violations
            if v.category == "banned_words_and_competitors"
            and "spelling" in v.message.lower()
        ]
        assert len(spelling_violations) == 0
