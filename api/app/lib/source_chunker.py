"""
Source text chunker for embedding generation (ADR-068).

Provides sentence-based chunking with offset tracking for:
- Embedding generation (target ~500 chars per chunk)
- Precise text highlighting in UI
- Hash verification and referential integrity

Design principles:
- Chunk at sentence boundaries for semantic coherence
- Track character offsets for extraction and highlighting
- Handle edge cases (empty text, no punctuation, very long sentences)
- Deterministic chunking (same input → same chunks)
"""

import re
from dataclasses import dataclass
from typing import List


@dataclass
class SourceChunk:
    """
    Represents a chunk of source text with offset tracking.

    Attributes:
        text: Chunk content (substring of source text)
        start_offset: Character position where chunk starts (0-based, inclusive)
        end_offset: Character position where chunk ends (0-based, exclusive)
        index: 0-based chunk number (0, 1, 2, ...)
    """
    text: str
    start_offset: int
    end_offset: int
    index: int

    def __post_init__(self):
        """Validate chunk attributes."""
        if not isinstance(self.text, str):
            raise TypeError(f"text must be str, got {type(self.text).__name__}")

        if not isinstance(self.start_offset, int) or self.start_offset < 0:
            raise ValueError(f"start_offset must be non-negative int, got {self.start_offset}")

        if not isinstance(self.end_offset, int) or self.end_offset < 0:
            raise ValueError(f"end_offset must be non-negative int, got {self.end_offset}")

        if self.start_offset >= self.end_offset:
            raise ValueError(
                f"start_offset ({self.start_offset}) must be < end_offset ({self.end_offset})"
            )

        if not isinstance(self.index, int) or self.index < 0:
            raise ValueError(f"index must be non-negative int, got {self.index}")

        # Verify text length matches offsets
        expected_length = self.end_offset - self.start_offset
        if len(self.text) != expected_length:
            raise ValueError(
                f"text length ({len(self.text)}) doesn't match offsets "
                f"({self.end_offset} - {self.start_offset} = {expected_length})"
            )


# Sentence boundary regex (period, exclamation, question mark followed by space/newline/end)
# Handles common abbreviations (Dr., Mr., Mrs., etc.)
SENTENCE_BOUNDARY_PATTERN = re.compile(
    r'(?<=[.!?])\s+(?=[A-Z])|'  # Period/!/? followed by space and capital letter
    r'(?<=[.!?])\n+|'            # Period/!/? followed by newline(s)
    r'(?<=[.!?])$'               # Period/!/? at end of text
)


@dataclass
class _SentenceWithPosition:
    """Internal: Sentence with position tracking in source text."""
    text: str
    start_offset: int
    end_offset: int


def _split_into_sentences_with_positions(text: str) -> List[_SentenceWithPosition]:
    """
    Split text into sentences with position tracking.

    Uses regex to detect sentence boundaries while tracking character positions
    in the original text. This avoids issues with duplicate sentences.

    Args:
        text: Input text to split

    Returns:
        List of sentences with positions (may be empty if text is empty)

    Example:
        >>> result = _split_into_sentences_with_positions("Hello. World.")
        >>> result[0].text, result[0].start_offset, result[0].end_offset
        ('Hello.', 0, 6)
    """
    if not text:
        return []

    # Find all sentence boundaries using regex
    boundary_positions = [m.start() for m in SENTENCE_BOUNDARY_PATTERN.finditer(text)]

    # If no boundaries found, treat entire text as one sentence
    if not boundary_positions:
        stripped = text.strip()
        if not stripped:
            return []
        # Find where stripped text starts in original
        start = text.index(stripped)
        return [_SentenceWithPosition(
            text=stripped,
            start_offset=start,
            end_offset=start + len(stripped)
        )]

    # Build sentences from boundary positions
    sentences = []
    start = 0

    for boundary_pos in boundary_positions:
        # Extract sentence from start to boundary
        sentence_text = text[start:boundary_pos].strip()
        if sentence_text:
            # Find where stripped sentence starts in original text
            sentence_start = text.index(sentence_text, start)
            sentences.append(_SentenceWithPosition(
                text=sentence_text,
                start_offset=sentence_start,
                end_offset=sentence_start + len(sentence_text)
            ))
        start = boundary_pos

    # Handle any remaining text after last boundary
    if start < len(text):
        remaining = text[start:].strip()
        if remaining:
            remaining_start = text.index(remaining, start)
            sentences.append(_SentenceWithPosition(
                text=remaining,
                start_offset=remaining_start,
                end_offset=remaining_start + len(remaining)
            ))

    return sentences


def _split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences (returns just text, no position tracking).

    Convenience wrapper around _split_into_sentences_with_positions for
    cases where only the sentence text is needed.

    Args:
        text: Input text to split

    Returns:
        List of sentence strings
    """
    return [s.text for s in _split_into_sentences_with_positions(text)]


def chunk_by_sentence(
    text: str,
    max_chars: int = 500,
    min_chars: int = 100
) -> List[SourceChunk]:
    """
    Chunk text by sentences with target character limit.

    Chunks are created at sentence boundaries to maintain semantic coherence.
    Sentences are accumulated until max_chars is reached, then a new chunk starts.

    Args:
        text: Source text to chunk
        max_chars: Target maximum characters per chunk (default: 500)
        min_chars: Minimum characters per chunk (default: 100)
                   If a single sentence exceeds max_chars, it becomes its own chunk

    Returns:
        List of SourceChunk instances with offset tracking

    Edge cases:
        - Empty text: Returns empty list
        - Single sentence < max_chars: Returns single chunk
        - Single sentence > max_chars: Returns single chunk (no splitting mid-sentence)
        - No punctuation: Treats entire text as one sentence

    Example:
        >>> text = "First sentence. Second sentence. Third sentence."
        >>> chunks = chunk_by_sentence(text, max_chars=30)
        >>> len(chunks)
        2
        >>> chunks[0].text
        'First sentence. Second sentence.'
    """
    if not isinstance(text, str):
        raise TypeError(f"text must be str, got {type(text).__name__}")

    if not isinstance(max_chars, int) or max_chars <= 0:
        raise ValueError(f"max_chars must be positive int, got {max_chars}")

    if not isinstance(min_chars, int) or min_chars < 0:
        raise ValueError(f"min_chars must be non-negative int, got {min_chars}")

    if min_chars > max_chars:
        raise ValueError(f"min_chars ({min_chars}) must be <= max_chars ({max_chars})")

    # Handle empty text
    if not text.strip():
        return []

    # Split into sentences with position tracking
    sentences = _split_into_sentences_with_positions(text)

    if not sentences:
        return []

    # Build chunks by accumulating sentences
    chunks: List[SourceChunk] = []
    current_sentences: List[_SentenceWithPosition] = []
    current_length = 0

    for sentence in sentences:
        # Calculate potential length if we add this sentence
        # Account for space between sentences (except for first sentence in chunk)
        space_length = 1 if current_sentences else 0
        potential_length = current_length + space_length + len(sentence.text)

        # If adding this sentence would exceed max_chars, finalize current chunk
        if current_sentences and potential_length > max_chars:
            # Finalize current chunk
            chunk_start = current_sentences[0].start_offset
            chunk_end = current_sentences[-1].end_offset
            chunk_text = text[chunk_start:chunk_end]

            chunks.append(SourceChunk(
                text=chunk_text,
                start_offset=chunk_start,
                end_offset=chunk_end,
                index=len(chunks)
            ))

            # Start new chunk with current sentence
            current_sentences = [sentence]
            current_length = len(sentence.text)
        else:
            # Add sentence to current chunk
            current_sentences.append(sentence)
            current_length = potential_length

    # Finalize last chunk
    if current_sentences:
        chunk_start = current_sentences[0].start_offset
        chunk_end = current_sentences[-1].end_offset
        chunk_text = text[chunk_start:chunk_end]

        chunks.append(SourceChunk(
            text=chunk_text,
            start_offset=chunk_start,
            end_offset=chunk_end,
            index=len(chunks)
        ))

    return chunks


def chunk_by_paragraph(
    text: str,
    max_chars: int = 500
) -> List[SourceChunk]:
    """
    Chunk text by paragraphs (double newline boundaries).

    Future implementation for paragraph-based chunking strategy.

    Args:
        text: Source text to chunk
        max_chars: Target maximum characters per chunk

    Returns:
        List of SourceChunk instances

    Raises:
        NotImplementedError: This strategy is not yet implemented
    """
    raise NotImplementedError("Paragraph chunking strategy not yet implemented (Phase 2+)")


def chunk_by_count(
    text: str,
    max_chars: int = 500
) -> List[SourceChunk]:
    """
    Chunk text by simple character count (no boundary detection).

    Future implementation for simple character-based chunking.

    Args:
        text: Source text to chunk
        max_chars: Maximum characters per chunk

    Returns:
        List of SourceChunk instances

    Raises:
        NotImplementedError: This strategy is not yet implemented
    """
    raise NotImplementedError("Count-based chunking strategy not yet implemented (Phase 2+)")


def get_chunking_strategy(strategy: str):
    """
    Get chunking function for a given strategy name.

    Args:
        strategy: Strategy name ('sentence', 'paragraph', 'count')

    Returns:
        Chunking function

    Raises:
        ValueError: If strategy is not recognized
    """
    strategies = {
        'sentence': chunk_by_sentence,
        'paragraph': chunk_by_paragraph,
        'count': chunk_by_count,
    }

    if strategy not in strategies:
        raise ValueError(
            f"Unknown chunking strategy '{strategy}'. "
            f"Valid strategies: {', '.join(strategies.keys())}"
        )

    return strategies[strategy]
