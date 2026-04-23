"""
Settings panel.

A Toplevel window with sections for Display, Reading, and AI
Summarization preferences. Changes apply immediately (live preview)
and are persisted to config on close or on change.

Phase 4, steps 2-4.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import colorchooser
from typing import Callable

from storage import keystore
from ui.theme import Theme


# Font options available in the dropdown.
FONT_FAMILIES = [
    "Helvetica",
    "Arial",
    "Consolas",
    "Georgia",
    "Times New Roman",
]

# Font size range.
MIN_FONT_SIZE = 18
MAX_FONT_SIZE = 72

# Predefined accent color swatches.
ACCENT_SWATCHES = [
    "#4a9eff",  # Default blue
    "#2563eb",  # Deeper blue
    "#10b981",  # Green
    "#f59e0b",  # Amber
    "#ef4444",  # Red
    "#8b5cf6",  # Purple
    "#ec4899",  # Pink
    "#06b6d4",  # Cyan
]


class SettingsWindow:
    """Toplevel window for user preferences."""

    def __init__(
        self,
        parent: tk.Misc,
        theme: Theme,
        current_config: dict,
        on_font_changed: Callable[[str, int], None],
        on_accent_changed: Callable[[str | None], None],
        on_restart_confirm_changed: Callable[[bool], None],
        on_summary_prefs_changed: Callable[[dict], None],
        on_close: Callable[[dict], None],
    ) -> None:
        """
        Callbacks:
            on_font_changed(family, size) — live preview.
            on_accent_changed(color_hex_or_None) — live preview.
            on_restart_confirm_changed(enabled) — immediate.
            on_summary_prefs_changed(prefs_dict) — immediate.
            on_close(final_config) — called when the window closes.
        """
        self._theme = theme
        self._config = dict(current_config)
        self._on_font_changed = on_font_changed
        self._on_accent_changed = on_accent_changed
        self._on_restart_confirm_changed = on_restart_confirm_changed
        self._on_summary_prefs_changed = on_summary_prefs_changed
        self._on_close_cb = on_close

        self.top = tk.Toplevel(parent)
        self.top.title("Settings")
        self.top.geometry("440x560")
        self.top.resizable(False, True)
        self.top.minsize(440, 480)
        self.top.transient(parent)
        self.top.config(bg=theme.background)

        self.top.protocol("WM_DELETE_WINDOW", self._on_close)
        self.top.bind("<Escape>", lambda _e: self._on_close())

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

        # Scrollable content area.
        canvas = tk.Canvas(
            self.top, bg=theme.background, highlightthickness=0, bd=0
        )
        scrollbar = tk.Scrollbar(self.top, command=canvas.yview)

        self._content = tk.Frame(canvas, bg=theme.background)
        self._content.bind(
            "<Configure>",
            lambda _e: canvas.configure(scrollregion=canvas.bbox("all")),
        )

        canvas.create_window((0, 0), window=self._content, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Button row at bottom — packed first so it stays visible.
        btn_frame = tk.Frame(self.top, bg=theme.background)
        btn_frame.pack(side="bottom", fill="x", padx=18, pady=(8, 14))

        close_btn = tk.Button(
            btn_frame, text="Close", width=10,
            command=self._on_close,
            bg=theme.surface, fg=theme.text,
            activebackground=theme.background,
            activeforeground=theme.text,
            highlightbackground=theme.surface,
            relief="flat",
        )
        close_btn.pack(side="right")

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # --- Display section -------------------------------------------------
        self._section_header("Display")

        # Font family.
        font_row = self._option_row("Font")
        self._font_var = tk.StringVar(value=self._config.get("font_family", "Helvetica"))
        font_menu = tk.OptionMenu(
            font_row, self._font_var, *FONT_FAMILIES,
            command=self._on_font_family_changed,
        )
        font_menu.config(
            bg=theme.surface, fg=theme.text, width=16,
            highlightthickness=0, relief="flat",
            activebackground=theme.background, activeforeground=theme.text,
        )
        font_menu["menu"].config(bg=theme.surface, fg=theme.text)
        font_menu.pack(side="right")

        # Font size.
        size_row = self._option_row("Size")
        self._size_var = tk.IntVar(value=self._config.get("font_size", 36))

        size_minus = tk.Button(
            size_row, text="−", width=2,
            command=lambda: self._adjust_font_size(-2),
            bg=theme.surface, fg=theme.text, relief="flat",
        )
        size_minus.pack(side="left", padx=(0, 4))

        self._size_label = tk.Label(
            size_row, textvariable=self._size_var, width=4,
            bg=theme.background, fg=theme.text,
            font=("Helvetica", 10, "bold"),
            anchor="center",
        )
        self._size_label.pack(side="left")

        size_plus = tk.Button(
            size_row, text="+", width=2,
            command=lambda: self._adjust_font_size(2),
            bg=theme.surface, fg=theme.text, relief="flat",
        )
        size_plus.pack(side="left", padx=(4, 0))

        # Accent color.
        accent_row = self._option_row("Accent")
        swatch_frame = tk.Frame(accent_row, bg=theme.background)
        swatch_frame.pack(side="right")

        current_accent = self._config.get("accent_color") or theme.accent
        self._accent_var = current_accent

        self._swatch_buttons: list[tk.Button] = []
        for color in ACCENT_SWATCHES:
            btn = tk.Button(
                swatch_frame, bg=color, width=2, height=1,
                relief="solid" if color == current_accent else "flat",
                bd=2 if color == current_accent else 1,
                command=lambda c=color: self._on_accent_swatch(c),
            )
            btn.pack(side="left", padx=1)
            self._swatch_buttons.append(btn)

        custom_btn = tk.Button(
            swatch_frame, text="...", width=2,
            command=self._on_accent_custom,
            bg=theme.surface, fg=theme.text, relief="flat",
        )
        custom_btn.pack(side="left", padx=(4, 0))

        # --- Reading section -------------------------------------------------
        self._section_header("Reading")

        restart_row = self._option_row("")
        self._restart_var = tk.BooleanVar(
            value=self._config.get("restart_confirm", True)
        )
        restart_check = tk.Checkbutton(
            restart_row,
            text="Confirm before restarting",
            variable=self._restart_var,
            command=self._on_restart_confirm_toggled,
            bg=theme.background, fg=theme.text,
            selectcolor=theme.surface,
            activebackground=theme.background,
            activeforeground=theme.text,
            highlightthickness=0, bd=0,
            anchor="w",
        )
        restart_check.pack(side="left")

        # --- AI Summarization section ----------------------------------------
        self._section_header("AI Summarization")

        # Provider (currently only Anthropic).
        provider_row = self._option_row("Provider")
        provider_label = tk.Label(
            provider_row, text="Anthropic (Claude)",
            bg=theme.background, fg=theme.text,
            font=("Helvetica", 10),
        )
        provider_label.pack(side="right")

        # API key entry.
        key_row = self._option_row("API Key")
        key_inner = tk.Frame(key_row, bg=theme.background)
        key_inner.pack(side="right")

        self._key_var = tk.StringVar()
        self._key_show = False

        # Load existing key (masked).
        existing_key = keystore.get_api_key()
        if existing_key:
            self._key_var.set(existing_key)

        self._key_entry = tk.Entry(
            key_inner, textvariable=self._key_var, width=22,
            show="•", font=("Helvetica", 10),
            bg=theme.surface, fg=theme.text,
            insertbackground=theme.text,
            highlightthickness=1,
            highlightbackground=theme.surface,
            highlightcolor=theme.accent,
            relief="flat",
        )
        self._key_entry.pack(side="left", padx=(0, 4))
        self._key_entry.bind("<FocusOut>", lambda _e: self._on_key_changed())

        self._toggle_key_btn = tk.Button(
            key_inner, text="Show", width=4,
            command=self._toggle_key_visibility,
            bg=theme.surface, fg=theme.text_muted, relief="flat",
        )
        self._toggle_key_btn.pack(side="left")

        # Storage backend info.
        backend_row = self._option_row("")
        backend_info = tk.Label(
            backend_row,
            text=f"Stored in: {keystore.storage_backend()}",
            bg=theme.background, fg=theme.text_muted,
            font=("Helvetica", 8),
            anchor="w",
        )
        backend_info.pack(side="left")

        # Test connection button.
        test_row = self._option_row("")
        self._test_btn = tk.Button(
            test_row, text="Test connection", width=14,
            command=self._on_test_connection,
            bg=theme.surface, fg=theme.text, relief="flat",
        )
        self._test_btn.pack(side="left")

        self._test_status = tk.Label(
            test_row, text="", bg=theme.background,
            fg=theme.text_muted, font=("Helvetica", 9),
        )
        self._test_status.pack(side="left", padx=(8, 0))

        # Auto-prompt checkbox.
        auto_row = self._option_row("")
        self._auto_prompt_var = tk.BooleanVar(
            value=self._config.get("summary_auto_prompt", False)
        )
        auto_check = tk.Checkbutton(
            auto_row,
            text="Offer summary when I finish a document",
            variable=self._auto_prompt_var,
            command=self._on_auto_prompt_toggled,
            bg=theme.background, fg=theme.text,
            selectcolor=theme.surface,
            activebackground=theme.background,
            activeforeground=theme.text,
            highlightthickness=0, bd=0,
            anchor="w",
        )
        auto_check.pack(side="left")

    # --- Widget builders (reduce repetition) ---------------------------------

    def _section_header(self, title: str) -> None:
        theme = self._theme
        header = tk.Label(
            self._content, text=title,
            font=("Helvetica", 12, "bold"),
            bg=theme.background, fg=theme.text,
            anchor="w",
        )
        header.pack(fill="x", padx=18, pady=(14, 4))

        # Separator line.
        sep = tk.Frame(self._content, bg=theme.text_muted, height=1)
        sep.pack(fill="x", padx=18, pady=(0, 8))

    def _option_row(self, label_text: str) -> tk.Frame:
        theme = self._theme
        row = tk.Frame(self._content, bg=theme.background)
        row.pack(fill="x", padx=18, pady=3)

        if label_text:
            lbl = tk.Label(
                row, text=label_text,
                bg=theme.background, fg=theme.text_muted,
                font=("Helvetica", 10),
                anchor="w", width=8,
            )
            lbl.pack(side="left")

        return row

    # --- Display callbacks ---------------------------------------------------

    def _on_font_family_changed(self, family: str) -> None:
        self._config["font_family"] = family
        self._on_font_changed(family, self._size_var.get())

    def _adjust_font_size(self, delta: int) -> None:
        new_size = max(MIN_FONT_SIZE, min(MAX_FONT_SIZE, self._size_var.get() + delta))
        if new_size != self._size_var.get():
            self._size_var.set(new_size)
            self._config["font_size"] = new_size
            self._on_font_changed(self._font_var.get(), new_size)

    def _on_accent_swatch(self, color: str) -> None:
        self._accent_var = color
        self._config["accent_color"] = color

        # Update swatch button visuals.
        for btn in self._swatch_buttons:
            btn_color = btn.cget("bg")
            if btn_color == color:
                btn.config(relief="solid", bd=2)
            else:
                btn.config(relief="flat", bd=1)

        self._on_accent_changed(color)

    def _on_accent_custom(self) -> None:
        result = colorchooser.askcolor(
            initialcolor=self._accent_var,
            title="Choose accent color",
            parent=self.top,
        )
        if result and result[1]:
            color = result[1]
            self._accent_var = color
            self._config["accent_color"] = color

            # Deselect all swatches since this is custom.
            for btn in self._swatch_buttons:
                btn.config(relief="flat", bd=1)

            self._on_accent_changed(color)

    # --- Reading callbacks ---------------------------------------------------

    def _on_restart_confirm_toggled(self) -> None:
        enabled = self._restart_var.get()
        self._config["restart_confirm"] = enabled
        self._on_restart_confirm_changed(enabled)

    # --- AI callbacks --------------------------------------------------------

    def _toggle_key_visibility(self) -> None:
        self._key_show = not self._key_show
        self._key_entry.config(show="" if self._key_show else "•")
        self._toggle_key_btn.config(text="Hide" if self._key_show else "Show")

    def _on_key_changed(self) -> None:
        """Save the API key when the entry loses focus."""
        key = self._key_var.get().strip()
        if key:
            success = keystore.set_api_key(key)
            self._config["api_key_stored"] = success
        else:
            keystore.delete_api_key()
            self._config["api_key_stored"] = False

    def _on_test_connection(self) -> None:
        """Test the API key on a background thread."""
        key = self._key_var.get().strip()
        if not key:
            self._test_status.config(text="Enter a key first.", fg="#ef4444")
            return

        # Save the key first.
        self._on_key_changed()

        self._test_btn.config(state="disabled", text="Testing...")
        self._test_status.config(text="", fg=self._theme.text_muted)

        def _bg_test():
            from core.summarizer import test_api_key
            success, message = test_api_key(key, "anthropic")
            # Schedule UI update on main thread.
            self.top.after(0, lambda: self._show_test_result(success, message))

        thread = threading.Thread(target=_bg_test, daemon=True)
        thread.start()

    def _show_test_result(self, success: bool, message: str) -> None:
        self._test_btn.config(state="normal", text="Test connection")
        color = "#10b981" if success else "#ef4444"
        self._test_status.config(text=message, fg=color)

    def _on_auto_prompt_toggled(self) -> None:
        self._config["summary_auto_prompt"] = self._auto_prompt_var.get()
        self._on_summary_prefs_changed({
            "summary_auto_prompt": self._auto_prompt_var.get(),
        })

    # --- Close ---------------------------------------------------------------

    def _on_close(self) -> None:
        # Ensure key is saved on close.
        self._on_key_changed()
        self._on_close_cb(self._config)
        self.top.destroy()

    def is_alive(self) -> bool:
        try:
            return self.top.winfo_exists()
        except tk.TclError:
            return False
