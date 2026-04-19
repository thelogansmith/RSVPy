"""
Tokenizer: converts raw text into a stream of Token objects.

A document is split on blank lines into paragraphs, then on whitespace
into words. Each word is tagged with a TokenType so later phases can
apply variable timing at sentence and paragraph boundaries.
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


# Characters that, when appearing at the end of a word, signal a sentence break.
_SENTENCE_ENDINGS = {".", "!", "?"}

# Matches one or more blank lines (a blank line = optional whitespace between
# two newlines). Used to split text into paragraphs.
_PARAGRAPH_SPLIT = re.compile(r"\n\s*\n")


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
    """
    tokens: list[Token] = []
    if not text or not text.strip():
        return tokens

    paragraphs = _PARAGRAPH_SPLIT.split(text.strip())
    idx = 0

    for p_i, paragraph in enumerate(paragraphs):
        words = paragraph.split()
        if not words:
            continue

        is_last_paragraph = (p_i == len(paragraphs) - 1)

        for w_i, word in enumerate(words):
            is_last_word = (w_i == len(words) - 1)

            if is_last_word and not is_last_paragraph:
                ttype = TokenType.PARAGRAPH_END
            elif _ends_sentence(word):
                ttype = TokenType.SENTENCE_END
            else:
                ttype = TokenType.WORD

            tokens.append(Token(text=word, type=ttype, index=idx))
            idx += 1

    return tokens
