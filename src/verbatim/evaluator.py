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
        violations.extend(self._check_quotation_marks(text))
        violations.extend(self._check_gender_neutral_terms(text))
        violations.extend(self._check_mailchimp_capitalization(text))
        violations.extend(self._check_number_formatting(text))
        violations.extend(self._check_race_heritage_capitalization(text))

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
            # Use a negative lookbehind to exclude words preceded by a hyphen.
            # This prevents "old" from matching in "3-year-old" while still
            # catching "old" in "old people" and in "old-fashioned" (only the
            # trailing side of a compound should be excluded, not the leading
            # side - a \b boundary already exists on both sides of a hyphen).
            pattern = r"(?<!-)\b" + escaped_word + r"\b"
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

        Note: This is a known limitation of the allowlist approach - any real
        brand name not present in `allowed_brand_names` (e.g. "Simon &
        Schuster") will still be flagged. A general brand-name detector is
        out of scope here.

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
            words_before_match = re.findall(
                r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)*", before_text
            )
            words_after_match = re.findall(
                r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)*", after_text
            )

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
                char = text[boundary_pos]
                if char in ".!?":
                    # A '.' immediately followed by a digit is a decimal point
                    # (e.g. "$2.99"), not a sentence boundary
                    next_char = (
                        text[boundary_pos + 1] if boundary_pos + 1 < len(text) else ""
                    )
                    if next_char.isdigit():
                        continue
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
            # A clause-starter only suppresses this match if there's no other
            # comma before it in the sentence - if there is, the starter word
            # is followed by list items, not directly by the "and" pair,
            # e.g. "In short, templates, automation and analytics" (extra
            # comma -> genuine list) vs. "In 2020, mobile and desktop" (no
            # extra comma -> two-item conjunction after an intro clause)
            looks_like_clause = (
                re.search(clause_starters, current_sentence_prefix, re.IGNORECASE)
                is not None
                and "," not in current_sentence_prefix
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

        # Find patterns of 2 or more consecutive spaces, including
        # non-breaking spaces (\xa0), which Google Docs commonly inserts
        pattern = r"[ \xa0]{2,}"
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
            r"\bhere\b(?=\s+to\b|\s+for\b)",  # "here to" or "here for"
            r"\bthis\s+link\b",
            r"\bread\s+more\s+here\b",
        ]

        # Patterns can overlap on the same phrase (e.g. "click here" and the
        # standalone "here" in "click here to..."); collect all matches
        # first, then skip any whose span overlaps one already recorded so
        # each real instance of bad link text produces one violation.
        all_matches = [
            match
            for pattern in patterns
            for match in re.finditer(pattern, text, re.IGNORECASE)
        ]

        matched_spans: list[tuple[int, int]] = []
        for match in sorted(all_matches, key=lambda m: m.start()):
            span = match.span()
            if any(start < span[1] and span[0] < end for start, end in matched_spans):
                continue
            matched_spans.append(span)
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

    def _check_race_heritage_capitalization(self, text: str) -> list[Violation]:
        """Check for race and heritage capitalization standards.

        Brand guidelines:
        - Standardize dual heritage references without hyphens
          (e.g., 'Asian American', not 'Asian-American')
        - Capitalize 'Black' when referring to people in the African diaspora,
          but keep 'white' lowercase

        Args:
            text: The text to check

        Returns:
            List of violations for race/heritage capitalization issues
        """
        violations: list[Violation] = []

        # Common dual heritage terms that should not be hyphenated
        heritage_patterns = [
            (r"\bAsian-American\b", "Asian American"),
            (r"\bAfrican-American\b", "African American"),
            (r"\bMexican-American\b", "Mexican American"),
            (r"\bNative-American\b", "Native American"),
            (r"\bLatin-American\b", "Latin American"),
            (r"\bItalian-American\b", "Italian American"),
            (r"\bIrish-American\b", "Irish American"),
        ]

        for pattern, correct_form in heritage_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                violations.append(
                    Violation(
                        category="formatting_and_style",
                        severity="warning",
                        message=(
                            "Remove hyphen from dual heritage references "
                            f"(use '{correct_form}', not '{match.group()}')"
                        ),
                        matched_text=match.group(),
                        suggestion=correct_form,
                    )
                )

        # Context words to check if black/white refers to race/people
        race_context = (
            r"(?:communit(?:y|ies)|people|person|individual(?:s)?|"
            r"American(?:s)?|famil(?:y|ies)|business(?:es)?|entrepreneur(?:s)?|"
            r"leader(?:s)?|voice(?:s)?|experience(?:s)?|culture(?:s)?|"
            r"man|men|woman|women|child(?:ren)?|youth|student(?:s)?|"
            r"professional(?:s)?|worker(?:s)?|writer(?:s)?|artist(?:s)?|"
            r"population(?:s)?|neighborhood(?:s)?)"
        )

        black_pattern = r"\bblack\s+" + race_context
        matches = re.finditer(black_pattern, text, re.IGNORECASE)
        for match in matches:
            matched_word = match.group().split()[0]
            if matched_word == "black":  # Case-sensitive check for lowercase
                violations.append(
                    Violation(
                        category="formatting_and_style",
                        severity="warning",
                        message=(
                            "Capitalize 'Black' when referring to people "
                            "in the African diaspora"
                        ),
                        matched_text=match.group(),
                        suggestion=match.group().replace(matched_word, "Black", 1),
                    )
                )

        white_pattern = r"\bWhite\s+" + race_context
        matches = re.finditer(white_pattern, text)

        for match in matches:
            violations.append(
                Violation(
                    category="formatting_and_style",
                    severity="warning",
                    message="Use lowercase 'white' when referring to race",
                    matched_text=match.group(),
                    suggestion=match.group().replace("White", "white", 1),
                )
            )

        return violations

    def _is_likely_year(
        self, text: str, match_start: int, match_end: int, matched_val: str
    ) -> bool:
        """Helper to determine if a 4-digit number represents a year in context."""
        if len(matched_val) != 4:
            return False
        try:
            val = int(matched_val)
            if not (1000 <= val <= 2999):
                return False
        except ValueError:
            return False

        # Trailing 's' for decades (e.g. 1990s)
        if match_end < len(text) and text[match_end] == "s":
            return True

        # Preceding context checks
        pre_text = text[max(0, match_start - 25) : match_start].lower().strip()
        year_markers = [
            r"\b(in|since|during|by|before|after|year|est\.?|established|circa|class\s+of)$",
            r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)$",
            r"\b\d{1,2}(?:st|nd|rd|th)?$",  # e.g., "July 4" or "25 Dec"
        ]
        for marker in year_markers:
            if re.search(marker, pre_text):
                return True

        # Check for date boundary symbols (e.g., 2025-12-31, 12/25/2020)
        if match_start > 0 and text[match_start - 1] in "-/.":
            return True
        return match_end < len(text) and text[match_end] in "-/."

    def _check_number_formatting(self, text: str) -> list[Violation]:
        """Check for incorrect number and time formatting.

        Brand guidelines:
        - Use commas for numbers over 3 digits (1,000)
        - Time: Use numeral + space + lowercase am/pm (7 am, 7:30 pm)

        Args:
            text: The text to check

        Returns:
            List of violations for number formatting issues
        """
        violations: list[Violation] = []

        # Check for numbers >= 1000 without commas (ignore decimals and likely years)
        pattern_number = r"(?<![\d.])([1-9]\d{3,})(?![,\d])"
        matches = re.finditer(pattern_number, text)

        for match in matches:
            number_str = match.group()
            if self._is_likely_year(text, match.start(), match.end(), number_str):
                continue

            formatted = f"{int(number_str):,}"
            violations.append(
                Violation(
                    category="formatting_and_style",
                    severity="warning",
                    message="Use commas for numbers over 999",
                    matched_text=number_str,
                    suggestion=formatted,
                )
            )

        # Check for time formatting issues
        # Pattern 1: Time without space before am/pm (3pm, 7:30PM)
        pattern_time_no_space = r"\b(\d{1,2}(?::\d{2})?)(am|pm|AM|PM)\b"
        matches = re.finditer(pattern_time_no_space, text)

        for match in matches:
            time_part = match.group(1)
            am_pm_part = match.group(2).lower()

            violations.append(
                Violation(
                    category="formatting_and_style",
                    severity="warning",
                    message="Time should have space before am/pm and be lowercase",
                    matched_text=match.group(),
                    suggestion=f"{time_part} {am_pm_part}",
                )
            )

        # Pattern 2: Time with uppercase AM/PM (but with space)
        pattern_time_uppercase = r"\b(\d{1,2}(?::\d{2})?)\s+(AM|PM)\b"
        matches = re.finditer(pattern_time_uppercase, text)

        for match in matches:
            time_part = match.group(1)
            am_pm_part = match.group(2).lower()

            violations.append(
                Violation(
                    category="formatting_and_style",
                    severity="warning",
                    message="Use lowercase am/pm for times",
                    matched_text=match.group(),
                    suggestion=f"{time_part} {am_pm_part}",
                )
            )

        return violations

    def _check_mailchimp_capitalization(self, text: str) -> list[Violation]:
        """Check for incorrect Mailchimp brand name capitalization.

        Brand guideline: Always write company name as 'Mailchimp'
        (capital M, lowercase c). Do not use 'The Rocket Science Group'
        unless in legal documents.

        Args:
            text: The text to check

        Returns:
            List of violations for incorrect Mailchimp capitalization
        """
        violations: list[Violation] = []

        # Single regex to capture all variations (spaces, hyphens, and mixed case)
        pattern = r"\bmail[- ]?chimp\b"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            matched = match.group()
            if matched != "Mailchimp":
                # Determine detailed reason for feedback
                if matched.lower() == "mailchimp":
                    if matched == "MailChimp":
                        reason = "Old spelling with capital C"
                    elif matched.islower():
                        reason = "All lowercase"
                    elif matched.isupper():
                        reason = "All uppercase"
                    else:
                        reason = "Incorrect capitalization"
                else:
                    reason = "Should be one word, not two or hyphenated"

                violations.append(
                    Violation(
                        category="formatting_and_style",
                        severity="warning",
                        message=f"Incorrect Mailchimp capitalization: {reason}",
                        matched_text=matched,
                        suggestion="Mailchimp",
                    )
                )

        return violations

    def _check_gender_neutral_terms(self, text: str) -> list[Violation]:
        """Check for gendered terms that should be gender-neutral.

        Brand guidelines:
        - Use gender-neutral terms instead of gendered ones
        - Do not call groups 'guys' or women 'girls'
        - Use singular 'they/them' if gender is unknown

        Args:
            text: The text to check

        Returns:
            List of violations for gendered language
        """
        violations: list[Violation] = []

        # Mapping of singular and plural gendered terms to gender-neutral alternatives
        gendered_terms = {
            # Singular
            r"\bwaitress\b": ("server", "waitstaff"),
            r"\bwaiter\b": ("server", "waitstaff"),
            r"\bbusinessman\b": ("businessperson", "business professional"),
            r"\bbusinesswoman\b": ("businessperson", "business professional"),
            r"\bchairman\b": ("chair", "chairperson"),
            r"\bchairwoman\b": ("chair", "chairperson"),
            r"\bpoliceman\b": ("police officer", None),
            r"\bpolicewoman\b": ("police officer", None),
            r"\bfireman\b": ("firefighter", None),
            r"\bfirewoman\b": ("firefighter", None),
            r"\bsteward\b": ("flight attendant", None),
            r"\bstewardess\b": ("flight attendant", None),
            r"\bmailman\b": ("mail carrier", "postal worker"),
            r"\bsalesman\b": ("salesperson", "sales representative"),
            r"\bsaleswoman\b": ("salesperson", "sales representative"),
            r"\bsportsman\b": ("athlete", "sports enthusiast"),
            r"\bsportswoman\b": ("athlete", "sports enthusiast"),
            r"\bmanpower\b": ("workforce", "personnel"),
            r"\bmankind\b": ("humankind", "humanity"),
            # Plural
            r"\bwaitresses\b": ("servers", "waitstaff"),
            r"\bwaiters\b": ("servers", "waitstaff"),
            r"\bbusinessmen\b": ("businesspeople", "business professionals"),
            r"\bbusinesswomen\b": ("businesspeople", "business professionals"),
            r"\bchairmen\b": ("chairs", "chairpersons"),
            r"\bchairwomen\b": ("chairs", "chairpersons"),
            r"\bpolicemen\b": ("police officers", None),
            r"\bpolicewomen\b": ("police officers", None),
            r"\bfiremen\b": ("firefighters", None),
            r"\bfirewomen\b": ("firefighters", None),
            r"\bstewards\b": ("flight attendants", None),
            r"\bstewardesses\b": ("flight attendants", None),
            r"\bmailmen\b": ("mail carriers", "postal workers"),
            r"\bsalesmen\b": ("salespeople", "sales representatives"),
            r"\bsaleswomen\b": ("salespeople", "sales representatives"),
            r"\bsportsmen\b": ("athletes", "sports enthusiasts"),
            r"\bsportswomen\b": ("athletes", "sports enthusiasts"),
        }

        for pattern, (primary_suggestion, alt_suggestion) in gendered_terms.items():
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                suggestion = primary_suggestion
                if alt_suggestion:
                    suggestion = f"{primary_suggestion} or {alt_suggestion}"

                violations.append(
                    Violation(
                        category="formatting_and_style",
                        severity="warning",
                        message="Use gender-neutral terms",
                        matched_text=match.group(),
                        suggestion=suggestion,
                    )
                )

        # Check for "guys" when referring to groups
        # Allow optional punctuation/comma in direct address greetings
        guys_pattern = r"\b(hey|hi|thank(?:s)?|you)\b[\s,]*\bguys\b"
        matches = re.finditer(guys_pattern, text, re.IGNORECASE)
        for match in matches:
            violations.append(
                Violation(
                    category="formatting_and_style",
                    severity="warning",
                    message="Avoid using 'guys' for groups; use gender-neutral terms",
                    matched_text=match.group(),
                    suggestion="Use 'everyone', 'team', 'folks', or 'all'",
                )
            )

        # Check for "girls" when referring to adult women
        # Pattern matches "the girls" as a group reference
        girls_pattern = r"\bthe\s+girls\b"
        matches = re.finditer(girls_pattern, text, re.IGNORECASE)
        for match in matches:
            violations.append(
                Violation(
                    category="formatting_and_style",
                    severity="warning",
                    message=(
                        "Avoid using 'girls' to refer to adult women; "
                        "use 'women' instead"
                    ),
                    matched_text=match.group(),
                    suggestion="Use 'the women' or 'the team'",
                )
            )

        return violations

    def _check_quotation_marks(self, text: str) -> list[Violation]:
        """Check for incorrect quotation mark punctuation placement.

        Brand guideline: Periods and commas go inside quotation marks.
        Question marks go inside quotes only if part of the quote.

        Args:
            text: The text to check

        Returns:
            List of violations for quotation mark punctuation issues
        """
        violations: list[Violation] = []

        # Match either straight quotes or curly/smart quotes
        # Character class includes: " (straight), " (left curly), " (right curly)
        left_curly = chr(8220)  # "
        right_curly = chr(8221)  # "
        quote_chars = f'["{left_curly}{right_curly}]'
        neg_class = f'[^"{left_curly}{right_curly}]'

        pattern_period = (
            rf"(?P<text>{quote_chars}{neg_class}+)(?P<close>{quote_chars})\s*\."
        )
        matches = re.finditer(pattern_period, text)
        for match in matches:
            violations.append(
                Violation(
                    category="formatting_and_style",
                    severity="warning",
                    message="Period should go inside quotation marks",
                    matched_text=match.group(),
                    suggestion=f"{match.group('text')}.{match.group('close')}",
                )
            )

        pattern_comma = (
            rf"(?P<text>{quote_chars}{neg_class}+)(?P<close>{quote_chars})\s*,"
        )
        matches = re.finditer(pattern_comma, text)
        for match in matches:
            violations.append(
                Violation(
                    category="formatting_and_style",
                    severity="warning",
                    message="Comma should go inside quotation marks",
                    matched_text=match.group(),
                    suggestion=f"{match.group('text')},{match.group('close')}",
                )
            )

        return violations

    def _check_channel_constraints(self, text: str, channel: str) -> list[Violation]:
        """Check for channel-specific constraint violations.

        Different channels have different length and format requirements:
        - Twitter: 280 character limit
        - Facebook: 1-2 short sentences preferred
        - Instagram: 1 sentence or short phrase
        - Email: subject line (first line of text) should be descriptive,
          sentence case, and not at risk of truncation. This is a
          deliberately simple first pass - it doesn't check Title Case,
          since that would false-positive on any subject with capitalized
          proper nouns/products.

        Args:
            text: The text to check
            channel: The target channel (e.g., "twitter", "facebook",
                "instagram", "email")

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

        # Email: subject line (first line) should be descriptive, sentence
        # case, and not at risk of truncation
        elif channel_lower == "email":
            stripped = text.strip()
            subject_line = stripped.splitlines()[0].strip() if stripped else ""

            if subject_line:
                if subject_line.isupper():
                    violations.append(
                        Violation(
                            category="channel_constraints",
                            severity="warning",
                            message=(
                                "Email subject lines should use sentence case, "
                                "not all caps"
                            ),
                            matched_text=subject_line,
                            suggestion="Rewrite in sentence case",
                        )
                    )

                generic_subjects = {"newsletter", "update", "news", "hello", "info"}
                if (
                    len(subject_line) < 15
                    or subject_line.strip(".!?").lower() in generic_subjects
                ):
                    violations.append(
                        Violation(
                            category="channel_constraints",
                            severity="warning",
                            message=(
                                "Email subject lines should be descriptive, not generic"
                            ),
                            matched_text=subject_line,
                            suggestion="Front-load the most important, specific words",
                        )
                    )

                if len(subject_line) > 60 and subject_line[-1].isalnum():
                    violations.append(
                        Violation(
                            category="channel_constraints",
                            severity="warning",
                            message=(
                                "Email subject line may get truncated; "
                                "put important words first"
                            ),
                            matched_text=subject_line,
                            suggestion=(
                                "Shorten to under ~60 characters or "
                                "front-load key words"
                            ),
                        )
                    )

        return violations
