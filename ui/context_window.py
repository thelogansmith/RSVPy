"""
Context window.

A separate Toplevel that displays the full source text of the loaded
document with the currently-displayed word highlighted. Provides
click-to-seek: clicking any word in the text jumps the reader to that
position in the token stream.

The window stays open across file loads (content refreshes) and its
open/closed state is persisted in config. It does not affect playback
when closed.

Playback keyboard shortcuts (Space, Left, Right, Home) are bound on
the Toplevel so the user can control playback while the context window
has focus, without needing to click back to the main window.

Phase 3, steps 6-8.
"""

from __future__ import annotations

import bisect
import tkinter as tk
from typing import Callable

from ui.theme import Theme


class ContextWindow:
    """Toplevel window showing source text with current-word highlighting."""

    FONT_FAMILY = "Consolas"  # Falls back to system monospace.
    FONT_SIZE = 11
    HIGHLIGHT_TAG = "current_word"

    def __init__(
        self,
        parent: tk.Misc,
        theme: Theme,
        on_seek: Callable[[int], None],
        on_close: Callable[[], None],
        callbacks: dict[str, Callable[[], None]] | None = None,
    ) -> None:
        """Create the context window.

        on_seek is called with a character offset when the user clicks
        in the text widget. The caller (MainWindow) is responsible for
        mapping that offset to a token index and updating the session.

        on_close is called when the user closes the window so the main
        window can update its bookkeeping.

        callbacks is an optional dict of playback actions to bind as
        keyboard shortcuts on this Toplevel. Recognized keys:
            "play_pause", "rewind", "skip", "restart"
        This lets the user control playback without switching focus
        back to the main window.
        """
        self._theme = theme
        self._on_seek = on_seek
        self._on_close_cb = on_close

        self.top = tk.Toplevel(parent)
        self.top.title("Context")
        self.top.geometry("500x400")
        self.top.minsize(300, 200)
        self.top.config(bg=theme.background)

        self.top.protocol("WM_DELETE_WINDOW", self._on_close)
        self.top.bind("<Escape>", lambda _e: self._on_close())

        self._build_widgets()
        self._bind_playback_shortcuts(callbacks)

    def _bind_playback_shortcuts(
        self, callbacks: dict[str, Callable[[], None]] | None
    ) -> None:
        """Bind playback keyboard shortcuts on the Toplevel.

        Mirrors the shortcuts on the main window so playback is
        controllable from either window.
        """
        if not callbacks:
            return

        if "play_pause" in callbacks:
            self.top.bind("<space>", lambda _e: callbacks["play_pause"]())
        if "rewind" in callbacks:
            self.top.bind("<Left>", lambda _e: callbacks["rewind"]())
        if "skip" in callbacks:
            self.top.bind("<Right>", lambda _e: callbacks["skip"]())
        if "restart" in callbacks:
            self.top.bind("<Home>", lambda _e: callbacks["restart"]())

    def _build_widgets(self) -> None:
        theme = self._theme

        # Scrollable text widget fills the entire window.
        text_frame = tk.Frame(self.top, bg=theme.background)
        text_frame.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        self._text = tk.Text(
            text_frame,
            font=(self.FONT_FAMILY, self.FONT_SIZE),
            bg=theme.background,
            fg=theme.text,
            wrap="word",
            padx=14,
            pady=10,
            spacing1=2,   # Extra space above each line.
            spacing3=2,   # Extra space below each line.
            highlightthickness=0,
            bd=0,
            cursor="arrow",
            yscrollcommand=scrollbar.set,
        )
        self._text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._text.yview)

        # Configure the highlight tag for the current word.
        self._text.tag_configure(
            self.HIGHLIGHT_TAG,
            background=theme.accent,
            foreground="#ffffff",
        )

        # Make the text widget read-only. We insert text programmatically
        # by toggling state around the insert call.
        self._text.config(state="disabled")

        # Click-to-seek binding.
        self._text.bind("<Button-1>", self._on_click)

    def load_text(self, source_text: str, filename: str) -> None:
        """Replace the displayed text with a new document's source."""
        self.top.title(f"Context — {filename}")
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("1.0", source_text)
        self._text.config(state="disabled")

    def highlight(self, source_start: int, source_end: int) -> None:
        """Highlight the character range [source_start, source_end) and
        auto-scroll to keep it visible.

        Called on every tick of the play loop from the main window.
        """
        self._text.tag_remove(self.HIGHLIGHT_TAG, "1.0", "end")

        # Tk Text indices are "line.char" strings. We convert our flat
        # character offsets using the "1.0 + N chars" syntax.
        start_idx = f"1.0 + {source_start} chars"
        end_idx = f"1.0 + {source_end} chars"

        self._text.tag_add(self.HIGHLIGHT_TAG, start_idx, end_idx)
        self._text.see(start_idx)

    def clear_highlight(self) -> None:
        """Remove any active highlight."""
        self._text.tag_remove(self.HIGHLIGHT_TAG, "1.0", "end")

    def apply_theme(self, theme: Theme) -> None:
        """Re-color the context window to match a new theme."""
        self._theme = theme
        self.top.config(bg=theme.background)
        self._text.config(bg=theme.background, fg=theme.text)
        self._text.tag_configure(
            self.HIGHLIGHT_TAG,
            background=theme.accent,
            foreground="#ffffff",
        )

    def _on_click(self, event: tk.Event) -> None:
        """Handle a click in the text widget. Determine the character
        offset under the cursor and call on_seek with it.
        """
        # Text.index("@x,y") returns a "line.char" index for the click.
        index = self._text.index(f"@{event.x},{event.y}")
        # Convert "line.char" to a flat character offset by counting
        # characters from "1.0" to the clicked position.
        offset = self._char_offset(index)
        self._on_seek(offset)

    def _char_offset(self, tk_index: str) -> int:
        """Convert a Tk 'line.char' index to a flat character offset."""
        # count(start, end, "chars") returns an integer on Tk 8.5+.
        return self._text.count("1.0", tk_index, "chars")[0] or 0

    def _on_close(self) -> None:
        self.top.destroy()
        self._on_close_cb()

    def is_alive(self) -> bool:
        """Return True if the Toplevel still exists."""
        try:
            return self.top.winfo_exists()
        except tk.TclError:
            return False