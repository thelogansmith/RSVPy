# RSVPy

A lightweight, cross-platform desktop app for reading text using Rapid Serial Visual Presentation (RSVP).

RSVP displays words one at a time at a fixed focal point, eliminating eye movement and enabling faster reading. RSVPy aims to bring this technique to your local files — plain text, ebooks, documents, and PDFs — without the bloat of a modern Electron app.

## Status

🚧 **Phase 4 complete.** The app reads `.txt`, `.md`, `.epub`, `.docx`, and `.pdf` files with transport controls, reading statistics, recent-files history, a context window, scrubbable progress bar, settings panel for customizing font and accent color, and optional AI-powered document summaries. See [Roadmap](#roadmap) for what's next.

## Goals

- **Lightweight.** Minimal dependencies, fast startup, low memory footprint. Targets the resource budget of an early-2000s desktop application.
- **Cross-platform.** Runs on Windows, macOS, and Linux via Python and Tkinter.
- **File-first.** Import from common document formats rather than relying on web sources or cloud services.
- **Offline by default.** No telemetry, no required network access. AI features are opt-in and use your own API key.

## Features

- Configurable words-per-minute (WPM) with pause, resume, and rewind
- Support for `.txt`, `.md`, `.epub`, `.docx`, and text-based `.pdf`
- Per-file reading progress and resume
- Customizable display font (family and size) and accent color
- Dark mode toggle
- Context window showing surrounding text with current-word highlighting
- Click-to-seek in context window
- Scrubbable progress bar
- Recent files list and reading statistics
- Optional AI-generated summaries via Anthropic Claude API
- Keyboard-driven controls

## Roadmap

**Phase 1 — Core skeleton (complete)**
Tkinter window, `.txt` import, WPM control, play/pause/rewind, session persistence, dark mode.

**Phase 2 — More formats and polish (complete)**
`.md`, `.epub`, `.docx` importers. Transport controls (restart, rewind, play/pause, skip). Recent files window. Reading statistics. Stale-position detection. Additional keyboard shortcuts.

**Phase 3 — PDF support and context window (complete)**
Text-based PDF import with extraction preview. Context window showing surrounding text with current-word highlighting. Click-to-seek in context window. Scrubbable progress bar. Threaded file loading. Resizable main window.

**Phase 4 — AI integration and settings (complete)**
Settings panel for font family, font size, and accent color customization. Transport button design overhaul. Optional post-session summaries using a user-supplied Anthropic API key. Hierarchical summarization for long documents. Secure API key storage via OS credential store.

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

## AI Summaries (Optional)

RSVPy can generate document summaries using the Anthropic Claude API. This feature is entirely opt-in and requires your own API key.

1. Open Settings (⚙ icon in the status bar, or Ctrl+,)
2. Enter your Anthropic API key in the AI Summarization section
3. Click "Test connection" to verify
4. Use the "Summarize" button that appears in the transport controls after loading a document

Your API key is stored securely using your operating system's credential store (Windows Credential Locker, macOS Keychain, or Linux Secret Service). If the OS credential store is unavailable, the key is stored in a file with restricted permissions — it is never written to `config.json`.

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
| Ctrl+,    | Open settings              |

## License

MIT — see [LICENSE](LICENSE).