"""
Main window.

Owns the Session, the Tk root, and the play loop. Delegates word
display to ReaderView, file parsing to the importer registry, and
persistence to the storage package.

Phase 5 changes:
  - _tick() passes token_type and word_length to delay_ms() for
    variable timing (sentence/paragraph pauses, word-length scaling,
    punctuation-only reduced delay).
"""

from __future__ import annotations

import bisect
import hashlib
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from core.session import Session
from core.timing import clamp_wpm, delay_ms
from importers.registry import all_extensions, find_importer
from storage import config as config_store
from storage import keystore
from storage import progress as progress_store
from storage import stats as stats_store
from ui.context_window import ContextWindow
from ui.dialogs import ask_file_changed, ask_restart_confirm
from ui.reader_view import ReaderView
from ui.recents_window import RecentsWindow
from ui.stats_window import StatsWindow
from ui.summary_window import SummaryWindow
from ui.theme import DARK, LIGHT, Theme, get_theme
from ui.tooltip import ToolTip


# --- Layout constants ---------------------------------------------------------

WINDOW_TITLE = "RSVPy"
DEFAULT_WIDTH = 700
DEFAULT_HEIGHT = 300
MIN_WIDTH = 700
MIN_HEIGHT = 300
WPM_STEP = 25
REWIND_TOKENS = 5
SKIP_TOKENS = 5
PROGRESS_CHECKPOINT_EVERY = 100
LOAD_POLL_MS = 50
PROGRESS_BAR_HEIGHT = 8


def _hash_source(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class MainWindow:

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.session = Session()
        self._tokens_since_checkpoint = 0
        self._context_window: ContextWindow | None = None
        self._settings_window = None
        self._summary_window: SummaryWindow | None = None
        self._loading = False
        self._load_queue: queue.Queue = queue.Queue()
        self._summary_queue: queue.Queue = queue.Queue()

        cfg = self._load_config()
        self.session.wpm = clamp_wpm(cfg.get("wpm", 300))
        self._dark_mode = bool(cfg.get("dark_mode", True))
        self._accent_color: str | None = cfg.get("accent_color")
        self._theme: Theme = get_theme(self._dark_mode, self._accent_color)
        self._restart_confirm: bool = bool(cfg.get("restart_confirm", True))
        self._context_window_open: bool = bool(cfg.get("context_window_open", False))
        self._font_family: str = cfg.get("font_family", "Helvetica")
        self._font_size: int = cfg.get("font_size", 36)
        self._summary_auto_prompt: bool = bool(cfg.get("summary_auto_prompt", False))

        self._build_window(cfg)
        self._build_widgets()
        self._bind_shortcuts()
        self._apply_theme(self._theme)
        self._refresh_status()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # --- Window setup ---------------------------------------------------------

    def _build_window(self, cfg: dict) -> None:
        self.root.title(WINDOW_TITLE)

        saved_geom = cfg.get("main_window_geometry")
        if saved_geom and isinstance(saved_geom, str):
            self.root.geometry(saved_geom)
        else:
            self.root.geometry(f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")

        self.root.resizable(True, True)
        self.root.minsize(MIN_WIDTH, MIN_HEIGHT)

    def _build_widgets(self) -> None:
        # Status bar (top) ----------------------------------------------------
        self.status_bar = tk.Frame(self.root, height=28)
        self.status_bar.pack(side="top", fill="x")
        self.status_bar.pack_propagate(False)

        self.filename_label = tk.Label(self.status_bar, anchor="w", padx=10)
        self.filename_label.pack(side="left", fill="y")

        self.wpm_label = tk.Label(self.status_bar, anchor="e", padx=10)
        self.wpm_label.pack(side="right", fill="y")

        self.progress_label = tk.Label(self.status_bar, anchor="e", padx=10)
        self.progress_label.pack(side="right", fill="y")

        # Status bar buttons (right-aligned): Settings, Stats, Recent, Context.
        self.settings_btn = tk.Button(
            self.status_bar, text="\u2699", bd=0, padx=6,
            command=self._on_settings,
        )
        self.settings_btn.pack(side="right", fill="y", padx=2)

        self.stats_btn = tk.Button(
            self.status_bar, text="Stats", bd=0, padx=6,
            command=self._on_stats,
        )
        self.stats_btn.pack(side="right", fill="y", padx=2)

        self.recent_btn = tk.Button(
            self.status_bar, text="Recent", bd=0, padx=6,
            command=self._on_recents,
        )
        self.recent_btn.pack(side="right", fill="y", padx=2)

        self.context_btn = tk.Button(
            self.status_bar, text="Context", bd=0, padx=6,
            command=self._on_toggle_context,
        )
        self.context_btn.pack(side="right", fill="y", padx=2)

        # Control bar (bottom) ------------------------------------------------
        self.control_bar = tk.Frame(self.root, height=50)
        self.control_bar.pack(side="bottom", fill="x")
        self.control_bar.pack_propagate(False)

        # Left zone: Open button.
        self.open_btn = tk.Button(
            self.control_bar, text="Open", width=6, command=self._on_open
        )
        self.open_btn.pack(side="left", padx=(10, 0), pady=8)

        # Right zone: theme toggle + WPM stepper (packed right-to-left).
        self.theme_btn = tk.Button(
            self.control_bar, text="\u2600" if self._dark_mode else "\U0001f319",
            width=3, command=self._on_toggle_theme,
        )
        self.theme_btn.pack(side="right", padx=(4, 10), pady=8)

        self.wpm_plus_btn = tk.Button(
            self.control_bar, text="+", width=2,
            command=lambda: self._adjust_wpm(WPM_STEP),
        )
        self.wpm_plus_btn.pack(side="right", padx=1, pady=8)

        self.wpm_value_label = tk.Label(self.control_bar, width=4, anchor="center")
        self.wpm_value_label.pack(side="right", padx=1, pady=8)

        self.wpm_minus_btn = tk.Button(
            self.control_bar, text="\u2212", width=2,
            command=lambda: self._adjust_wpm(-WPM_STEP),
        )
        self.wpm_minus_btn.pack(side="right", padx=1, pady=8)

        self.wpm_prefix_label = tk.Label(self.control_bar, text="WPM:")
        self.wpm_prefix_label.pack(side="right", padx=(4, 1), pady=8)

        # Center zone: transport buttons.
        transport = tk.Frame(self.control_bar)
        transport.pack(side="left", fill="both", expand=True, pady=4)
        self._transport_frame = transport

        inner = tk.Frame(transport)
        inner.place(relx=0.5, rely=0.5, anchor="center")

        self.restart_btn = tk.Button(
            inner, text="\u23EE", width=3, command=self._on_restart
        )
        self.restart_btn.pack(side="left", padx=2)

        self.rewind_btn = tk.Button(
            inner, text="\u23EA", width=3, command=self._on_rewind
        )
        self.rewind_btn.pack(side="left", padx=2)

        self.play_btn = tk.Button(
            inner, text="\u25B6 Play", width=8, command=self._on_play_pause
        )
        self.play_btn.pack(side="left", padx=2)

        self.skip_btn = tk.Button(
            inner, text="\u23E9", width=3, command=self._on_skip
        )
        self.skip_btn.pack(side="left", padx=2)

        # Summarize button — visible only when API key is configured.
        self.summarize_btn = tk.Button(
            inner, text="Summarize", width=9, command=self._on_summarize
        )

        # Tooltips for transport buttons.
        self._tip_restart = ToolTip(self.restart_btn, "Restart from beginning (Home)")
        self._tip_rewind = ToolTip(self.rewind_btn, "Rewind 5 words (\u2190)")
        self._tip_play = ToolTip(self.play_btn, "Play / Pause (Space)")
        self._tip_skip = ToolTip(self.skip_btn, "Skip forward 5 words (\u2192)")
        self._tip_summarize = ToolTip(self.summarize_btn, "Generate AI summary of document")

        # Progress bar — between reader view and control bar.
        self._progress_canvas = tk.Canvas(
            self.root,
            height=PROGRESS_BAR_HEIGHT,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        self._progress_canvas.pack(side="bottom", fill="x")
        self._progress_canvas.bind("<Button-1>", self._on_progress_click)
        self._progress_canvas.bind("<B1-Motion>", self._on_progress_drag)

        # Reader view (fills remaining space).
        self.reader_view = ReaderView(
            self.root, self._theme,
            font_family=self._font_family,
            font_size=self._font_size,
        )
        self.reader_view.pack(side="top", fill="both", expand=True)

        # Collect transport buttons for enable/disable during loading.
        self._transport_buttons = [
            self.restart_btn, self.rewind_btn,
            self.play_btn, self.skip_btn,
        ]

        # Show/hide summarize button based on API key status.
        self._refresh_summarize_button()

    def _bind_shortcuts(self) -> None:
        self.root.bind("<space>", lambda _e: self._on_play_pause())
        self.root.bind("<Left>", lambda _e: self._on_rewind())
        self.root.bind("<Right>", lambda _e: self._on_skip())
        self.root.bind("<Home>", lambda _e: self._on_restart())
        self.root.bind("<Control-o>", lambda _e: self._on_open())
        self.root.bind("<Control-r>", lambda _e: self._on_recents())
        self.root.bind("<Control-t>", lambda _e: self._on_toggle_context())
        self.root.bind("<Control-comma>", lambda _e: self._on_settings())

    # --- Theming --------------------------------------------------------------

    def _apply_theme(self, theme: Theme) -> None:
        self._theme = theme
        bg = theme.background
        surface = theme.surface
        text = theme.text
        muted = theme.text_muted

        self.root.config(bg=bg)
        for bar in (self.status_bar, self.control_bar):
            bar.config(bg=surface)
        for label in (
            self.filename_label,
            self.progress_label,
            self.wpm_label,
            self.wpm_prefix_label,
            self.wpm_value_label,
        ):
            label.config(bg=surface, fg=muted if label is not self.filename_label else text)

        self._transport_frame.config(bg=surface)
        for child in self._transport_frame.winfo_children():
            child.config(bg=surface)

        for btn in (
            self.open_btn, self.restart_btn, self.rewind_btn,
            self.play_btn, self.skip_btn, self.theme_btn,
            self.wpm_plus_btn, self.wpm_minus_btn,
            self.summarize_btn,
        ):
            btn.config(bg=surface, fg=text, activebackground=bg, activeforeground=text,
                       highlightbackground=surface, relief="flat")

        for status_btn in (self.recent_btn, self.stats_btn, self.context_btn,
                           self.settings_btn):
            status_btn.config(
                bg=surface, fg=muted,
                activebackground=bg, activeforeground=text,
                highlightbackground=surface,
            )

        self.theme_btn.config(text="\u2600" if theme.name == "dark" else "\U0001f319")
        self.reader_view.apply_theme(theme)

        # Progress bar.
        self._progress_canvas.config(bg=surface)
        self._draw_progress_bar()

        # Context window, if open.
        if self._context_window and self._context_window.is_alive():
            self._context_window.apply_theme(theme)

    def _on_toggle_theme(self) -> None:
        self._dark_mode = not self._dark_mode
        new_theme = get_theme(self._dark_mode, self._accent_color)
        self._apply_theme(new_theme)
        self._save_config()

    # --- Progress bar ---------------------------------------------------------

    def _draw_progress_bar(self) -> None:
        c = self._progress_canvas
        c.delete("all")
        w = c.winfo_width()
        h = PROGRESS_BAR_HEIGHT

        if w <= 1:
            self.root.after(50, self._draw_progress_bar)
            return

        progress = self.session.progress()
        fill_w = int(w * progress)

        c.create_rectangle(0, 0, w, h, fill=self._theme.surface, outline="")
        if fill_w > 0:
            c.create_rectangle(0, 0, fill_w, h, fill=self._theme.accent, outline="")

    def _on_progress_click(self, event: tk.Event) -> None:
        self._seek_to_progress_x(event.x)

    def _on_progress_drag(self, event: tk.Event) -> None:
        self._seek_to_progress_x(event.x)

    def _seek_to_progress_x(self, x: int) -> None:
        if not self.session.tokens or self._loading:
            return
        w = self._progress_canvas.winfo_width()
        if w <= 0:
            return
        ratio = max(0.0, min(1.0, x / w))
        new_pos = int(ratio * (len(self.session.tokens) - 1))
        self.session.position = new_pos

        current = self.session.current_token()
        if current is not None:
            self.reader_view.show(current.text)
            self._update_context_highlight()
        self._refresh_status()
        self._draw_progress_bar()

    # --- File loading (threaded) ----------------------------------------------

    def _on_open(self) -> None:
        if self._loading:
            return
        exts = all_extensions()
        filetypes = [
            ("Supported", " ".join(f"*{e}" for e in exts)),
            ("All files", "*.*"),
        ]
        path_str = filedialog.askopenfilename(
            title="Open file", filetypes=filetypes
        )
        if not path_str:
            return
        self._load_file(Path(path_str))

    def _load_file(self, path: Path) -> None:
        if self._loading:
            return

        importer = find_importer(path)
        if importer is None:
            print(f"No importer for {path.suffix!r}")
            return

        if path.suffix.lower() == ".pdf":
            if not self._show_pdf_preview(path):
                return

        self.session.is_playing = False
        self._update_play_button()

        self._loading = True
        self.reader_view.show("Loading...")
        self._set_transport_enabled(False)

        def _bg_load():
            try:
                result = importer.load(path)
                self._load_queue.put(("ok", path, result))
            except Exception as e:
                import traceback
                traceback.print_exc()
                self._load_queue.put(("error", path, e))

        thread = threading.Thread(target=_bg_load, daemon=True)
        thread.start()
        self._poll_load_queue()

    def _poll_load_queue(self) -> None:
        try:
            msg = self._load_queue.get_nowait()
        except queue.Empty:
            if self._loading:
                self.root.after(LOAD_POLL_MS, self._poll_load_queue)
            return

        self._loading = False
        self._set_transport_enabled(True)

        status = msg[0]
        path: Path = msg[1]

        if status == "error":
            error = msg[2]
            print(f"Failed to load {path}: {error}")
            self.reader_view.show("Failed to load")
            self.root.after(2000, self.reader_view.clear)
            return

        source_text, tokens = msg[2]
        resolved = str(path.resolve())
        source_hash = _hash_source(source_text)

        if not tokens:
            print(f"RSVPy: no tokens extracted from {path.name}")
            self.reader_view.show("No readable text found")
            self.root.after(2000, self.reader_view.clear)
            return

        print(f"RSVPy: loaded {len(tokens)} tokens from {path.name}")

        position = self._resolve_resume_position(
            resolved, source_hash, len(tokens), path.name
        )

        self.session.tokens = tokens
        self.session.source_text = source_text
        self.session.source_hash = source_hash
        self.session.file_path = resolved
        self.session.position = position
        self._tokens_since_checkpoint = 0

        progress_store.set_entry(resolved, position, source_hash)
        stats_store.record_file_open(resolved)
        stats_store.flush_stats()

        current = self.session.current_token()
        if current is not None:
            self.reader_view.show(current.text)
        else:
            self.reader_view.clear()

        self._refresh_status()
        self._draw_progress_bar()
        self._update_play_button()
        self._refresh_summarize_button()

        if self._context_window_open:
            self._open_context_window()
        if self._context_window and self._context_window.is_alive():
            self._context_window.load_text(source_text, path.name)
            self._update_context_highlight()

        self._source_starts = [t.source_start for t in self.session.tokens]

    def _set_transport_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for btn in self._transport_buttons:
            btn.config(state=state)
        if enabled:
            self._refresh_summarize_button()
        else:
            self.summarize_btn.config(state="disabled")

    # --- PDF extraction preview -----------------------------------------------

    def _show_pdf_preview(self, path: Path) -> bool:
        from importers.pdf import extract_preview

        try:
            preview_text, total_pages = extract_preview(path, max_pages=3)
        except Exception as e:
            print(f"Failed to preview {path}: {e}")
            return False

        if not preview_text.strip():
            preview_text = "(No extractable text found in the first pages.)"

        return self._show_preview_dialog(preview_text, total_pages, path.name)

    def _show_preview_dialog(self, preview_text: str, total_pages: int,
                             filename: str) -> bool:
        theme = self._theme
        result = {"proceed": False}

        dialog = tk.Toplevel(self.root)
        dialog.title(f"PDF Preview \u2014 {filename}")
        dialog.geometry("520x420")
        dialog.resizable(True, True)
        dialog.minsize(400, 300)
        dialog.transient(self.root)
        dialog.config(bg=theme.background)

        preview_pages = min(3, total_pages)
        header = tk.Label(
            dialog,
            text=f"Preview ({preview_pages} of {total_pages} pages)",
            font=("Helvetica", 11, "bold"),
            bg=theme.background, fg=theme.text,
            anchor="w",
        )
        header.pack(side="top", fill="x", padx=14, pady=(12, 6))

        btn_frame = tk.Frame(dialog, bg=theme.background)
        btn_frame.pack(side="bottom", fill="x", padx=14, pady=(8, 14))

        def _cancel():
            result["proceed"] = False
            dialog.destroy()

        def _proceed():
            result["proceed"] = True
            dialog.destroy()

        cancel_btn = tk.Button(
            btn_frame, text="Cancel", width=10, command=_cancel,
            bg=theme.surface, fg=theme.text,
            activebackground=theme.background, activeforeground=theme.text,
            highlightbackground=theme.surface, relief="flat",
        )
        cancel_btn.pack(side="right", padx=(6, 0))

        read_btn = tk.Button(
            btn_frame, text="Read this", width=10, command=_proceed,
            bg=theme.surface, fg=theme.text,
            activebackground=theme.background, activeforeground=theme.text,
            highlightbackground=theme.surface, relief="flat",
        )
        read_btn.pack(side="right")

        text_frame = tk.Frame(dialog, bg=theme.background)
        text_frame.pack(side="top", fill="both", expand=True, padx=14)

        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        text_widget = tk.Text(
            text_frame,
            font=("Consolas", 10),
            bg=theme.surface, fg=theme.text,
            wrap="word", padx=10, pady=8,
            highlightthickness=0, bd=1, relief="flat",
            yscrollcommand=scrollbar.set,
        )
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=text_widget.yview)

        text_widget.insert("1.0", preview_text)
        text_widget.config(state="disabled")

        dialog.bind("<Escape>", lambda _e: _cancel())
        dialog.bind("<Return>", lambda _e: _proceed())

        dialog.update_idletasks()
        px = self.root.winfo_rootx()
        py = self.root.winfo_rooty()
        pw = self.root.winfo_width()
        ph = self.root.winfo_height()
        dw = dialog.winfo_width()
        dh = dialog.winfo_height()
        dialog.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 3}")

        dialog.grab_set()
        dialog.focus_set()
        read_btn.focus_set()
        dialog.wait_window()

        return result["proceed"]

    def _resolve_resume_position(self, file_path: str, source_hash: str,
                                  token_count: int, display_name: str) -> int:
        if token_count == 0:
            return 0

        entry = progress_store.get_entry(file_path)
        if entry is None:
            return 0

        stored_pos = int(entry.get("position", 0))
        stored_hash = entry.get("hash")

        if stored_hash is None:
            return _clamp(stored_pos, token_count)

        if stored_hash == source_hash:
            return _clamp(stored_pos, token_count)

        progress_pct = int(round(100 * (stored_pos + 1) / token_count))
        choice = ask_file_changed(
            self.root, self._theme, display_name, progress_pct,
        )
        if choice == "resume":
            return _clamp(stored_pos, token_count)
        return 0

    # --- Context window -------------------------------------------------------

    def _on_toggle_context(self) -> None:
        if self._context_window and self._context_window.is_alive():
            self._context_window.top.destroy()
            self._context_window = None
            self._context_window_open = False
        else:
            self._open_context_window()
        self._save_config()

    def _open_context_window(self) -> None:
        if self._context_window and self._context_window.is_alive():
            self._context_window.top.lift()
            return

        self._context_window = ContextWindow(
            self.root,
            self._theme,
            on_seek=self._on_context_seek,
            on_close=self._on_context_closed,
        )
        self._context_window_open = True

        if self.session.source_text:
            filename = Path(self.session.file_path).name if self.session.file_path else ""
            self._context_window.load_text(self.session.source_text, filename)
            self._update_context_highlight()

    def _on_context_closed(self) -> None:
        self._context_window = None
        self._context_window_open = False
        self._save_config()

    def _on_context_seek(self, char_offset: int) -> None:
        if not self.session.tokens:
            return

        starts = getattr(self, "_source_starts", None)
        if starts is None:
            starts = [t.source_start for t in self.session.tokens]
            self._source_starts = starts

        idx = bisect.bisect_right(starts, char_offset) - 1
        idx = max(0, min(idx, len(self.session.tokens) - 1))

        self.session.position = idx
        current = self.session.current_token()
        if current is not None:
            self.reader_view.show(current.text)
            self._update_context_highlight()
        self._refresh_status()
        self._draw_progress_bar()

    def _update_context_highlight(self) -> None:
        if not (self._context_window and self._context_window.is_alive()):
            return
        token = self.session.current_token()
        if token is not None:
            self._context_window.highlight(token.source_start, token.source_end)
        else:
            self._context_window.clear_highlight()

    # --- Settings (Phase 4) ---------------------------------------------------

    def _on_settings(self) -> None:
        from ui.settings_window import SettingsWindow

        if self._settings_window and self._settings_window.is_alive():
            self._settings_window.top.lift()
            return

        current_cfg = {
            "font_family": self._font_family,
            "font_size": self._font_size,
            "accent_color": self._accent_color,
            "restart_confirm": self._restart_confirm,
            "api_key_stored": bool(keystore.get_api_key()),
            "summary_auto_prompt": self._summary_auto_prompt,
        }

        self._settings_window = SettingsWindow(
            self.root,
            self._theme,
            current_cfg,
            on_font_changed=self._on_font_changed,
            on_accent_changed=self._on_accent_changed,
            on_restart_confirm_changed=self._on_restart_confirm_changed,
            on_summary_prefs_changed=self._on_summary_prefs_changed,
            on_close=self._on_settings_closed,
        )

    def _on_font_changed(self, family: str, size: int) -> None:
        self._font_family = family
        self._font_size = size
        self.reader_view.update_font(family, size)
        self._save_config()

    def _on_accent_changed(self, color: str | None) -> None:
        self._accent_color = color
        new_theme = get_theme(self._dark_mode, self._accent_color)
        self._apply_theme(new_theme)
        self._save_config()

    def _on_restart_confirm_changed(self, enabled: bool) -> None:
        self._restart_confirm = enabled
        self._save_config()

    def _on_summary_prefs_changed(self, prefs: dict) -> None:
        if "summary_auto_prompt" in prefs:
            self._summary_auto_prompt = prefs["summary_auto_prompt"]
        self._save_config()

    def _on_settings_closed(self, final_config: dict) -> None:
        self._settings_window = None
        self._refresh_summarize_button()
        self._save_config()

    # --- AI Summarization (Phase 4) -------------------------------------------

    def _refresh_summarize_button(self) -> None:
        has_key = bool(keystore.get_api_key())
        has_file = bool(self.session.tokens)

        if has_key and has_file:
            if not self.summarize_btn.winfo_ismapped():
                self.summarize_btn.pack(side="left", padx=(8, 2))
            self.summarize_btn.config(state="normal")
        else:
            self.summarize_btn.pack_forget()

    def _on_summarize(self) -> None:
        if not self.session.source_text:
            return

        api_key = keystore.get_api_key()
        if not api_key:
            return

        filename = Path(self.session.file_path).name if self.session.file_path else "Document"
        self._run_summarization(api_key, filename)

    def _run_summarization(self, api_key: str, filename: str) -> None:
        if self._summary_window and self._summary_window.is_alive():
            self._summary_window.top.lift()
        else:
            self._summary_window = SummaryWindow(
                self.root,
                self._theme,
                filename,
                on_regenerate=lambda: self._run_summarization(api_key, filename),
            )

        self._summary_window.show_progress("Generating summary...")

        source_text = self.session.source_text

        def _bg_summarize():
            from core.summarizer import summarize, SummarizationError

            def _progress_cb(msg: str):
                self._summary_queue.put(("progress", msg))

            try:
                result = summarize(
                    source_text, api_key,
                    provider="anthropic",
                    on_progress=_progress_cb,
                )
                self._summary_queue.put(("done", result))
            except SummarizationError as e:
                self._summary_queue.put(("error", str(e)))
            except Exception as e:
                self._summary_queue.put(("error", str(e)))

        thread = threading.Thread(target=_bg_summarize, daemon=True)
        thread.start()
        self._poll_summary_queue()

    def _poll_summary_queue(self) -> None:
        try:
            msg = self._summary_queue.get_nowait()
        except queue.Empty:
            if self._summary_window and self._summary_window.is_alive():
                self.root.after(LOAD_POLL_MS, self._poll_summary_queue)
            return

        if not (self._summary_window and self._summary_window.is_alive()):
            return

        status = msg[0]
        content = msg[1]

        if status == "progress":
            self._summary_window.show_progress(content)
            self.root.after(LOAD_POLL_MS, self._poll_summary_queue)
        elif status == "done":
            self._summary_window.show_summary(content)
        elif status == "error":
            self._summary_window.show_error(content)

    def _on_playback_finished(self) -> None:
        if not self._summary_auto_prompt:
            return

        api_key = keystore.get_api_key()
        if not api_key:
            return

        filename = Path(self.session.file_path).name if self.session.file_path else "Document"
        self._show_auto_summary_prompt(api_key, filename)

    def _show_auto_summary_prompt(self, api_key: str, filename: str) -> None:
        theme = self._theme

        dialog = tk.Toplevel(self.root)
        dialog.title("Reading Complete")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.config(bg=theme.background)

        msg = tk.Label(
            dialog,
            text="You've finished reading!\nWould you like a summary?",
            font=("Helvetica", 11),
            bg=theme.background, fg=theme.text,
            justify="center",
        )
        msg.pack(padx=20, pady=(16, 12))

        btn_frame = tk.Frame(dialog, bg=theme.background)
        btn_frame.pack(fill="x", padx=20, pady=(0, 14))

        def _no():
            dialog.destroy()

        def _yes():
            dialog.destroy()
            self._run_summarization(api_key, filename)

        no_btn = tk.Button(
            btn_frame, text="No thanks", width=10, command=_no,
            bg=theme.surface, fg=theme.text,
            activebackground=theme.background, activeforeground=theme.text,
            highlightbackground=theme.surface, relief="flat",
        )
        no_btn.pack(side="right", padx=(6, 0))

        yes_btn = tk.Button(
            btn_frame, text="Yes", width=10, command=_yes,
            bg=theme.surface, fg=theme.text,
            activebackground=theme.background, activeforeground=theme.text,
            highlightbackground=theme.surface, relief="flat",
        )
        yes_btn.pack(side="right")

        dialog.bind("<Escape>", lambda _e: _no())
        dialog.bind("<Return>", lambda _e: _yes())

        dialog.update_idletasks()
        px = self.root.winfo_rootx()
        py = self.root.winfo_rooty()
        pw = self.root.winfo_width()
        ph = self.root.winfo_height()
        dw = dialog.winfo_width()
        dh = dialog.winfo_height()
        dialog.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 3}")

        dialog.grab_set()
        dialog.focus_set()
        yes_btn.focus_set()

    # --- Recents / Stats ------------------------------------------------------

    def _on_recents(self) -> None:
        RecentsWindow(self.root, self._theme, self._load_file)

    def _on_stats(self) -> None:
        StatsWindow(self.root, self._theme)

    # --- Playback -------------------------------------------------------------

    def _on_play_pause(self) -> None:
        if not self.session.tokens or self._loading:
            return
        if self.session.is_playing:
            self._pause()
        else:
            self._play()

    def _play(self) -> None:
        if self.session.is_finished():
            self.session.position = 0
        self.session.is_playing = True
        self._update_play_button()
        self._tick()

    def _pause(self) -> None:
        self.session.is_playing = False
        self._update_play_button()
        self._save_progress()

    def _tick(self) -> None:
        """One step of the play loop. Scheduled via root.after.

        Phase 5: passes token_type and word_length to delay_ms() for
        variable timing — sentence/paragraph pauses, word-length
        scaling, and punctuation-only reduced delay.
        """
        if not self.session.is_playing:
            return
        token = self.session.current_token()
        if token is None:
            self.session.is_playing = False
            self._update_play_button()
            return

        self.reader_view.show(token.text)
        self._refresh_status()
        self._draw_progress_bar()
        self._update_context_highlight()

        # Phase 5: variable timing. Pass token type and the display
        # word's length (for chunked tokens, this is the full chunk
        # length, which is fine — longer chunks deserve more time).
        current_delay = delay_ms(
            self.session.wpm,
            token_type=token.type,
            word_length=len(token.text),
        )

        tick_seconds = current_delay / 1000.0
        progress_pct = int(self.session.progress() * 100)
        stats_store.record_tick(
            self.session.file_path, tick_seconds, progress_pct
        )

        self.session.advance()
        self._tokens_since_checkpoint += 1
        if self._tokens_since_checkpoint >= PROGRESS_CHECKPOINT_EVERY:
            self._save_progress()
            self._tokens_since_checkpoint = 0

        if self.session.is_playing:
            self.root.after(current_delay, self._tick)
        else:
            # Playback ended (advance() stopped us).
            self._update_play_button()
            self._save_progress()
            self._on_playback_finished()

    def _on_rewind(self) -> None:
        if not self.session.tokens or self._loading:
            return
        self.session.rewind(REWIND_TOKENS)
        current = self.session.current_token()
        if current is not None:
            self.reader_view.show(current.text)
            self._update_context_highlight()
        self._refresh_status()
        self._draw_progress_bar()

    def _on_skip(self) -> None:
        if not self.session.tokens or self._loading:
            return
        self.session.skip(SKIP_TOKENS)
        current = self.session.current_token()
        if current is not None:
            self.reader_view.show(current.text)
            self._update_context_highlight()
        self._refresh_status()
        self._draw_progress_bar()

    def _on_restart(self) -> None:
        if not self.session.tokens or self._loading:
            return
        if self.session.position == 0 and not self.session.is_playing:
            return

        if self._restart_confirm:
            choice = ask_restart_confirm(self.root, self._theme)
            if choice == "cancel":
                return
            if choice == "restart_no_ask":
                self._restart_confirm = False
                self._save_config()

        self.session.position = 0
        current = self.session.current_token()
        if current is not None:
            self.reader_view.show(current.text)
            self._update_context_highlight()
        self._refresh_status()
        self._draw_progress_bar()
        self._save_progress()

    # --- WPM ------------------------------------------------------------------

    def _adjust_wpm(self, delta: int) -> None:
        new_wpm = clamp_wpm(self.session.wpm + delta)
        if new_wpm == self.session.wpm:
            return
        self.session.wpm = new_wpm
        self._refresh_status()
        self._save_config()

    # --- Status bar -----------------------------------------------------------

    def _refresh_status(self) -> None:
        if self.session.file_path:
            self.filename_label.config(text=Path(self.session.file_path).name)
            self.progress_label.config(
                text=f"{self.session.progress() * 100:.0f}%"
            )
        else:
            self.filename_label.config(text="No file loaded")
            self.progress_label.config(text="")

        self.wpm_label.config(text=f"{self.session.wpm} wpm")
        self.wpm_value_label.config(text=str(self.session.wpm))

    def _update_play_button(self) -> None:
        if self.session.is_playing:
            self.play_btn.config(text="\u23F8 Pause")
            self._tip_play.update_text("Pause (Space)")
        else:
            self.play_btn.config(text="\u25B6 Play")
            self._tip_play.update_text("Play (Space)")

    # --- Lifecycle ------------------------------------------------------------

    def _on_close(self) -> None:
        self.session.is_playing = False
        self._save_progress()
        self._save_config()
        self.root.destroy()

    # --- Persistence ----------------------------------------------------------

    def _load_config(self) -> dict:
        return config_store.load_config()

    def _save_config(self) -> None:
        geom = self.root.geometry()
        config_store.save_config({
            "wpm": self.session.wpm,
            "dark_mode": self._dark_mode,
            "restart_confirm": self._restart_confirm,
            "context_window_open": self._context_window_open,
            "main_window_geometry": geom,
            "font_family": self._font_family,
            "font_size": self._font_size,
            "accent_color": self._accent_color,
            "api_key_stored": bool(keystore.get_api_key()),
            "api_provider": "anthropic",
            "summary_enabled": True,
            "summary_auto_prompt": self._summary_auto_prompt,
        })

    def _save_progress(self) -> None:
        if not self.session.file_path:
            return
        progress_store.set_entry(
            self.session.file_path,
            self.session.position,
            self.session.source_hash,
        )
        stats_store.flush_stats()


def _clamp(position: int, token_count: int) -> int:
    if token_count <= 0:
        return 0
    return max(0, min(position, token_count - 1))


def launch() -> None:
    """Create the Tk root and run the main loop."""
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()