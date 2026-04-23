"""
Tooltip helper.

Tkinter has no native tooltip widget. This module provides a small
ToolTip class that shows a floating label on hover after a short
delay. Used by the transport buttons and anywhere else a tooltip
would help discoverability.

Usage:
    ToolTip(button_widget, "Restart from beginning (Home)")
"""

from __future__ import annotations

import tkinter as tk


class ToolTip:
    """Attach a hover tooltip to any Tk widget."""

    DELAY_MS = 500      # Time before showing the tooltip.
    WRAP_LENGTH = 250   # Max tooltip width in pixels.

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self._widget = widget
        self._text = text
        self._tip_window: tk.Toplevel | None = None
        self._after_id: str | None = None

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")

    def update_text(self, text: str) -> None:
        """Change the tooltip text (e.g. when button state changes)."""
        self._text = text

    def _on_enter(self, _event: tk.Event) -> None:
        self._after_id = self._widget.after(self.DELAY_MS, self._show)

    def _on_leave(self, _event: tk.Event) -> None:
        if self._after_id is not None:
            self._widget.after_cancel(self._after_id)
            self._after_id = None
        self._hide()

    def _show(self) -> None:
        if self._tip_window or not self._text:
            return

        x = self._widget.winfo_rootx() + self._widget.winfo_width() // 2
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 4

        self._tip_window = tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)

        label = tk.Label(
            tw,
            text=self._text,
            background="#333333",
            foreground="#f0f0f0",
            font=("Helvetica", 9),
            relief="solid",
            borderwidth=1,
            wraplength=self.WRAP_LENGTH,
            padx=6,
            pady=3,
        )
        label.pack()

        # Position the tooltip centered below the widget.
        tw.update_idletasks()
        tip_width = tw.winfo_width()
        x = x - tip_width // 2
        tw.wm_geometry(f"+{x}+{y}")

    def _hide(self) -> None:
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None
