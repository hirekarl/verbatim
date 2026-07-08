"""Brand guidelines loader for the Verbatim copy auditing system."""

import json
from pathlib import Path
from typing import Any, cast


class BrandGuidelines:
    """Loads and provides access to brand voice, tone, and style guidelines."""

    def __init__(self, filepath: str | Path | None = None) -> None:
        """Initialize and load brand guidelines from a JSON file.

        Args:
            filepath: Path to the brand_guidelines.json file. If None, uses the
                default data/brand_guidelines.json bundled with this package.
        """
        if filepath is None:
            # Default to the bundled data file
            filepath = Path(__file__).parent / "data" / "brand_guidelines.json"
        self.filepath = Path(filepath)
        self.data: dict[str, Any] = {}
        self.is_valid = True
        self.error_message: str | None = None
        try:
            self.load()
        except (FileNotFoundError, ValueError, KeyError, TypeError) as err:
            self.is_valid = False
            self.error_message = str(err)

    def load(self) -> None:
        """Load and validate the brand guidelines JSON file."""
        if not self.filepath.exists():
            raise FileNotFoundError(
                f"Brand guidelines fixture not found at: {self.filepath}"
            )

        with open(self.filepath, encoding="utf-8") as f:
            try:
                self.data = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in brand guidelines file: {e}") from e

        # Verify basic expected schema
        expected_keys = ["metadata", "voice_and_tone", "rules"]
        for key in expected_keys:
            if key not in self.data:
                raise KeyError(
                    f"Missing expected root key in brand guidelines: '{key}'"
                )

        # Validate nested structure of rules section
        rules = self.data.get("rules", {})
        if not isinstance(rules, dict):
            raise TypeError("'rules' must be a dictionary")

        # Validate banned_words_and_competitors structure
        if "banned_words_and_competitors" in rules:
            bwc = rules["banned_words_and_competitors"]
            if not isinstance(bwc, dict):
                raise TypeError(
                    "'rules.banned_words_and_competitors' must be a dictionary, "
                    f"got {type(bwc).__name__}"
                )

            # Check expected sub-keys exist and have correct types
            if "banned_words" in bwc and not isinstance(bwc["banned_words"], list):
                raise TypeError(
                    "'rules.banned_words_and_competitors.banned_words' "
                    f"must be a list, got {type(bwc['banned_words']).__name__}"
                )

            if "standardized_spellings" in bwc and not isinstance(
                bwc["standardized_spellings"], dict
            ):
                raise TypeError(
                    "'rules.banned_words_and_competitors.standardized_spellings' "
                    f"must be a dict, got "
                    f"{type(bwc['standardized_spellings']).__name__}"
                )

            if "allowed_brand_names" in bwc and not isinstance(
                bwc["allowed_brand_names"], list
            ):
                raise TypeError(
                    "'rules.banned_words_and_competitors.allowed_brand_names' "
                    f"must be a list, got {type(bwc['allowed_brand_names']).__name__}"
                )

    def get_voice_and_tone_summary(self) -> str:
        """Format voice principles and tone guidelines as Markdown.

        Returns:
            A Markdown-formatted string with voice principles and tone guidance.
        """
        vt = self.data.get("voice_and_tone", {})
        lines = ["### Voice Principles:"]
        for name, desc in vt.get("voice_principles", {}).items():
            lines.append(f"- **{name.capitalize()}**: {desc}")

        lines.append("\n### Tone Guidance:")
        for name, desc in vt.get("tone_guidance", {}).items():
            clean_name = name.replace("_", " ").capitalize()
            lines.append(f"- **{clean_name}**: {desc}")

        return "\n".join(lines)

    def get_rules_for_category(self, category: str) -> list[str]:
        """Get the list of rules for a specific category.

        Args:
            category: The category name (e.g., 'readability', 'formatting_and_style')

        Returns:
            List of rules for the specified category, or empty list if not found.
        """
        rules_dict = self.data.get("rules", {})
        cat_data = rules_dict.get(category, {})
        if isinstance(cat_data, dict):
            return cast(list[str], cat_data.get("rules", []))
        return []

    def get_banned_words(self) -> list[str]:
        """Get the list of banned words.

        Returns:
            List of words/phrases that should never be used.
        """
        rules_dict = self.data.get("rules", {})
        bwc = rules_dict.get("banned_words_and_competitors", {})
        return cast(list[str], bwc.get("banned_words", []))

    def get_standardized_spellings(self) -> dict[str, str]:
        """Get the dictionary of standardized spellings.

        Returns:
            Mapping of terms to their correct spelling/usage rules.
        """
        rules_dict = self.data.get("rules", {})
        bwc = rules_dict.get("banned_words_and_competitors", {})
        return cast(dict[str, str], bwc.get("standardized_spellings", {}))

    def get_allowed_brand_names(self) -> list[str]:
        """Get the list of brand names that may use ampersands.

        Returns:
            List of brand names where ampersand usage is acceptable.
        """
        rules_dict = self.data.get("rules", {})
        bwc = rules_dict.get("banned_words_and_competitors", {})
        return cast(list[str], bwc.get("allowed_brand_names", []))

    def format_for_llm_prompt(self, target_channel: str | None = None) -> str:
        """Synthesize rules into a structured Markdown prompt block for an LLM.

        Args:
            target_channel: Optional channel name to filter channel-specific
                constraints (e.g., "twitter", "email").

        Returns:
            Token-efficient Markdown string suitable for LLM system prompts.
        """
        prompt = []
        prompt.append("=== BRAND VOICE & STYLE GUIDELINES ===")
        prompt.append(self.get_voice_and_tone_summary())
        prompt.append("")

        prompt.append("### Core Audit Rules:")

        # Add rules by category
        categories = [
            "tone_drift",
            "information_hierarchy",
            "cta_cadence",
            "readability",
            "formatting_and_style",
        ]
        for cat in categories:
            rules = self.get_rules_for_category(cat)
            if rules:
                cat_name = cat.replace("_", " ").upper()
                prompt.append(f"\n* {cat_name}:")
                for rule in rules:
                    prompt.append(f"  - {rule}")

        # Add channel constraints if target_channel is provided
        if target_channel:
            cc_rules = self.get_rules_for_category("channel_constraints")
            matching_rules = [
                r for r in cc_rules if target_channel.lower() in r.lower()
            ]
            if matching_rules:
                prompt.append("\n* CHANNEL-SPECIFIC CONSTRAINTS:")
                for rule in matching_rules:
                    prompt.append(f"  - {rule}")

        # Add Banned Words & Spellings
        banned = self.get_banned_words()
        if banned:
            prompt.append(
                f"\n* BANNED WORDS (Do not use under any circumstances): "
                f"{', '.join(banned)}"
            )

        spellings = self.get_standardized_spellings()
        if spellings:
            prompt.append("\n* STANDARDIZED SPELLINGS & USAGE:")
            for term, rule in spellings.items():
                prompt.append(f"  - **{term}**: {rule}")

        prompt.append("======================================")
        return "\n".join(prompt)
