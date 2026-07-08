"""Tests for the BrandGuidelines loader."""

import json
from pathlib import Path

import pytest

from verbatim.brand_guidelines import BrandGuidelines


class TestBrandGuidelines:
    """Test suite for the BrandGuidelines class."""

    @pytest.fixture
    def guidelines(self) -> BrandGuidelines:
        """Create a BrandGuidelines instance with default bundled data."""
        return BrandGuidelines()

    def test_loads_bundled_guidelines_successfully(
        self, guidelines: BrandGuidelines
    ) -> None:
        """Test that the default bundled guidelines load without error."""
        assert guidelines is not None
        assert guidelines.data is not None

    def test_has_required_root_keys(self, guidelines: BrandGuidelines) -> None:
        """Test that loaded data has all required root keys."""
        assert "metadata" in guidelines.data
        assert "voice_and_tone" in guidelines.data
        assert "rules" in guidelines.data

    def test_get_banned_words_returns_list(self, guidelines: BrandGuidelines) -> None:
        """Test that get_banned_words returns a non-empty list."""
        banned_words = guidelines.get_banned_words()
        assert isinstance(banned_words, list)
        assert len(banned_words) > 0
        # Verify some expected entries
        assert "leverage" in banned_words
        assert "disruption" in banned_words

    def test_get_standardized_spellings_returns_dict(
        self, guidelines: BrandGuidelines
    ) -> None:
        """Test that get_standardized_spellings returns a dict."""
        spellings = guidelines.get_standardized_spellings()
        assert isinstance(spellings, dict)
        assert len(spellings) > 0
        # Verify some expected entries
        assert "email" in spellings
        assert "website" in spellings

    def test_get_rules_for_category_readability(
        self, guidelines: BrandGuidelines
    ) -> None:
        """Test that get_rules_for_category returns rules for readability."""
        rules = guidelines.get_rules_for_category("readability")
        assert isinstance(rules, list)
        assert len(rules) > 0

    def test_get_rules_for_nonexistent_category(
        self, guidelines: BrandGuidelines
    ) -> None:
        """Test that get_rules_for_category returns empty list for unknown category."""
        rules = guidelines.get_rules_for_category("nonexistent")
        assert isinstance(rules, list)
        assert len(rules) == 0

    def test_get_voice_and_tone_summary_returns_markdown(
        self, guidelines: BrandGuidelines
    ) -> None:
        """Test that get_voice_and_tone_summary returns formatted markdown."""
        summary = guidelines.get_voice_and_tone_summary()
        assert isinstance(summary, str)
        assert "Voice Principles:" in summary
        assert "Tone Guidance:" in summary

    def test_format_for_llm_prompt_without_channel(
        self, guidelines: BrandGuidelines
    ) -> None:
        """Test that format_for_llm_prompt returns structured prompt text."""
        prompt = guidelines.format_for_llm_prompt()
        assert isinstance(prompt, str)
        assert "=== BRAND VOICE & STYLE GUIDELINES ===" in prompt
        assert "BANNED WORDS" in prompt
        assert "STANDARDIZED SPELLINGS" in prompt

    def test_format_for_llm_prompt_with_channel(
        self, guidelines: BrandGuidelines
    ) -> None:
        """Test that format_for_llm_prompt includes channel-specific rules."""
        prompt = guidelines.format_for_llm_prompt(target_channel="twitter")
        assert isinstance(prompt, str)
        assert "=== BRAND VOICE & STYLE GUIDELINES ===" in prompt

    def test_raises_file_not_found_for_invalid_path(self) -> None:
        """Test that loading from a nonexistent path sets is_valid to False."""
        guidelines = BrandGuidelines("nonexistent.json")
        assert not guidelines.is_valid
        assert guidelines.error_message is not None
        assert "fixture not found" in guidelines.error_message.lower()

    def test_validates_banned_words_and_competitors_structure(
        self, tmp_path: Path
    ) -> None:
        """Test that malformed banned_words_and_competitors sets is_valid to False."""
        # Create a JSON with banned_words_and_competitors as a list (should be dict)
        malformed_json = {
            "metadata": {"name": "Test"},
            "voice_and_tone": {},
            "rules": {
                "banned_words_and_competitors": [
                    "leverage",
                    "synergy",
                ]  # Wrong: should be dict
            },
        }

        json_file = tmp_path / "malformed.json"
        json_file.write_text(json.dumps(malformed_json))

        guidelines = BrandGuidelines(json_file)
        assert not guidelines.is_valid
        assert guidelines.error_message is not None
        assert "must be a dictionary" in guidelines.error_message.lower()

    def test_validates_banned_words_type(self, tmp_path: Path) -> None:
        """Test that banned_words with wrong type sets is_valid to False."""
        malformed_json = {
            "metadata": {"name": "Test"},
            "voice_and_tone": {},
            "rules": {
                "banned_words_and_competitors": {
                    "banned_words": "not-a-list"  # Wrong: should be list
                }
            },
        }

        json_file = tmp_path / "malformed.json"
        json_file.write_text(json.dumps(malformed_json))

        guidelines = BrandGuidelines(json_file)
        assert not guidelines.is_valid
        assert guidelines.error_message is not None
        assert "must be a list" in guidelines.error_message.lower()

    def test_validates_standardized_spellings_type(self, tmp_path: Path) -> None:
        """Test that standardized_spellings with wrong type sets is_valid to False."""
        malformed_json = {
            "metadata": {"name": "Test"},
            "voice_and_tone": {},
            "rules": {
                "banned_words_and_competitors": {
                    "banned_words": [],
                    # Wrong: should be dict
                    "standardized_spellings": ["not", "a", "dict"],
                }
            },
        }

        json_file = tmp_path / "malformed.json"
        json_file.write_text(json.dumps(malformed_json))

        guidelines = BrandGuidelines(json_file)
        assert not guidelines.is_valid
        assert guidelines.error_message is not None
        assert "must be a dict" in guidelines.error_message.lower()
