"""
Reader view: the big centered word in the middle of the window.

Phase 5: ORP (Optimal Recognition Point) alignment. The word is split
into three parts — pre-ORP text, the ORP character (highlighted in the
accent color), and post-ORP text. The ORP character is pinned at a
fixed pixel coordinate (approximately 38% of the view width) using
place() for absolute positioning. The pre-ORP label is right-aligned
*to* that coordinate, and the post-ORP label is left-aligned *from* it.

Unlike a grid layout, this guarantees the ORP character never shifts
horizontally regardless of the surrounding text content. The vertical
tick marks sit at exactly the same x-coordinate as the ORP label.
"""

import tkinter as tk
import tkinter.font as tkfont

from ui.theme import Theme


# The ORP focal point as a fraction of the view width. 0.38 places it
# slightly left of center, matching natural reading fixation.
ORP_RELX = 0.50


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
    """Displays one word at a time with ORP alignment at a fixed focal point."""

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

        # Cache the font object for measurement.
        self._font = tkfont.Font(
            family=self._font_family,
            size=self._font_size,
            weight="bold",
        )

        self._build_layout()

        # Re-position elements whenever the frame resizes.
        self.bind("<Configure>", self._on_resize)

    def _build_layout(self) -> None:
        theme = self._theme
        bold_font = (self._font_family, self._font_size, "bold")

        # Top tick mark — pinned at the ORP x-coordinate.
        self._tick_top = tk.Frame(
            self,
            bg=theme.accent,
            width=self.TICK_WIDTH,
            height=self.TICK_LENGTH,
        )

        # Pre-ORP label: right-aligned so its right edge meets the ORP point.
        self._pre_label = tk.Label(
            self,
            text="",
            font=bold_font,
            bg=theme.background,
            fg=theme.text,
            anchor="e",
        )

        # ORP character label: its left edge starts at the ORP point.
        self._orp_label = tk.Label(
            self,
            text="",
            font=bold_font,
            bg=theme.background,
            fg=theme.accent,
            anchor="w",
        )

        # Post-ORP label: left-aligned, starts after the ORP character.
        self._post_label = tk.Label(
            self,
            text="",
            font=bold_font,
            bg=theme.background,
            fg=theme.text,
            anchor="w",
        )

        # Bottom tick mark — pinned at the ORP x-coordinate.
        self._tick_bottom = tk.Frame(
            self,
            bg=theme.accent,
            width=self.TICK_WIDTH,
            height=self.TICK_LENGTH,
        )

        # Initial placement — will be corrected on first <Configure>.
        self._place_elements()

    def _place_elements(self) -> None:
        """Position all elements using place() at the fixed ORP coordinate."""
        w = self.winfo_width()
        h = self.winfo_height()

        # If the widget hasn't been mapped yet, defer.
        if w <= 1 or h <= 1:
            return

        orp_x = int(w * ORP_RELX)
        center_y = h // 2

        # Measure the ORP character height for vertical centering.
        line_height = self._font.metrics("linespace")
        half_line = line_height // 2

        # Top tick: centered horizontally on orp_x, above the text.
        tick_top_y = center_y - half_line - self.TICK_LENGTH - 2
        self._tick_top.place(
            x=orp_x - self.TICK_WIDTH // 2,
            y=tick_top_y,
            width=self.TICK_WIDTH,
            height=self.TICK_LENGTH,
        )

        # Bottom tick: centered horizontally on orp_x, below the text.
        tick_bot_y = center_y + half_line + 2
        self._tick_bottom.place(
            x=orp_x - self.TICK_WIDTH // 2,
            y=tick_bot_y,
            width=self.TICK_WIDTH,
            height=self.TICK_LENGTH,
        )

        # Pre-ORP label: right edge at orp_x, vertically centered.
        # anchor="e" means the label's right edge is at (x, y).
        self._pre_label.place(x=orp_x, y=center_y, anchor="e")

        # ORP label: left edge at orp_x, vertically centered.
        self._orp_label.place(x=orp_x, y=center_y, anchor="w")

        # Post-ORP label: positioned just after the ORP character.
        # We measure the ORP character's width and offset from orp_x.
        self._place_post_label(orp_x, center_y)

    def _place_post_label(self, orp_x: int, center_y: int) -> None:
        """Position the post-ORP label immediately after the ORP character."""
        orp_text = self._orp_label.cget("text")
        if orp_text:
            orp_char_width = self._font.measure(orp_text)
        else:
            orp_char_width = 0
        self._post_label.place(
            x=orp_x + orp_char_width,
            y=center_y,
            anchor="w",
        )

    def _on_resize(self, _event: tk.Event) -> None:
        """Re-pin elements when the frame changes size."""
        self._place_elements()

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

        # Re-position the post label since the ORP character may have
        # a different width than the previous one.
        w = self.winfo_width()
        h = self.winfo_height()
        if w > 1 and h > 1:
            orp_x = int(w * ORP_RELX)
            center_y = h // 2
            self._place_post_label(orp_x, center_y)

    def clear(self) -> None:
        self._pre_label.config(text="")
        self._orp_label.config(text="")
        self._post_label.config(text="")

    def apply_theme(self, theme: Theme) -> None:
        """Re-color every widget to match the new theme."""
        self._theme = theme
        self.config(bg=theme.background)
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

        # Rebuild the measurement font.
        self._font.config(
            family=self._font_family,
            size=self._font_size,
            weight="bold",
        )

        # Re-position everything since line height may have changed.
        self._place_elements()