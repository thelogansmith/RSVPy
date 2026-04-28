# Phase 2 Specification

**Status:** Completed
**Goal:** Extend RSVPy from a single-format reader into a multi-format
reader with transport controls, reliable resume behavior, and basic
reading history. Lay the groundwork for the context window that arrives
in Phase 3.

This document defines scope, architecture decisions, and build order
for Phase 2. Anything not listed here is out of scope.

---

## Scope

### In scope

- `.md` (Markdown) importer
- `.epub` importer
- `.docx` importer
- Stale-position detection with user prompt on file change
- Transport control buttons (restart, rewind, play/pause, skip forward)
- Restart confirmation dialog with "don't ask again" option
- Recent files list / basic library view
- Reading statistics (per-file and aggregate)
- Additional keyboard shortcuts (Right for skip forward, at minimum)
- Tokenizer and Session changes to carry source text and per-token
  source offsets, enabling Phase 3's context window

### Out of scope

- PDF support (Phase 3)
- Context window / source text display (Phase 3)
- Click-to-seek (Phase 3)
- AI summarization (Phase 4)
- Configurable font, colors, and size beyond dark mode (Phase 4)
- Reverting "don't ask again" choices via a settings panel (Phase 4)
- ORP alignment, variable timing (Phase 5)
- Punctuation-only token handling (Phase 5)
- Error dialogs for general errors (console messages still acceptable
  for Phase 2; file-change prompt is a deliberate exception)

---

## Architectural Decisions

### Third-party dependencies: accepted

Phase 1 had zero third-party deps. Phase 2 accepts two:

- `python-docx` — DOCX parsing. The stdlib alternative is writing a
  ZIP+XML parser by hand, which is meaningful work and permanently more
  code to maintain.
- `ebooklib` — EPUB parsing. Same reasoning; EPUBs vary enough in the
  wild that a tested library is worth the dependency.

Markdown is handled without a dep: a short regex-based stripper in the
importer is sufficient for Phase 2 needs.

Dependencies go in a `requirements.txt` at the repo root. README gets
an installation section update: `pip install -r requirements.txt`.
This is the developer's first exposure to pip-installed packages, so
a `venv` step should be documented at the same time.

### Reading statistics: new JSON file

A new `stats.json` alongside `config.json` and `progress.json`. Still
simple, still atomic-write, still stdlib. SQLite is deferred; stats
aren't relational enough to need it yet.

### Window: stays fixed for now

The 600×300 fixed window is retained. The recent-files view is a
separate `Toplevel` window reachable from a "Recent" button or menu,
not a panel inside the reader. This keeps the reader's visual quiet.

---

## Data Structure Changes

### `progress.json` format change

Old format (Phase 1):

```json
{
  "/home/user/essay.txt": 847
}
```

New format (Phase 2):

```json
{
  "/home/user/essay.txt": {
    "position": 847,
    "hash": "3b4f..."
  }
}
```

`hash` is the hex SHA-256 of the file's raw bytes at save time.

**Migration:** on load, entries whose value is a bare int are upgraded
in memory to `{"position": int, "hash": null}`. Null hashes are treated
as "no validation possible" — the saved position is used without
prompting. Next save writes the upgraded format to disk. Old users
therefore see no behavior change on their first Phase 2 session.

### `stats.json` format

```json
{
  "totals": {
    "tokens_read": 42017,
    "seconds_active": 9815,
    "sessions": 27
  },
  "per_file": {
    "/home/user/essay.txt": {
      "tokens_read": 1204,
      "seconds_active": 287,
      "last_opened": "2026-04-19T18:32:11Z"
    }
  }
}
```

"Active" time is time with playback running — paused time does not
count. Counted in `_tick` by incrementing with `delay_ms(wpm) / 1000`
rather than by sampling wall clock, so slow machines don't inflate
numbers.

### `Token` dataclass: add source offsets

```python
@dataclass
class Token:
    text: str
    type: TokenType
    index: int
    source_start: int   # inclusive byte offset into source text
    source_end: int     # exclusive byte offset into source text
```

Offsets refer to the *tokenizer input string*, not the raw file bytes.
Each importer is responsible for producing the canonical text string
that the tokenizer then maps offsets into; that same string is stored
on the Session and hashed for fingerprinting.

### `Session` dataclass: add source

```python
@dataclass
class Session:
    tokens: list[Token] = field(default_factory=list)
    source_text: str = ""          # new
    source_hash: str = ""          # new, hex SHA-256 of source_text
    position: int = 0
    wpm: int = 300
    is_playing: bool = False
    file_path: str = ""
```

Source hashing uses the tokenizer input, not the raw file bytes. This
means a `.docx` whose XML changes but whose extracted text is identical
will correctly be recognized as "the same reading material."

---

## Features

### Stale-position detection (issue #1 from Phase 1 handoff)

On file open:

1. Importer loads file, produces canonical text.
2. Compute SHA-256 of canonical text.
3. Look up stored `{position, hash}` for the file path.
4. If no stored entry: start at 0.
5. If stored hash is null (migrated from Phase 1): resume at stored
   position, no prompt.
6. If stored hash matches current hash: resume at stored position.
7. If stored hash differs: **show a prompt**:

   > This file has changed since you last read it.
   > Resume at 45%, or start from the beginning?
   >
   > `[Start over]`  `[Resume anyway]`

   Default button is "Start over." No "remember this choice" option —
   every mismatch gets prompted, because silently resuming on a changed
   file is the bug this feature exists to fix.

This is the first UI dialog in the app. A small utility function in
`ui/dialogs.py` wraps `tkinter.messagebox` or a custom `Toplevel` and
is reused by the restart confirmation below.

### Transport control buttons

Four buttons grouped in the control bar:

```
[Open]   [⏮ Restart] [⏪ Rewind] [▶ Play] [⏩ Skip]   WPM: [-] 300 [+]   [🌙]
```

- **Restart** — jumps to position 0. Shows confirmation dialog (see
  next section).
- **Rewind** — moves back 5 tokens. Exposes the existing `_on_rewind`
  handler as a button.
- **Play/Pause** — unchanged from Phase 1.
- **Skip** — moves forward 5 tokens. New method `Session.skip(n: int = 5)`,
  symmetric with `rewind`. Bound to Right arrow.

All four respect the playing state: pressing Rewind or Skip during
playback reposions without pausing. Restart during playback also does
not pause — after confirmation, playback continues from position 0.

### Restart confirmation

A `Toplevel` dialog with:

> Restart reading from the beginning?
>
> `[ ] Don't ask again`
>
> `[Cancel]`  `[Restart]`

"Don't ask again" writes a new config key `restart_confirm: false`.
Phase 2 provides no UI to flip it back; the developer has explicitly
scoped that to Phase 4 polishing. A user who wants it back can edit
`config.json` directly.

Default button is Cancel. The dialog is modal to the main window.

### Recent files / library view

A `Toplevel` window opened via a new "Recent" button or `Ctrl+R`.
Contents:

- List of recently opened files, newest first
- For each: filename, last-opened timestamp, progress percentage
- Double-click or Enter opens the file in the main window
- Right-click → "Remove from list" (optional for Phase 2, nice to have)

Maximum list length: 20 (arbitrary, enough for Phase 2). Older entries
drop off the end.

Storage: reuses `stats.json`'s `per_file` section, ordered by
`last_opened`. No separate recents file needed.

### Reading statistics

Stats are accumulated during playback and surfaced two ways:

- **Per-file:** a small indicator in the recent-files list (progress %,
  approx reading time remaining at current WPM).
- **Aggregate:** a `Stats` menu option or button that opens a `Toplevel`
  with totals: total words read, total time, sessions count, maybe a
  simple "you read X words this week" if time permits.

Update cadence: `_tick` increments an in-memory counter; the same
100-token checkpoint that saves progress also flushes stats to disk.
Matches the existing cadence and avoids a second I/O loop.

### Keyboard shortcuts (additions)

| Key          | Action                 |
|--------------|------------------------|
| `Right`      | Skip forward 5 tokens  |
| `Home`       | Restart (with prompt)  |
| `Ctrl+R`     | Open recents window    |

`Ctrl+R` conflicts with browser-style "reload" — not a problem in Tk,
but worth flagging for anyone who adapts this to a different toolkit.

### Tokenizer: source offsets

`tokenize(text: str) -> list[Token]` gains the responsibility of
tracking where in `text` each token starts and ends. The split logic
stays the same; an offset counter accompanies the existing index
counter.

Importers change signature:

```python
def load(self, path: Path) -> tuple[str, list[Token]]:
    """Return (canonical_text, tokens)."""
```

The canonical text is whatever the importer decides to tokenize —
raw contents for `.txt`, stripped Markdown for `.md`, joined chapter
text for EPUB, extracted body text for DOCX. The tokens' offsets
refer to that returned string.

`MainWindow._load_file` updates to unpack both, store both on the
Session, and hash the source.

### Importers

- **MarkdownImporter** (`.md`): read file as UTF-8, strip Markdown
  syntax with regex (headers, bold/italic markers, link syntax, image
  syntax, code fence markers), tokenize the result. Code blocks are
  preserved as plain text. HTML inside Markdown is not supported in
  Phase 2 — it passes through with its tags visible, flagged for Phase 5.
- **EpubImporter** (`.epub`): uses `ebooklib` to iterate chapters in
  spine order, extract text from each chapter's XHTML via
  `BeautifulSoup` (bundled dep of ebooklib) or stdlib `html.parser`,
  join with double newlines, tokenize.
- **DocxImporter** (`.docx`): uses `python-docx` to iterate paragraphs,
  join with double newlines, tokenize. Tables are flattened
  row-by-row; headers and footers are skipped.

Each new importer is one file in `importers/` and one line in
`registry.py`. The UI file dialog automatically picks up the new
extensions via `all_extensions()`.

---

## UI Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  essay.md              Recent | Stats        45%  │  300 wpm        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│                         interesting                                 │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│ [Open] [⏮][⏪][▶][⏩]   WPM: [-] 300 [+]    [🌙]                 │
└─────────────────────────────────────────────────────────────────────┘
```

"Recent" and "Stats" are compact text buttons in the status bar, or
icons if space is tight. The control bar grows by ~60 pixels to fit
the new transport buttons; window width increases proportionally.

Exact dimensions determined during implementation, but window remains
fixed-size in Phase 2. Resizability is a Phase 3 concern tied to the
context window.

---

## Build Order

Each step leaves the app in a runnable, shippable state.

1. **Tokenizer source offsets.** Add `source_start`/`source_end` to
   `Token`. Update `tokenize` to populate them. Update the existing
   `.txt` importer to return `(text, tokens)`. Update `MainWindow` to
   handle the new importer signature. Nothing user-visible yet.
2. **Session source storage + fingerprinting.** Add `source_text` and
   `source_hash` to `Session`. Update `progress.json` format with
   migration. Update `_load_progress_for` to compare hashes and call
   the prompt. Implement the file-changed prompt.
3. **Transport control buttons.** Add `Session.skip`. Wire up four
   buttons in the control bar. Add Right arrow shortcut. Implement
   restart confirmation dialog and `restart_confirm` config key.
4. **Stats infrastructure.** Add `storage/stats.py` mirroring
   `storage/progress.py`'s shape. Increment counters in `_tick` and
   the 100-token checkpoint. Nothing surfaced in UI yet.
5. **Markdown importer.** One file, one regex-based stripper, one
   line added to registry. Smallest of the three formats.
6. **DOCX importer.** Add dep to `requirements.txt`. Write importer.
   Document the dep change in README.
7. **EPUB importer.** Add dep. Write importer. Hardest of the three;
   leaving it last gives the most time with the new dep.
8. **Recents window.** Toplevel, listbox of files sorted by
   `last_opened`. Double-click to open.
9. **Stats window.** Toplevel, aggregate numbers. Small cosmetic
   polish.
10. **Docs.** README gets the requirements.txt section, updated
    roadmap (Phase 2 → in progress), close the unclosed fence in the
    Installation section.

Steps 1–4 are the core changes; 5–7 are the advertised "more formats"
headline; 8–9 are the "polish" half; 10 is cleanup. If time runs out,
stopping after step 7 still delivers a meaningfully better app.

---

## Persistence Behavior Changes

Everything in Phase 1's persistence section still applies. Additions:

- File hash is saved at every `progress.json` write, alongside position.
- Stats save at the 100-token checkpoint, on pause, and on close
  (same cadence as progress).
- `last_opened` timestamps update on successful file open, not on
  progress save.

---

## Open Questions

These don't block starting; flagging so they get decided consciously
during implementation rather than by accident:

- **Should restart reset stats for the current file?** Leaning no —
  "words read" is cumulative across sessions, and restarting to reread
  still counts as reading. But worth confirming.
- **Does changing WPM mid-file count as a "session"?** Probably not —
  a session starts on file open and ends on close. Increments once.
- **What happens when a file in the recents list is deleted or moved?**
  Leaning: on attempted open, show a one-line status message and
  remove from list. No prompt.
