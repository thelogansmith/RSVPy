"""
AI summarization module.

Handles API calls to Claude for generating document summaries. Supports
both short documents (single call) and long documents (hierarchical
chunked summarization).

The module is provider-abstracted: switching from Anthropic to another
provider means changing the _call_api function. The rest of the logic
(chunking, progress reporting, error handling) stays the same.

All API calls are designed to run on a background thread. The caller
(MainWindow) is responsible for threading and UI updates.
"""

from __future__ import annotations

import re
from typing import Callable


# Approximate word count threshold for chunking. Documents under this
# limit get a single summarization call.
CHUNK_THRESHOLD_WORDS = 4000

# Target chunk size in words. Chunks split at paragraph boundaries.
CHUNK_TARGET_WORDS = 3500


def summarize(
    source_text: str,
    api_key: str,
    provider: str = "anthropic",
    on_progress: Callable[[str], None] | None = None,
) -> str:
    """Generate a summary of the given text.

    Args:
        source_text: The full canonical document text.
        api_key: The user's API key.
        provider: "anthropic" (only supported provider for now).
        on_progress: Optional callback for progress updates. Called
            with a status string like "Summarizing section 2 of 5...".
            Must be thread-safe (the caller wraps it with queue + after).

    Returns:
        The generated summary text.

    Raises:
        SummarizationError: On any failure (network, auth, rate limit, etc).
    """
    if not api_key:
        raise SummarizationError("No API key configured.")

    if not source_text.strip():
        raise SummarizationError("No text to summarize.")

    word_count = len(source_text.split())

    if word_count <= CHUNK_THRESHOLD_WORDS:
        # Short document: single call.
        if on_progress:
            on_progress("Generating summary...")
        return _summarize_text(source_text, api_key, provider)
    else:
        # Long document: chunked hierarchical summarization.
        return _summarize_chunked(source_text, api_key, provider, on_progress)


def _summarize_chunked(
    source_text: str,
    api_key: str,
    provider: str,
    on_progress: Callable[[str], None] | None,
) -> str:
    """Hierarchical summarization for long documents."""
    chunks = _split_into_chunks(source_text)
    total = len(chunks)

    chunk_summaries: list[str] = []
    for i, chunk in enumerate(chunks, 1):
        if on_progress:
            on_progress(f"Summarizing section {i} of {total}...")

        prompt = (
            "Summarize the following section of a document concisely, "
            "preserving key points and important details:\n\n"
            f"{chunk}"
        )
        summary = _call_api(prompt, api_key, provider)
        chunk_summaries.append(summary)

    # Final synthesis call.
    if on_progress:
        on_progress("Producing final summary...")

    combined = "\n\n---\n\n".join(
        f"Section {i}: {s}" for i, s in enumerate(chunk_summaries, 1)
    )
    final_prompt = (
        "The following are summaries of consecutive sections of a document. "
        "Produce a single cohesive summary that captures the main points, "
        "themes, and key takeaways:\n\n"
        f"{combined}"
    )
    return _call_api(final_prompt, api_key, provider)


def _split_into_chunks(text: str) -> list[str]:
    """Split text into chunks of approximately CHUNK_TARGET_WORDS words,
    splitting at paragraph boundaries. Falls back to sentence boundaries
    for single-paragraph texts."""
    paragraphs = re.split(r"\n\s*\n", text)

    # If there's only one giant paragraph, split on sentence boundaries
    # so chunking still works for long single-paragraph texts.
    if len(paragraphs) <= 1 and len(text.split()) > CHUNK_TARGET_WORDS:
        sentences = re.split(r"(?<=[.!?])\s+", text)
        paragraphs = sentences

    chunks: list[str] = []
    current_chunk: list[str] = []
    current_words = 0
    joiner = "\n\n" if len(paragraphs) > 1 else " "

    for para in paragraphs:
        para_words = len(para.split())
        if current_words + para_words > CHUNK_TARGET_WORDS and current_chunk:
            chunks.append(joiner.join(current_chunk))
            current_chunk = []
            current_words = 0
        current_chunk.append(para)
        current_words += para_words

    if current_chunk:
        chunks.append(joiner.join(current_chunk))

    return chunks if chunks else [text]


def _summarize_text(text: str, api_key: str, provider: str) -> str:
    """Single-call summarization for short documents."""
    prompt = (
        "Provide a concise summary of the following document, including "
        "key points, main themes, and important takeaways:\n\n"
        f"{text}"
    )
    return _call_api(prompt, api_key, provider)


def _call_api(prompt: str, api_key: str, provider: str) -> str:
    """Make an API call to the configured provider.

    Currently supports Anthropic (Claude) only. The provider parameter
    is here for future extensibility.
    """
    if provider != "anthropic":
        raise SummarizationError(f"Unsupported provider: {provider}")

    return _call_anthropic(prompt, api_key)


def _call_anthropic(prompt: str, api_key: str) -> str:
    """Call the Anthropic Messages API using the anthropic SDK."""
    try:
        import anthropic
    except ImportError:
        raise SummarizationError(
            "The 'anthropic' package is not installed.\n"
            "Run: pip install anthropic"
        )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[
                {"role": "user", "content": prompt}
            ],
        )

        # Extract text from the response content blocks.
        parts: list[str] = []
        for block in message.content:
            if hasattr(block, "text"):
                parts.append(block.text)

        result = "\n".join(parts).strip()
        if not result:
            raise SummarizationError("The API returned an empty response.")
        return result

    except ImportError:
        raise SummarizationError(
            "The 'anthropic' package is not installed.\n"
            "Run: pip install anthropic"
        )
    except SummarizationError:
        raise
    except Exception as e:
        error_msg = str(e)

        # Provide user-friendly messages for common errors.
        if "401" in error_msg or "authentication" in error_msg.lower():
            raise SummarizationError(
                "Authentication failed. Please check your API key in Settings."
            )
        elif "429" in error_msg or "rate" in error_msg.lower():
            raise SummarizationError(
                "Rate limit reached. Please wait a moment and try again."
            )
        elif "insufficient" in error_msg.lower() or "credit" in error_msg.lower():
            raise SummarizationError(
                "Insufficient API credits. Please check your account balance."
            )
        else:
            raise SummarizationError(f"API error: {error_msg}")


def test_api_key(api_key: str, provider: str = "anthropic") -> tuple[bool, str]:
    """Test whether an API key is valid by making a minimal API call.

    Returns (success: bool, message: str).
    """
    if not api_key:
        return False, "No API key provided."

    try:
        result = _call_api("Say 'ok' and nothing else.", api_key, provider)
        if result:
            return True, "Connection successful."
        return False, "Empty response from API."
    except SummarizationError as e:
        return False, str(e)


class SummarizationError(Exception):
    """Raised when summarization fails for any reason."""
    pass
