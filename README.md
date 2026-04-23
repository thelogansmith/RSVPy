# RSVPy

A lightweight, cross-platform desktop app for reading text using Rapid Serial Visual Presentation (RSVP).

RSVP displays words one at a time at a fixed focal point, eliminating eye movement and enabling faster reading. RSVPy aims to bring this technique to your local files — plain text, ebooks, documents, and PDFs — without the bloat of a modern Electron app.

## Status

🚧 **Phase 3 complete.** The app reads `.txt`, `.md`, `.epub`, `.docx`, and `.pdf` files with transport controls, reading statistics, recent-files history, a context window for tracking your position in the document, and a scrubbable progress bar. See [Roadmap](#roadmap) for what's next.

## Goals

- **Lightweight.** Minimal dependencies, fast startup, low memory footprint. Targets the resource budget of an early-2000s desktop application.
- **Cross-platform.** Runs on Windows, macOS, and Linux via Python and Tkinter.
- **File-first.** Import from common document formats rather than relying on web sources or cloud services.
- **Offline by default.** No telemetry, no required network access. Optional AI features (later phases) are opt-in and use your own API key.

## Planned Features

- Configurable words-per-minute (WPM) with pause, resume, and rewind
- Support for `.txt`, `.md`, `.epub`, `.docx`, and text-based `.pdf`
- Per-file reading progress and resume
- Customizable display (font, size, colors, dark mode)
- Keyboard-driven controls
- Optional AI-generated summaries for reinforcement (later phase)

## Roadmap

**Phase 1 — Core skeleton (complete)**
Tkinter window, `.txt` import, WPM control, play/pause/rewind, session persistence, dark mode.

**Phase 2 — More formats and polish (complete)**
`.md`, `.epub`, `.docx` importers. Transport controls (restart, rewind, play/pause, skip). Recent files window. Reading statistics. Stale-position detection. Additional keyboard shortcuts.

**Phase 3 — PDF support and context window (complete)**
Text-based PDF import with extraction preview. Context window showing surrounding text with current-word highlighting. Click-to-seek in context window. Scrubbable progress bar. Threaded file loading. Resizable main window.

**Phase 4 — AI integration and settings**
Optional post-session summaries using a user-supplied API key. Hierarchical summarization for long documents. Settings panel for font, color, and size customization.

**Phase 5 — Reading optimizations**
Optimal Recognition Point (ORP) alignment, variable timing based on word length and punctuation, chunked display for function words.

## Non-goals

- OCR or image-based text extraction
- Mobile platforms
- Cloud sync or account systems
- Monetization

## Requirements

- Python 3.10 or newer
- Tkinter (included with standard Python installations on Windows and macOS; may require `python3-tk` on Linux)

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

## Keyboard Shortcuts

| Key       | Action                     |
|-----------|----------------------------|
| Space     | Play / Pause               |
| Left      | Rewind 5 words             |
| Right     | Skip forward 5 words       |
| Home      | Restart from beginning     |
| Ctrl+O    | Open file                  |
| Ctrl+R    | Recent files               |
| Ctrl+T    | Toggle context window      |

## License

MIT — see [LICENSE](LICENSE).