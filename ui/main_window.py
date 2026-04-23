"""
Main window.

Owns the Session, the Tk root, and the play loop. Delegates word
display to ReaderView, file parsing to the importer registry, and
persistence to the storage package.

Phase 3 additions:
  - Threaded file loading (step 1): importer.load() runs on a
    background thread. A queue + root.after polling loop delivers
    the result back to the main thread. Transport buttons are
    disabled during loading. The reader view shows "Loading...".
  - Resizable window (step 2): main window is now resizable with
    geometry persistence.
  - Progress bar (step 3): a thin canvas bar between the reader
    view and control bar. Click and drag to seek.
  - PDF extraction preview (step 5): a modal dialog showing the
    first 2-3 pages before committing to a full load.
  - Context window integration (steps 6-8): a "Context" button
    in the status bar opens a Toplevel showing the source text
    with the current word highlighted. Click-to-seek.

Threading primer (for the developer):
  Only the file loading (the importer's load() call) runs on a
  background thread. Everything Tkinter-related stays on the main
  thread — Tk is not thread-safe and will crash if you call widget
  methods from another thread. Communication between threads uses
  queue.Queue, which is thread-safe, plus root.after() polling on
  the main thread to check for results.
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
from storage import progress as progress_store
from storage import stats as stats_store
from ui.context_window import ContextWindow
from ui.dialogs import ask_file_changed, ask_restart_confirm
from ui.reader_view import ReaderView
from ui.recents_window import RecentsWindow
from ui.stats_window import StatsWindow
from ui.theme import DARK, LIGHT, Theme, get_theme


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
LOAD_POLL_MS = 50  # How often to check the loading queue.
PROGRESS_BAR_HEIGHT = 8


def _hash_source(text: str) -> str:
    """Return the hex SHA-256 of the canonical source text, UTF-8 encoded."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class MainWindow:

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.session = Session()
        self._tokens_since_checkpoint = 0
        self._context_window: ContextWindow | None = None
        self._loading = False  # True while a background load is in progress.
        self._load_queue: queue.Queue = queue.Queue()

        cfg = self._load_config()
        self.session.wpm = clamp_wpm(cfg.get("wpm", 300))
        self._theme: Theme = get_theme(cfg.get("dark_mode", True))
        self._restart_confirm: bool = bool(cfg.get("restart_confirm", True))
        self._context_window_open: bool = bool(cfg.get("context_window_open", False))

        self._build_window(cfg)
        self._build_widgets()
        self._bind_shortcuts()
        self._apply_theme(self._theme)
        self._refresh_status()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # --- Window setup ---------------------------------------------------------

    def _build_window(self, cfg: dict) -> None:
        self.root.title(WINDOW_TITLE)

        # Restore saved geometry or use default.
        saved_geom = cfg.get("main_window_geometry")
        if saved_geom and isinstance(saved_geom, str):
            self.root.geometry(saved_geom)
        else:
            self.root.geometry(f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}")

        # Phase 3: window is now resizable.
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

        # Stats button in the status bar.
        self.stats_btn = tk.Button(
            self.status_bar, text="Stats", bd=0, padx=6,
            command=self._on_stats,
        )
        self.stats_btn.pack(side="right", fill="y", padx=2)

        # Recent button in the status bar.
        self.recent_btn = tk.Button(
            self.status_bar, text="Recent", bd=0, padx=6,
            command=self._on_recents,
        )
        self.recent_btn.pack(side="right", fill="y", padx=2)

        # Context button in the status bar (Phase 3).
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
            self.control_bar, text="☀" if self._theme.name == "dark" else "🌙",
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
            self.control_bar, text="−", width=2,
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
            inner, text="⏮ Start", width=6, command=self._on_restart
        )
        self.restart_btn.pack(side="left", padx=2)

        self.rewind_btn = tk.Button(
            inner, text="⏪ Back", width=6, command=self._on_rewind
        )
        self.rewind_btn.pack(side="left", padx=2)

        self.play_btn = tk.Button(
            inner, text="▶ Play", width=7, command=self._on_play_pause
        )
        self.play_btn.pack(side="left", padx=2)

        self.skip_btn = tk.Button(
            inner, text="Skip ⏩", width=6, command=self._on_skip
        )
        self.skip_btn.pack(side="left", padx=2)

        # Progress bar (Phase 3) — between reader view and control bar.
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

        # Reader view (fills remaining space) ---------------------------------
        self.reader_view = ReaderView(self.root, self._theme)
        self.reader_view.pack(side="top", fill="both", expand=True)

        # Collect transport buttons for enable/disable during loading.
        self._transport_buttons = [
            self.restart_btn, self.rewind_btn,
            self.play_btn, self.skip_btn,
        ]

    def _bind_shortcuts(self) -> None:
        self.root.bind("<space>", lambda _e: self._on_play_pause())
        self.root.bind("<Left>", lambda _e: self._on_rewind())
        self.root.bind("<Right>", lambda _e: self._on_skip())
        self.root.bind("<Home>", lambda _e: self._on_restart())
        self.root.bind("<Control-o>", lambda _e: self._on_open())
        self.root.bind("<Control-r>", lambda _e: self._on_recents())
        self.root.bind("<Control-t>", lambda _e: self._on_toggle_context())

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
        ):
            btn.config(bg=surface, fg=text, activebackground=bg, activeforeground=text,
                       highlightbackground=surface, relief="flat")

        # Status bar buttons get a subtler look.
        for status_btn in (self.recent_btn, self.stats_btn, self.context_btn):
            status_btn.config(
                bg=surface, fg=muted,
                activebackground=bg, activeforeground=text,
                highlightbackground=surface,
            )

        self.theme_btn.config(text="☀" if theme.name == "dark" else "🌙")
        self.reader_view.apply_theme(theme)

        # Progress bar.
        self._progress_canvas.config(bg=surface)
        self._draw_progress_bar()

        # Context window, if open.
        if self._context_window and self._context_window.is_alive():
            self._context_window.apply_theme(theme)

    def _on_toggle_theme(self) -> None:
        new_theme = LIGHT if self._theme.name == "dark" else DARK
        self._apply_theme(new_theme)
        self._save_config()

    # --- Progress bar ---------------------------------------------------------

    def _draw_progress_bar(self) -> None:
        """Redraw the progress bar canvas."""
        c = self._progress_canvas
        c.delete("all")
        w = c.winfo_width()
        h = PROGRESS_BAR_HEIGHT

        if w <= 1:
            # Widget not yet laid out; schedule a redraw after layout.
            self.root.after(50, self._draw_progress_bar)
            return

        progress = self.session.progress()
        fill_w = int(w * progress)

        # Track (full width).
        c.create_rectangle(0, 0, w, h, fill=self._theme.surface, outline="")
        # Filled portion.
        if fill_w > 0:
            c.create_rectangle(0, 0, fill_w, h, fill=self._theme.accent, outline="")

    def _on_progress_click(self, event: tk.Event) -> None:
        """Seek to the clicked position on the progress bar."""
        self._seek_to_progress_x(event.x)

    def _on_progress_drag(self, event: tk.Event) -> None:
        """Scrub while dragging on the progress bar."""
        self._seek_to_progress_x(event.x)

    def _seek_to_progress_x(self, x: int) -> None:
        """Convert an x pixel coordinate on the progress bar to a token
        position and seek there."""
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

    # --- File loading (threaded, Phase 3) -------------------------------------

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
        """Start loading a file. For PDFs, show a preview dialog first.
        The actual importer.load() runs on a background thread."""
        if self._loading:
            return

        importer = find_importer(path)
        if importer is None:
            print(f"No importer for {path.suffix!r}")
            return

        # PDF extraction preview (Phase 3 step 5).
        if path.suffix.lower() == ".pdf":
            if not self._show_pdf_preview(path):
                return  # User cancelled.

        # Stop any in-flight playback before starting the load.
        self.session.is_playing = False
        self._update_play_button()

        # Show loading state.
        self._loading = True
        self.reader_view.show("Loading...")
        self._set_transport_enabled(False)

        # Run the importer on a background thread.
        def _bg_load():
            try:
                result = importer.load(path)
                self._load_queue.put(("ok", path, result))
            except Exception as e:
                self._load_queue.put(("error", path, e))

        thread = threading.Thread(target=_bg_load, daemon=True)
        thread.start()

        # Start polling for the result.
        self._poll_load_queue()

    def _poll_load_queue(self) -> None:
        """Check if the background loading thread has finished."""
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

        # Success.
        source_text, tokens = msg[2]
        resolved = str(path.resolve())
        source_hash = _hash_source(source_text)

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

        # Refresh context window if open; auto-open if configured.
        if self._context_window_open:
            self._open_context_window()
        if self._context_window and self._context_window.is_alive():
            self._context_window.load_text(source_text, path.name)
            self._update_context_highlight()

        # Pre-build the source_starts list for click-to-seek.
        self._source_starts = [t.source_start for t in self.session.tokens]

    def _set_transport_enabled(self, enabled: bool) -> None:
        """Enable or disable transport buttons during loading."""
        state = "normal" if enabled else "disabled"
        for btn in self._transport_buttons:
            btn.config(state=state)

    # --- PDF extraction preview (Phase 3 step 5) -----------------------------

    def _show_pdf_preview(self, path: Path) -> bool:
        """Show a modal preview of the first few pages of a PDF.
        Returns True if the user wants to proceed, False to cancel."""
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
        """Display the extraction preview modal. Returns True to proceed."""
        theme = self._theme
        result = {"proceed": False}

        dialog = tk.Toplevel(self.root)
        dialog.title(f"PDF Preview — {filename}")
        dialog.geometry("520x420")
        dialog.resizable(True, True)
        dialog.minsize(400, 300)
        dialog.transient(self.root)
        dialog.config(bg=theme.background)

        # Header with page count.
        preview_pages = min(3, total_pages)
        header = tk.Label(
            dialog,
            text=f"Preview ({preview_pages} of {total_pages} pages)",
            font=("Helvetica", 11, "bold"),
            bg=theme.background, fg=theme.text,
            anchor="w",
        )
        header.pack(fill="x", padx=14, pady=(12, 6))

        # Scrollable text widget showing the preview.
        text_frame = tk.Frame(dialog, bg=theme.background)
        text_frame.pack(fill="both", expand=True, padx=14, pady=(0, 8))

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

        # Button row.
        btn_frame = tk.Frame(dialog, bg=theme.background)
        btn_frame.pack(fill="x", padx=14, pady=(0, 14))

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

        dialog.bind("<Escape>", lambda _e: _cancel())
        dialog.bind("<Return>", lambda _e: _proceed())

        # Center on parent.
        dialog.update_idletasks()
        px = self.root.winfo_rootx()
        py = self.root.winfo_rooty()
        pw = self.root.winfo_width()
        ph = self.root.winfo_height()
        dw = dialog.winfo_width()
        dh = dialog.winfo_height()
        dialog.geometry(f"+{px + (pw - dw) // 2}+{py + (ph - dh) // 3}")

        # Modal.
        dialog.grab_set()
        dialog.focus_set()
        read_btn.focus_set()
        dialog.wait_window()

        return result["proceed"]

    def _resolve_resume_position(self, file_path: str, source_hash: str,
                                  token_count: int, display_name: str) -> int:
        """Decide the starting position for a freshly loaded file."""
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

    # --- Context window (Phase 3 steps 6-8) -----------------------------------

    def _on_toggle_context(self) -> None:
        """Toggle the context window open/closed."""
        if self._context_window and self._context_window.is_alive():
            self._context_window.top.destroy()
            self._context_window = None
            self._context_window_open = False
        else:
            self._open_context_window()
        self._save_config()

    def _open_context_window(self) -> None:
        """Open the context window (or bring it to front if already open)."""
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

        # Load current document text if there is one.
        if self.session.source_text:
            filename = Path(self.session.file_path).name if self.session.file_path else ""
            self._context_window.load_text(self.session.source_text, filename)
            self._update_context_highlight()

    def _on_context_closed(self) -> None:
        """Called when the user closes the context window."""
        self._context_window = None
        self._context_window_open = False
        self._save_config()

    def _on_context_seek(self, char_offset: int) -> None:
        """Handle a click-to-seek from the context window.
        Maps a character offset to a token index and updates position."""
        if not self.session.tokens:
            return

        # Binary search: find the token whose source_start is <= char_offset.
        starts = getattr(self, "_source_starts", None)
        if starts is None:
            starts = [t.source_start for t in self.session.tokens]
            self._source_starts = starts

        idx = bisect.bisect_right(starts, char_offset) - 1
        if idx < 0:
            idx = 0
        if idx >= len(self.session.tokens):
            idx = len(self.session.tokens) - 1

        self.session.position = idx
        current = self.session.current_token()
        if current is not None:
            self.reader_view.show(current.text)
            self._update_context_highlight()
        self._refresh_status()
        self._draw_progress_bar()

    def _update_context_highlight(self) -> None:
        """Update the context window's highlight to the current token."""
        if not (self._context_window and self._context_window.is_alive()):
            return
        token = self.session.current_token()
        if token is not None:
            self._context_window.highlight(token.source_start, token.source_end)
        else:
            self._context_window.clear_highlight()

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
        """One step of the play loop. Scheduled via root.after."""
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

        tick_seconds = delay_ms(self.session.wpm) / 1000.0
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
            self.root.after(delay_ms(self.session.wpm), self._tick)
        else:
            self._update_play_button()
            self._save_progress()

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
        self.play_btn.config(
            text="⏸ Pause" if self.session.is_playing else "▶ Play"
        )

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
        # Capture current window geometry for persistence.
        geom = self.root.geometry()
        config_store.save_config({
            "wpm": self.session.wpm,
            "dark_mode": self._theme.name == "dark",
            "restart_confirm": self._restart_confirm,
            "context_window_open": self._context_window_open,
            "main_window_geometry": geom,
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
    """Clamp a position into [0, token_count-1]. Empty streams map to 0."""
    if token_count <= 0:
        return 0
    return max(0, min(position, token_count - 1))


def launch() -> None:
    """Create the Tk root and run the main loop."""
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()