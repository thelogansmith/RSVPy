"""
RSVPy entry point.

Phase 1, step 1: a console driver that tokenizes a hardcoded string and
streams it to stdout at the configured WPM. This exercises the core
modules (tokenizer, timing, session) without any UI code, proving the
model works before Tkinter is wired in.

Step 2 will replace this with a Tkinter window. The core modules
stay unchanged.

Run:
    python main.py
"""

import sys
import time

from core.session import Session
from core.timing import delay_ms
from core.tokenizer import tokenize


SAMPLE_TEXT = """
Rapid serial visual presentation displays words one at a time at a fixed
focal point. Because the eye does not have to move, reading can be faster.

This is the second paragraph. It tests that paragraph breaks are detected
correctly. The last word of this paragraph should be tagged PARAGRAPH_END.

A final paragraph confirms that sentence endings work. Does it handle
questions? Yes! And exclamations too.
""".strip()


def run_console_demo(text: str, wpm: int = 300) -> None:
    """Tokenize the given text and stream it to stdout at the given WPM."""
    tokens = tokenize(text)
    if not tokens:
        print("No tokens to display.", file=sys.stderr)
        return

    session = Session(tokens=tokens, wpm=wpm, is_playing=True)
    per_token_delay = delay_ms(session.wpm) / 1000.0

    print(f"Streaming {len(tokens)} tokens at {session.wpm} WPM.")
    print(f"Per-token delay: {per_token_delay * 1000:.1f} ms\n")

    while session.is_playing:
        token = session.current_token()
        if token is None:
            break

        # Overwrite the same line to simulate the eventual fixed focal point.
        # The token type is shown in brackets so we can verify tagging.
        sys.stdout.write(
            f"\r\033[K[{token.type.value:>14}] "
            f"{token.text:<30} "
            f"({session.progress() * 100:5.1f}%)"
        )
        sys.stdout.flush()

        session.advance()
        if session.is_playing:
            time.sleep(per_token_delay)

    print("\n\nDone.")


if __name__ == "__main__":
    run_console_demo(SAMPLE_TEXT, wpm=300)
