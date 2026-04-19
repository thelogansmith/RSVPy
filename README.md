# RSVPy

A lightweight, cross-platform desktop app for reading text using Rapid Serial Visual Presentation (RSVP).

RSVP displays words one at a time at a fixed focal point, eliminating eye movement and enabling faster reading. RSVPy aims to bring this technique to your local files — plain text, ebooks, documents, and PDFs — without the bloat of a modern Electron app.

## Status

🚧 **Early development — Phase 1.** Not yet usable. See [Roadmap](#roadmap) for planned features.

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

**Phase 1 — Core skeleton (in progress)**
Tkinter window, `.txt` import, WPM control, play/pause/rewind, session persistence, dark mode.

**Phase 2 — More formats and polish**
`.md`, `.epub`, `.docx` importers. Keyboard shortcuts. Library view of recent files. Reading statistics.

**Phase 3 — PDF support**
Text-based PDF import with an extraction preview step. Scanned PDFs and OCR are explicitly out of scope.

**Phase 4 — AI integration**
Optional post-session summaries using a user-supplied API key. Hierarchical summarization for long documents.

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

Not yet available. Once Phase 1 is functional:

```bash
