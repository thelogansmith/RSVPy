Phase 1 · MD
# Phase 1 Specification
 
**Status:** In development
**Goal:** A functional RSVP reader capable of loading a `.txt` file and streaming its contents at a configurable WPM with pause, resume, and rewind. Reading position persists across sessions.
 
This document is the working specification for Phase 1. It defines scope, architecture, data structures, and the intended build order. Anything not listed here is out of scope for Phase 1 and belongs to a later phase.
 
---
 
## Scope
 
### In scope
- Single-window Tkinter desktop application
- Import of plain `.txt` files via a file dialog
- RSVP display of tokenized text at a user-configurable WPM
- Play, pause, and rewind controls (buttons and keyboard)
- Dark mode toggle
- Persistence of user config (WPM, theme) across sessions
- Persistence of per-file reading progress across sessions
- Status bar showing current filename, progress percentage, and WPM
### Out of scope
- Any file format other than `.txt`
- Font, color, or size customization beyond a dark mode toggle
- Library or recent-files view
- Scrubbable progress bar
- Sentence- or paragraph-aware timing (tokens will be tagged but timing ignores the tags)
- Error dialogs (errors print to console)
- Automated tests
- Optimal Recognition Point (ORP) alignment
- AI summarization
- Packaging or distribution (run from source only)
---
 
## Requirements
 
- Python 3.10 or newer
- Tkinter (bundled with standard Python on Windows and macOS; `python3-tk` package on Linux)
- No third-party dependencies
---
 
## Project Structure
 
```
RSVPy/
├── main.py                 # Entry point
├── core/
│   ├── __init__.py
│   ├── tokenizer.py        # Text → token list
│   ├── timing.py           # WPM → delay in ms
│   └── session.py          # Reading state
├── importers/
│   ├── __init__.py
│   ├── base.py             # Importer interface
│   └── txt.py              # .txt importer
├── ui/
│   ├── __init__.py
│   ├── main_window.py      # Tk root and layout
│   └── reader_view.py      # Word display widget
├── storage/
│   ├── __init__.py
│   ├── config.py           # User preferences
│   └── progress.py         # Per-file position tracking
├── README.md
├── LICENSE
└── .gitignore
```
 
All `__init__.py` files are empty; they exist to mark directories as Python packages.
 
---
 
## Data Structures
 
### Token
 
The atomic unit of the reading stream. Defined in `core/tokenizer.py`.
 
```python
from dataclasses import dataclass
from enum import Enum
 
class TokenType(Enum):
    WORD = "word"
    SENTENCE_END = "sentence_end"
    PARAGRAPH_END = "paragraph_end"
 
@dataclass
class Token:
    text: str           # The word to display
    type: TokenType     # Used by later phases for variable timing
    index: int          # Position in the full token stream
```
 
A document is represented as `list[Token]`. Phase 1 uses `text` and `index` only; `type` is populated correctly but not yet consumed by the timing module.
 
### Session
 
The in-memory reading state. Defined in `core/session.py`.
 
```python
@dataclass
class Session:
    tokens: list[Token]
    position: int = 0
    wpm: int = 300
    is_playing: bool = False
    file_path: str = ""
```
 
Methods:
- `current_token() -> Token | None`
- `advance() -> None` — moves forward one token; sets `is_playing = False` at the end
- `rewind(n: int = 5) -> None` — moves backward up to `n` tokens, floored at 0
- `progress() -> float` — returns `position / len(tokens)`, or `0.0` if empty
### Config file
 
JSON at `<config_dir>/config.json`:
 
```json
{
  "wpm": 300,
  "dark_mode": true
}
```
 
### Progress file
 
JSON at `<config_dir>/progress.json`, keyed by absolute file path:
 
```json
{
  "/home/user/docs/essay.txt": 847,
  "/home/user/docs/story.txt": 0
}
```
 
### Config directory
 
Platform-appropriate user config directory:
- Windows: `%APPDATA%\RSVPy\`
- macOS / Linux: `$XDG_CONFIG_HOME/RSVPy/` or `~/.config/RSVPy/` as fallback
---
 
## Module Contracts
 
### `core/tokenizer.py`
 
```python
def tokenize(text: str) -> list[Token]
```
 
Splits input on paragraph breaks (blank lines), then on whitespace within each paragraph. Tags the last word of a paragraph as `PARAGRAPH_END`, words ending in `.`, `!`, or `?` as `SENTENCE_END`, and everything else as `WORD`. Assigns sequential `index` values starting at 0.
 
Edge cases like `Mr. Smith` producing false sentence breaks are accepted for Phase 1.
 
### `core/timing.py`
 
```python
def delay_ms(wpm: int) -> int:
    return int(60_000 / wpm)
```
 
That is the entire Phase 1 implementation. The signature is stable; later phases will add optional parameters for token type and word length.
 
### `importers/base.py`
 
```python
from abc import ABC, abstractmethod
from pathlib import Path
 
class Importer(ABC):
    @abstractmethod
    def can_handle(self, path: Path) -> bool: ...
 
    @abstractmethod
    def load(self, path: Path) -> list[Token]: ...
```
 
### `importers/txt.py`
 
Implements `Importer` for `.txt` files. `can_handle` returns `True` for paths with a `.txt` suffix. `load` reads the file as UTF-8 and passes the contents to `tokenize`.
 
### `storage/config.py`
 
```python
def config_dir() -> Path
def load_config() -> dict       # returns defaults if file missing
def save_config(cfg: dict) -> None
```
 
Defaults: `{"wpm": 300, "dark_mode": True}`.
 
### `storage/progress.py`
 
```python
def load_progress() -> dict[str, int]
def save_progress(progress: dict[str, int]) -> None
def get_position(file_path: str) -> int
def set_position(file_path: str, position: int) -> None
```
 
---
 
## UI Layout
 
A single fixed-size window, approximately 600×300 pixels, non-resizable in Phase 1.
 
```
┌─────────────────────────────────────────────┐
│  essay.txt                  45%  │  300 wpm │   ← status bar (top)
├─────────────────────────────────────────────┤
│                                             │
│                                             │
│                interesting                  │   ← reader view (center)
│                                             │
│                                             │
├─────────────────────────────────────────────┤
│  [Open]  [▶ Play]   WPM: [-] 300 [+]   [🌙] │   ← controls (bottom)
└─────────────────────────────────────────────┘
```
 
### Reader view
 
A single `tk.Label` centered in the content area. Font size 36pt, monospace or a clean sans-serif (Arial / Helvetica / system default). Text is centered horizontally and vertically. The label's text is swapped on each tick of the play loop.
 
### Status bar
 
Three fields, left to right: filename (or "No file loaded"), progress percentage (or blank), WPM readout.
 
### Controls
 
- **Open** button — opens a file dialog filtered to `.txt`
- **Play / Pause** button — toggles `session.is_playing` and label between `▶ Play` and `⏸ Pause`
- **WPM** control — label showing current WPM with `-` and `+` buttons; steps of 25, clamped to 100–1000
- **Theme toggle** — switches between light and dark mode, persisted to config
### Colors
 
**Dark mode (default):**
- Background: `#1e1e1e`
- Text: `#e8e8e8`
- Accent / focus: `#4a9eff`
**Light mode:**
- Background: `#f5f5f5`
- Text: `#1a1a1a`
- Accent / focus: `#2563eb`
---
 
## Keyboard Shortcuts
 
| Key         | Action                  |
| ----------- | ----------------------- |
| `Space`     | Toggle play / pause     |
| `Left`      | Rewind 5 tokens         |
| `Ctrl+O`    | Open file dialog        |
 
All other keys are unbound in Phase 1.
 
---
 
## The Play Loop
 
The loop is driven by Tkinter's `root.after`. No threads, no `time.sleep`.
 
```python
def tick(self):
    if not self.session.is_playing:
        return
    token = self.session.current_token()
    if token is None:
        self.session.is_playing = False
        self._update_play_button()
        return
    self.reader_view.show(token.text)
    self.session.advance()
    self.root.after(delay_ms(self.session.wpm), self.tick)
```
 
- **Pause:** set `session.is_playing = False`. The next scheduled tick will return immediately.
- **Resume:** set `session.is_playing = True` and call `self.tick()` once to restart the chain.
- **Rewind:** call `session.rewind(5)`. The display catches up on the next tick.
- **WPM change mid-stream:** no special handling needed; the next `after` call uses the new value.
---
 
## Persistence Behavior
 
Progress is saved:
- When the user pauses playback
- When the app window closes (bind to `WM_DELETE_WINDOW`)
- Every 100 tokens during playback (checkpoint against crashes)
Config is saved:
- When WPM changes (debounced or on release; simplest is on every change)
- When the theme toggle is flipped
- When the app window closes
On startup:
- Load config; apply WPM and theme
- Do not auto-load any file; the user must explicitly open one
On opening a file:
- Parse into tokens
- Look up the absolute path in `progress.json`; if found, set `session.position` to the stored value
- Do not auto-play; wait for the user to press Play
---

 

