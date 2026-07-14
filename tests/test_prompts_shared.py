"""Contract tests for verbatim.prompts.shared.

Written as the TDD red step ahead of `prompts/shared.py` existing -- see
`MULTI_AGENT_PLAN.md`'s "Category validation" section for the rationale.
`validate_category` is the enforcement point closing the gap where a tool
call's `category` argument isn't hard-validated by the model's tool-calling
JSON-schema `enum`.
"""

from verbatim.prompts.shared import (
    CATEGORIES,
    UNCATEGORIZED_CATEGORY,
    validate_category,
)


class TestCategories:
    """Tests for the canonical CATEGORIES vocabulary."""

    def test_contains_the_7_canonical_category_strings(self) -> None:
        """Matches brand_guidelines.json's rules keys, relocated from prompt.py."""
        assert CATEGORIES == [
            "tone_drift",
            "information_hierarchy",
            "cta_cadence",
            "readability",
            "formatting_and_style",
            "channel_constraints",
            "banned_words_and_competitors",
        ]


class TestValidateCategory:
    """Tests for validate_category's enforcement of a closed vocabulary."""

    def test_returns_the_category_unchanged_when_it_is_in_the_allowed_list(
        self,
    ) -> None:
        assert validate_category("cta_cadence", CATEGORIES) == "cta_cadence"

    def test_falls_back_to_uncategorized_when_category_is_none(self) -> None:
        """The tool call's `category` key was missing entirely."""
        assert validate_category(None, CATEGORIES) == UNCATEGORIZED_CATEGORY

    def test_falls_back_to_uncategorized_when_category_is_present_but_unrecognized(
        self,
    ) -> None:
        """A misspelled tag (e.g. `info_hierarchy`) isn't silently accepted."""
        assert validate_category("info_hierarchy", CATEGORIES) == UNCATEGORIZED_CATEGORY

    def test_falls_back_when_category_belongs_to_a_different_agents_list(
        self,
    ) -> None:
        """A real global category, just not this agent's -- e.g. the Structural
        agent's own allowed list doesn't include Line-Editor categories."""
        structural_categories = ["information_hierarchy", "cta_cadence"]

        assert (
            validate_category("tone_drift", structural_categories)
            == UNCATEGORIZED_CATEGORY
        )

    def test_is_case_sensitive(self) -> None:
        assert validate_category("Tone_Drift", CATEGORIES) == UNCATEGORIZED_CATEGORY
