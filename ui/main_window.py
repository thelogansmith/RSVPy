"""
Main window.

Owns the Session, the Tk root, and the play loop. Delegates word
display to ReaderView, file parsing to the importer registry, and
persistence to the storage package.
"""

from __future__ import annotations

import hashlib
import tkinter as tk
from pathlib import Path
from tkinter import filedialog

from core.session import Session
from core.timing import clamp_wpm, delay_ms
from importers.registry import all_extensions, find_importer
from storage import config as config_store
from storage import progress as progress_store
from ui.dialogs import ask_file_changed, ask_restart_confirm
from ui.reader_view import ReaderView
from ui.theme import DARK, LIGHT, Theme, get_theme


# --- Layout constants ---------------------------------------------------------

WINDOW_TITLE = "RSVPy"
WINDOW_WIDTH = 700
WINDOW_HEIGHT = 300
WPM_STEP = 25
REWIND_TOKENS = 5
SKIP_TOKENS = 5
# How often during playback to persist the current position, measured
# in tokens. Spec requires every ~100 tokens.
PROGRESS_CHECKPOINT_EVERY = 100


def _hash_source(text: str) -> str:
    """Return the hex SHA-256 of the canonical source text, UTF-8 encoded."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class MainWindow:

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.session = Session()
        self._tokens_since_checkpoint = 0

        # Load persisted config.
        cfg = self._load_config()
        self.session.wpm = clamp_wpm(cfg.get("wpm", 300))
        self._theme: Theme = get_theme(cfg.get("dark_mode", True))
        self._restart_confirm: bool = bool(cfg.get("restart_confirm", True))

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
        # Three zones: Open on the left, transport centered, WPM+theme
        # on the right. Using a sub-frame for the transport group so
        # pack(side="left") + pack(side="right") leaves the center frame
        # naturally balanced in the remaining space.
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

        # Center zone: transport buttons inside a sub-frame. The frame
        # fills whatever space remains between Open and the WPM cluster,
        # and its children are packed centrally via place() or inner pack.
        transport = tk.Frame(self.control_bar)
        transport.pack(side="left", fill="both", expand=True, pady=4)
        self._transport_frame = transport

        # Inner frame to hold the actual buttons, centered in the transport
        # zone. place() centers it regardless of how wide the parent is.
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

        # Reader view (fills remaining space) ---------------------------------
        self.reader_view = ReaderView(self.root, self._theme)
        self.reader_view.pack(side="top", fill="both", expand=True)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<space>", lambda _e: self._on_play_pause())
        self.root.bind("<Left>", lambda _e: self._on_rewind())
        self.root.bind("<Right>", lambda _e: self._on_skip())
        self.root.bind("<Home>", lambda _e: self._on_restart())
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

        # Transport frame and its children need theming too.
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
            print(f"No importer for {path.suffix!r}")
            return

        try:
            source_text, tokens = importer.load(path)
        except Exception as e:
            print(f"Failed to load {path}: {e}")
            return

        self.session.is_playing = False
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

        current = self.session.current_token()
        if current is not None:
            self.reader_view.show(current.text)
        else:
            self.reader_view.clear()

        self._refresh_status()
        self._update_play_button()

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

    def _on_skip(self) -> None:
        if not self.session.tokens:
            return
        self.session.skip(SKIP_TOKENS)
        current = self.session.current_token()
        if current is not None:
            self.reader_view.show(current.text)
        self._refresh_status()

    def _on_restart(self) -> None:
        """Jump to position 0, prompting for confirmation unless disabled."""
        if not self.session.tokens:
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
        self._refresh_status()
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
        config_store.save_config({
            "wpm": self.session.wpm,
            "dark_mode": self._theme.name == "dark",
            "restart_confirm": self._restart_confirm,
        })

    def _save_progress(self) -> None:
        if not self.session.file_path:
            return
        progress_store.set_entry(
            self.session.file_path,
            self.session.position,
            self.session.source_hash,
        )


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