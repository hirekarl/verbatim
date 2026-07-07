"""Brand guidelines evaluator that checks text against brand rules."""

import re
from dataclasses import dataclass
from typing import Literal

from verbatim.brand_guidelines import BrandGuidelines


@dataclass
class Violation:
    """Represents a single brand guideline violation."""

    category: str
    severity: Literal["error", "warning", "info"]
    message: str
    matched_text: str
    suggestion: str | None = None


class BrandGuidelinesEvaluator:
    """Evaluates text against brand guidelines and returns violations."""

    def __init__(self, guidelines_path: str | None = None) -> None:
        """Initialize the evaluator with brand guidelines.

        Args:
            guidelines_path: Path to the brand_guidelines.json file. If None,
                uses the default bundled guidelines.
        """
        self.guidelines = BrandGuidelines(guidelines_path)

    def evaluate(self, text: str, channel: str | None = None) -> list[Violation]:
        """Evaluate text against all brand guidelines.

        Args:
            text: The text to evaluate
            channel: Optional target channel (e.g., "twitter", "facebook",
                    "instagram", "email") for channel-specific constraints

        Returns:
            List of violations found in the text
        """
        violations: list[Violation] = []

        # Check banned words
        violations.extend(self._check_banned_words(text))
        violations.extend(self._check_standardized_spellings(text))

        # Check formatting and style rules
        violations.extend(self._check_ampersands(text))
        violations.extend(self._check_oxford_comma(text))
        violations.extend(self._check_semicolons(text))
        violations.extend(self._check_exclamation_points(text))
        violations.extend(self._check_double_spaces(text))
        violations.extend(self._check_click_here_links(text))

        # Check channel-specific constraints if channel is specified
        if channel:
            violations.extend(self._check_channel_constraints(text, channel))

        return violations

    def _check_banned_words(self, text: str) -> list[Violation]:
        """Check for banned words in the text.

        Args:
            text: The text to check

        Returns:
            List of violations for banned words found
        """
        violations: list[Violation] = []
        banned_words = self.guidelines.get_banned_words()

        for word in banned_words:
            # Use word boundaries to avoid partial matches
            # Case-insensitive matching
            # For multi-word phrases, normalize whitespace to match any sequence
            # (spaces, line breaks, tabs) to catch Google Docs line-wrapped text
            escaped_word = re.escape(word)
            if " " in word:
                # Replace literal spaces with \s+ to match any whitespace
                escaped_word = escaped_word.replace(r"\ ", r"\s+")
            # Use negative lookbehind/lookahead to exclude hyphenated compounds
            # This prevents "old" from matching in "3-year-old" while still
            # catching "old" in "old people" (ageist language)
            pattern = r"(?<!-)\b" + escaped_word + r"\b(?!-)"
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                violations.append(
                    Violation(
                        category="banned_words_and_competitors",
                        severity="error",
                        message=f"Banned word found: '{word}'",
                        matched_text=match.group(),
                        suggestion=None,
                    )
                )

        return violations

    def _check_standardized_spellings(self, text: str) -> list[Violation]:
        """Check for non-standard spellings.

        Brand guidelines specify standardized spellings for common terms
        (email, website, WiFi, OK, etc.).

        Args:
            text: The text to check

        Returns:
            List of violations for non-standard spellings
        """
        violations: list[Violation] = []

        # Define patterns for non-standard spellings
        # Format: (wrong_pattern, correct_form, explanation)
        spelling_patterns = [
            (r"\be-mail\b", "email", "Never hyphenate 'email'"),
            (r"\bE-mail\b", "Email", "Never hyphenate 'email'"),
            (r"\bWeb\s+site\b", "website", "Write as one word: 'website'"),
            (r"\bhome\s+page\b", "homepage", "Write as one word: 'homepage'"),
            (r"\bco-worker\b", "coworker", "Write as one word: 'coworker'"),
            (r"\bco\s+worker\b", "coworker", "Write as one word: 'coworker'"),
            # Capitalization errors (mid-sentence)
            (
                r"(?<=[a-z])\s+Internet\b",
                "internet",
                "Don't capitalize 'internet' mid-sentence",
            ),
            (
                r"(?<=[a-z])\s+Online\b",
                "online",
                "Don't capitalize 'online' mid-sentence",
            ),
            # OK/ok variations
            (r"\bok\b", "OK", "Always write as 'OK' (all caps)"),
            (r"\bOk\b", "OK", "Always write as 'OK' (all caps)"),
            # WiFi variations
            (r"\bwifi\b", "WiFi", "Always write as 'WiFi' (capital W and F)"),
            (r"\bWifi\b", "WiFi", "Always write as 'WiFi' (capital W and F)"),
        ]

        for pattern, correct_form, explanation in spelling_patterns:
            matches = re.finditer(pattern, text)
            for match in matches:
                violations.append(
                    Violation(
                        category="banned_words_and_competitors",
                        severity="warning",
                        message=f"Non-standard spelling: {explanation}",
                        matched_text=match.group().strip(),
                        suggestion=correct_form,
                    )
                )

        return violations

    def _check_ampersands(self, text: str) -> list[Violation]:
        """Check for improper ampersand usage.

        Ampersands should only be used in company/brand names.
        Uses an allowlist of known brand names for accurate detection.

        Args:
            text: The text to check

        Returns:
            List of violations for improper ampersand usage
        """
        violations: list[Violation] = []
        allowed_brands = self.guidelines.get_allowed_brand_names()

        # Normalize brand names for case-insensitive matching
        # Keep track of original spacing variations
        normalized_brands = []
        for brand in allowed_brands:
            # Normalize whitespace around ampersand: "A&B", "A & B", "A  &  B" all match
            normalized = re.sub(r"\s*&\s*", "&", brand.lower())
            normalized_brands.append(normalized)

        # Find all ampersands
        matches = re.finditer(r"&", text)

        for match in matches:
            pos = match.start()

            # Extract a window of text around the ampersand to check for brand names
            # Look back and forward far enough to catch multi-word brand names
            before_text = text[max(0, pos - 30) : pos]
            after_text = text[pos + 1 : min(len(text), pos + 31)]

            # Get the words immediately before and after the &
            # Use word boundary regex to extract words without punctuation
            words_before_match = re.findall(r"\b\w+\b", before_text)
            words_after_match = re.findall(r"\b\w+\b", after_text)

            # Build potential brand name phrases of varying lengths
            # Check 1-word before/after (e.g., "AT&T"), 2-words (e.g., "Ben & Jerry's")
            is_allowed_brand = False
            for num_before in range(1, min(3, len(words_before_match) + 1)):
                for num_after in range(1, min(3, len(words_after_match) + 1)):
                    phrase_words = [
                        *words_before_match[-num_before:],
                        "&",
                        *words_after_match[:num_after],
                    ]
                    phrase = " ".join(phrase_words)
                    # Normalize whitespace around ampersand for matching
                    phrase_normalized = re.sub(r"\s*&\s*", "&", phrase.lower())

                    if phrase_normalized in normalized_brands:
                        is_allowed_brand = True
                        break
                if is_allowed_brand:
                    break

            if not is_allowed_brand:
                violations.append(
                    Violation(
                        category="formatting_and_style",
                        severity="warning",
                        message=(
                            "Avoid using ampersands (&) unless part of a "
                            "company or brand name"
                        ),
                        matched_text="&",
                        suggestion="Use 'and' instead",
                    )
                )

        return violations

    def _check_oxford_comma(self, text: str) -> list[Violation]:
        """Check for missing Oxford commas in lists.

        Detects patterns like "A, B and C" and suggests "A, B, and C".
        Only flags 3+ item lists, not two-item conjunctions.

        Args:
            text: The text to check

        Returns:
            List of violations for missing Oxford commas
        """
        violations: list[Violation] = []

        # Pattern: Find potential Oxford comma violations
        # Matches: ", word(s) and word(s)"
        pattern = r",\s+(\w+(?:\s+\w+)?)\s+and\s+(\w+)"

        matches = re.finditer(pattern, text)

        for match in matches:
            start_pos = match.start()

            # Extract the current sentence by looking back to the last sentence boundary
            # or the start of text, whichever comes first
            sentence_start = 0
            for boundary_pos in range(start_pos - 1, -1, -1):
                if text[boundary_pos] in ".!?":
                    sentence_start = boundary_pos + 1
                    break

            # Get the text from sentence start to the match
            current_sentence_prefix = text[sentence_start:start_pos].strip()

            # Check if this sentence starts with a clause-starting phrase
            # that indicates a two-item conjunction rather than a list
            # E.g., "In 2020, mobile and desktop" or "After launch, sales and marketing"
            clause_starters = (
                r"^\s*(In|After|For|By|When|Since|Before|During|From|"
                r"Yesterday|Today|Tomorrow|Meanwhile|However|Therefore|"
                r"Thus|Hence|Otherwise|Nevertheless)\b"
            )
            looks_like_clause = re.search(
                clause_starters, current_sentence_prefix, re.IGNORECASE
            )

            # Only flag if it doesn't look like a clause-based two-item conjunction
            # This catches real lists like "templates, automation and analytics"
            # while avoiding "In 2020, mobile and desktop"
            if not looks_like_clause:
                violations.append(
                    Violation(
                        category="formatting_and_style",
                        severity="warning",
                        message="Missing Oxford comma in list",
                        matched_text=match.group(),
                        suggestion=match.group().replace(" and ", ", and "),
                    )
                )

        return violations

    def _check_semicolons(self, text: str) -> list[Violation]:
        """Check for semicolons in the text.

        Brand guideline: Avoid semicolons. Simplify sentences, use an em dash
        (—) without spaces, or start a new sentence instead.

        Args:
            text: The text to check

        Returns:
            List of violations for semicolons found
        """
        violations: list[Violation] = []

        # Find all semicolons
        matches = re.finditer(r";", text)

        for _match in matches:
            violations.append(
                Violation(
                    category="formatting_and_style",
                    severity="warning",
                    message="Avoid semicolons",
                    matched_text=";",
                    suggestion=(
                        "Simplify sentence, use em dash (—), or start new sentence"
                    ),
                )
            )

        return violations

    def _check_exclamation_points(self, text: str) -> list[Violation]:
        """Check for multiple consecutive exclamation points.

        Brand guideline: Use exclamation points sparingly, never more than one
        at a time, and never in failure messages or alerts.

        Args:
            text: The text to check

        Returns:
            List of violations for multiple exclamation points
        """
        violations: list[Violation] = []

        # Find patterns of 2 or more consecutive exclamation points
        pattern = r"!{2,}"
        matches = re.finditer(pattern, text)

        for match in matches:
            violations.append(
                Violation(
                    category="formatting_and_style",
                    severity="warning",
                    message="Use only one exclamation point at a time",
                    matched_text=match.group(),
                    suggestion="Use single exclamation point (!)",
                )
            )

        return violations

    def _check_double_spaces(self, text: str) -> list[Violation]:
        """Check for multiple consecutive spaces.

        Brand guideline: Leave exactly a single space between sentences
        (never two spaces).

        Args:
            text: The text to check

        Returns:
            List of violations for multiple consecutive spaces
        """
        violations: list[Violation] = []

        # Find patterns of 2 or more consecutive spaces
        pattern = r" {2,}"
        matches = re.finditer(pattern, text)

        for match in matches:
            violations.append(
                Violation(
                    category="formatting_and_style",
                    severity="warning",
                    message="Use only single spaces between words and sentences",
                    matched_text=match.group(),
                    suggestion="Use single space",
                )
            )

        return violations

    def _check_click_here_links(self, text: str) -> list[Violation]:
        """Check for non-descriptive link text.

        Brand guideline: Avoid 'Click here'; link descriptive keywords instead.
        Do not link punctuation. Do not link preceding articles.

        Args:
            text: The text to check

        Returns:
            List of violations for non-descriptive link text
        """
        violations: list[Violation] = []

        # Common non-descriptive link patterns
        patterns = [
            r"\bclick\s+here\b",
            r"\bclick\s+this\b",
            r"\bhere\b(?=\s+to|\s+for)",  # "here to" or "here for"
            r"\bthis\s+link\b",
            r"\bread\s+more\s+here\b",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                violations.append(
                    Violation(
                        category="formatting_and_style",
                        severity="warning",
                        message="Avoid non-descriptive link text like 'click here'",
                        matched_text=match.group(),
                        suggestion="Use descriptive keywords that indicate destination",
                    )
                )

        return violations

    def _check_channel_constraints(self, text: str, channel: str) -> list[Violation]:
        """Check for channel-specific constraint violations.

        Different channels have different length and format requirements:
        - Twitter: 280 character limit
        - Facebook: 1-2 short sentences preferred
        - Instagram: 1 sentence or short phrase

        Args:
            text: The text to check
            channel: The target channel (e.g., "twitter", "facebook", "instagram")

        Returns:
            List of violations for channel constraint issues
        """
        violations: list[Violation] = []
        channel_lower = channel.lower()

        # Twitter: 280 character limit
        if channel_lower == "twitter":
            if len(text) > 280:
                violations.append(
                    Violation(
                        category="channel_constraints",
                        severity="error",
                        message="Twitter posts must be 280 characters or less",
                        matched_text=text[:50] + "..." if len(text) > 50 else text,
                        suggestion=f"Reduce from {len(text)} to 280 characters",
                    )
                )

        # Facebook: 1-2 short sentences
        elif channel_lower == "facebook":
            # Split on sentence-ending punctuation
            sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
            if len(sentences) > 2:
                violations.append(
                    Violation(
                        category="channel_constraints",
                        severity="warning",
                        message="Facebook posts should be 1-2 short sentences",
                        matched_text=text[:50] + "..." if len(text) > 50 else text,
                        suggestion=f"Reduce from {len(sentences)} to 1-2 sentences",
                    )
                )

        # Instagram: 1 sentence or short phrase
        elif channel_lower == "instagram":
            sentences = [s.strip() for s in re.split(r"[.!?]+", text) if s.strip()]
            if len(sentences) > 1:
                violations.append(
                    Violation(
                        category="channel_constraints",
                        severity="warning",
                        message="Instagram posts should be 1 sentence or short phrase",
                        matched_text=text[:50] + "..." if len(text) > 50 else text,
                        suggestion=(
                            f"Reduce to single sentence (currently {len(sentences)})"
                        ),
                    )
                )

        return violations
