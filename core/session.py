"""
Session: holds the in-memory reading state.

Position is an index into the token list, never a byte offset or character
count. This keeps rewind, progress tracking, and future features like
jump-to-sentence trivial.

As of Phase 2, the Session also carries the canonical source text and
its SHA-256 hash. The hash backs the stale-position detection that
prompts the user on file-changed reopens. The source text itself is
unused in Phase 2 beyond hashing; Phase 3's context window will consume
it, reading token.source_start / source_end into this string.
"""

from dataclasses import dataclass, field

from core.tokenizer import Token
from core.timing import clamp_wpm


@dataclass
class Session:
    tokens: list[Token] = field(default_factory=list)
    source_text: str = ""
    source_hash: str = ""
    position: int = 0
    wpm: int = 300
    is_playing: bool = False
    file_path: str = ""

    def current_token(self) -> Token | None:
        """Return the token at the current position, or None if out of range."""
        if 0 <= self.position < len(self.tokens):
            return self.tokens[self.position]
        return None

    def advance(self) -> None:
        """Move forward one token. Stops playback at the end of the stream."""
        if self.position < len(self.tokens) - 1:
            self.position += 1
        else:
            # Reached the end; stop playback but leave position at the last
            # token so progress() reports ~100% rather than overflowing.
            self.is_playing = False

    def rewind(self, n: int = 5) -> None:
        """Move backward up to n tokens, floored at 0."""
        self.position = max(0, self.position - n)

    def progress(self) -> float:
        """Return reading progress as a float in [0.0, 1.0]."""
        if not self.tokens:
            return 0.0
        # +1 so that reaching the final token reports as 100%.
        return min(1.0, (self.position + 1) / len(self.tokens))

    def set_wpm(self, wpm: int) -> None:
        """Set WPM, clamped to the valid range."""
        self.wpm = clamp_wpm(wpm)

    def is_finished(self) -> bool:
        """True if the session has reached the end of the token stream."""
        return bool(self.tokens) and self.position >= len(self.tokens) - 1