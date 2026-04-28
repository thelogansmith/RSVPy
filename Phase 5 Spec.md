# Phase 5 Specification

**Status:** Completed
**Goal:** Optimize the RSVP reading experience with Optimal Recognition
Point alignment, variable timing based on word length and punctuation,
and punctuation-only token handling. Phase 5 turns RSVPy from a uniform
word-by-word flasher into a reader that adapts its pacing and layout
to the structure of the text.

This document defines scope, architecture decisions, and build order
for Phase 5. Anything not listed here is out of scope.

---

## Scope

### In scope

- Optimal Recognition Point (ORP) alignment in the reader view
- Variable timing based on token type (sentence end, paragraph end)
  and word length
- Punctuation-only token handling (new token type, reduced timing)
- ORP character highlighting in the accent color
- Settings panel additions for variable timing toggle

### Removed during development

- **Chunked display for short function words.** Implemented and
  tested; removed before Phase 5 was marked complete. Function words
  flashed too fast to register as part of the chunk, and the variable
  display widths interfered with ORP alignment. The original design
  is preserved further down in this document for the record.

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

The focal point is a fixed x-position at the configured ORP_RELX
fraction of the reader view width. The implementation uses 0.50
(true center). Earlier drafts targeted ~38% (left-of-center), which
mirrors natural Western fixation, but center alignment proved more
robust against layout drift across font sizes.

**Why not a Canvas?** A Canvas offers pixel-precise positioning but
complicates font handling, text rendering, and the existing
`update_font()` API from Phase 4. Three labels in a frame preserve
the Tkinter idiom used everywhere else in the app.

**Why not a single label with dynamic relx?** Computing `relx` from
font metrics is fragile in Tkinter — `font.measure()` can disagree
with actual rendered width, especially for proportional fonts. Three
labels avoid font measurement entirely; Tkinter handles the layout.

### ORP calculation

The ORP position within a word is computed from word length. The
implementation uses a simple formula: position 0 for words of 3 or
fewer characters, and `max(1, len // 3 - 1)` for longer words. This
places the ORP roughly at the "left of center" of the word, which is
where skilled readers naturally fixate.

```python
def _orp_index(word: str) -> int:
    n = len(word)
    if n <= 3:
        return 0
    return max(1, n // 3 - 1)
```

The formula was chosen over a fixed lookup table because it's simpler
to maintain, gives nearly identical results across the relevant range,
and degrades gracefully for very long words without a special case.

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
- `PARAGRAPH_END`: 2.5×
- `PUNCTUATION_ONLY`: 0.25× with a 50ms floor (brief flash, not
  skipped entirely)

**Word length adjustment:**
- 1–3 characters: 0.85× (short words need less fixation time)
- 7+ characters: 1.0× + 4% per character beyond 6 (longer words
  linger proportionally)
- 4–6 characters: 1.0× (baseline)

The final delay is `base_delay × type_multiplier × length_multiplier`.
Token-type multipliers for SENTENCE_END and PARAGRAPH_END take
precedence over word-length adjustment; those pauses are about
comprehension rhythm, not word complexity.

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

### Chunked display: function word grouping (REMOVED)

> **Status: Removed.** Implemented and tested during Phase 5
> development; removed before Phase 5 was marked complete. Two
> observed problems: function words flashed too fast to register as
> part of the chunk, and the variable display widths interfered with
> ORP alignment. The design is preserved below as a record of what
> was attempted and why it didn't work.

Short function words were going to be displayed alongside the
following content word for display. Instead of showing "the" then
"cat" as two separate flashes, show "the cat" as a single display
unit.

**Function word list** (hard-coded, English-only):

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

**Grouping rules (as designed):**
- A function word is grouped with the **next** token if:
  - The next token exists and is not itself a function word
  - The next token is not a `PUNCTUATION_ONLY` token
  - The combined display length ≤ 20 characters
- A function word at the end of the stream is displayed alone.
- A function word followed by another function word is displayed
  alone.

The grouping was implemented as a display-time pass in `_tick()`
rather than a tokenizer change, so the token stream, progress
tracking, source offsets, context window highlighting, and
click-to-seek all worked without modification. The reading
experience is what failed: the function word effectively became
invisible at any meaningful WPM, and the wider chunks pulled the
ORP character off its anchor more than the alignment system could
absorb gracefully.

### Settings additions

One new toggle in the Reading section of the settings panel:

- **Variable timing:** checkbox, default on. When off, all tokens
  get the flat `60000 / wpm` delay regardless of type or length.
  Stored as `variable_timing` in config.

ORP alignment has no toggle — it is always active.

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
  "variable_timing": true
}
```

Defaults to `true`. Stored alongside existing keys.

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

The ORP works with all fonts available in the Phase 4 settings panel.
`update_font()` applies to all three labels simultaneously.

### Variable timing

Tokens display for different durations based on their type and
length:

- **Sentence ends** (`.`, `!`, `?`) pause 50% longer, giving the
  reader time to process the end of a thought.
- **Paragraph ends** pause 150% longer, marking a clear structural
  break.
- **Short words** (1–3 chars) flash 15% faster — they're recognized
  in peripheral vision and need less fixation.
- **Long words** (7+ chars) linger proportionally longer (4% per
  character beyond 6) for adequate processing.
- **Punctuation-only tokens** flash at 25% of normal speed (with a
  50ms floor) — visible but not disruptive.

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

A thin vertical guide line (the tick marks above and below the focal
point) provides a persistent visual anchor at the ORP column.

### Settings additions

```
│  Reading                                 │
│  ─────────────────────────────────────   │
│  [✓] Confirm before restarting           │
│  [✓] Variable timing                     │
```

One checkbox added below the existing restart confirmation toggle.

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
   the three-label layout. Implement the ORP position formula. Wire
   accent color to the ORP label. Ensure `update_font()` and
   `apply_theme()` still work correctly. Ensure `show()` and
   `clear()` maintain their existing call signatures so
   `main_window.py` needs no changes beyond the reader view itself.

4. **Polish and docs.** README update (Phase 5 status, new features).
   Test with real documents — prose, technical writing, PDF extracts,
   EPUBs. Verify that progress tracking, context window highlighting,
   click-to-seek, and save/resume all work correctly with the new
   timing and display logic. Confirm that disabling the variable
   timing toggle restores exact Phase 4 behavior.

A fifth step — chunked function-word display — was attempted but
removed; see the Removed section above.

---

## Persistence Behavior Changes

Everything from Phases 1–4 still applies. Additions:

- `variable_timing` boolean saved to config on change and on close.
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

The new key (`variable_timing`) is added to `DEFAULT_CONFIG` and
merged on load, so existing config files from Phase 4 get the new
default automatically. No migration needed.
