"""
Reader view: the big centered word in the middle of the window.

Phase 4: font family and size are now configurable via the settings
panel. The update_font() method allows live preview when settings
change.
"""

import tkinter as tk

from ui.theme import Theme


class ReaderView(tk.Frame):
    """A centered Label that displays one word at a time."""

    DEFAULT_FONT_SIZE = 36
    DEFAULT_FONT_FAMILY = "Helvetica"

    def __init__(self, parent: tk.Misc, theme: Theme,
                 font_family: str | None = None,
                 font_size: int | None = None) -> None:
        super().__init__(parent, bg=theme.background)
        self._theme = theme
        self._font_family = font_family or self.DEFAULT_FONT_FAMILY
        self._font_size = font_size or self.DEFAULT_FONT_SIZE
        self._label = tk.Label(
            self,
            text="",
            font=(self._font_family, self._font_size, "bold"),
            bg=theme.background,
            fg=theme.text,
        )
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

    def update_font(self, family: str | None = None,
                    size: int | None = None) -> None:
        """Update the display font. Used for live preview from settings."""
        if family is not None:
            self._font_family = family
        if size is not None:
            self._font_size = size
        self._label.config(font=(self._font_family, self._font_size, "bold"))