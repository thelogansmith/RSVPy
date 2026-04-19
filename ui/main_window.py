"""
Main window.

Owns the Session, the Tk root, and the play loop. Delegates word
display to ReaderView, file parsing to the importer registry, and
persistence to the storage package.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from core.session import Session
from core.timing import clamp_wpm, delay_ms
from importers.registry import all_extensions, find_importer
from storage import config as config_store
from storage import progress as progress_store
from ui.reader_view import ReaderView
from ui.theme import DARK, LIGHT, Theme, get_theme


# --- Layout constants ---------------------------------------------------------

WINDOW_TITLE = "RSVPy"
WINDOW_WIDTH = 600
WINDOW_HEIGHT = 300
WPM_STEP = 25
REWIND_TOKENS = 5
# How often during playback to persist the current position, measured
# in tokens. Spec requires every ~100 tokens.
PROGRESS_CHECKPOINT_EVERY = 100


class MainWindow:

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.session = Session()
        self._tokens_since_checkpoint = 0

        # Load persisted config.
        cfg = self._load_config()
        self.session.wpm = clamp_wpm(cfg.get("wpm", 300))
        self._theme: Theme = get_theme(cfg.get("dark_mode", True))

        self._build_window()
        self._build_widgets()
        self._bind_shortcuts()
        self._apply_theme(self._theme)
        self._refresh_status()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # --- Window setup ---------------------------------------------------------

    def _build_window(self) -> None:
        self.root.title(WINDOW_TITLE)
        self.root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.root.resizable(False, False)
        self.root.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)

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

        # Control bar (bottom) ------------------------------------------------
        self.control_bar = tk.Frame(self.root, height=44)
        self.control_bar.pack(side="bottom", fill="x")
        self.control_bar.pack_propagate(False)

        self.open_btn = tk.Button(
            self.control_bar, text="Open", width=8, command=self._on_open
        )
        self.open_btn.pack(side="left", padx=(10, 6), pady=8)

        self.play_btn = tk.Button(
            self.control_bar, text="▶ Play", width=10, command=self._on_play_pause
        )
        self.play_btn.pack(side="left", padx=6, pady=8)

        # Theme toggle is far-right; WPM stepper sits next to it.
        self.theme_btn = tk.Button(
            self.control_bar, text="☀" if self._theme.name == "dark" else "🌙",
            width=3, command=self._on_toggle_theme,
        )
        self.theme_btn.pack(side="right", padx=(6, 10), pady=8)

        self.wpm_plus_btn = tk.Button(
            self.control_bar, text="+", width=2,
            command=lambda: self._adjust_wpm(WPM_STEP),
        )
        self.wpm_plus_btn.pack(side="right", padx=2, pady=8)

        self.wpm_value_label = tk.Label(self.control_bar, width=5, anchor="center")
        self.wpm_value_label.pack(side="right", padx=2, pady=8)

        self.wpm_minus_btn = tk.Button(
            self.control_bar, text="−", width=2,
            command=lambda: self._adjust_wpm(-WPM_STEP),
        )
        self.wpm_minus_btn.pack(side="right", padx=(6, 2), pady=8)

        self.wpm_prefix_label = tk.Label(self.control_bar, text="WPM:")
        self.wpm_prefix_label.pack(side="right", padx=(6, 2), pady=8)

        # Reader view (fills remaining space) ---------------------------------
        self.reader_view = ReaderView(self.root, self._theme)
        self.reader_view.pack(side="top", fill="both", expand=True)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<space>", lambda _e: self._on_play_pause())
        self.root.bind("<Left>", lambda _e: self._on_rewind())
        self.root.bind("<Control-o>", lambda _e: self._on_open())

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

        # Buttons: Tk on macOS ignores bg on native buttons, but setting
        # it works on Windows and Linux and does no harm on macOS.
        for btn in (
            self.open_btn, self.play_btn, self.theme_btn,
            self.wpm_plus_btn, self.wpm_minus_btn,
        ):
            btn.config(bg=surface, fg=text, activebackground=bg, activeforeground=text,
                       highlightbackground=surface, relief="flat")

        self.theme_btn.config(text="☀" if theme.name == "dark" else "🌙")
        self.reader_view.apply_theme(theme)

    def _on_toggle_theme(self) -> None:
        new_theme = LIGHT if self._theme.name == "dark" else DARK
        self._apply_theme(new_theme)
        self._save_config()

    # --- File loading ---------------------------------------------------------

    def _on_open(self) -> None:
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
        importer = find_importer(path)
        if importer is None:
            # Phase 1: no error dialogs, just a console message.
            print(f"No importer for {path.suffix!r}")
            return

        try:
            # Step 1: importers now return (canonical_text, tokens).
            # We accept the text here but don't yet store it on the
            # Session - that's step 2. Leading underscore marks it as
            # a deliberately-unused local.
            _source_text, tokens = importer.load(path)
        except Exception as e:  # Intentionally broad for Phase 1.
            print(f"Failed to load {path}: {e}")
            return

        # Stop any in-flight playback before swapping the token stream.
        self.session.is_playing = False
        resolved = str(path.resolve())
        self.session.tokens = tokens
        self.session.position = self._load_progress_for(resolved)
        self.session.file_path = resolved
        self._tokens_since_checkpoint = 0

        # Show the word at the resumed position so the user sees where
        # they are, instead of a blank screen.
        current = self.session.current_token()
        if current is not None:
            self.reader_view.show(current.text)
        else:
            self.reader_view.clear()

        self._refresh_status()
        self._update_play_button()

    # --- Playback -------------------------------------------------------------

    def _on_play_pause(self) -> None:
        if not self.session.tokens:
            return
        if self.session.is_playing:
            self._pause()
        else:
            self._play()

    def _play(self) -> None:
        if self.session.is_finished():
            # Restart from the beginning if they press play at the end.
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

        self.session.advance()
        self._tokens_since_checkpoint += 1
        if self._tokens_since_checkpoint >= PROGRESS_CHECKPOINT_EVERY:
            self._save_progress()
            self._tokens_since_checkpoint = 0

        if self.session.is_playing:
            self.root.after(delay_ms(self.session.wpm), self._tick)
        else:
            # advance() stopped us at the end of the stream.
            self._update_play_button()
            self._save_progress()

    def _on_rewind(self) -> None:
        if not self.session.tokens:
            return
        self.session.rewind(REWIND_TOKENS)
        current = self.session.current_token()
        if current is not None:
            self.reader_view.show(current.text)
        self._refresh_status()

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
    # Thin wrappers around the storage package. Keeping them as methods
    # (rather than inlining the calls at every site) means UI code stays
    # ignorant of the storage module layout, and a future switch to,
    # say, SQLite would only touch these four methods.

    def _load_config(self) -> dict:
        return config_store.load_config()

    def _save_config(self) -> None:
        config_store.save_config({
            "wpm": self.session.wpm,
            "dark_mode": self._theme.name == "dark",
        })

    def _load_progress_for(self, file_path: str) -> int:
        stored = progress_store.get_position(file_path)
        # Clamp into the current token stream's bounds. Even in Phase 2
        # where a hash check guards against file changes, we keep this:
        # the same source text could produce a different token count
        # across RSVPy versions if tokenizer logic ever changes (Phase 5
        # ORP work is a likely trigger), so this is a cheap defense
        # against future-version IndexErrors.
        if not self.session.tokens:
            return 0
        return max(0, min(stored, len(self.session.tokens) - 1))

    def _save_progress(self) -> None:
        # No file loaded → nothing to record. Avoids writing an
        # empty-string key into progress.json on app close before the
        # user opens anything.
        if not self.session.file_path:
            return
        progress_store.set_position(self.session.file_path, self.session.position)


def launch() -> None:
    """Create the Tk root and run the main loop."""
    root = tk.Tk()
    MainWindow(root)
    root.mainloop()