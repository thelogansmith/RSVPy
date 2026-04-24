"""
Tokenizer: converts raw text into a stream of Token objects.

A document is split on blank lines into paragraphs, then on whitespace
into words. Each word is tagged with a TokenType so the timing module
can apply variable delays at sentence/paragraph boundaries and for
punctuation-only tokens. Each token carries its byte span in the source
text so later features can correlate tokens with the original document.

Phase 5 additions:
  - PUNCTUATION_ONLY token type for standalone punctuation (em-dashes,
    ellipses, etc.) that would otherwise flash too quickly during RSVP.
  - Function-word chunking: short function words (a, the, in, of, etc.)
    are merged with the following content word into a single display
    token, producing a more natural reading rhythm.
"""

from dataclasses import dataclass
from enum import Enum
import re


class TokenType(Enum):
    WORD = "word"
    SENTENCE_END = "sentence_end"
    PARAGRAPH_END = "paragraph_end"
    PUNCTUATION_ONLY = "punctuation_only"


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

# Regex to check if a token contains any alphanumeric character.
_HAS_ALNUM = re.compile(r"[a-zA-Z0-9]")

# Function words that can be merged with the following content word.
# Kept lowercase; comparison is case-insensitive. Only single short
# words — no multi-word merges.
_FUNCTION_WORDS = frozenset({
    "a", "an", "the",
    "i", "in", "of", "to", "for", "at", "by", "on", "up",
    "and", "but", "or", "nor", "so", "if", "as", "no",
    "is", "am", "do",
    "it", "my", "we", "he",
})


def _ends_sentence(word: str) -> bool:
    """Return True if the word's final non-quote character ends a sentence.

    Strips trailing closing quotes and brackets so that `said."` and `done!)`
    are still recognized as sentence ends.
    """
    stripped = word.rstrip('")]}\'')
    return bool(stripped) and stripped[-1] in _SENTENCE_ENDINGS


def _is_punctuation_only(word: str) -> bool:
    """Return True if the token contains no alphanumeric characters."""
    return not _HAS_ALNUM.search(word)


def _is_function_word(word: str) -> bool:
    """Return True if the word is a known function word."""
    return word.lower() in _FUNCTION_WORDS


def tokenize(text: str) -> list[Token]:
    """Convert raw text into a list of Token objects.

    Paragraphs are separated by blank lines. Within a paragraph, words are
    separated by whitespace. The last word of a non-final paragraph is
    tagged PARAGRAPH_END. Words ending in sentence-terminating punctuation
    are tagged SENTENCE_END. Tokens with no alphanumeric characters are
    tagged PUNCTUATION_ONLY. Everything else is WORD.

    Each token carries source_start and source_end, the inclusive/exclusive
    character offsets of the word in the input text.

    After initial tagging, a merge pass groups function words with the
    following content word for chunked display.
    """
    # Find every paragraph-break gap in the original text.
    para_break_ends = [m.end() for m in _PARAGRAPH_BREAK.finditer(text)]

    # Collect every word with its span in the original text.
    word_spans: list[tuple[str, int, int]] = [
        (m.group(), m.start(), m.end()) for m in _WORD.finditer(text)
    ]
    if not word_spans:
        return []

    # First pass: tag types without merging.
    raw_tokens: list[Token] = []
    for i, (word, start, end) in enumerate(word_spans):
        is_last_word_overall = (i == len(word_spans) - 1)

        # Check for paragraph break between this word and the next.
        is_paragraph_end = False
        if not is_last_word_overall:
            next_start = word_spans[i + 1][1]
            is_paragraph_end = any(
                end < brk <= next_start for brk in para_break_ends
            )

        # Determine token type.
        if _is_punctuation_only(word):
            ttype = TokenType.PUNCTUATION_ONLY
        elif is_paragraph_end:
            ttype = TokenType.PARAGRAPH_END
        elif _ends_sentence(word):
            ttype = TokenType.SENTENCE_END
        else:
            ttype = TokenType.WORD

        raw_tokens.append(Token(
            text=word,
            type=ttype,
            index=i,
            source_start=start,
            source_end=end,
        ))

    # Second pass: merge function words with the following content word.
    merged = _merge_function_words(raw_tokens)

    # Reassign sequential indices after merging.
    for i, token in enumerate(merged):
        token.index = i

    return merged


def _merge_function_words(tokens: list[Token]) -> list[Token]:
    """Merge function words with the following content word.

    Rules:
      - Only merge if the function word is tagged WORD (not at a sentence
        or paragraph boundary, and not punctuation-only).
      - Only merge with a following token that is NOT punctuation-only and
        NOT itself a function word (so we don't chain "in the cat" into
        one mega-token — only the last function word merges).
      - The merged token's type is the content word's type.
      - Source offsets span both tokens.
    """
    if len(tokens) <= 1:
        return list(tokens)

    result: list[Token] = []
    i = 0

    while i < len(tokens):
        token = tokens[i]

        # Check if this is a function word eligible for merging.
        if (
            i + 1 < len(tokens)
            and token.type == TokenType.WORD
            and _is_function_word(token.text)
        ):
            next_token = tokens[i + 1]
            # Only merge if the next token has alphanumeric content and
            # is not itself a lone function word that will want to merge
            # forward. We let the last function word in a chain do the
            # merge.
            next_is_content = (
                next_token.type != TokenType.PUNCTUATION_ONLY
                and not (
                    next_token.type == TokenType.WORD
                    and _is_function_word(next_token.text)
                    and i + 2 < len(tokens)
                )
            )
            if next_is_content:
                # Merge: "function content"
                merged_text = f"{token.text} {next_token.text}"
                merged_token = Token(
                    text=merged_text,
                    type=next_token.type,
                    index=0,  # Reassigned later.
                    source_start=token.source_start,
                    source_end=next_token.source_end,
                )
                result.append(merged_token)
                i += 2
                continue

        result.append(token)
        i += 1

    return result