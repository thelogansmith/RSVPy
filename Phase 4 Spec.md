# Phase 4 Specification

**Status:** Not started
**Goal:** Add optional AI-powered post-session summaries, a settings
panel for customizing the reading experience, and a design overhaul
of the transport controls. Phase 4 transforms RSVPy from a functional
reader into a polished, personalized tool.

This document defines scope, architecture decisions, and build order
for Phase 4. Anything not listed here is out of scope.

---

## Scope

### In scope

- Settings panel (Toplevel window) for user preferences
- Configurable font family, font size, and accent color
- Transport button label / design overhaul
- Re-enable "don't ask again" choices via settings panel
- Optional AI-generated post-session summaries using a user-supplied
  API key
- Hierarchical summarization for long documents (chunked approach)
- API key management (entry, storage, validation)
- Summary display in a dedicated view

### Out of scope

- ORP alignment (Phase 5)
- Variable timing based on word length and punctuation (Phase 5)
- Chunked display for function words (Phase 5)
- Punctuation-only token handling (Phase 5)
- OCR or image-based text extraction
- Cloud sync or account systems
- Packaging or distribution

---

## Dependencies

### New dependency

- `anthropic>=0.40.0` — Anthropic Python SDK for Claude API calls.
  Used for post-session summarization. The dependency is optional at
  runtime: if the user has not configured an API key, all AI features
  are hidden or gracefully disabled. The SDK is always listed in
  `requirements.txt` for install simplicity.

### Alternative: OpenAI SDK

If the developer prefers OpenAI over Anthropic, swap `anthropic` for
`openai>=1.0.0`. The summarization module should abstract the API
behind a thin wrapper so switching providers is a one-file change.
Decide at implementation time.

### Existing dependencies (unchanged)

- `python-docx>=1.1.0`
- `EbookLib>=0.18`
- `pdfplumber>=0.10.0`

---

## Architectural Decisions

### Settings panel: separate Toplevel

A `Toplevel` window opened from a "Settings" button (replacing or
alongside the theme toggle). Contains all user-facing preferences in
one place. Changes apply immediately (live preview) and are persisted
to `config.json` on close or on change.

This replaces the scattered config touch points (theme toggle button,
WPM stepper, "don't ask again" checkbox) with a unified UI. The
existing controls remain for quick access — settings is the
comprehensive view.

### AI summarization: opt-in, local API key

The AI feature is entirely opt-in:

- No API key configured → no AI UI elements shown (or shown as
  disabled with a hint to configure in settings)
- API key is stored in `config.json` (not ideal for production, but
  acceptable for a personal desktop app with no cloud component)
- All API calls run on a background thread using the existing
  threading pattern from Phase 3
- Summaries are not persisted to disk (generated fresh each time)
- No data leaves the machine except to the configured API endpoint

### Summarization strategy: chunked for long documents

Short documents (under ~4000 tokens) get a single summarization call.
Long documents use hierarchical summarization:

1. Split the canonical text into chunks (~3000–4000 words each)
2. Summarize each chunk individually
3. Combine chunk summaries into a final summary with one more call

This keeps each API call within context limits and produces coherent
summaries for book-length content. The chunk size is configurable in
code but not exposed to the user.

### Button label overhaul

The developer has explicitly flagged "⏮ Start" and "⏪ Back" as
unsatisfying. Phase 4 redesigns the transport buttons:

- Cleaner, shorter labels or icon-only buttons
- Consistent visual weight across all four buttons
- Tooltip text on hover for discoverability
- Exact labels decided during implementation — candidates include
  icon-only (⏮ ⏪ ▶ ⏩), short text ("Start", "Back", "Play",
  "Skip"), or a hybrid

---

## Data Structure Changes

### `config.json` additions

```json
{
  "wpm": 300,
  "dark_mode": true,
  "restart_confirm": true,
  "context_window_open": false,
  "main_window_geometry": "700x300+100+200",
  "font_family": "Helvetica",
  "font_size": 36,
  "accent_color": null,
  "api_key": "",
  "api_provider": "anthropic",
  "summary_enabled": true,
  "summary_auto_prompt": false
}
```

- `font_family`: display font for the reader view. Default matches
  current ReaderView.FONT_FAMILY.
- `font_size`: display font size for the reader view. Default 36.
- `accent_color`: override for the theme's accent color. Null means
  use the theme default.
- `api_key`: user-supplied API key. Empty string means not configured.
- `api_provider`: "anthropic" or "openai". Determines which SDK and
  endpoint to use.
- `summary_enabled`: master toggle for AI features.
- `summary_auto_prompt`: if true, automatically prompt for a summary
  when the user finishes a document. If false, summary is manual only.

### No changes to Token, Session, or progress/stats

The data model is stable. Summaries are transient (not persisted).

---

## Features

### Settings panel

A `Toplevel` window (`ui/settings_window.py`) with sections:

**Display**
- Font family: dropdown or entry field with common options
  (Helvetica, Arial, Consolas, Georgia, Times New Roman, system
  default). Applies to the reader view only — context window keeps
  its own font.
- Font size: slider or stepper, range 18–72, default 36.
- Accent color: color picker or predefined palette. Affects the
  progress bar fill, context window highlight, and any future
  accent-colored UI.

**Reading**
- WPM: slider showing current value (mirrors the control bar stepper)
- Restart confirmation: checkbox to re-enable the "are you sure?"
  prompt. This is the "undo" for the Phase 2 "don't ask again"
  checkbox.

**AI Summarization**
- API key: masked entry field with show/hide toggle
- Provider: radio buttons for Anthropic / OpenAI
- Auto-prompt: checkbox ("Offer summary when I finish a document")
- "Test connection" button that makes a minimal API call to verify
  the key works

**About**
- App version, phase, link to repo

Changes apply immediately where possible (font size, accent color).
API key changes apply on next summary request.

### Transport button overhaul

Replace the current four transport buttons with cleaner styling:

- **Labels:** shorter or icon-only. Suggested: "⏮", "⏪", "▶ Play",
  "⏩" — only the play/pause button gets a text label because its
  state changes. The others are recognizable as icons.
- **Tooltips:** hover text on each button explaining the action and
  keyboard shortcut ("Restart from beginning (Home)").
- **Visual consistency:** all buttons same width, flat relief, themed
  colors matching the rest of the app.

The exact labels should be discussed with the developer during
implementation — they've had opinions about this since Phase 2.

### AI post-session summaries

**Trigger:**
- Manual: a "Summarize" button appears in the status bar (or control
  bar) when a file is loaded and the API key is configured.
- Automatic: if `summary_auto_prompt` is true and the user reaches
  the end of the document, a prompt appears: "You've finished!
  Would you like a summary?" with Yes/No buttons.

**Generation:**
- Runs on a background thread using the Phase 3 threading pattern.
- The reader view (or a separate summary Toplevel) shows
  "Generating summary..." during the API call.
- On success: display the summary in a scrollable text view.
- On error: show a brief error message, log details to console.

**Summary content:**
- The prompt asks for a concise summary of the document, including
  key points and themes.
- For short documents (~4000 words or less): single API call with the
  full canonical text.
- For long documents: hierarchical chunked summarization (see
  Architectural Decisions).

**Display:**
- A `Toplevel` or panel showing the formatted summary.
- Themed to match the app.
- Copy-to-clipboard button.
- Option to regenerate.

### Hierarchical summarization

For documents exceeding ~4000 words:

1. Split `session.source_text` into chunks of ~3000–4000 words at
   paragraph boundaries (never mid-sentence).
2. Summarize each chunk with a prompt like: "Summarize the following
   section of a document concisely, preserving key points."
3. Concatenate all chunk summaries.
4. Final summary call: "The following are summaries of consecutive
   sections of a document. Produce a single cohesive summary."

Progress indication: "Summarizing section 2 of 5..." updates in the
UI as each chunk completes.

---

## UI Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│  essay.pdf    Context | Recent | Stats | ⚙    45%  │  300 wpm      │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│                                                                      │
│                          interesting                                 │
│                                                                      │
│                                                                      │
├══════════════════════════════════════════════════════════════════════╤
│ ████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
├──────────────────────────────────────────────────────────────────────┤
│ [Open] [⏮][⏪][▶ Play][⏩]  [Summarize]   WPM: [-] 300 [+]     [🌙] │
└──────────────────────────────────────────────────────────────────────┘
```

The settings gear icon (⚙) sits in the status bar. "Summarize" button
appears in the control bar when an API key is configured and a file is
loaded.

### Settings window

```
┌──────────────────────────────────────────┐
│  Settings                                │
├──────────────────────────────────────────┤
│                                          │
│  Display                                 │
│  Font:     [Helvetica        ▾]          │
│  Size:     [--- 36 ---]                  │
│  Accent:   [●●●●●●] (color swatches)    │
│                                          │
│  Reading                                 │
│  [✓] Confirm before restarting           │
│                                          │
│  AI Summarization                        │
│  Provider:  (●) Anthropic  ( ) OpenAI    │
│  API Key:   [••••••••••••] [👁]           │
│  [Test connection]                       │
│  [✓] Offer summary when I finish         │
│                                          │
│                            [Close]       │
└──────────────────────────────────────────┘
```

### Summary window

```
┌──────────────────────────────────────────┐
│  Summary — essay.pdf                     │
├──────────────────────────────────────────┤
│                                          │
│  This document discusses the evolution   │
│  of security operations centers and      │
│  their role in modern cybersecurity...   │
│                                          │
│                                          │
│            [Copy] [Regenerate] [Close]   │
└──────────────────────────────────────────┘
```

---

## Keyboard Shortcuts (additions)

| Key       | Action                         |
|-----------|--------------------------------|
| `Ctrl+,`  | Open settings                  |

All existing shortcuts remain unchanged.

---

## Build Order

Each step leaves the app in a runnable, shippable state.

1. **Transport button overhaul.** Redesign the four transport buttons
   with cleaner labels. Add tooltip support (Tk doesn't have native
   tooltips — implement a small helper or use `<Enter>`/`<Leave>`
   bindings to show a floating label). This is a visual-only change
   with no new logic. Discuss label options with the developer.

2. **Settings panel — display section.** Create
   `ui/settings_window.py` with font family, font size, and accent
   color controls. Wire changes to `reader_view`, `theme`, and
   `config.json`. Live preview. Gear icon or "Settings" button in
   status bar. Ctrl+, shortcut.

3. **Settings panel — reading section.** Add the restart confirmation
   re-enable checkbox. Wire to `_restart_confirm` and config.

4. **Settings panel — AI section (UI only).** Add provider selector,
   API key entry, test connection button, auto-prompt checkbox. Wire
   to config. No actual API calls yet — this is the settings UI.

5. **AI summarization module.** Create a summarization module
   (e.g. `core/summarizer.py`) that handles API calls, chunking,
   and hierarchical summarization. Abstract behind a clean interface
   so the provider can be swapped later. Test with a simple call.

6. **Summary trigger and display.** Add "Summarize" button to the
   control bar (visible only when API key is configured). Wire to
   the summarization module via the threaded loading pattern.
   Create the summary display window. Handle progress updates for
   chunked summarization.

7. **Auto-prompt on finish.** When playback reaches the end and
   `summary_auto_prompt` is true, show a prompt offering to
   generate a summary. Wire to the same summarization flow.

8. **Polish and docs.** README update (Phase 4 status, new dep,
   new shortcuts, AI feature description). Verify all features work
   together. Edge cases: empty API key, invalid API key, network
   errors, very long documents, rapid settings changes.

Steps 1-4 are the settings/UI overhaul. Steps 5-7 are the AI
feature. Step 8 is cleanup. If time runs short, stopping after
step 4 still delivers a meaningfully better app with the settings
panel and button overhaul.

---

## Persistence Behavior Changes

Everything from Phases 1–3 still applies. Additions:

- Font family, font size, and accent color saved to config on change
  and on close.
- API key saved to config on entry (consider whether to save on
  every keystroke or on focus-out / close).
- Summary preferences (auto-prompt, provider) saved to config on
  change.
- Summaries themselves are **not** persisted to disk.

---

## Open Questions

These don't block starting; decide during implementation:

- **Should the API key be stored in config.json or a separate
  secrets file?** config.json is simplest and consistent with the
  app's approach. A separate file would allow different permissions
  but adds complexity. Leaning config.json for Phase 4.
- **Should summaries be cached to disk?** Leaning no — they're
  cheap to regenerate, and caching adds staleness concerns. But
  if generation is slow (large documents), caching could improve UX.
- **What model to use?** For Anthropic: `claude-sonnet-4-20250514` is
  a good balance of quality and speed. For OpenAI: `gpt-4o-mini` for
  cost efficiency. Make configurable if time permits.
- **Should the summary window replace the context window or coexist?**
  Leaning coexist — they serve different purposes (navigation vs.
  comprehension). But screen real estate is a concern.
- **Exact transport button labels?** The developer should choose.
  Present 2-3 options and let them pick.
