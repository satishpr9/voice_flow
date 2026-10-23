import re
from typing import Optional


class TextCleaner:
    """Polishes transcribed speech into natural, clean written text (Wispr Flow style).
    Removes verbal fillers, stutters, self-corrections, and normalizes capitalization/punctuation.
    """

    # Common spoken filler words and hesitations
    FILLERS = [
        r"\b(um+h*|uh+m*|er+|ah+|eh+|hmm+)\b",
        r"\b(you know|like\s*,\s*|i mean|sort of|kind of|basically)\b",
    ]

    # Stutter patterns (e.g. "the the", "I I", "we we")
    STUTTER_PATTERN = re.compile(r"\b(\w+)\s+\1\b", re.IGNORECASE)

    # Self-correction patterns (e.g. "X, actually Y", "X, wait no, Y")
    SELF_CORRECTION_PATTERNS = [
        (re.compile(r"\b(?:[a-zA-Z0-9]+)\s*,\s*(?:actually|wait no|scratch that|no wait|i mean)\s+([a-zA-Z0-9]+)\b", re.IGNORECASE), r"\1"),
    ]

    @classmethod
    def clean(cls, text: str, remove_fillers: bool = True) -> str:
        """Transforms raw transcription into polished text."""
        if not text or not text.strip():
            return ""

        cleaned = text.strip()

        # 1. Remove stutter repetitions ("the the" -> "the")
        cleaned = cls.STUTTER_PATTERN.sub(r"\1", cleaned)

        # 2. Handle self-corrections
        for pattern, replacement in cls.SELF_CORRECTION_PATTERNS:
            cleaned = pattern.sub(replacement, cleaned)

        # 3. Strip verbal disfluencies / fillers if enabled
        if remove_fillers:
            for filler_regex in cls.FILLERS:
                cleaned = re.sub(filler_regex, "", cleaned, flags=re.IGNORECASE)

        # 4. Clean extra spaces around punctuation
        cleaned = re.sub(r"\s+([.,!?;:])", r"\1", cleaned) # "hello ," -> "hello,"
        cleaned = re.sub(r"([.,!?;:])(?=[^\s\d])", r"\1 ", cleaned) # "hello,world" -> "hello, world"
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

        # 5. Fix standalone pronoun 'i' -> 'I', 'i\'m' -> 'I\'m', etc.
        cleaned = re.sub(r"\bi\b", "I", cleaned)
        cleaned = re.sub(r"\bi'm\b", "I'm", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bi'll\b", "I'll", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bi've\b", "I've", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\bi'd\b", "I'd", cleaned, flags=re.IGNORECASE)

        # 6. Sentence capitalization
        sentences = re.split(r"([.!?]\s+)", cleaned)
        capitalized_parts = []
        for part in sentences:
            if part and not re.match(r"^[.!?]\s+$", part):
                # Capitalize first non-whitespace character
                part = part[0].upper() + part[1:] if len(part) > 1 else part.upper()
            capitalized_parts.append(part)

        cleaned = "".join(capitalized_parts)

        # Add period if sentence looks complete and lacks ending punctuation
        if cleaned and cleaned[-1].isalnum():
            cleaned += "."

        return cleaned
