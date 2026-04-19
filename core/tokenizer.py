"""
Tokenizer: converts raw text into a stream of Token objects.
 
A document is split on blank lines into paragraphs, then on whitespace
into words. Each word is tagged with a TokenType so later phases can
apply variable timing at sentence and paragraph boundaries, and carries
its byte span in the source text so later phases can correlate tokens
with the original document (Phase 3 context window, click-to-seek).
"""

from dataclasses import dataclass
from enum import Enum
import re


class TokenType(Enum):
    WORD = "word"
    SENTENCE_END = "sentence_end"
    PARAGRAPH_END = "paragraph_end"


@dataclass
class Token:
    text: str
    type: TokenType
    index: int
    source_start: int   # inclusive char offset into tokenizer input
    source_end: int     # exclusive char offset into tokenizer input


# Characters that, when appearing at the end of a word, signal a sentence break.
_SENTENCE_ENDINGS = {".", "!", "?"}

# Matches a paragraph break: a newline, then any amount of whitespace
# that contains at least one more newline. finditer gives us the spans
# of every such gap, which we use to assign paragraph numbers to words.
_PARAGRAPH_BREAK = re.compile(r"\n[ \t\r\f\v]*\n\s*")

# Matches a run of non-whitespace characters - i.e. a "word" in the
# tokenizer's sense. finditer gives us start/end offsets directly.
_WORD = re.compile(r"\S+")

def _ends_sentence(word: str) -> bool:
    """Return True if the word's final non-quote character ends a sentence.

    Strips trailing closing quotes and brackets so that `said."` and `done!)`
    are still recognized as sentence ends.
    """
    stripped = word.rstrip('")]}\'')
    return bool(stripped) and stripped[-1] in _SENTENCE_ENDINGS


def tokenize(text: str) -> list[Token]:
    """Convert raw text into a list of Token objects.
 
    Paragraphs are separated by blank lines. Within a paragraph, words are
    separated by whitespace. The last word of a non-final paragraph is
    tagged PARAGRAPH_END. Words ending in sentence-terminating punctuation
    are tagged SENTENCE_END. Everything else is WORD.
 
    Each token carries source_start and source_end, the inclusive/exclusive
    character offsets of the word in the input text.
    """
    # Find every paragraph-break gap in the original text. These are the
    # positions that, if a word ends before one of them and the next word
    # starts after it, mark the word as PARAGRAPH_END.
    para_break_ends = [m.end() for m in _PARAGRAPH_BREAK.finditer(text)]
 
    # Collect every word with its span in the original text. We don't
    # tag types yet because PARAGRAPH_END depends on what comes after.
    word_spans: list[tuple[str, int, int]] = [
        (m.group(), m.start(), m.end()) for m in _WORD.finditer(text)
    ]
    if not word_spans:
        return []

    tokens: list[Token] = []
    for i, (word, start, end) in enumerate(word_spans):
        is_last_word_overall = (i == len(word_spans) - 1)
 
        # A word is the end of its paragraph if there's a paragraph
        # break between its end and the next word's start. The last
        # word overall can't be PARAGRAPH_END - there's no next paragraph.
        is_paragraph_end = False
        if not is_last_word_overall:
            next_start = word_spans[i + 1][1]
            # A break falls "between" this word and the next if its
            # end position is within (end, next_start].
            is_paragraph_end = any(
                end < brk <= next_start for brk in para_break_ends
            )
 
        if is_paragraph_end:
            ttype = TokenType.PARAGRAPH_END
        elif _ends_sentence(word):
            ttype = TokenType.SENTENCE_END
        else:
            ttype = TokenType.WORD
 
        tokens.append(Token(
            text=word,
            type=ttype,
            index=i,
            source_start=start,
            source_end=end,
        ))
 
    return tokens
