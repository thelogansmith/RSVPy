"""
Recent files window.

A Toplevel showing recently opened files sorted by last-opened date,
newest first. Double-click or Enter opens the selected file in the
main reader window. Files that no longer exist on disk are flagged
and removed from the list.

Backed by stats.json's per_file section — no separate recents file.
"""

from __future__ import annotations

import tkinter as tk
from datetime import datetime
from pathlib import Path
from typing import Callable

from storage import stats as stats_store
from ui.theme import Theme


class RecentsWindow:
    """Toplevel window listing recently opened files."""

    def __init__(self, parent: tk.Misc, theme: Theme,
                 on_open_file: Callable[[Path], None]) -> None:
        self._theme = theme
        self._on_open_file = on_open_file
        self._entries: list[dict] = []

        self.top = tk.Toplevel(parent)
        self.top.title("Recent Files")
        self.top.geometry("500x360")
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.config(bg=theme.background)

        self._build_widgets()
        self._populate()

        self.top.bind("<Escape>", lambda _e: self.top.destroy())

    def _build_widgets(self) -> None:
        theme = self._theme

        # Header label.
        header = tk.Label(
            self.top, text="Recent Files",
            font=("Helvetica", 13, "bold"),
            bg=theme.background, fg=theme.text,
            anchor="w",
        )
        header.pack(fill="x", padx=14, pady=(12, 6))

        # Listbox with scrollbar.
        list_frame = tk.Frame(self.top, bg=theme.background)
        list_frame.pack(fill="both", expand=True, padx=14, pady=(0, 6))

        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        self._listbox = tk.Listbox(
            list_frame,
            font=("Helvetica", 10),
            bg=theme.surface,
            fg=theme.text,
            selectbackground=theme.accent,
            selectforeground="#ffffff",
            activestyle="none",
            highlightthickness=0,
            bd=1,
            relief="flat",
            yscrollcommand=scrollbar.set,
        )
        self._listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=self._listbox.yview)

        self._listbox.bind("<Double-Button-1>", lambda _e: self._on_select())
        self._listbox.bind("<Return>", lambda _e: self._on_select())

        # Bottom bar with hint text and close button.
        bottom = tk.Frame(self.top, bg=theme.background)
        bottom.pack(fill="x", padx=14, pady=(0, 12))

        hint = tk.Label(
            bottom,
            text="Double-click or press Enter to open",
            bg=theme.background, fg=theme.text_muted,
            font=("Helvetica", 9),
            anchor="w",
        )
        hint.pack(side="left")

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

    def _populate(self) -> None:
        """Fill the listbox with recent files from stats."""
        self._entries = stats_store.recent_files()
        self._listbox.delete(0, tk.END)

        if not self._entries:
            self._listbox.insert(tk.END, "  No recent files")
            self._listbox.config(state="disabled")
            return

        for entry in self._entries:
            line = self._format_entry(entry)
            self._listbox.insert(tk.END, line)

        # Select the first entry.
        self._listbox.selection_set(0)
        self._listbox.focus_set()

    def _format_entry(self, entry: dict) -> str:
        """Format a single recents entry for display in the listbox."""
        filename = entry["filename"]
        progress = entry.get("progress_percent", 0)

        # Parse and format the timestamp for readability.
        last_opened = entry.get("last_opened", "")
        date_str = self._format_date(last_opened)

        return f"  {filename:<30s} {progress:>3d}%    {date_str}"

    @staticmethod
    def _format_date(iso_str: str) -> str:
        """Convert an ISO timestamp to a human-friendly short format."""
        if not iso_str:
            return ""
        try:
            dt = datetime.fromisoformat(iso_str)
            now = datetime.now(dt.tzinfo)
            delta = now - dt

            if delta.days == 0:
                return f"Today {dt.strftime('%H:%M')}"
            elif delta.days == 1:
                return f"Yesterday {dt.strftime('%H:%M')}"
            elif delta.days < 7:
                return dt.strftime("%A %H:%M")
            else:
                return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return iso_str[:10] if len(iso_str) >= 10 else iso_str

    def _on_select(self) -> None:
        """Handle double-click or Enter on a listbox entry."""
        sel = self._listbox.curselection()
        if not sel:
            return

        idx = sel[0]
        if idx >= len(self._entries):
            return

        entry = self._entries[idx]
        path = Path(entry["path"])

        if not path.exists():
            # File was deleted or moved since it was last opened.
            # Remove from stats and refresh the list.
            stats_store.remove_file(entry["path"])
            self._listbox.delete(idx)
            self._entries.pop(idx)

            # Show a brief message in the listbox.
            self._listbox.insert(idx, f"  (File not found: {entry['filename']})")
            self._listbox.itemconfig(idx, fg=self._theme.text_muted)

            # Auto-remove the message after 2 seconds and re-populate.
            self.top.after(2000, self._populate)
            return

        self.top.destroy()
        self._on_open_file(path)
