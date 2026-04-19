"""
Timing: converts reading speed into per-token display delay.

Phase 1 implementation is a straight WPM-to-milliseconds conversion.
The signature is stable; later phases will extend the function to
account for token type (sentence / paragraph pauses) and word length
without changing callers.
"""

# Clamp bounds match the UI's WPM stepper. Defined here so both the
# timing logic and the UI can reference a single source of truth.
MIN_WPM = 100
MAX_WPM = 1000


def delay_ms(wpm: int) -> int:
    """Return the per-token delay in milliseconds for the given WPM.

    Raises ValueError if wpm is outside [MIN_WPM, MAX_WPM].
    """
    if not MIN_WPM <= wpm <= MAX_WPM:
        raise ValueError(
            f"wpm must be between {MIN_WPM} and {MAX_WPM}, got {wpm}"
        )
    return int(60_000 / wpm)


def clamp_wpm(wpm: int) -> int:
    """Clamp a WPM value into the valid range. Useful for UI steppers."""
    return max(MIN_WPM, min(MAX_WPM, wpm))
