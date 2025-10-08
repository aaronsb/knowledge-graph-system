"""
Smart text chunker for large document ingestion.

Splits documents into semantically meaningful chunks with configurable boundaries.
"""

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class ChunkingConfig:
    """Configuration for smart text chunking."""

    target_words: int = 1000
    """Target number of words per chunk (ideal size)"""

    min_words: int = 800
    """Minimum words per chunk (don't go below this)"""

    max_words: int = 1500
    """Maximum words per chunk (hard limit)"""

    overlap_words: int = 200
    """Number of words to overlap between chunks for context"""

    search_window: int = 100
    """Words to search forward/backward for boundaries"""


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""

    text: str
    """The chunk text content"""

    start_char: int
    """Character position where chunk starts in source document"""

    end_char: int
    """Character position where chunk ends in source document"""

    chunk_number: int
    """Sequential chunk number (1-indexed)"""

    word_count: int
    """Number of words in this chunk"""

    boundary_type: str
    """Type of boundary found: paragraph, sentence, pause, hard_cut"""


class SmartChunker:
    """Intelligently chunks large documents at natural boundaries."""

    def __init__(self, config: Optional[ChunkingConfig] = None):
        """
        Initialize chunker with configuration.

        Args:
            config: Chunking configuration (uses defaults if None)
        """
        self.config = config or ChunkingConfig()

        # Boundary patterns in priority order
        self.paragraph_pattern = re.compile(r'\n\n+')
        self.sentence_pattern = re.compile(r'[.!?]\s+[A-Z]')
        self.pause_pattern = re.compile(r'[.]{3}\s+|—\s+|;\s+')

    def _count_words(self, text: str) -> int:
        """Count words in text."""
        return len(text.split())

    def _char_to_word_position(self, text: str, char_pos: int) -> int:
        """Convert character position to approximate word position."""
        return self._count_words(text[:char_pos])

    def _word_to_char_position(self, text: str, word_pos: int) -> int:
        """Convert word position to approximate character position."""
        words = text.split()
        if word_pos >= len(words):
            return len(text)
        return len(' '.join(words[:word_pos]))

    def _find_best_boundary(
        self,
        text: str,
        start_char: int,
        ideal_char: int,
        max_char: int
    ) -> Tuple[int, str]:
        """
        Find the best boundary near the ideal position.

        Args:
            text: Full text being chunked
            start_char: Where this chunk started
            ideal_char: Ideal end position (target_words)
            max_char: Maximum allowed end position (max_words)

        Returns:
            Tuple of (boundary_char_position, boundary_type)
        """
        # Define search range around ideal position
        search_start = max(start_char, ideal_char - 500)
        search_end = min(len(text), ideal_char + 500)
        search_text = text[search_start:search_end]

        # Try to find paragraph break
        paragraph_matches = list(self.paragraph_pattern.finditer(search_text))
        if paragraph_matches:
            # Find closest to ideal position
            best_match = min(
                paragraph_matches,
                key=lambda m: abs((search_start + m.start()) - ideal_char)
            )
            return search_start + best_match.start(), "paragraph"

        # Try to find sentence boundary
        sentence_matches = list(self.sentence_pattern.finditer(search_text))
        if sentence_matches:
            best_match = min(
                sentence_matches,
                key=lambda m: abs((search_start + m.start()) - ideal_char)
            )
            # Position after the period/punctuation
            return search_start + best_match.start() + 1, "sentence"

        # Try to find natural pause
        pause_matches = list(self.pause_pattern.finditer(search_text))
        if pause_matches:
            best_match = min(
                pause_matches,
                key=lambda m: abs((search_start + m.start()) - ideal_char)
            )
            return search_start + best_match.start(), "pause"

        # No boundary found - hard cut at max position
        return min(max_char, len(text)), "hard_cut"

    def chunk_text(
        self,
        text: str,
        start_position: int = 0
    ) -> List[Chunk]:
        """
        Split text into smart chunks with natural boundaries.

        Args:
            text: Text to chunk
            start_position: Character position to start from (for resume)

        Returns:
            List of Chunk objects
        """
        chunks = []
        current_pos = start_position
        chunk_num = 1

        # Skip to start position if resuming
        if start_position > 0:
            # Count how many chunks would have been processed
            chunk_num = self._count_words(text[:start_position]) // self.config.target_words + 1

        while current_pos < len(text):
            # Calculate target positions in words
            words_from_start = self._count_words(text[current_pos:])

            if words_from_start < self.config.min_words:
                # Last chunk - take everything remaining
                chunk_text = text[current_pos:].strip()
                if chunk_text:
                    chunks.append(Chunk(
                        text=chunk_text,
                        start_char=current_pos,
                        end_char=len(text),
                        chunk_number=chunk_num,
                        word_count=self._count_words(chunk_text),
                        boundary_type="end_of_document"
                    ))
                break

            # Find ideal and max positions
            ideal_words = self.config.target_words
            max_words = self.config.max_words

            # Convert to character positions (approximate)
            words_so_far = text[current_pos:].split()[:max_words]
            search_text = ' '.join(words_so_far)
            max_char = current_pos + len(search_text)

            words_ideal = text[current_pos:].split()[:ideal_words]
            ideal_text = ' '.join(words_ideal)
            ideal_char = current_pos + len(ideal_text)

            # Find best boundary
            end_pos, boundary_type = self._find_best_boundary(
                text=text,
                start_char=current_pos,
                ideal_char=ideal_char,
                max_char=max_char
            )

            # Extract chunk
            chunk_text = text[current_pos:end_pos].strip()

            if chunk_text:
                chunks.append(Chunk(
                    text=chunk_text,
                    start_char=current_pos,
                    end_char=end_pos,
                    chunk_number=chunk_num,
                    word_count=self._count_words(chunk_text),
                    boundary_type=boundary_type
                ))

                # Move to next chunk with overlap
                overlap_chars = self._word_to_char_position(
                    chunk_text,
                    max(0, self._count_words(chunk_text) - self.config.overlap_words)
                )
                current_pos = current_pos + overlap_chars
                chunk_num += 1
            else:
                # Safety: if we get empty chunk, advance by at least 1 char
                current_pos = end_pos + 1

        return chunks

    def get_chunk_summary(self, chunks: List[Chunk]) -> str:
        """
        Get summary of chunking results.

        Args:
            chunks: List of chunks

        Returns:
            Formatted summary string
        """
        if not chunks:
            return "No chunks generated"

        total_words = sum(c.word_count for c in chunks)
        avg_words = total_words / len(chunks)

        boundary_counts = {}
        for chunk in chunks:
            boundary_counts[chunk.boundary_type] = boundary_counts.get(chunk.boundary_type, 0) + 1

        summary = f"""Chunking Summary:
  Total chunks: {len(chunks)}
  Total words: {total_words:,}
  Average words/chunk: {avg_words:.0f}

  Boundaries found:
"""
        for boundary_type, count in sorted(boundary_counts.items()):
            summary += f"    {boundary_type}: {count}\n"

        return summary
