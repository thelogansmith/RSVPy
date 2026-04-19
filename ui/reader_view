"""
Reader view: the big centered word in the middle of the window.

Deliberately minimal. Phase 1 only needs to show a single word at a
time in a large font. ORP alignment and variable layout come in a
later phase; keeping this widget dumb now means those can be added
without rewriting the call sites.
"""

import tkinter as tk

from ui.theme import Theme


class ReaderView(tk.Frame):
    """A centered Label that displays one word at a time."""

    FONT_SIZE = 36
    FONT_FAMILY = "Helvetica"  # Tk falls back to a system sans if unavailable.

    def __init__(self, parent: tk.Misc, theme: Theme) -> None:
        super().__init__(parent, bg=theme.background)
        self._theme = theme
        self._label = tk.Label(
            self,
            text="",
            font=(self.FONT_FAMILY, self.FONT_SIZE, "bold"),
            bg=theme.background,
            fg=theme.text,
        )
        # place() with relx/rely=0.5 centers the label both horizontally
        # and vertically inside the frame, regardless of frame size.
        self._label.place(relx=0.5, rely=0.5, anchor="center")

    def show(self, word: str) -> None:
        """Display the given word. Called once per tick of the play loop."""
        self._label.config(text=word)

    def clear(self) -> None:
        self._label.config(text="")

    def apply_theme(self, theme: Theme) -> None:
        """Re-color every widget to match the new theme."""
        self._theme = theme
        self.config(bg=theme.background)
        self._label.config(bg=theme.background, fg=theme.text)
