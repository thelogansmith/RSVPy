What is rapid serial presentation?
7:16 PM

Rapid serial visual presentation (RSVP) is a technique where words, images, or other stimuli are displayed one at a time in quick succession at a fixed location on a screen, rather than being read or scanned spatially.

In reading applications, RSVP flashes individual words (or short chunks) at the same spot, typically at rates of 200–1000 words per minute. Because your eyes don't have to move across a page—saccades and fixations take up a surprising amount of normal reading time—proponents argue you can read faster. Apps like Spritz, Spreeder, and various "speed reading" tools use this approach.

In cognitive psychology research, RSVP is a workhorse paradigm for studying attention and perception. It's most famous for revealing the attentional blink: if you're shown a stream of letters and asked to spot two targets, you'll reliably miss the second one if it appears roughly 200–500 milliseconds after the first, even though you caught it easily at other intervals. This suggests attention has a brief refractory period after locking onto something. RSVP is also used to study word recognition, visual working memory, and subliminal processing.

The tradeoff in reading contexts is comprehension. Normal reading involves regressions (glancing back) and variable fixation times on harder words, which RSVP eliminates by design. For light material this may not matter much, but for dense or technical text, forced-pace word-by-word presentation tends to hurt understanding and retention.

Are these apps free?
7:16 PM

It varies by app. Here's a quick rundown of the common ones:

Spritz — Not a standalone consumer app anymore; it's mainly licensed as a technology to other apps and e-readers. You'll encounter it embedded in third-party products rather than downloading "Spritz" directly.

Spreeder — Has a free web version with basic functionality. Spreeder CX (the fuller product with training courses, import tools, and progress tracking) is paid, typically via subscription or one-time purchase.

Reedy (browser extension and Android app) — Free, and one of the more popular no-cost options.

Spreed (Chrome extension) — Free.

Outread, ReadMe!, Acceleread — Mix of free tiers with paid upgrades, or one-time purchase apps in the $3–10 range.

Readsy — Free web-based tool, very minimal.

If you just want to try RSVP to see whether it works for you, the free options (Reedy, Spreed, Readsy, or Spreeder's free web version) are more than enough. The paid apps mostly add things like PDF/ePub import, syncing across devices, comprehension drills, and progress tracking—useful if you decide to stick with it, but not necessary to evaluate the technique.

One caveat: the speed-reading app space has churned a lot over the years, with apps getting abandoned, acquired, or pulled from stores. If you want, I can check what's currently available and active.

What would it be like to develop one?
I would think you need an input section for text either directly in a text box or a file. Then you would set a WPM, then you could initiate it and it could count done and begin listing the words at a specific focal point on the word until the queue is finished.
7:19 PM

You've actually sketched the core architecture pretty accurately. Building a basic RSVP reader is a genuinely approachable project—probably a weekend for a working version, longer if you want to polish it. Let me walk through what's involved and where the interesting challenges hide.

The skeleton you described is right: input → tokenize → timer loop → display. The naive implementation is maybe 50 lines of JavaScript. You split the text on whitespace, set an interval based on 60000 / wpm milliseconds, and swap words into a div. Done.

But a few things get interesting once you start actually using it:

The Optimal Recognition Point (ORP). You mentioned a "specific focal point on the word"—this is the real design insight behind Spritz and why their presentation felt smoother than earlier RSVP tools. Your eye doesn't fixate on the center of a word; it lands slightly left of center, on a specific letter that varies by word length (roughly: 1st letter for 1-letter words, 2nd for 2–5 letters, 3rd for 6–9, 4th for 10–13, etc.). If you horizontally align every word so that the ORP letter sits at the same pixel position—often highlighted in red—your eye never has to move. Without this, longer words force micro-saccades and the whole "no eye movement" premise breaks down. Spritz actually patented their specific algorithm, but the general technique is well-documented and you can implement your own variation.

Variable timing. Fixed WPM feels robotic. Real readers slow down on long words, punctuation, and sentence boundaries. A common trick: give longer words extra time (e.g., +50ms per character over 8), and add a pause after periods, commas, and paragraph breaks. This dramatically improves comprehension.

Chunking decisions. Do you show one word at a time, or two or three? Short function words ("of," "the," "in") can be paired with adjacent words without losing clarity, and this helps at higher speeds. This is a rabbit hole—some apps try to parse phrases.

Controls that matter. Pause/resume is obvious, but the non-obvious ones are: rewind by a few words (you will zone out), jump back to sentence start, and a speed slider you can adjust mid-stream. Also a progress indicator—knowing you're 40% through a chapter matters psychologically.

File input. Plain text and pasted text are trivial. PDFs are a pain (use pdf.js in the browser or pypdf/pdfplumber in Python, and expect messy output). EPUB is structured XML inside a zip, very doable with a library. Web articles are best handled by grabbing the URL and running something like Mozilla's Readability.js to strip boilerplate.

Stack choice. For a personal tool, a single HTML file with vanilla JS is the fastest path—no build tools, no server, just open it in a browser. If you want it on your phone, a web app still works (add it to home screen), or you go React Native / Flutter. Python with Tkinter works but feels dated; Python with a web frontend (Flask + JS) is fine if you want server-side file parsing.

If you want, I could actually build you a working prototype right now—a single-file HTML artifact with text input, WPM control, ORP alignment, and variable timing. It'd be a decent starting point you could extend. Want me to do that?

I would like to flesh this out more prior to starting anything. The goals would be to read more, pretty simple but just generally I would like to read more content. I think this will also help with my school work and extended education.

Ideally this would be a desktop app.
It would need to be able to grab text from multiple different types of text files, especially pdfs. I don't know if this should be in the form of a conversion or how that would like precisely yet. I know most official pdf sources allow for relatively easy word recognition but when it comes to images that will require much more work.
There will need to be customization for the reading window, colors/fonts/sizes/etc.
Before optimizing the word recognition with longer words I feel that may be a later integration.
There could also be an AI integration with a summary to reinforce what was learned.
7:24 PM

This is a solid foundation. Your goals are clear, the scope is reasonable, and you're already thinking about phasing (deferring ORP optimization is smart—it's a polish feature, not a core one). Let me help you think through the architecture and surface some decisions you'll want to make before writing code.
Stack choice for a desktop app

Since this is desktop-first with file handling, you have three realistic paths:

Electron (JavaScript/TypeScript + Chromium). Pros: massive ecosystem, easy UI with React/Vue/Svelte, pdf.js works beautifully, cross-platform for free. Cons: heavy (100MB+ install), RAM-hungry. If you already know web tech, this is the fastest path.

Tauri (Rust backend + web frontend). Pros: tiny binaries (~10MB), fast, more secure, same web-frontend flexibility as Electron. Cons: Rust learning curve if you don't know it, smaller ecosystem, PDF handling requires more plumbing.

Python + PyQt/PySide or Tkinter. Pros: excellent PDF libraries (pdfplumber, PyMuPDF), great for AI integration since most ML tooling is Python-native, simple to prototype. Cons: packaging for distribution is annoying (PyInstaller works but is fiddly), UI feels less modern unless you invest effort.

My honest take: Electron or Tauri with a web frontend is probably the right call for this specific app. The reading experience is fundamentally a UI problem—typography, animation, controls—and web tech is unmatched for that. Python is tempting for the AI/PDF side, but you can call Python as a subprocess or use JS equivalents.
PDF handling—the real complexity

This is where your project gets genuinely hard. PDFs fall into three categories:

    Text-based PDFs (born-digital, like most academic papers from publishers). Text is extractable directly. Libraries like pdf.js, PyMuPDF, or pdfplumber handle these well, though layout reconstruction (columns, footnotes, headers) is tricky. A two-column paper naively extracted reads as: left column line 1, right column line 1, left column line 2... you need layout-aware extraction.
    Scanned PDFs (images of pages). Require OCR. Tesseract is the free standard; it's decent but not great. Cloud OCR (Google Vision, AWS Textract, Azure) is significantly better but costs money and sends data externally. For school use this might matter—some textbook scans are rough.
    Hybrid/messy PDFs (has text layer but it's garbage, or mix of both). These are the worst. You often don't know which category you're dealing with until extraction fails.

Design decision to make now: do you want a one-click "just open this PDF and start reading" flow, or an explicit "import → preview extracted text → clean up → start reading" flow? The first is nicer UX but will sometimes produce garbled streams. The second is more honest about PDF messiness and lets users fix obvious problems before a 40-minute reading session. I'd lean toward the second with a "quick start" option for known-good PDFs.
File format priorities

Rough order of difficulty/value:

    .txt — trivial, do first
    .md — trivial, strip formatting
    .epub — straightforward (it's HTML in a zip), high value for books
    .docx — easy with libraries (mammoth.js, python-docx)
    .html / web articles — use a readability extractor (Readability.js, trafilatura in Python)
    .pdf (text-based) — medium, most of the work
    .pdf (scanned/OCR) — hard, save for later

I'd suggest getting txt/md/epub/docx working first (they're all quick wins) before tackling PDF. This also gives you something usable sooner.
Customization layer

Standard things to expose: font family (include a dyslexia-friendly option like OpenDyslexic or Atkinson Hyperlegible), font size, font weight, text color, background color (dark mode matters for long sessions), window size, and—importantly—a few preset themes so users don't have to tune every variable. "Sepia," "dark," "high contrast," "paper" covers most preferences.

One thing worth adding to your list: position of the reading window on screen. Some users want fullscreen, some want a small floating window they can put next to other work. This matters more than it sounds.
AI summary integration

A few ways to structure this, in increasing ambition:

    Post-session summary. After reading, generate a summary of what was just read. Simple, useful, low-risk.
    Chunked summaries. Break long texts into sections (chapters, or every N words), summarize each. Better for retention on long material.
    Active recall prompts. Generate 3–5 questions about the content, quiz the user. This is pedagogically the strongest option—testing beats re-reading for retention, well-established in learning science.
    Pre-reading preview. Generate a brief "here's what you're about to read" orientation before starting. Helps with comprehension.

For the API, you have options: Anthropic (Claude), OpenAI, or local models via Ollama. Local models are appealing for privacy and cost (school readings are a lot of tokens) but quality varies. A reasonable architecture: abstract the AI calls behind an interface so you can swap providers, and let the user bring their own API key.

Consideration: long documents exceed context windows. You'll need to chunk and either summarize hierarchically (summarize sections, then summarize the summaries) or use retrieval (store chunks, pull relevant ones for questions). Hierarchical summarization is simpler and fine for v1.
Things not on your list worth considering

    Session persistence. If you're 30% through a 200-page PDF, the app must remember where you were. This is table stakes for any reading app but easy to forget until you've lost your place once.
    Library/recent files. A list of what you've imported, progress on each.
    Reading statistics. Words read, time spent, average WPM. Motivating if your goal is "read more."
    Keyboard shortcuts. Space to pause, arrows to adjust speed, R to rewind. Critical—you don't want to reach for the mouse every time your attention wanders.
    Highlight/bookmark. Mark a passage to revisit. Hard to do mid-RSVP but valuable.

Suggested phasing

Phase 1 (MVP): Electron or Tauri shell, text/markdown input, basic RSVP display, WPM control, pause/resume/rewind, minimal customization (font size, dark mode), session persistence. Goal: you can actually use it to read something.

Phase 2: EPUB and DOCX support, proper theming/customization, keyboard shortcuts, library view, reading stats.

Phase 3: PDF support (text-based first), with a preview-and-clean step.

Phase 4: AI summaries and/or quiz generation.

Phase 5: OCR for scanned PDFs, ORP optimization, variable timing, chunked display.

Each phase gives you something useful; you don't lose motivation waiting for the "real" version.

Want to dig into any of these in more depth? The stack choice and the PDF import UX are probably the two decisions that will shape the most downstream work, so those might be worth firming up first.

I would like something that is extremely efficient and lightweight. It doesn't need to be perfect but something that is akin to the early 2000s where resources are at a premium. It would be nice to go cross platform as well, python is pretty ubiquitous in that regard. I would like to avoid OCR and image based stuff until the very end. That seems like a luxury I'm not interested in humoring until I have to especially when it caters to a lot of pirated content.
7:35 PM

Good instincts. The "early 2000s resource budget" framing is actually a useful design constraint—it'll force decisions that keep the app fast and focused. And your reasoning on OCR is sound; it's a huge complexity tax for a use case you're explicitly not trying to serve.

Let me recalibrate based on these constraints.
Stack reconsidered

With lightweight + cross-platform + Python on the table, your realistic options are:

Python + Tkinter. Ships with Python, zero extra dependencies for the GUI, runs on Windows/Mac/Linux identically. Ugly by default but very tunable with ttk themes. Memory footprint is tiny—we're talking 30–50MB for a running app. This is the closest thing to your early-2000s aesthetic goal.

Python + PyQt6/PySide6. Much prettier and more capable, but Qt is a large dependency (~40MB just for the Qt libs) and packaging gets heavier. Still lightweight compared to Electron, but not featherweight.

Python + Dear PyGui or Toga. Smaller/newer options. Dear PyGui is genuinely fast (GPU-rendered) but has a learning curve and less documentation. Toga is BeeWare's cross-platform toolkit, still maturing.

My recommendation: Tkinter. It sounds unfashionable, but for an RSVP reader it's ideal. The UI is fundamentally simple—a big label that changes text, some controls, a text import dialog. Tkinter handles all of that in its sleep, launches instantly, and has no dependencies to manage. You can make it look decent with ttk and careful font/color choices. If you outgrow it later, porting the logic to PyQt is straightforward because you've kept the reading engine separate from the UI (which you should anyway).
Packaging and distribution

The cross-platform story for Python desktop apps has one real wart: distribution. Users shouldn't need to install Python. Your options:

    PyInstaller — most common, bundles Python + your code into a single executable per platform. Produces ~15–30MB executables for a Tkinter app. Works but each platform needs to be built on that platform (or via CI).
    Nuitka — compiles Python to C, smaller and faster binaries, more setup.
    Just ship the .py files — if it's for you and a few friends, pip install + a launcher script is fine.

For a personal project, start with "run it from source" and add PyInstaller once you want to share it. Don't sink time into packaging early.
Revised architecture

Keep the codebase clean by separating concerns from day one. Rough module layout:

rsvp_reader/
  core/
    tokenizer.py      # text → word stream with metadata
    timing.py         # WPM → delay calculations, pause rules
    session.py        # reading state, position, persistence
  importers/
    txt.py
    markdown.py
    epub.py
    docx.py
    pdf.py            # text-based only
  ui/
    main_window.py
    reader_view.py
    settings.py
  storage/
    library.py        # recent files, progress
    config.py         # user preferences
  main.py

The key move: the core modules know nothing about the UI, and the importers all return the same data structure (a list of tokens with type annotations—word, sentence_end, paragraph_break, etc.). This way adding a new file format is a single file, and swapping the UI later is painful but not catastrophic.
Library choices (keeping it lean)

For importers, pick the lightest library that works:

    txt/md — standard library, no dependencies. For markdown stripping, a tiny regex pass beats pulling in a full parser.
    epub — ebooklib is the standard, modest size. It's just a zip of XHTML files; you could roll your own with zipfile + html.parser from stdlib if you want zero dependencies, and honestly that's not a bad idea.
    docx — python-docx is the obvious choice. Medium weight. Alternative: docx is also just a zip of XML, and for pure text extraction you can parse it with stdlib.
    pdf — here's where it matters most. PyMuPDF (fitz) is fast and accurate but has a larger footprint and AGPL license (matters if you ever distribute). pdfplumber is pure-Python-ish, slower, permissive license. pypdf is pure Python, smallest, but text extraction quality is noticeably worse on complex layouts. For your "efficient and lightweight" goal, I'd try pypdf first and fall back to pdfplumber if extraction quality bothers you. Skip PyMuPDF unless you need its speed.

If you want to be hardcore about minimalism, you could target stdlib-only for txt/md/epub/docx and only pull in an external dependency for PDF. That's genuinely achievable and keeps the install tiny.
The reading engine

A few implementation notes that matter at the architecture level:

Don't use time.sleep in a loop. You'll block the UI. Tkinter's root.after(ms, callback) is the right primitive—schedule the next word, return control to the event loop, repeat. This also makes pause/resume trivial (just don't schedule the next callback).

Tokenize once, display forever. Parse the full document into a token list upfront with all the metadata you need (word text, is_sentence_end, is_paragraph_break, word length). The display loop should be dumb—pull the next token, figure out the delay, schedule it. This separation makes variable timing a one-line change later.

Position is an index into the token list. Not a byte offset, not a character count. This makes rewind, jump-to-sentence, and progress tracking all trivial.
Scope adjustments given your constraints

Given the lightweight goal, I'd trim the earlier phasing:

Phase 1: Tkinter shell, txt/md import, RSVP display with WPM control, pause/rewind, dark mode, session persistence. This is maybe a weekend.

Phase 2: EPUB and DOCX (both are just zips of markup—attack them together). Keyboard shortcuts. A simple library view of recent files.

Phase 3: PDF (text-based only, with a preview step so users can see garbled extraction before committing). This is the biggest single piece of work.

Phase 4: AI summaries. Given your lightweight ethos, consider making this optional and off by default—it's a network call, requires an API key, and isn't core to the reading experience. A "summarize what I just read" button is probably the right scope. Skip quiz generation for now.

Phase 5 (maybe never): ORP, variable timing, OCR, advanced layout handling.
One concrete question worth deciding now

How do you want to handle the import-then-read flow versus paste-and-go? Two natural modes:

    A library model: import files, they get parsed and stored, you open them from a list, progress is tracked per file.
    A clipboard/paste model: paste text or drop a file, read it, done, no persistence.

These aren't mutually exclusive but they imply different default UX. For your goal of "read more," the library model is probably right—friction to restart is what kills reading habits, and "open app → click last book → resume" is the magic flow. But the paste model is trivial to add on top.

If all this sounds right, the natural next step is a concrete Phase 1 spec—exact UI layout, keyboard shortcuts, data structures—before any code. Want to work through that?

I don't want to make money off this, it will remain private until its in beta. I won't really advertise this ether so I'm not too worried about licensing unless it prohibits opensource distribution.
7:44 PM

That simplifies things considerably. For a private/personal project that might eventually go open source, here's how licensing actually shakes out for your likely dependencies:

PyMuPDF's AGPL is the main thing worth understanding. AGPL doesn't prohibit open source distribution—it requires it, and requires that anyone who uses your software over a network also gets the source. For a desktop app you give away on GitHub, AGPL is fine. The catch is viral: if you use an AGPL library, your project has to be AGPL too (or compatible). That's not a problem for an open source hobby project, but it forecloses ever making it proprietary or using a permissive license like MIT. Given that, PyMuPDF is back on the table for you—and it's genuinely the best PDF library in the Python ecosystem. Faster extraction, better layout handling, handles edge cases pypdf chokes on.

Everything else you'd likely use is permissive (MIT, BSD, Apache): Tkinter (Python's own PSF license), ebooklib, python-docx, pypdf, pdfplumber, requests, and the Anthropic/OpenAI SDKs. No constraints worth worrying about.

So the real licensing decision is just: do you want PyMuPDF's quality (and accept AGPL for your project), or stay fully permissive with pypdf/pdfplumber? For a personal reader where PDF extraction quality directly affects your reading experience, I'd lean PyMuPDF. You can always swap it later—your importer architecture isolates the choice to one file.
Where this leaves you

With licensing off the table as a constraint, the remaining open decisions before Phase 1 coding are:

    Import flow: library model vs. paste-and-go vs. both. (I'd suggest library as primary, paste as a secondary entry point.)
    PDF library: PyMuPDF vs. pypdf. (I'd suggest PyMuPDF given the above.)
    Phase 1 scope lock: what exactly is in the first working version.

Want to nail down Phase 1 next? A concrete spec would cover the window layout, the token data structure, the keyboard shortcuts, where config/progress files live on disk, and the exact file formats supported in v1. That's the document you'd actually build from.

Lets go with your recommendations, this is all new to me. For phase 1 I would like to have the skeleton and connections made. A guess a good goal would be to be able to complete the RSVP with a basic txt file
7:46 PM

Good call—getting a working end-to-end slice first is the right instinct. Even a minimal version that reads one txt file teaches you more than a week of planning. Let me spec out Phase 1 concretely.
Phase 1 goal

Open the app, load a .txt file, see the words flash at your chosen WPM, pause/resume/rewind, close the app and reopen to find your position preserved. That's it. No library view, no themes beyond dark mode, no AI, no other formats. Everything else is scaffolding for later phases.
Project structure

rsvp_reader/
├── main.py                 # entry point
├── core/
│   ├── __init__.py
│   ├── tokenizer.py        # text → token list
│   ├── timing.py           # WPM → delay math
│   └── session.py          # reading state
├── importers/
│   ├── __init__.py
│   ├── base.py             # Importer interface
│   └── txt.py              # .txt importer
├── ui/
│   ├── __init__.py
│   ├── main_window.py      # the Tk root + layout
│   └── reader_view.py      # the big word display
├── storage/
│   ├── __init__.py
│   ├── config.py           # user prefs (WPM, theme)
│   └── progress.py         # per-file position tracking
└── requirements.txt        # empty for Phase 1 — stdlib only

The __init__.py files can be empty; they just make the directories into Python packages.
Token data structure

This is the most important design decision in Phase 1 because every later feature depends on it. Keep it simple but extensible:
python

from dataclasses import dataclass
from enum import Enum

class TokenType(Enum):
    WORD = "word"
    SENTENCE_END = "sentence_end"    # word that ends a sentence
    PARAGRAPH_END = "paragraph_end"  # word that ends a paragraph

@dataclass
class Token:
    text: str           # the actual word to display
    type: TokenType     # for pause logic later
    index: int          # position in the full stream

A document becomes a list[Token]. Phase 1 only really uses text and index, but having type already there means adding sentence/paragraph pauses in Phase 5 is a one-line change in the timing module.
Tokenizer (stdlib only)

The logic: split on whitespace, then inspect each word for terminal punctuation to tag its type. Something like:
python

import re

SENTENCE_ENDINGS = {".", "!", "?"}

def tokenize(text: str) -> list[Token]:
    tokens = []
    paragraphs = re.split(r'\n\s*\n', text.strip())
    idx = 0
    for p_i, para in enumerate(paragraphs):
        words = para.split()
        for w_i, word in enumerate(words):
            is_last_in_para = (w_i == len(words) - 1)
            ends_sentence = word and word[-1] in SENTENCE_ENDINGS
            if is_last_in_para and p_i < len(paragraphs) - 1:
                ttype = TokenType.PARAGRAPH_END
            elif ends_sentence:
                ttype = TokenType.SENTENCE_END
            else:
                ttype = TokenType.WORD
            tokens.append(Token(text=word, type=ttype, index=idx))
            idx += 1
    return tokens

Don't overthink edge cases for Phase 1. "Mr. Smith" will be split wrong; that's fine for now.
Importer interface
python

# importers/base.py
from abc import ABC, abstractmethod
from pathlib import Path
from core.tokenizer import Token

class Importer(ABC):
    @abstractmethod
    def can_handle(self, path: Path) -> bool: ...
    
    @abstractmethod
    def load(self, path: Path) -> list[Token]: ...

The txt importer just reads the file and calls the tokenizer. Later importers (epub, pdf) all conform to the same interface, and main.py picks one by asking each can_handle(path).
Timing module
python

# core/timing.py
def delay_ms(wpm: int) -> int:
    return int(60_000 / wpm)

That's literally it for Phase 1. In Phase 5 this grows to account for word length and token type, but the signature stays the same.
Session
python

# core/session.py
from dataclasses import dataclass
from core.tokenizer import Token

@dataclass
class Session:
    tokens: list[Token]
    position: int = 0
    wpm: int = 300
    is_playing: bool = False
    file_path: str = ""
    
    def current_token(self) -> Token | None:
        if 0 <= self.position < len(self.tokens):
            return self.tokens[self.position]
        return None
    
    def advance(self) -> None:
        if self.position < len(self.tokens) - 1:
            self.position += 1
        else:
            self.is_playing = False
    
    def rewind(self, n: int = 5) -> None:
        self.position = max(0, self.position - n)
    
    def progress(self) -> float:
        if not self.tokens:
            return 0.0
        return self.position / len(self.tokens)

Storage

Two tiny JSON files in the platform-appropriate user config directory. Stdlib has pathlib and json, and the convention is:

    Linux/Mac: ~/.config/rsvp_reader/
    Windows: %APPDATA%\rsvp_reader\

python

# storage/config.py
import json
import os
from pathlib import Path

def config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home()))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / "rsvp_reader"
    path.mkdir(parents=True, exist_ok=True)
    return path

def load_config() -> dict:
    f = config_dir() / "config.json"
    if f.exists():
        return json.loads(f.read_text())
    return {"wpm": 300, "dark_mode": True}

def save_config(cfg: dict) -> None:
    (config_dir() / "config.json").write_text(json.dumps(cfg, indent=2))

progress.py is similar—a dict mapping absolute file paths to token indices, saved to progress.json.
UI layout

Tkinter window, fixed-width 600×300 or so, with:

┌───────────────────────────────────────┐
│  File: essay.txt          45% │ 300wpm│  ← status bar
├───────────────────────────────────────┤
│                                       │
│                                       │
│            interesting                │  ← reader_view
│                                       │
│                                       │
├───────────────────────────────────────┤
│  [Open]  [▶ Play]  WPM: [- 300 +]     │  ← controls
└───────────────────────────────────────┘

The reader_view is just a tk.Label with a large font (say 36pt), centered, that gets its text swapped on each tick. Do not do anything fancy here in Phase 1—centered text is fine. ORP comes later.
The play loop

This is the one place to be careful. Use root.after, not threads or sleep:
python

def tick(self):
    if not self.session.is_playing:
        return
    token = self.session.current_token()
    if token is None:
        self.session.is_playing = False
        return
    self.reader_view.show(token.text)
    self.session.advance()
    self.root.after(delay_ms(self.session.wpm), self.tick)

Pause is session.is_playing = False. Resume is session.is_playing = True; self.tick(). Rewind is session.rewind(5) (no need to touch the timer).
Keyboard shortcuts for Phase 1

Just three, bound on the root window:

    Space — toggle play/pause
    Left — rewind 5 words
    Ctrl+O — open file dialog

Anything more is Phase 2.
Save points

Save progress on: pause, window close, and every ~100 words during playback (so a crash doesn't lose much). Save config on: WPM change, window close.
What's explicitly out of scope for Phase 1

Writing this down helps you resist scope creep:

    No library/recents view (you re-open files via file dialog)
    No font/color customization beyond a dark mode toggle
    No progress bar that lets you scrub (just a percentage readout)
    No sentence/paragraph pauses (tokens are tagged but timing ignores it)
    No error dialogs beyond print-to-console (real error UX in Phase 2)
    No tests (add in Phase 2 once the shape is stable)

Suggested build order

    Tokenizer + Session + timing module with a tiny throwaway __main__ that prints tokens to console with the right delays. Proves the core works without any UI.
    Minimal Tkinter window with a hardcoded string streaming into the Label. Proves root.after works and the display looks okay.
    Wire in the txt importer + file dialog. Now you can read real files.
    Add pause/play/rewind controls (buttons + keys).
    Add config + progress persistence. Close the app mid-read, reopen, resume.
    Add the status bar with filename, percent, and WPM readout.

Each step is small, testable, and leaves you with a running program. If you hit a wall at any step, you know exactly what broke.

This should be genuinely achievable in a weekend or two of focused evenings. Want me to put this all into a spec document you can reference while building, or do you want to start coding and ask questions as you go?

This looks good. What licensing should I add based on our current progression?
7:56 PM

For where you are now—private project, may go open source later, using only permissive-licensed d
Claude's response was interrupted

This looks good. What licensing should I add based on our current progression?
7:56 PM

Nice repo name, "RSVPy" is clever.

Your current selections are all solid, with one thing worth changing:

Apache 2.0 license — good choice. This fits your situation well. It's permissive (no viral constraints), compatible with all your planned dependencies (Tkinter, pypdf/pdfplumber or PyMuPDF, ebooklib, python-docx, the AI SDKs), and has an explicit patent grant that MIT lacks—which is a small but real benefit if you ever integrate AI features that might touch patented territory. Apache 2.0 is also what a lot of modern Python projects default to, so it'll look familiar to anyone who stumbles across the repo later.

The only alternative worth considering is MIT, which is simpler and more common for tiny projects. Functionally for you the difference is minor. Apache is slightly more protective (patent grant, explicit contribution terms); MIT is slightly more minimal (shorter, more permissive feel). Either is fine—stick with Apache 2.0 if you've already selected it.

One thing to change: add a .gitignore. You have it set to "No .gitignore" and you'll want one for Python. GitHub's Python template covers the standard stuff—__pycache__/, *.pyc, .venv/, build/, dist/, *.egg-info/, etc. Without it your first commit after running the code will pull in a bunch of cache files you don't want tracked. Just select "Python" from the .gitignore dropdown.

Private visibility is right for now. Keep it private through Phase 1 and 2 at minimum. Flip to public when you have something you'd actually want someone else to look at—probably around the time you finish Phase 3 (PDF support) or when you're genuinely ready to call it a beta.

Two things worth adding to the repo after creation:

A short README beyond the auto-generated one. Even just: what it is, current status ("in development, Phase 1"), planned features, how to run it once there's code. Future-you will appreciate it when you return after a break, and it's the first thing anyone sees if you go public.

Consider adding a NOTICE file if you end up vendoring or heavily adapting any Apache-licensed code from elsewhere. Not needed for Phase 1, just something to keep in mind.

So: keep Apache 2.0, flip the .gitignore to Python, and you're set. Create the repo and you're ready to start on the tokenizer.

Alright, provide a README for the project.
8:12 PM

Here's a README suited to where the project is now—honest about its early stage, but structured so it can grow with you.
markdown

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
git clone https://github.com/thelogansmith/RSVPy.git
cd RSVPy
python main.py
```

## Project Structure

rsvp_reader/
├── main.py              # Entry point
├── core/                # Tokenizer, timing, session state
├── importers/           # File format handlers
├── ui/                  # Tkinter window and reader view
└── storage/             # Config and progress persistence


## License

Licensed under the [Apache License 2.0](LICENSE).

## Contributing

This is a personal project in early development and is not currently accepting contributions. Once it reaches beta, issues and pull requests will be welcome.

A few notes on what I included and why:

I kept the tone factual rather than promotional—"aims to" and "planned" rather than claiming features that don't exist. Overselling an early-stage project ages poorly.

The roadmap mirrors the phasing we worked out, so it doubles as your own working document. You can tick items off as you go, and anyone who finds the repo understands exactly where you are.

The explicit "non-goals" section is useful for personal projects because it reminds future-you what you already decided not to build. It also deflects feature requests if this ever goes public.

I used python main.py for the install command assuming you'll structure it that way per the Phase 1 spec. If you end up with a different entry point, adjust that line.

The contributing section is optional for a private/early repo but it's a nice touch that signals this is a real project with a trajectory, not abandoned code.

Drop this in as README.md in your repo root. When you hit Phase 2 or beyond, update the status line and check off roadmap items—that steady visible progress is genuinely motivating.

Create the phase 1 docs per the current plan
9:05 PM

I'll create a proper Phase 1 specification document you can reference throughout the build.
Check the docx skill for document creation guidance

For developer-facing documentation like this, markdown is honestly the better format than docx—it renders natively on GitHub, lives in the repo next to the code, and you can edit it without leaving your editor. Let me create it as markdown instead.
Created a file, ran a command, read a file

I wrote this as markdown rather than docx because it belongs in the repo next to the code—drop it in as docs/PHASE_1.md (or at the root) and GitHub will render it with proper formatting. You can edit it in any text editor as the plan evolves, and it diffs cleanly in git alongside your code changes.

The spec covers everything we discussed—scope, data structures, module contracts, UI layout, keyboard shortcuts, the play loop, persistence rules, the 6-step build order, and explicit acceptance criteria. The "known limitations accepted" section at the end is worth keeping; writing down what you're deliberately not fixing prevents scope creep later when you notice Mr. Smith tokenizing wrong and think "I should fix that right now."

One suggestion: create a docs/ folder in the repo and put this there. When Phase 2 rolls around, you'll add PHASE_2.md next to it, and the progression becomes a nice record of how the project evolved.
Phase 1
Document · MD 


Claude is AI and can make mistakes. Please double-check responses.
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
 
## Build Order
 
Each step is self-contained and leaves the program in a runnable state.
 
1. **Core, without UI.**
   Implement `tokenizer.py`, `timing.py`, and `session.py`. Write a throwaway `if __name__ == "__main__"` block in `main.py` that tokenizes a hardcoded string and prints each token to stdout with the right delay using `time.sleep`. Verifies that the core model works before any UI code exists.
2. **Minimal Tkinter shell.**
   Open a window with a centered label. Hardcode a list of words. Use `root.after` to swap them in at 300 WPM. Verifies the timing mechanism in the real GUI.
3. **Wire in the txt importer and file dialog.**
   Add the Open button. Load a real file. Confirm the display runs against actual content.
4. **Controls and keyboard shortcuts.**
   Play / pause toggle, rewind button, Space and Left bindings, Ctrl+O for open.
5. **Persistence.**
   Implement `config.py` and `progress.py`. Load on startup, save on the events listed above. Close and reopen the app; confirm position and settings survive.
6. **Status bar and WPM controls.**
   Filename, progress percent, WPM readout. `+` / `-` buttons with clamping. Theme toggle.
At the end of step 6, Phase 1 is complete.
 
---
 
## Acceptance Criteria
 
Phase 1 is done when all of the following are true:
 
- The app launches from `python main.py` on Windows, macOS, and Linux
- A `.txt` file can be opened via the file dialog
- Words stream at the configured WPM with visible pause, resume, and rewind
- WPM can be adjusted mid-session and takes effect immediately
- Dark mode toggle works and persists across restarts
- Closing and reopening the app restores the last WPM, last theme, and last position for each previously opened file
- No uncaught exceptions during normal use
- Total third-party dependency count: zero
---
 
## Known Limitations Accepted for Phase 1
 
- `Mr.`, `Dr.`, `e.g.`, and similar abbreviations produce spurious `SENTENCE_END` tags. Harmless in Phase 1 because timing ignores the tag.
- No handling of extremely long words that might overflow the label; acceptable because `.txt` files rarely contain them.
- No recovery from a corrupt `config.json` or `progress.json` beyond falling back to defaults.
- Window is not resizable.
- No visual indication of rewind beyond the next word appearing.
 

