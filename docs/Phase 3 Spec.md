# Phase 3 Specification

**Status:** Completed
**Goal:** Add PDF support with an extraction preview step, a context
window that shows surrounding text during playback, and threaded file
loading to fix the EPUB performance problem. Phase 3 turns RSVPy from
a format converter into a reader that lets you see where you are in
the document.

This document defines scope, architecture decisions, and build order
for Phase 3. Anything not listed here is out of scope.

---

## Scope

### In scope

- `.pdf` importer (text-based PDFs only, no OCR)
- Extraction preview dialog for PDFs before committing to read
- Context window (separate Toplevel) showing source text with current
  word highlighted during playback
- Click-to-seek in the context window
- Threaded file loading with progress indicator (fixes EPUB freeze)
- Window resizability for the main reader window
- Scrubbable progress bar in the control area

### Out of scope

- Scanned PDFs / OCR (explicit non-goal per roadmap)
- Chapter / TOC navigation in the context window (Phase 4 or 5)
- AI summarization (Phase 4)
- Font, color, and size customization beyond dark mode (Phase 4)
- Settings panel to revert "don't ask again" choices (Phase 4)
- ORP alignment, variable timing, punctuation-only token handling
  (Phase 5)
- Packaging or distribution

---

## Dependencies

### New dependency

- `pdfplumber>=0.10.0` — PDF text extraction. Pure-ish Python,
  MIT-licensed, good extraction quality for single-column and
  moderately complex layouts. Chosen over PyMuPDF to preserve the
  project's MIT license; chosen over pypdf for better extraction
  quality on real-world documents.

### Existing dependencies (unchanged)

- `python-docx>=1.1.0`
- `EbookLib>=0.18`

`requirements.txt` gains one line.

---

## Architectural Decisions

### PDF library: pdfplumber

pdfplumber extracts text page-by-page with layout awareness. It
handles columns reasonably for most documents but can struggle with
complex multi-column layouts, dense tables, and math-heavy content.
The extraction preview step (see Features) is the safety net: users
see what they're getting before committing to read.

If extraction quality becomes a persistent pain point in practice,
swapping to PyMuPDF is a one-file change in `importers/pdf.py`. The
importer architecture isolates the dependency completely.

### Context window: separate Toplevel

The context window is a standalone `Toplevel`, not an embedded panel.
This preserves the reader window's visual simplicity (the "quiet
reading" feel) and avoids the complexity of a split-pane layout in
Tkinter. Users can position, resize, or close the context window
independently.

The main window becomes resizable in Phase 3 — not because of the
context window, but because it's been a limitation since Phase 1 and
this is the right time to address it. The context window is always
resizable.

### Threaded loading: `threading.Thread` + queue

File loading moves off the main thread to prevent UI freezes. The
pattern:

1. `_load_file` shows a "Loading..." indicator in the reader view.
2. A background thread runs the importer's `load()` method.
3. On completion, the thread puts the result on a `queue.Queue`.
4. A `root.after` poll loop checks the queue every 50ms.
5. When the result arrives, the main thread processes it as before.

Errors in the background thread are caught and forwarded through the
queue. The loading indicator includes a Cancel button that sets a
threading event; importers that support cancellation can check it
during long operations.

This pattern benefits all formats — `.txt` and `.md` are fast enough
to never need it, but `.docx`, `.epub`, and `.pdf` all benefit. The
importer interface does not change; the threading wrapper lives
entirely in `main_window.py`.

### Progress bar: `ttk.Scale` or canvas

A thin horizontal bar below the reader view (or at the bottom of the
status bar) showing reading progress. Clicking or dragging seeks to
the corresponding position. This replaces the text-only percentage
in the status bar with something interactive. The text percentage
remains in the status bar alongside the bar.

---

## Data Structure Changes

### No changes to Token or Session

Phase 2 already added `source_start`, `source_end` to Token and
`source_text`, `source_hash` to Session. The context window consumes
these existing fields. No data model changes are needed.

### `config.json` additions

```json
{
  "wpm": 300,
  "dark_mode": true,
  "restart_confirm": true,
  "context_window_open": false,
  "main_window_geometry": null
}
```

- `context_window_open`: whether to auto-open the context window on
  file load. Defaults to false.
- `main_window_geometry`: Tk geometry string (e.g. "800x400+100+200")
  persisted on close, restored on launch. Null means use default.

---

## Features

### PDF importer

`importers/pdf.py` using pdfplumber:

- Opens the PDF, iterates pages in order.
- Extracts text from each page via `page.extract_text()`.
- Pages are joined with double newlines (paragraph breaks) so the
  tokenizer correctly identifies page boundaries.
- Empty pages are skipped.
- The importer returns `(canonical_text, tokens)` like all others.

Known limitations (acceptable for Phase 3):
- Multi-column layouts may interleave columns incorrectly.
- Tables may extract with garbled structure.
- Math, diagrams, and images are silently skipped.
- Password-protected PDFs raise an exception (handled by the existing
  broad `except` in `_load_file`).

### Extraction preview dialog

When a PDF is opened, before loading begins:

1. Extract text from the first 2-3 pages as a preview.
2. Show a modal dialog with the preview text in a scrollable `Text`
   widget.
3. User sees what the extraction looks like and can choose:
   - **"Read this"** — proceed with full extraction and loading.
   - **"Cancel"** — abort, return to the reader.

This runs on the main thread (preview is fast for 2-3 pages). Full
extraction after confirmation runs on the background thread.

The dialog is specific to PDFs. Other formats load directly because
their extraction is reliable. If a format's extraction proves
unreliable in practice, the preview can be extended to it later.

### Context window

A `Toplevel` window (`ui/context_window.py`) containing a `tk.Text`
widget that displays the full source text of the current document.

**Display:**
- Source text is loaded from `session.source_text`.
- Read-only (user cannot edit).
- Monospace or clean sans-serif font, comfortable reading size (~11pt).
- Themed to match the main window (dark/light).

**Highlighting:**
- The word currently displayed in the reader view is highlighted in
  the context window using a Tk text tag with the accent color
  background.
- Highlighting updates on every tick of the play loop. The main
  window calls `context_window.highlight(source_start, source_end)`
  each tick.
- The text widget auto-scrolls to keep the highlighted word visible,
  centered vertically when possible.

**Click-to-seek:**
- Clicking a word in the context window seeks playback to that token.
- Implementation: on click, get the character offset from the Text
  widget, binary-search the token list for the token whose
  `source_start <= offset < source_end`, set `session.position` to
  that token's index.
- If playing, playback continues from the new position. If paused,
  the reader view updates to show the clicked word.

**Lifecycle:**
- Opened via a "Context" button in the status bar or `Ctrl+T`.
- Stays open across file loads (content refreshes).
- Position and open/closed state persisted in config.
- Closing the context window does not affect playback.

### Threaded file loading

See Architectural Decisions above for the pattern. User-visible
behavior:

- Reader view shows "Loading..." (or a simple spinner text) while
  the background thread works.
- Transport buttons are disabled during loading.
- A "Cancel" option is available (sets a flag; the importer may not
  check it, in which case the load completes and the result is
  discarded).
- On success: file loads as before, context window refreshes.
- On error: reader view shows "Failed to load" briefly, then clears.
  Error details go to console as in Phase 1-2.

### Scrubbable progress bar

A thin interactive bar showing reading position:

- Horizontal, full width, positioned between the reader view and the
  control bar (or integrated into the control bar).
- Filled portion represents `session.progress()`.
- Click anywhere to seek to that percentage position.
- Drag to scrub through the document.
- Updates every tick during playback.
- Themed (accent color for filled portion, surface color for track).

### Main window resizability

- `root.resizable(True, True)` replaces `resizable(False, False)`.
- Minimum size stays at 700x300.
- Reader view font does not scale with window size (Phase 5 concern).
- Window geometry (size + position) persisted in config on close,
  restored on launch.

---

## UI Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  essay.pdf         Context | Recent | Stats      45%  │  300 wpm   │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                                                                      │
│                          interesting                                 │
│                                                                      │
│                                                                      │
├══════════════════════════════════════════════════════════════════════╤
│ ████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
├──────────────────────────────────────────────────────────────────────┤
│ [Open] [⏮][⏪][▶][⏩]   WPM: [-] 300 [+]                       [🌙] │
└──────────────────────────────────────────────────────────────────────┘
```

The progress bar sits between the reader view and the control bar as
a thin interactive strip.

"Context" button added to the status bar alongside "Recent" and
"Stats", styled identically.

### Context window (separate Toplevel)

```
┌──────────────────────────────────────────┐
│  Context — essay.pdf                     │
├──────────────────────────────────────────┤
│                                          │
│  ...the study found that one of the      │
│  most ██interesting██ aspects of the     │
│  phenomenon was its relationship to      │
│  existing theoretical frameworks...      │
│                                          │
│                                          │
└──────────────────────────────────────────┘
```

The highlighted word tracks playback. Clicking any word seeks to it.

---

## Keyboard Shortcuts (additions)

| Key       | Action                         |
|-----------|--------------------------------|
| `Ctrl+T`  | Toggle context window          |

All existing shortcuts (Space, Left, Right, Home, Ctrl+O, Ctrl+R)
remain unchanged.

---

## Build Order

Each step leaves the app in a runnable, shippable state.

1. **Threaded file loading.** Implement the background-thread +
   queue pattern in `_load_file`. Show "Loading..." in reader view
   during load. Disable transport buttons while loading. Test with
   large EPUB files to verify the UI stays responsive. No new
   features yet — this is infrastructure.

2. **Main window resizability.** Flip `resizable(True, True)`, set
   minimum size, persist geometry in config. Verify layout integrity
   at various sizes.

3. **Progress bar.** Add a thin interactive bar. Wire click-to-seek
   and drag-to-scrub. Updates every tick. Themed.

4. **PDF importer.** Write `importers/pdf.py` using pdfplumber. Add
   to registry. Add dep to `requirements.txt`. Test with several
   PDFs of varying complexity.

5. **Extraction preview dialog.** Modal dialog showing first 2-3
   pages of PDF text. "Read this" / "Cancel" buttons. Only shown
   for `.pdf` files.

6. **Context window — display.** New `ui/context_window.py` Toplevel
   with read-only Text widget. Loads `session.source_text`. Themed.
   "Context" button in status bar, Ctrl+T shortcut. Persist
   open/closed state in config.

7. **Context window — highlighting.** Highlight current word during
   playback using text tags. Auto-scroll to keep highlighted word
   visible.

8. **Context window — click-to-seek.** Click handler that maps
   text widget offset to token index and updates session position.

9. **Polish and docs.** README update (Phase 3 status, new dep,
   new shortcuts). Verify all features work together. Edge cases:
   empty PDFs, single-page PDFs, very long documents, rapid
   clicking in context window during playback.

Steps 1-3 are infrastructure. Steps 4-5 are the PDF headline.
Steps 6-8 are the context window. Step 9 is cleanup. If time runs
short, stopping after step 5 still delivers the PDF feature.

---

## Persistence Behavior Changes

Everything from Phase 1 and Phase 2 still applies. Additions:

- Main window geometry saved on close, restored on launch.
- Context window open/closed state saved in config.
- Progress bar position is derived from `session.progress()`, not
  independently persisted.

---

## Open Questions

These don't block starting; decide during implementation:

- **Should the progress bar show during loading?** Leaning no — it
  represents reading progress, not loading progress. A separate
  loading indicator is clearer.
- **Should the context window have its own scroll position memory?**
  Leaning no — it auto-scrolls to the current word, so saved scroll
  position would be immediately overridden.
- **Should clicking in the context window pause playback?** Leaning
  no — seeking without pausing feels more natural for quick
  repositioning. The user can always hit Space to pause first.
- **Should the extraction preview show a page count?** Leaning yes
  — "Preview (3 of 47 pages)" helps the user gauge document length
  before committing.
