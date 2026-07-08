"""Tests for the BrandGuidelinesEvaluator."""

import pytest

from verbatim.evaluator import BrandGuidelinesEvaluator


class TestBrandGuidelinesEvaluator:
    """Test suite for the BrandGuidelinesEvaluator class."""

    @pytest.fixture
    def evaluator(self) -> BrandGuidelinesEvaluator:
        """Create an evaluator instance with the default guidelines."""
        return BrandGuidelinesEvaluator()

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

        # Should not flag ampersands in known brand names (from allowlist)
        ampersand_violations = [
            v
            for v in violations
            if v.category == "formatting_and_style" and "ampersand" in v.message.lower()
        ]
        assert len(ampersand_violations) == 0

    def test_ampersand_allowed_in_brand_name_with_apostrophe(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that apostrophes don't break brand-name tokenization for ampersands."""
        test_cases = [
            "We love Ben & Jerry's ice cream.",
            "Try the new M&M's promotion.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            ampersand_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "ampersand" in v.message.lower()
            ]
            assert len(ampersand_violations) == 0, (
                f"False positive: apostrophe brand name flagged in '{text}'"
            )

    def test_ampersand_flags_title_case_non_brands(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that Title Case non-brands with ampersands are flagged."""
        test_cases = [
            "Please review our Terms & Conditions before signing.",
            "Save Time & Money Today with our platform.",
            "Check out our Data & Analytics dashboard.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            ampersand_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "ampersand" in v.message.lower()
            ]
            assert len(ampersand_violations) > 0, (
                f"Expected to flag ampersand in Title Case phrase: '{text}'"
            )

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
            "Yesterday, John and Mary went to the store.",  # Karl's example
            "Tomorrow, sales and marketing meet.",
            "However, data and insights matter.",
            "For $2.99, subscribers and members get access.",
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

    def test_oxford_comma_across_sentence_boundaries(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test Oxford comma violations caught after sentence boundaries."""
        # This was a false negative due to too-wide lookback window
        text = (
            "The launch went well. Our platform offers templates, "
            "automation and analytics."
        )
        violations = evaluator.evaluate(text)

        oxford_violations = [
            v
            for v in violations
            if v.category == "formatting_and_style"
            and "oxford comma" in v.message.lower()
        ]
        assert len(oxford_violations) > 0, (
            "Should flag missing Oxford comma in second sentence"
        )

    def test_oxford_comma_list_after_clause_starter_still_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test a genuine 3+-item list isn't suppressed by a clause-starter word."""
        text = "In short, templates, automation and analytics all matter."
        violations = evaluator.evaluate(text)

        oxford_violations = [
            v
            for v in violations
            if v.category == "formatting_and_style"
            and "oxford comma" in v.message.lower()
        ]
        assert len(oxford_violations) > 0, (
            "Should flag missing Oxford comma even when sentence starts "
            "with a clause-starter word, if it's actually a 3+ item list"
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

    def test_hyphenated_compounds_not_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that banned words in hyphenated compounds aren't flagged."""
        # "old" is a banned word (ageist language) but shouldn't match in compounds
        test_cases = [
            "Our 3-year-old product line just got better.",
            "This is a 5-year-old company with great values.",
            "We have a brand-new approach.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            # Check that "old" is not flagged in hyphenated compounds
            old_violations = [
                v
                for v in violations
                if v.category == "banned_words_and_competitors"
                and "old" in v.message.lower()
            ]
            assert len(old_violations) == 0, (
                f"False positive: 'old' incorrectly flagged in "
                f"hyphenated compound: '{text}'"
            )

    def test_hyphen_first_compounds_still_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that banned words leading a hyphenated compound are still flagged."""
        test_cases = [
            "We prefer the old-fashioned approach.",
            "This has an old-school vibe.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            old_violations = [
                v
                for v in violations
                if v.category == "banned_words_and_competitors"
                and "old" in v.message.lower()
            ]
            assert len(old_violations) == 1, f"Expected 'old' to be flagged in '{text}'"

    def test_standalone_banned_words_still_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that standalone banned words are still correctly flagged."""
        # "old" should be flagged when used as standalone ageist language
        text = "We don't hire old people or young developers."
        violations = evaluator.evaluate(text)

        banned_violations = [
            v
            for v in violations
            if v.category == "banned_words_and_competitors"
            and ("old" in v.message.lower() or "young" in v.message.lower())
        ]
        # Should flag both "old" and "young"
        assert len(banned_violations) == 2

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

    def test_double_space_with_non_breaking_space(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of double spaces using non-breaking spaces (NBSP)."""
        text = "One sentence." + chr(0xA0) * 2 + "Another sentence from Google Docs."
        violations = evaluator.evaluate(text)

        space_violations = [
            v
            for v in violations
            if v.category == "formatting_and_style" and "space" in v.message.lower()
        ]
        assert len(space_violations) == 1

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

    def test_click_here_no_duplicate_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that overlapping click-here patterns produce one violation, not two."""
        text = "Click here to learn more."
        violations = evaluator.evaluate(text)

        link_violations = [
            v
            for v in violations
            if v.category == "formatting_and_style" and "link" in v.message.lower()
        ]
        assert len(link_violations) == 1

    def test_here_word_boundary_not_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that 'here today'/'here forever' aren't mistaken for link phrases."""
        test_cases = [
            "I'll be here today.",
            "We'll be here forever.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            link_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style" and "link" in v.message.lower()
            ]
            assert len(link_violations) == 0, f"False positive in '{text}'"

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

    def test_twitter_character_limit(self, evaluator: BrandGuidelinesEvaluator) -> None:
        """Test detection of Twitter character limit violations."""
        # Create text longer than 280 characters
        long_text = "a" * 281
        violations = evaluator.evaluate(long_text, channel="twitter")

        channel_violations = [
            v for v in violations if v.category == "channel_constraints"
        ]
        assert len(channel_violations) > 0
        assert "280" in channel_violations[0].message

    def test_twitter_within_limit_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that Twitter text within 280 chars produces no violation."""
        text = "Check out our new features for better email marketing!"
        violations = evaluator.evaluate(text, channel="twitter")

        channel_violations = [
            v for v in violations if v.category == "channel_constraints"
        ]
        assert len(channel_violations) == 0

    def test_facebook_sentence_count(self, evaluator: BrandGuidelinesEvaluator) -> None:
        """Test detection of Facebook verbosity violations."""
        # More than 2 sentences
        long_text = "First sentence. Second sentence. Third sentence. Fourth sentence."
        violations = evaluator.evaluate(long_text, channel="facebook")

        channel_violations = [
            v for v in violations if v.category == "channel_constraints"
        ]
        assert len(channel_violations) > 0
        assert (
            "1-2" in channel_violations[0].message
            or "sentence" in channel_violations[0].message.lower()
        )

    def test_no_channel_no_constraint_check(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that no channel constraints are checked without channel specified."""
        long_text = "a" * 500  # Would violate Twitter, but no channel specified
        violations = evaluator.evaluate(long_text)

        channel_violations = [
            v for v in violations if v.category == "channel_constraints"
        ]
        assert len(channel_violations) == 0

    def test_instagram_sentence_count(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of Instagram verbosity violations."""
        # More than 1 sentence
        long_text = "First sentence. Second sentence."
        violations = evaluator.evaluate(long_text, channel="instagram")

        channel_violations = [
            v for v in violations if v.category == "channel_constraints"
        ]
        assert len(channel_violations) > 0
        assert "1 sentence" in channel_violations[0].message.lower()

    def test_instagram_within_limit_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that Instagram text with 1 sentence produces no violation."""
        text = "Check out our new features!"
        violations = evaluator.evaluate(text, channel="instagram")

        channel_violations = [
            v for v in violations if v.category == "channel_constraints"
        ]
        assert len(channel_violations) == 0

    def test_email_all_caps_subject_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of all-caps email subject lines."""
        text = "HUGE SALE THIS WEEK ONLY"
        violations = evaluator.evaluate(text, channel="email")

        channel_violations = [
            v for v in violations if v.category == "channel_constraints"
        ]
        assert any("sentence case" in v.message.lower() for v in channel_violations)

    def test_email_generic_subject_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of generic/non-descriptive email subject lines."""
        text = "Newsletter"
        violations = evaluator.evaluate(text, channel="email")

        channel_violations = [
            v for v in violations if v.category == "channel_constraints"
        ]
        assert any("descriptive" in v.message.lower() for v in channel_violations)

    def test_email_truncated_subject_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of email subject lines likely to get truncated."""
        text = "Check out all of our brand new product features and updates this month"
        violations = evaluator.evaluate(text, channel="email")

        channel_violations = [
            v for v in violations if v.category == "channel_constraints"
        ]
        assert any("truncat" in v.message.lower() for v in channel_violations)

    def test_email_descriptive_subject_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that a good email subject line produces no violations."""
        text = "Your Q3 report is ready to download."
        violations = evaluator.evaluate(text, channel="email")

        channel_violations = [
            v for v in violations if v.category == "channel_constraints"
        ]
        assert len(channel_violations) == 0

    def test_quotation_mark_period_outside_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of periods outside quotation marks."""
        test_cases = [
            'She said "hello". Then she left.',
            'The feature is called "automation". It saves time.',
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            quote_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "quotation" in v.message.lower()
            ]
            assert len(quote_violations) > 0, f"Should flag: {text}"

    def test_quotation_mark_comma_outside_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of commas outside quotation marks."""
        test_cases = [
            'She said "hello", then waved.',
            'The option is "advanced", which means premium.',
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            quote_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "quotation" in v.message.lower()
            ]
            assert len(quote_violations) > 0, f"Should flag: {text}"

    def test_quotation_mark_correct_placement_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that correct quotation mark placement produces no violations."""
        test_cases = [
            'She said "hello."',
            'She said "hello," and smiled.',
            'The feature is called "automation."',
            'Did she say "hello?"',  # Question mark inside (part of quote)
            'Did she say "hello"?',  # Question mark outside (not part of quote)
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            quote_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "quotation" in v.message.lower()
            ]
            assert len(quote_violations) == 0, f"Should not flag: {text}"

    def test_gendered_terms_flagged(self, evaluator: BrandGuidelinesEvaluator) -> None:
        """Test detection of gendered terms that should be gender-neutral."""
        test_cases = [
            ("The waitress brought our order.", "server"),
            ("She's a businesswoman in tech.", "businessperson"),
            ("He works as a policeman.", "police officer"),
            ("The chairman called the meeting.", "chair"),
            ("Ask the stewardess for assistance.", "flight attendant"),
        ]

        for text, _expected_suggestion in test_cases:
            violations = evaluator.evaluate(text)
            gender_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "gender-neutral" in v.message.lower()
            ]
            assert len(gender_violations) > 0, f"Should flag gendered term in: {text}"

    def test_guys_for_mixed_groups_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of 'guys' used for mixed-gender groups."""
        test_cases = [
            "Hey guys, welcome to the team!",
            "Thanks guys for your feedback.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            gender_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and ("guys" in v.message.lower() or "gender" in v.message.lower())
            ]
            assert len(gender_violations) > 0, f"Should flag 'guys' in: {text}"

    def test_girls_for_adult_women_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of 'girls' used to refer to adult women."""
        test_cases = [
            "The girls in marketing did a great job.",
            "She went out with the girls last night.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            gender_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style" and "girls" in v.message.lower()
            ]
            assert len(gender_violations) > 0, f"Should flag 'girls' in: {text}"

    def test_gender_neutral_terms_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that gender-neutral terms produce no violations."""
        test_cases = [
            "The server brought our order.",
            "She's a businessperson in tech.",
            "They work as a police officer.",
            "The chair called the meeting.",
            "Everyone on the team contributed.",
            "The flight attendant provided assistance.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            gender_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "gender" in v.message.lower()
            ]
            assert len(gender_violations) == 0, f"Should not flag: {text}"

    def test_mailchimp_capitalization_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of incorrect Mailchimp capitalization."""
        test_cases = [
            "MailChimp is our platform.",  # Old spelling
            "mailchimp helps you grow.",  # All lowercase
            "MAILCHIMP is powerful.",  # All uppercase
            "Mail Chimp saves time.",  # Two words
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            mailchimp_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "mailchimp" in v.message.lower()
            ]
            assert len(mailchimp_violations) > 0, f"Should flag: {text}"

    def test_correct_mailchimp_spelling_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that correct Mailchimp spelling produces no violations."""
        test_cases = [
            "Mailchimp is our platform.",
            "Use Mailchimp to grow your business.",
            "Send better email with Mailchimp.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            mailchimp_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "mailchimp" in v.message.lower()
            ]
            assert len(mailchimp_violations) == 0, f"Should not flag: {text}"

    def test_number_comma_separator_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of numbers over 999 without comma separators."""
        test_cases = [
            "We sent 5000 emails.",
            "The campaign reached 15000 people.",
            "Over 1000 users signed up.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            number_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style" and "comma" in v.message.lower()
            ]
            assert len(number_violations) > 0, (
                f"Should flag number without comma: {text}"
            )

    def test_time_formatting_flagged(self, evaluator: BrandGuidelinesEvaluator) -> None:
        """Test detection of incorrect time formatting."""
        test_cases = [
            "The webinar starts at 3pm.",  # Missing space
            "Join us at 7:30PM today.",  # Uppercase AM/PM
            "Office hours: 9AM-5PM",  # Uppercase and no spaces
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            time_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style" and "time" in v.message.lower()
            ]
            assert len(time_violations) > 0, f"Should flag time format in: {text}"

    def test_correct_number_formatting_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that correct number formatting produces no violations."""
        test_cases = [
            "We sent 5,000 emails.",
            "The campaign reached 15,000 people.",
            "Join us at 7 pm today.",
            "Office hours: 9 am to 5 pm",
            "The meeting is at 3:30 pm.",
            "We have 999 subscribers.",  # Under 1000, no comma needed
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            number_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and ("number" in v.message.lower() or "time" in v.message.lower())
            ]
            assert len(number_violations) == 0, f"Should not flag: {text}"

    def test_hyphenated_dual_heritage_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test detection of hyphenated dual heritage references."""
        test_cases = [
            "Our Asian-American community is vibrant.",
            "The African-American experience is central to our story.",
            "Mexican-American entrepreneurs are thriving.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            heritage_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "heritage" in v.message.lower()
            ]
            assert len(heritage_violations) > 0, f"Should flag hyphen in: {text}"

    def test_lowercase_black_flagged(self, evaluator: BrandGuidelinesEvaluator) -> None:
        """Test detection of lowercase 'black' when referring to people."""
        test_cases = [
            "We serve black communities.",
            "Support for black entrepreneurs is essential.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            race_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and ("black" in v.message.lower() or "race" in v.message.lower())
            ]
            assert len(race_violations) > 0, f"Should flag lowercase 'black' in: {text}"

    def test_uppercase_white_flagged(self, evaluator: BrandGuidelinesEvaluator) -> None:
        """Test detection of uppercase 'White' when referring to race."""
        test_cases = [
            "White communities and Black communities working together.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            race_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and ("white" in v.message.lower() or "race" in v.message.lower())
            ]
            assert len(race_violations) > 0, f"Should flag uppercase 'White' in: {text}"

    def test_correct_race_heritage_capitalization_no_violation(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that correct race/heritage capitalization produces no violations."""
        test_cases = [
            "Our Asian American community is vibrant.",
            "Black entrepreneurs are thriving.",
            "Support for Black and white communities.",
            "Mexican American heritage is celebrated.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            race_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and ("heritage" in v.message.lower() or "race" in v.message.lower())
            ]
            assert len(race_violations) == 0, f"Should not flag: {text}"

    def test_decimal_numbers_not_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that decimal fractions are not flagged as needing commas."""
        test_cases = [
            "The version is 1.2345.",
            "Pi is approximately 3.14159.",
            "The price is $99.9999.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            number_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style" and "comma" in v.message.lower()
            ]
            assert len(number_violations) == 0, f"Should not flag decimal: {text}"

    def test_years_not_flagged(self, evaluator: BrandGuidelinesEvaluator) -> None:
        """Test that years in context are not flagged as needing commas."""
        test_cases = [
            "In 2026, we launched our product.",
            "Since 1999, we've been growing.",
            "The company was established in 2020.",
            "Popular in the 1990s.",
            "Founded circa 1850.",
            "Class of 2024 graduates.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            number_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style" and "comma" in v.message.lower()
            ]
            assert len(number_violations) == 0, f"Should not flag year: {text}"

    def test_curly_quotes_flagged(self, evaluator: BrandGuidelinesEvaluator) -> None:
        """Test that curly/smart quotes are detected for punctuation placement."""
        # Curly quotes: chr(8220) is " and chr(8221) is "
        left_quote = chr(8220)
        right_quote = chr(8221)
        test_cases = [
            f"She said {left_quote}hello{right_quote}. Then left.",
            f"The feature is {left_quote}automation{right_quote}, which helps.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            quote_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "quotation" in v.message.lower()
            ]
            assert len(quote_violations) > 0, f"Should flag curly quotes issue: {text}"

    def test_plural_gendered_terms_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that plural gendered terms are detected."""
        test_cases = [
            ("We hired three businessmen.", "businesspeople"),
            ("The waitresses were friendly.", "servers"),
            ("Several policemen responded.", "police officers"),
        ]

        for text, _expected in test_cases:
            violations = evaluator.evaluate(text)
            gender_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "gender-neutral" in v.message.lower()
            ]
            assert len(gender_violations) > 0, f"Should flag plural term in: {text}"

    def test_guys_with_comma_flagged(self, evaluator: BrandGuidelinesEvaluator) -> None:
        """Test that 'guys' with comma is detected."""
        test_cases = [
            "Hey, guys!",
            "Thanks, guys, for your help.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            guys_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style" and "guys" in v.message.lower()
            ]
            assert len(guys_violations) > 0, f"Should flag 'guys' with comma: {text}"

    def test_lowercase_heritage_terms_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that lowercase hyphenated heritage terms are detected."""
        test_cases = [
            "Our asian-american community.",
            "The african-american experience.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            heritage_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and "heritage" in v.message.lower()
            ]
            assert len(heritage_violations) > 0, (
                f"Should flag lowercase heritage: {text}"
            )

    def test_singular_race_terms_flagged(
        self, evaluator: BrandGuidelinesEvaluator
    ) -> None:
        """Test that singular race terms are detected."""
        test_cases = [
            "Support for black community.",
            "A black entrepreneur founded it.",
            "The White population grew.",
        ]

        for text in test_cases:
            violations = evaluator.evaluate(text)
            race_violations = [
                v
                for v in violations
                if v.category == "formatting_and_style"
                and ("black" in v.message.lower() or "white" in v.message.lower())
            ]
            assert len(race_violations) > 0, f"Should flag singular race term: {text}"
