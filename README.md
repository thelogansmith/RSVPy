# RSVPy

A lightweight, cross-platform desktop app for reading text using Rapid Serial Visual Presentation (RSVP).

RSVP displays words one at a time at a fixed focal point, eliminating eye movement and enabling faster reading. RSVPy brings this technique to your local files — plain text, ebooks, documents, and PDFs — without the bloat of a modern Electron app.

## Status

✅ **Phase 5 complete — beta.** The app reads `.txt`, `.md`, `.epub`, `.docx`, and `.pdf` files with transport controls, reading statistics, recent-files history, a context window, scrubbable progress bar, settings panel for customizing font and accent color, optional AI-powered document summaries, ORP alignment, and variable timing tuned to sentence and paragraph boundaries. See [Roadmap](#roadmap) for what's next.

## Goals

- **Lightweight.** Minimal, deliberate dependencies, fast startup, low memory footprint. Targets the resource budget of an early-2000s desktop application.
- **Cross-platform.** Runs on Windows, macOS, and Linux via Python and Tkinter.
- **File-first.** Import from common document formats rather than relying on web sources or cloud services.
- **Offline by default.** No telemetry, no required network access. AI features are opt-in and use your own API key.

## Features

- Configurable words-per-minute (WPM) with play, pause, rewind, and skip controls
- Support for `.txt`, `.md`, `.epub`, `.docx`, and text-based `.pdf`
- Per-file reading progress and resume, with stale-position detection when a file has changed
- Optimal Recognition Point (ORP) alignment — words are positioned so the focal character sits at a fixed column, with that character highlighted in the accent color
- Variable timing — sentence ends pause longer, paragraph ends pause longer still, short words flash faster, long words linger, standalone punctuation flashes briefly
- Configurable display font (family and size) and accent color
- Dark mode and light mode toggle
- Context window showing surrounding text with current-word highlighting
- Click-to-seek in the context window
- Scrubbable progress bar
- Threaded file loading (no UI freeze on large EPUB or PDF files)
- Recent files list and reading statistics
- Optional AI-generated summaries via the Anthropic Claude API
- Keyboard-driven controls

## Requirements

- Python 3.10 or newer
- Tkinter (included with standard Python on Windows and macOS; may require `python3-tk` on Linux)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/thelogansmith/RSVPy.git
cd RSVPy
```

2. Create and activate a virtual environment:

```bash
# Create the venv
python -m venv .venv

# Activate it
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# Windows (cmd):
.venv\Scripts\activate.bat
# macOS / Linux:
source .venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the app:

```bash
python main.py
```

## AI Summaries (Optional)

RSVPy can generate document summaries using the Anthropic Claude API. This feature is entirely opt-in and requires your own API key.

1. Open Settings (⚙ icon in the status bar, or `Ctrl+,`)
2. Enter your Anthropic API key in the AI Summarization section
3. Click "Test connection" to verify
4. A "Summarize" button will appear in the transport controls after loading a document

Your API key is stored securely using your operating system's credential store (Windows Credential Locker, macOS Keychain, or Linux Secret Service). If the OS credential store is unavailable, the key is stored in a file with restricted permissions. It is never written to `config.json`.

## Keyboard Shortcuts

| Key        | Action                     |
|------------|----------------------------|
| `Space`    | Play / Pause               |
| `Left`     | Rewind 5 words             |
| `Right`    | Skip forward 5 words       |
| `Home`     | Restart from beginning     |
| `Ctrl+O`   | Open file                  |
| `Ctrl+R`   | Recent files               |
| `Ctrl+T`   | Toggle context window      |
| `Ctrl+,`   | Open settings              |

## Project Structure

```
RSVPy/
├── main.py                   # Entry point
├── requirements.txt
├── core/
│   ├── session.py            # In-memory reading state
│   ├── summarizer.py         # AI summarization logic
│   ├── timing.py             # WPM → delay in ms (with variable timing)
│   └── tokenizer.py          # Text → token list
├── importers/
│   ├── base.py               # Importer interface
│   ├── docx.py               # .docx importer
│   ├── epub.py               # .epub importer
│   ├── md.py                 # .md importer
│   ├── pdf.py                # .pdf importer
│   ├── registry.py           # Importer lookup and extension list
│   └── txt.py                # .txt importer
├── storage/
│   ├── config.py             # User preferences (config.json)
│   ├── keystore.py           # Secure API key storage
│   ├── progress.py           # Per-file position (progress.json)
│   └── stats.py              # Reading statistics (stats.json)
└── ui/
    ├── context_window.py     # Source text Toplevel with highlighting
    ├── dialogs.py            # Modal dialogs (file changed, restart confirm)
    ├── main_window.py        # Tk root and layout
    ├── reader_view.py        # Word display widget (ORP-aligned)
    ├── recents_window.py     # Recent files Toplevel
    ├── settings_window.py    # Settings panel Toplevel
    ├── stats_window.py       # Reading statistics Toplevel
    ├── summary_window.py     # AI summary display Toplevel
    ├── theme.py              # Theme color definitions
    └── tooltip.py            # Hover tooltip helper
```

## Persistence

RSVPy stores three JSON files in the platform-appropriate config directory:
- **Windows:** `%APPDATA%\RSVPy\`
- **macOS / Linux:** `$XDG_CONFIG_HOME/RSVPy/` or `~/.config/RSVPy/`

| File              | Contents                                                  |
|-------------------|-----------------------------------------------------------|
| `config.json`     | WPM, dark mode, font, accent color, and other preferences |
| `progress.json`   | Per-file reading position and source hash                 |
| `stats.json`      | Reading statistics (tokens read, active time, sessions)   |
| `credentials.json`| API key fallback (only used if OS credential store fails) |

All writes are atomic (temp file + `os.replace`) so a crash mid-write cannot corrupt data.

## Roadmap

**Phase 1 — Core skeleton (complete)**
Tkinter window, `.txt` import, WPM control, play/pause/rewind, per-file progress, dark mode. Config and progress persistence.

**Phase 2 — More formats and polish (complete)**
`.md`, `.epub`, `.docx` importers. Transport controls (restart, rewind, play/pause, skip forward). Recent files window. Reading statistics. Stale-position detection with per-file SHA-256 hashing. Additional keyboard shortcuts.

**Phase 3 — PDF support and context window (complete)**
Text-based PDF import with extraction preview dialog. Context window showing surrounding source text with current-word highlighting. Click-to-seek in context window. Scrubbable progress bar. Threaded file loading (fixes EPUB/PDF freeze). Resizable main window with persisted geometry.

**Phase 4 — AI integration and settings (complete)**
Settings panel for font family, font size, and accent color customization. Transport button design overhaul with tooltips. Optional post-session summaries using a user-supplied Anthropic API key. Hierarchical summarization for long documents. Secure API key storage via OS credential store.

**Phase 5 — Reading optimizations (complete)**
Optimal Recognition Point (ORP) alignment, variable timing based on word length and punctuation, punctuation-only token handling. Function-word chunking was attempted and removed — function words flashed too fast to register as part of the chunk and the variable display widths interfered with ORP alignment. See the Phase 5 spec for details.

**What's next**
Cross-platform download releases for macOS, Debian, and RHEL. Normalization layer for EPUB and PDF extraction so the reading experience holds up regardless of source variability.

## Non-goals

- OCR or image-based text extraction
- Mobile platforms
- Cloud sync or account systems
- Monetization

## License

MIT — see [LICENSE](LICENSE).
