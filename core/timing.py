"""
Timing: converts reading speed into per-token display delay.

Phase 5 extends the flat WPM-to-milliseconds conversion with variable
timing based on token type and word length. Sentence and paragraph
boundaries get extra pause time, long words display longer, and short
words display faster. Punctuation-only tokens get a minimal delay.

The signature is backward-compatible: existing callers that pass only
wpm continue to work unchanged.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.tokenizer import TokenType

# Clamp bounds match the UI's WPM stepper. Defined here so both the
# timing logic and the UI can reference a single source of truth.
MIN_WPM = 100
MAX_WPM = 1000

# --- Variable timing multipliers --------------------------------------------
# These are constants, not user-facing settings. If they become
# configurable later, they move to config.json without architectural
# changes.

SENTENCE_END_MULTIPLIER = 1.5
PARAGRAPH_END_MULTIPLIER = 2.5
PUNCTUATION_ONLY_MIN_MS = 50
PUNCTUATION_ONLY_MULTIPLIER = 0.25

# Word length thresholds.
SHORT_WORD_MAX_LEN = 3
SHORT_WORD_MULTIPLIER = 0.85
LONG_WORD_MIN_LEN = 7       # Words longer than 6 chars get extra time.
LONG_WORD_EXTRA_PER_CHAR = 0.04  # +4% per character beyond 6.


def delay_ms(
    wpm: int,
    token_type: TokenType | None = None,
    word_length: int | None = None,
) -> int:
    """Return the per-token delay in milliseconds for the given WPM.

    Optional parameters enable variable timing:
      - token_type: if SENTENCE_END or PARAGRAPH_END, applies a pause
        multiplier. If PUNCTUATION_ONLY, applies a reduced delay.
      - word_length: longer words get more time, shorter words less.
        Word-length adjustments are NOT applied when a token-type
        multiplier is active for SENTENCE_END or PARAGRAPH_END (those
        pauses are about comprehension rhythm, not word complexity).

    Raises ValueError if wpm is outside [MIN_WPM, MAX_WPM].
    """
    if not MIN_WPM <= wpm <= MAX_WPM:
        raise ValueError(
            f"wpm must be between {MIN_WPM} and {MAX_WPM}, got {wpm}"
        )

    base = 60_000 / wpm

    if token_type is not None:
        # Import here to avoid circular imports at module level.
        from core.tokenizer import TokenType

        if token_type == TokenType.PUNCTUATION_ONLY:
            return max(PUNCTUATION_ONLY_MIN_MS,
                       int(base * PUNCTUATION_ONLY_MULTIPLIER))

        if token_type == TokenType.PARAGRAPH_END:
            return int(base * PARAGRAPH_END_MULTIPLIER)

        if token_type == TokenType.SENTENCE_END:
            return int(base * SENTENCE_END_MULTIPLIER)

    # Word-length adjustment (only for WORD tokens or when no type given).
    if word_length is not None:
        if word_length <= SHORT_WORD_MAX_LEN:
            return int(base * SHORT_WORD_MULTIPLIER)
        elif word_length >= LONG_WORD_MIN_LEN:
            extra_chars = word_length - (LONG_WORD_MIN_LEN - 1)
            multiplier = 1.0 + (extra_chars * LONG_WORD_EXTRA_PER_CHAR)
            return int(base * multiplier)

    return int(base)


def clamp_wpm(wpm: int) -> int:
    """Clamp a WPM value into the valid range. Useful for UI steppers."""
    return max(MIN_WPM, min(MAX_WPM, wpm))