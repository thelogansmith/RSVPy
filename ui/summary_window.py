"""
Summary display window.

A Toplevel showing the AI-generated summary of the current document.
Supports copy-to-clipboard and regeneration. Themed to match the app.

Phase 4, step 6.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from ui.theme import Theme


class SummaryWindow:
    """Toplevel window displaying a document summary."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: Theme,
        filename: str,
        on_regenerate: Callable[[], None],
    ) -> None:
        self._theme = theme
        self._on_regenerate = on_regenerate

        self.top = tk.Toplevel(parent)
        self.top.title(f"Summary — {filename}")
        self.top.geometry("520x400")
        self.top.resizable(True, True)
        self.top.minsize(400, 250)
        self.top.transient(parent)
        self.top.config(bg=theme.background)

        self.top.bind("<Escape>", lambda _e: self.top.destroy())

        self._build_widgets()
        self._center_on_parent(parent)

    def _center_on_parent(self, parent: tk.Misc) -> None:
        self.top.update_idletasks()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        dw = self.top.winfo_width()
        dh = self.top.winfo_height()
        x = px + (pw - dw) // 2
        y = py + (ph - dh) // 3
        self.top.geometry(f"+{x}+{y}")

    def _build_widgets(self) -> None:
        theme = self._theme

        # Button row — packed bottom-first to guarantee layout space.
        btn_frame = tk.Frame(self.top, bg=theme.background)
        btn_frame.pack(side="bottom", fill="x", padx=14, pady=(8, 14))

        close_btn = tk.Button(
            btn_frame, text="Close", width=8,
            command=self.top.destroy,
            bg=theme.surface, fg=theme.text,
            activebackground=theme.background,
            activeforeground=theme.text,
            highlightbackground=theme.surface,
            relief="flat",
        )
        close_btn.pack(side="right", padx=(6, 0))

        regen_btn = tk.Button(
            btn_frame, text="Regenerate", width=10,
            command=self._on_regenerate,
            bg=theme.surface, fg=theme.text,
            activebackground=theme.background,
            activeforeground=theme.text,
            highlightbackground=theme.surface,
            relief="flat",
        )
        regen_btn.pack(side="right", padx=(6, 0))

        copy_btn = tk.Button(
            btn_frame, text="Copy", width=8,
            command=self._copy_to_clipboard,
            bg=theme.surface, fg=theme.text,
            activebackground=theme.background,
            activeforeground=theme.text,
            highlightbackground=theme.surface,
            relief="flat",
        )
        copy_btn.pack(side="right")

        self._copy_status = tk.Label(
            btn_frame, text="", bg=theme.background,
            fg=theme.text_muted, font=("Helvetica", 9),
        )
        self._copy_status.pack(side="left")

        # Scrollable text widget.
        text_frame = tk.Frame(self.top, bg=theme.background)
        text_frame.pack(side="top", fill="both", expand=True, padx=14, pady=(12, 0))

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        self._text = tk.Text(
            text_frame,
            font=("Helvetica", 11),
            bg=theme.surface, fg=theme.text,
            wrap="word", padx=12, pady=10,
            highlightthickness=0, bd=0, relief="flat",
            yscrollcommand=scrollbar.set,
            spacing1=2, spacing3=2,
        )
        self._text.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._text.yview)

        self._text.config(state="disabled")

    def show_summary(self, text: str) -> None:
        """Display the summary text."""
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("1.0", text)
        self._text.config(state="disabled")

    def show_progress(self, message: str) -> None:
        """Show a progress/status message while generating."""
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("1.0", message)
        self._text.config(state="disabled")

    def show_error(self, message: str) -> None:
        """Show an error message."""
        self._text.config(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("1.0", f"Error: {message}")
        self._text.config(state="disabled")

    def _copy_to_clipboard(self) -> None:
        """Copy the summary text to the system clipboard."""
        content = self._text.get("1.0", "end-1c").strip()
        if not content or content.startswith("Error:") or content.startswith("Generating"):
            return
        self.top.clipboard_clear()
        self.top.clipboard_append(content)
        self._copy_status.config(text="Copied!")
        self.top.after(2000, lambda: self._copy_status.config(text=""))

    def apply_theme(self, theme: Theme) -> None:
        """Re-color to match a new theme."""
        self._theme = theme
        self.top.config(bg=theme.background)
        self._text.config(bg=theme.surface, fg=theme.text)

    def is_alive(self) -> bool:
        try:
            return self.top.winfo_exists()
        except tk.TclError:
            return False
