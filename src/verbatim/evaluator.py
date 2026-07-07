"""Brand guidelines evaluator that checks text against brand rules."""

import re

# Import from the root-level brand_guidelines.py (temporary until migration)
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from brand_guidelines import BrandGuidelines


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

    def __init__(self, guidelines_path: str) -> None:
        """Initialize the evaluator with brand guidelines.

        Args:
            guidelines_path: Path to the brand_guidelines.json file
        """
        self.guidelines = BrandGuidelines(guidelines_path)

    def evaluate(self, text: str) -> list[Violation]:
        """Evaluate text against all brand guidelines.

        Args:
            text: The text to evaluate

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
            pattern = r"\b" + escaped_word + r"\b"
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
        We use a heuristic: allow if surrounded by capital letters.

        Args:
            text: The text to check

        Returns:
            List of violations for improper ampersand usage
        """
        violations: list[Violation] = []

        # Find all ampersands not in brand names
        # Heuristic: flag & that isn't in a brand name pattern
        # Brand patterns: "AT&T", "Procter & Gamble", "Ben & Jerry's"
        matches = re.finditer(r"&", text)

        for match in matches:
            pos = match.start()

            # Extract words before and after the ampersand
            # Look back for the last word
            before_text = text[max(0, pos - 30) : pos]
            after_text = text[pos + 1 : min(len(text), pos + 31)]

            # Get the word immediately before the &
            words_before = before_text.split()
            word_before = words_before[-1].rstrip("&") if words_before else ""

            # Get the word immediately after the &
            words_after = after_text.split()
            word_after = words_after[0].lstrip("&") if words_after else ""

            # Heuristic: if both words start with capital letters, it's likely a brand
            # Examples: "AT&T" (A and T), "Procter & Gamble" (P and G)
            # Known limitation: Title-case non-brands like "Data & Analytics"
            # will pass this check. Future improvement: use an allowlist of
            # known brand names for more precise detection.
            looks_like_brand = False
            if (
                word_before
                and word_after
                and word_before[0].isupper()
                and word_after[0].isupper()
            ):
                looks_like_brand = True

            if not looks_like_brand:
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
            # Check if this is a 3+ item list by analyzing the context
            # The match includes the comma: ", item and item"
            # For a 3+ item list, we expect to see list-like structure before

            start_pos = match.start()

            # Look back to find the item before this comma
            # We need to skip back past the comma and the word before it
            lookback_start = max(0, start_pos - 80)
            preceding_text = text[lookback_start:start_pos]

            # Check if preceding text looks like a list or a clause boundary
            # Clause indicators: starts with prep phrases, has sentence punct
            sentence_boundary_pattern = r"[.!?]\s"
            has_sentence_boundary = re.search(sentence_boundary_pattern, preceding_text)

            # Check for common clause-starting phrases that indicate
            # this is NOT a list but a clause + conjunction
            # E.g., "In 2020,", "After launch,", "For iOS,", "By default,"
            clause_starters = (
                r"\b(In|After|For|By|When|Since|Before|During|From)\s+[\w\s]+$"
            )
            looks_like_clause = re.search(
                clause_starters, preceding_text, re.IGNORECASE
            )

            # Only flag if no sentence boundary and doesn't look like a clause
            # This catches real lists like "templates, automation and analytics"
            # while avoiding "In 2020, mobile and desktop"
            if not has_sentence_boundary and not looks_like_clause:
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
