"""
Reader view: the big centered word in the middle of the window.

Phase 5: ORP (Optimal Recognition Point) alignment. Instead of a
single centered label, the word is split into three parts — pre-ORP
text, the ORP character (highlighted in the accent color), and
post-ORP text — positioned so the ORP character sits at a fixed
focal column in the center of the view. Thin vertical tick marks
above and below the ORP position provide a persistent visual anchor.
"""

import tkinter as tk
import tkinter.font as tkfont

from ui.theme import Theme


def _orp_index(word: str) -> int:
    """Return the character index of the Optimal Recognition Point.

    The ORP is at roughly 1/3 into the word:
      - 1–3 chars: position 0
      - 4+ chars:  position len // 3 - 1, minimum 1

    For chunked tokens like "the cat", the caller should pass only
    the content word ("cat") and handle the prefix separately.
    """
    n = len(word)
    if n <= 3:
        return 0
    return max(1, n // 3 - 1)


class ReaderView(tk.Frame):
    """A three-label layout that displays one word at a time with ORP alignment."""

    DEFAULT_FONT_SIZE = 36
    DEFAULT_FONT_FAMILY = "Helvetica"

    TICK_LENGTH = 10    # Vertical tick mark height in pixels.
    TICK_WIDTH = 2      # Vertical tick mark width.

    def __init__(self, parent: tk.Misc, theme: Theme,
                 font_family: str | None = None,
                 font_size: int | None = None) -> None:
        super().__init__(parent, bg=theme.background)
        self._theme = theme
        self._font_family = font_family or self.DEFAULT_FONT_FAMILY
        self._font_size = font_size or self.DEFAULT_FONT_SIZE

        self._build_layout()

    def _build_layout(self) -> None:
        theme = self._theme
        bold_font = (self._font_family, self._font_size, "bold")

        # Container frame positioned at center of parent frame.
        self._container = tk.Frame(self, bg=theme.background)
        self._container.place(relx=0.5, rely=0.5, anchor="center")

        # Top tick mark (above the ORP character).
        self._tick_top = tk.Frame(
            self._container,
            bg=theme.accent,
            width=self.TICK_WIDTH,
            height=self.TICK_LENGTH,
        )
        self._tick_top.grid(row=0, column=1, pady=(0, 2))

        # Three labels for pre-ORP, ORP char, post-ORP.
        # The ORP label sits in the center column; pre and post flank it.
        self._pre_label = tk.Label(
            self._container,
            text="",
            font=bold_font,
            bg=theme.background,
            fg=theme.text,
            anchor="e",    # Right-align so it butts against the ORP char.
        )
        self._pre_label.grid(row=1, column=0, sticky="e")

        self._orp_label = tk.Label(
            self._container,
            text="",
            font=bold_font,
            bg=theme.background,
            fg=theme.accent,  # ORP character highlighted in accent color.
            anchor="center",
        )
        self._orp_label.grid(row=1, column=1)

        self._post_label = tk.Label(
            self._container,
            text="",
            font=bold_font,
            bg=theme.background,
            fg=theme.text,
            anchor="w",    # Left-align so it butts against the ORP char.
        )
        self._post_label.grid(row=1, column=2, sticky="w")

        # Bottom tick mark (below the ORP character).
        self._tick_bottom = tk.Frame(
            self._container,
            bg=theme.accent,
            width=self.TICK_WIDTH,
            height=self.TICK_LENGTH,
        )
        self._tick_bottom.grid(row=2, column=1, pady=(2, 0))

        # Give the pre-label a minimum width so short prefixes don't
        # cause the word to jump around. We measure a reasonable width
        # using font metrics and set it as minsize on column 0.
        self._update_min_width()

    def _update_min_width(self) -> None:
        """Set a minimum column width for the pre-ORP label so the ORP
        position stays roughly centered even for short words."""
        font = tkfont.Font(
            family=self._font_family,
            size=self._font_size,
            weight="bold",
        )
        # Reserve space for ~8 characters on each side, which handles
        # most words without clipping.
        char_width = font.measure("W")
        min_px = char_width * 8
        self._container.grid_columnconfigure(0, minsize=min_px)
        self._container.grid_columnconfigure(2, minsize=min_px)

    def show(self, word: str) -> None:
        """Display the given word with ORP alignment."""
        if not word:
            self.clear()
            return

        orp = _orp_index(word)

        pre_text = word[:orp]
        orp_char = word[orp] if orp < len(word) else ""
        post_text = word[orp + 1:] if orp + 1 < len(word) else ""

        self._pre_label.config(text=pre_text)
        self._orp_label.config(text=orp_char)
        self._post_label.config(text=post_text)

    def clear(self) -> None:
        self._pre_label.config(text="")
        self._orp_label.config(text="")
        self._post_label.config(text="")

    def apply_theme(self, theme: Theme) -> None:
        """Re-color every widget to match the new theme."""
        self._theme = theme
        self.config(bg=theme.background)
        self._container.config(bg=theme.background)
        self._pre_label.config(bg=theme.background, fg=theme.text)
        self._orp_label.config(bg=theme.background, fg=theme.accent)
        self._post_label.config(bg=theme.background, fg=theme.text)
        self._tick_top.config(bg=theme.accent)
        self._tick_bottom.config(bg=theme.accent)

    def update_font(self, family: str | None = None,
                    size: int | None = None) -> None:
        """Update the display font. Used for live preview from settings."""
        if family is not None:
            self._font_family = family
        if size is not None:
            self._font_size = size

        new_font = (self._font_family, self._font_size, "bold")
        for label in (self._pre_label, self._orp_label, self._post_label):
            label.config(font=new_font)
        self._update_min_width()