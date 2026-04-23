"""
Reading statistics window.

A Toplevel showing aggregate and per-file reading statistics from
stats.json. Shows total words read, total active reading time, total
sessions, and a brief per-file breakdown. Opened via a "Stats" button
in the status bar or programmatically.

Backed by storage.stats.load_stats(). The window is stateless — it
reads fresh data on every open.
"""

from __future__ import annotations

import tkinter as tk

from storage import stats as stats_store
from ui.theme import Theme


def _format_time(seconds: float) -> str:
    """Format seconds into a human-friendly duration string."""
    seconds = round(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


class StatsWindow:
    """Toplevel window displaying reading statistics."""

    def __init__(self, parent: tk.Misc, theme: Theme) -> None:
        self._theme = theme

        self.top = tk.Toplevel(parent)
        self.top.title("Reading Statistics")
        self.top.geometry("420x340")
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.config(bg=theme.background)

        self._build_widgets()

        self.top.bind("<Escape>", lambda _e: self.top.destroy())

    def _build_widgets(self) -> None:
        theme = self._theme
        data = stats_store.load_stats()
        totals = data.get("totals", {})
        per_file = data.get("per_file", {})

        # Header.
        header = tk.Label(
            self.top, text="Reading Statistics",
            font=("Helvetica", 13, "bold"),
            bg=theme.background, fg=theme.text,
            anchor="w",
        )
        header.pack(fill="x", padx=14, pady=(12, 10))

        # Totals section.
        totals_frame = tk.Frame(self.top, bg=theme.surface)
        totals_frame.pack(fill="x", padx=14, pady=(0, 10))

        tokens_read = totals.get("tokens_read", 0)
        seconds_active = totals.get("seconds_active", 0.0)
        sessions = totals.get("sessions", 0)

        stats_lines = [
            ("Words read", f"{tokens_read:,}"),
            ("Active reading time", _format_time(seconds_active)),
            ("Sessions", str(sessions)),
            ("Files opened", str(len(per_file))),
        ]

        for label_text, value_text in stats_lines:
            row = tk.Frame(totals_frame, bg=theme.surface)
            row.pack(fill="x", padx=12, pady=4)

            lbl = tk.Label(
                row, text=label_text,
                font=("Helvetica", 10),
                bg=theme.surface, fg=theme.text_muted,
                anchor="w",
            )
            lbl.pack(side="left")

            val = tk.Label(
                row, text=value_text,
                font=("Helvetica", 10, "bold"),
                bg=theme.surface, fg=theme.text,
                anchor="e",
            )
            val.pack(side="right")

        # Add a small top/bottom padding inside the totals frame.
        totals_frame.pack_configure(ipady=6)

        # Per-file breakdown (top 5 by tokens read).
        if per_file:
            breakdown_header = tk.Label(
                self.top, text="Top files by words read",
                font=("Helvetica", 10, "bold"),
                bg=theme.background, fg=theme.text,
                anchor="w",
            )
            breakdown_header.pack(fill="x", padx=14, pady=(0, 4))

            # Sort by tokens_read descending, take top 5.
            sorted_files = sorted(
                per_file.items(),
                key=lambda item: item[1].get("tokens_read", 0),
                reverse=True,
            )[:5]

            breakdown_frame = tk.Frame(self.top, bg=theme.surface)
            breakdown_frame.pack(fill="x", padx=14, pady=(0, 10))

            for file_path, info in sorted_files:
                from pathlib import Path
                filename = Path(file_path).name
                file_tokens = info.get("tokens_read", 0)
                file_time = _format_time(info.get("seconds_active", 0.0))

                row = tk.Frame(breakdown_frame, bg=theme.surface)
                row.pack(fill="x", padx=12, pady=2)

                name_lbl = tk.Label(
                    row, text=filename,
                    font=("Helvetica", 9),
                    bg=theme.surface, fg=theme.text,
                    anchor="w",
                )
                name_lbl.pack(side="left")

                detail_lbl = tk.Label(
                    row, text=f"{file_tokens:,} words · {file_time}",
                    font=("Helvetica", 9),
                    bg=theme.surface, fg=theme.text_muted,
                    anchor="e",
                )
                detail_lbl.pack(side="right")

            breakdown_frame.pack_configure(ipady=4)

        # Close button.
        bottom = tk.Frame(self.top, bg=theme.background)
        bottom.pack(fill="x", padx=14, pady=(0, 12), side="bottom")

        close_btn = tk.Button(
            bottom, text="Close", width=8,
            command=self.top.destroy,
            bg=theme.surface, fg=theme.text,
            activebackground=theme.background,
            activeforeground=theme.text,
            highlightbackground=theme.surface,
            relief="flat",
        )
        close_btn.pack(side="right")
