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


def _split_into_sentences(text: str) -> List[str]:
    """
    Split text into sentences at natural boundaries.

    Uses regex to detect sentence boundaries while avoiding common abbreviations.

    Args:
        text: Input text to split

    Returns:
        List of sentences (may be empty if text is empty)

    Example:
        >>> _split_into_sentences("Hello world. How are you?")
        ['Hello world.', 'How are you?']
    """
    if not text:
        return []

    # Split on sentence boundaries
    sentences = SENTENCE_BOUNDARY_PATTERN.split(text)

    # Filter out empty strings and strip whitespace
    sentences = [s.strip() for s in sentences if s.strip()]

    # If no sentences detected (no punctuation), treat entire text as one sentence
    if not sentences:
        sentences = [text.strip()]

    return sentences


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

    # Split into sentences
    sentences = _split_into_sentences(text)

    if not sentences:
        return []

    # Build chunks
    chunks: List[SourceChunk] = []
    current_chunk_text = ""
    current_chunk_start = 0

    for sentence in sentences:
        # Calculate position of this sentence in original text
        # Find next occurrence of sentence in remaining text
        search_start = current_chunk_start + len(current_chunk_text)
        sentence_pos = text.find(sentence, search_start)

        # If adding this sentence would exceed max_chars, finalize current chunk
        potential_length = len(current_chunk_text) + len(sentence)
        if current_chunk_text and potential_length > max_chars:
            # Finalize current chunk
            chunk_end = current_chunk_start + len(current_chunk_text)
            chunks.append(SourceChunk(
                text=current_chunk_text.strip(),
                start_offset=current_chunk_start,
                end_offset=chunk_end,
                index=len(chunks)
            ))

            # Start new chunk with this sentence
            current_chunk_text = sentence + " "
            current_chunk_start = sentence_pos
        else:
            # Add sentence to current chunk
            if not current_chunk_text:
                current_chunk_start = sentence_pos

            current_chunk_text += sentence + " "

    # Finalize last chunk
    if current_chunk_text.strip():
        chunk_end = current_chunk_start + len(current_chunk_text.strip())
        chunks.append(SourceChunk(
            text=current_chunk_text.strip(),
            start_offset=current_chunk_start,
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
