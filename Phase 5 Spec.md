# Phase 5 Specification

**Status:** Not started
**Goal:** Optimize the RSVP reading experience with Optimal Recognition
Point alignment, variable timing based on word length and punctuation,
chunked display for function words, and punctuation-only token handling.
Phase 5 turns RSVPy from a uniform word-by-word flasher into a reader
that adapts its pacing and layout to the structure of the text.

This document defines scope, architecture decisions, and build order
for Phase 5. Anything not listed here is out of scope.

---

## Scope

### In scope

- Optimal Recognition Point (ORP) alignment in the reader view
- Variable timing based on token type (sentence end, paragraph end)
  and word length
- Punctuation-only token handling (new token type, reduced timing)
- Chunked display for short function words alongside content words
- ORP character highlighting in the accent color
- Settings panel additions for variable timing toggle and chunk
  display toggle

### Out of scope

- New file formats
- New importers or changes to the importer interface
- Changes to the AI summarization feature
- Packaging or distribution
- OCR, cloud sync, or mobile platforms
- Animated transitions between words

---

## Dependencies

### No new dependencies

Phase 5 is entirely internal to the display and timing logic. No
new packages are needed.

### Existing dependencies (unchanged)

- `python-docx>=1.1.0`
- `EbookLib>=0.18`
- `pdfplumber>=0.10.0`
- `anthropic>=0.40.0`
- `keyring>=25.0.0`

---

## Architectural Decisions

### ORP alignment: three-label layout

The current reader view is a single `tk.Label` centered in a frame.
ORP alignment requires positioning the word so a specific character
sits at a fixed focal column, rather than centering the whole word.

The recommended approach is a **three-label layout**:

```
          [pre_label][orp_label][post_label]
                         ^
                    fixed x position
```

- `pre_label`: characters before the ORP, right-aligned to the
  focal point.
- `orp_label`: the single ORP character, centered at the focal
  point and highlighted in the accent color.
- `post_label`: characters after the ORP, left-aligned from the
  focal point.

All three labels share the same font (the user's configured font
family and size from Phase 4). The ORP label is colored with the
theme's accent color; the other two use the standard text color.

The focal point is a fixed x-position at approximately 35–40% of the
reader view width. This mirrors the natural left-biased fixation
point of Western-language readers.

**Why not a Canvas?** A Canvas offers pixel-precise positioning but
complicates font handling, text rendering, and the existing
`update_font()` API from Phase 4. Three labels in a frame preserve
the Tkinter idiom used everywhere else in the app.

**Why not a single label with dynamic relx?** Computing `relx` from
font metrics is fragile in Tkinter — `font.measure()` can disagree
with actual rendered width, especially for proportional fonts. Three
labels avoid font measurement entirely; Tkinter handles the layout.

### ORP calculation

The ORP position within a word follows standard RSVP research:

| Word length | ORP position (0-indexed) |
|-------------|--------------------------|
| 1           | 0                        |
| 2–5         | 1                        |
| 6–9         | 2                        |
| 10–13       | 3                        |
| 14+         | 4                        |

This places the ORP roughly at the "left of center" of the word,
which is where skilled readers naturally fixate. The exact table
can be adjusted by testing, but this is the standard starting point.

The ORP is computed from the display text of the token. For chunked
display (function word + content word), the ORP is computed from the
content word only, and the function word is part of the pre-ORP
segment.

### Variable timing: multipliers on base delay

The current `delay_ms(wpm)` returns a flat `60000 / wpm` for every
token. Phase 5 extends this with multipliers:

```python
def delay_ms(wpm: int,
             token_type: TokenType | None = None,
             word_length: int | None = None) -> int:
```

**Token type multipliers:**
- `WORD`: 1.0× (no change)
- `SENTENCE_END`: 1.5×
- `PARAGRAPH_END`: 2.0×
- `PUNCTUATION_ONLY`: 0.3× (brief flash, not skipped entirely)

**Word length adjustment:**
- 1–3 characters: 0.85× (short words need less fixation time)
- 4–7 characters: 1.0× (baseline)
- 8–11 characters: 1.15×
- 12+ characters: 1.3×

The final delay is: `base_delay × type_multiplier × length_multiplier`.
Clamped to a minimum of 40ms to prevent imperceptible flashes even at
1000 WPM with short punctuation tokens.

The existing call sites that pass only `wpm` continue to work
unchanged because both new parameters default to `None`, which
means "use 1.0× multiplier."

### Punctuation-only tokens: new TokenType

Add `PUNCTUATION_ONLY` to the `TokenType` enum:

```python
class TokenType(Enum):
    WORD = "word"
    SENTENCE_END = "sentence_end"
    PARAGRAPH_END = "paragraph_end"
    PUNCTUATION_ONLY = "punctuation_only"
```

A token is `PUNCTUATION_ONLY` if it contains no alphanumeric
characters. Examples: `—`, `...`, `–`, `*`, `***`. The tokenizer
already splits on whitespace, so these appear as standalone tokens
when the source text has them spaced (e.g., `word — word`).

Detection: after the existing type assignment logic, add a check:
if the token text has no `[a-zA-Z0-9]` characters and the type is
`WORD`, override to `PUNCTUATION_ONLY`. This check runs after the
sentence-end and paragraph-end logic so that a period at the end of
a paragraph still gets `PARAGRAPH_END`, not `PUNCTUATION_ONLY`.

Token count, indices, and source offsets are **unchanged**. This is
critical — saved positions and progress percentages must remain valid
across the Phase 4 → Phase 5 transition.

### Chunked display: function word grouping

Short function words are grouped with the following content word for
display. Instead of showing "the" then "cat" as two separate flashes,
show "the cat" as a single display unit.

**Function word list** (hard-coded, English-only for Phase 5):

```python
FUNCTION_WORDS = frozenset({
    "a", "an", "the",
    "i", "me", "my", "we", "us", "our",
    "he", "she", "it", "his", "her", "its",
    "to", "of", "in", "on", "at", "by", "for",
    "is", "am", "are", "was", "be",
    "no", "not", "nor",
    "and", "but", "or", "so", "if",
    "as", "do",
})
```

**Grouping rules:**
- A function word is grouped with the **next** token if:
  - The next token exists and is not itself a function word
  - The next token is not a `PUNCTUATION_ONLY` token
  - The combined display length ≤ 20 characters (prevents absurd
    widths from long content words)
- A function word at the end of the stream is displayed alone.
- A function word followed by another function word is displayed
  alone (to avoid triple-word chunks).

**Implementation:** a display-time grouping pass, not a tokenizer
change. The token list remains unmodified. In `_tick()`, before
displaying the current token, check if it qualifies for chunking.
If so, advance the position by 2 instead of 1 and display both
words joined by a space.

This keeps the token stream, progress tracking, source offsets,
context window highlighting, and click-to-seek all working without
modification. The only changes are in `_tick()` and the reader view.

**ORP interaction:** when displaying a chunk like "the cat", the
ORP is calculated on the content word ("cat"), and the function word
is prepended to the pre-ORP segment. So the display would be:

```
         [the ca][t][ ]
                  ^
             ORP (accent)
```

### Settings additions

Two new toggles in the Reading section of the settings panel:

- **Variable timing:** checkbox, default on. When off, all tokens
  get the flat `60000 / wpm` delay regardless of type or length.
  Stored as `variable_timing` in config.
- **Chunk function words:** checkbox, default on. When off, every
  token is displayed individually. Stored as `chunk_display` in
  config.

ORP alignment has no toggle — it is always active once implemented.
Users who prefer centered display can be accommodated in a future
phase if demand exists, but for Phase 5, ORP is the default and only
mode.

---

## Data Structure Changes

### `TokenType` addition

```python
class TokenType(Enum):
    WORD = "word"
    SENTENCE_END = "sentence_end"
    PARAGRAPH_END = "paragraph_end"
    PUNCTUATION_ONLY = "punctuation_only"
```

### `config.json` additions

```json
{
  "variable_timing": true,
  "chunk_display": true
}
```

Both default to `true`. Stored alongside existing keys.

### No changes to Token fields, Session, progress, or stats

Token count and indices are unchanged. Source offsets are unchanged.
Saved positions remain valid.

---

## Features

### ORP alignment

The reader view displays each word positioned so the Optimal
Recognition Point character sits at a fixed focal column. The ORP
character is highlighted in the accent color. Characters before the
ORP are right-aligned to the focal point; characters after are
left-aligned from it.

The three-label layout replaces the single centered label:

```
Before:     [        interesting        ]    (centered)

After:      [     int][e][resting       ]    (ORP-aligned)
                       ^
                  accent color
```

The focal point is fixed at ~38% of the reader view width, providing
a slight left-of-center bias that matches natural reading fixation.

The ORP works with all fonts available in the Phase 4 settings panel.
`update_font()` applies to all three labels simultaneously.

### Variable timing

Tokens display for different durations based on their type and
length:

- **Sentence ends** (`.`, `!`, `?`) pause 50% longer, giving the
  reader time to process the end of a thought.
- **Paragraph ends** pause 100% longer, marking a clear structural
  break.
- **Short words** (1–3 chars) flash 15% faster — they're recognized
  in peripheral vision and need less fixation.
- **Long words** (12+ chars) linger 30% longer for adequate
  processing.
- **Punctuation-only tokens** flash at 30% of normal speed — visible
  but not disruptive.

Timing is configurable: the "Variable timing" toggle in settings
switches between adaptive timing (on) and flat timing (off). The
WPM stepper still controls the base rate; variable timing adjusts
around that base.

### Punctuation-only token handling

Standalone punctuation tokens (em-dashes, ellipses, etc.) are tagged
`PUNCTUATION_ONLY` by the tokenizer and receive a very short display
time via the variable timing system. This fixes the long-standing
issue where `—` would flash on screen for 200ms at 300 WPM, the
same duration as a real word.

When variable timing is disabled, punctuation-only tokens display at
the standard flat rate (matching Phase 4 behavior).

### Chunked display for function words

Common short function words are displayed alongside the following
content word as a single unit:

```
Without chunking:   "the" → "cat" → "sat" → "on" → "the" → "mat"
With chunking:      "the cat" → "sat" → "on the" → "mat"
```

The chunk counts as one display step for timing purposes. The delay
is based on the content word's length and type, not the function
word. Progress advances by 2 tokens per chunk.

Chunking is configurable via the "Chunk function words" toggle in
settings. When off, every token displays individually.

---

## UI Layout

### Reader view with ORP

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│                                                                      │
│                         int e resting                                │
│                             ^                                        │
│                        (accent color)                                │
│                                                                      │
├══════════════════════════════════════════════════════════════════════╤
```

A thin vertical guide line at the focal point (1px, muted color)
provides a persistent visual anchor. This line is always visible,
even when no word is displayed. Optional — implement if it aids
readability, omit if it feels cluttered.

### Chunked display with ORP

```
│                    the c a t                                         │
│                          ^                                           │
│                     (accent color, on content word ORP)              │
```

The function word is displayed in the standard text color, flush
against the content word. The ORP calculation ignores the function
word — it is positioned as a prefix.

### Settings additions

```
│  Reading                                 │
│  ─────────────────────────────────────   │
│  [✓] Confirm before restarting           │
│  [✓] Variable timing                     │
│  [✓] Chunk function words                │
```

Two checkboxes added below the existing restart confirmation toggle.

---

## Keyboard Shortcuts

No new shortcuts in Phase 5. All existing shortcuts remain unchanged.

---

## Build Order

Each step leaves the app in a runnable, shippable state.

1. **Punctuation-only token type.** Add `PUNCTUATION_ONLY` to
   `TokenType`. Update `tokenize()` to detect tokens with no
   alphanumeric characters and tag them. No display or timing changes
   yet — this is a data model addition. Verify with a test text
   containing spaced em-dashes and ellipses that the tokens are
   correctly tagged.

2. **Variable timing.** Extend `delay_ms()` with optional
   `token_type` and `word_length` parameters. Define the multiplier
   tables. Update `_tick()` in `main_window.py` to pass the current
   token's type and word length. Add `variable_timing` config key
   and settings checkbox. Test at various WPM values — the reading
   should feel noticeably more natural with pauses at sentence and
   paragraph boundaries.

3. **ORP alignment.** Redesign `ReaderView` from a single label to
   the three-label layout. Implement the ORP position lookup table.
   Wire accent color to the ORP label. Ensure `update_font()` and
   `apply_theme()` still work correctly. Ensure `show()` and
   `clear()` maintain their existing call signatures so
   `main_window.py` needs no changes beyond the reader view itself.

4. **Chunked display.** Define the function word set. Implement the
   grouping check in `_tick()`. When chunking, advance position by 2
   and display both words joined by a space. Compute ORP on the
   content word with the function word as a prefix. Add
   `chunk_display` config key and settings checkbox. Edge cases:
   function word at end of stream, two consecutive function words,
   chunk exceeding 20 characters.

5. **Polish and docs.** README update (Phase 5 status, new features).
   Test with real documents — prose, technical writing, PDF extracts,
   EPUBs. Verify that progress tracking, context window highlighting,
   click-to-seek, and save/resume all work correctly with the new
   timing and display logic. Confirm that disabling both toggles
   restores exact Phase 4 behavior.

Steps 1–2 are low-risk and immediately improve the reading experience.
Step 3 is the most visible change. Step 4 is the most complex and
could be deferred to a later iteration if the first three steps
already deliver a substantially better reading experience.

---

## Persistence Behavior Changes

Everything from Phases 1–4 still applies. Additions:

- `variable_timing` and `chunk_display` booleans saved to config on
  change and on close.
- No changes to progress or stats persistence. Token counts and
  positions are unchanged despite the new timing and display logic.

---

## Migration

### Token stream compatibility

Phase 5 adds a new `TokenType` value but does not change token
indices, source offsets, or token count. A file whose position was
saved at token 847 in Phase 4 will resume at token 847 in Phase 5 —
the same word, at the same source offset, with the same progress
percentage. No migration logic is needed.

### Config compatibility

New keys (`variable_timing`, `chunk_display`) are added to
`DEFAULT_CONFIG` and merged on load, so existing config files from
Phase 4 get the new defaults automatically. No migration needed.

---

## Open Questions

These don't block starting; decide during implementation:

- **Should the ORP guide line be visible?** A thin vertical line at
  the focal point helps the eye lock onto the right position. But it
  might feel cluttered. Try it and decide visually. Leaning yes.
- **Should function word chunking work for non-English languages?**
  Phase 5 targets English only. The function word list is hard-coded.
  Internationalization can be added later with locale-specific lists.
- **Should the timing multipliers be user-configurable?** Leaning no
  for Phase 5 — the presets should be tuned by testing. If users
  request customization, it can be added to the settings panel later
  with a "Timing" section and sliders.
- **How should ORP interact with very long words (20+ chars)?** The
  ORP position caps at index 4. For a 25-character word, this still
  puts the fixation near the left side, which is correct for reading.
  No special handling needed.
- **Should chunked display affect the stats `tokens_read` counter?**
  Leaning: count each token individually, so a chunk increments by 2.
  "Tokens read" measures how much of the document was consumed, not
  how many display flashes occurred.
