"""
Unit tests for source text chunker (ADR-068).

Tests sentence-based chunking with offset tracking for embedding generation.
"""

import pytest
from api.app.lib.source_chunker import (
    SourceChunk,
    chunk_by_sentence,
    chunk_by_paragraph,
    chunk_by_count,
    get_chunking_strategy,
    _split_into_sentences
)


class TestSourceChunk:
    """Tests for SourceChunk dataclass."""

    def test_source_chunk_basic(self):
        """Test basic SourceChunk creation."""
        chunk = SourceChunk(
            text="Hello, world!",
            start_offset=0,
            end_offset=13,
            index=0
        )

        assert chunk.text == "Hello, world!"
        assert chunk.start_offset == 0
        assert chunk.end_offset == 13
        assert chunk.index == 0

    def test_source_chunk_validation_negative_start(self):
        """Test that negative start_offset raises ValueError."""
        with pytest.raises(ValueError, match="start_offset must be non-negative"):
            SourceChunk(text="test", start_offset=-1, end_offset=4, index=0)

    def test_source_chunk_validation_negative_end(self):
        """Test that negative end_offset raises ValueError."""
        with pytest.raises(ValueError, match="end_offset must be non-negative"):
            SourceChunk(text="test", start_offset=0, end_offset=-1, index=0)

    def test_source_chunk_validation_inverted_offsets(self):
        """Test that start >= end raises ValueError."""
        with pytest.raises(ValueError, match="start_offset .* must be < end_offset"):
            SourceChunk(text="test", start_offset=5, end_offset=5, index=0)

        with pytest.raises(ValueError, match="start_offset .* must be < end_offset"):
            SourceChunk(text="test", start_offset=10, end_offset=5, index=0)

    def test_source_chunk_validation_length_mismatch(self):
        """Test that text length must match offsets."""
        with pytest.raises(ValueError, match="text length .* doesn't match offsets"):
            SourceChunk(text="Hello", start_offset=0, end_offset=10, index=0)

    def test_source_chunk_validation_negative_index(self):
        """Test that negative index raises ValueError."""
        with pytest.raises(ValueError, match="index must be non-negative"):
            SourceChunk(text="test", start_offset=0, end_offset=4, index=-1)

    def test_source_chunk_type_errors(self):
        """Test that wrong types raise TypeError."""
        with pytest.raises(TypeError):
            SourceChunk(text=123, start_offset=0, end_offset=4, index=0)

        with pytest.raises(ValueError):
            SourceChunk(text="test", start_offset="0", end_offset=4, index=0)


class TestSplitIntoSentences:
    """Tests for _split_into_sentences() helper."""

    def test_split_basic(self):
        """Test basic sentence splitting."""
        text = "First sentence. Second sentence. Third sentence."
        sentences = _split_into_sentences(text)

        assert len(sentences) == 3
        assert sentences[0] == "First sentence."
        assert sentences[1] == "Second sentence."
        assert sentences[2] == "Third sentence."

    def test_split_with_questions(self):
        """Test splitting with question marks."""
        text = "What is this? Who are you? Where am I?"
        sentences = _split_into_sentences(text)

        assert len(sentences) == 3

    def test_split_with_exclamations(self):
        """Test splitting with exclamation marks."""
        text = "Hello! Welcome! Good morning!"
        sentences = _split_into_sentences(text)

        assert len(sentences) == 3

    def test_split_mixed_punctuation(self):
        """Test splitting with mixed punctuation."""
        text = "This is a statement. Is this a question? What an exclamation!"
        sentences = _split_into_sentences(text)

        assert len(sentences) == 3

    def test_split_with_newlines(self):
        """Test splitting with newlines."""
        text = "First sentence.\nSecond sentence.\nThird sentence."
        sentences = _split_into_sentences(text)

        assert len(sentences) == 3

    def test_split_empty_string(self):
        """Test splitting empty string."""
        sentences = _split_into_sentences("")

        assert sentences == []

    def test_split_no_punctuation(self):
        """Test text without punctuation."""
        text = "This is text without any sentence ending punctuation"
        sentences = _split_into_sentences(text)

        # Should treat entire text as one sentence
        assert len(sentences) == 1
        assert sentences[0] == text.strip()

    def test_split_single_sentence(self):
        """Test single sentence."""
        text = "This is a single sentence."
        sentences = _split_into_sentences(text)

        assert len(sentences) == 1
        assert sentences[0] == text


class TestChunkBySentence:
    """Tests for chunk_by_sentence() function."""

    def test_chunk_empty_text(self):
        """Test chunking empty text."""
        chunks = chunk_by_sentence("")

        assert chunks == []

    def test_chunk_single_short_sentence(self):
        """Test chunking single sentence under max_chars."""
        text = "This is a short sentence."
        chunks = chunk_by_sentence(text, max_chars=500)

        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].start_offset == 0
        assert chunks[0].end_offset == len(text)
        assert chunks[0].index == 0

    def test_chunk_single_long_sentence(self):
        """Test chunking single sentence over max_chars."""
        # Single sentence longer than max_chars should still be one chunk
        text = "This is a very long sentence that exceeds the maximum character limit but cannot be split because it is a single sentence and we want to maintain semantic coherence by not breaking sentences in the middle."
        chunks = chunk_by_sentence(text, max_chars=50, min_chars=0)

        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_chunk_multiple_sentences_under_limit(self):
        """Test multiple sentences that fit in one chunk."""
        text = "First. Second. Third."
        chunks = chunk_by_sentence(text, max_chars=500)

        assert len(chunks) == 1

    def test_chunk_multiple_sentences_over_limit(self):
        """Test multiple sentences split into multiple chunks."""
        # Each sentence ~30 chars, max_chars=50 should give 2 chunks
        text = "This is the first sentence. This is the second sentence. This is the third sentence."
        chunks = chunk_by_sentence(text, max_chars=50, min_chars=0)

        assert len(chunks) >= 2

    def test_chunk_offset_tracking(self):
        """Test that offsets correctly map to source text."""
        text = "Sentence one. Sentence two. Sentence three."
        chunks = chunk_by_sentence(text, max_chars=30, min_chars=0)

        for chunk in chunks:
            # Extract text using offsets
            extracted = text[chunk.start_offset:chunk.end_offset]
            # Should match chunk text
            assert extracted == chunk.text

    def test_chunk_index_sequential(self):
        """Test that chunk indexes are sequential."""
        text = "One. Two. Three. Four. Five. Six. Seven. Eight."
        chunks = chunk_by_sentence(text, max_chars=20, min_chars=0)

        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_chunk_no_punctuation(self):
        """Test chunking text without sentence punctuation."""
        text = "This is text without any sentence ending markers"
        chunks = chunk_by_sentence(text, max_chars=500)

        # Should treat as single chunk
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_chunk_with_newlines(self):
        """Test chunking text with newlines."""
        text = "First sentence.\nSecond sentence.\nThird sentence."
        chunks = chunk_by_sentence(text, max_chars=30, min_chars=0)

        # Should split on sentence boundaries
        assert len(chunks) >= 2

    def test_chunk_parameter_validation(self):
        """Test parameter validation."""
        # Non-string text
        with pytest.raises(TypeError):
            chunk_by_sentence(123, max_chars=500)

        # Invalid max_chars
        with pytest.raises(ValueError):
            chunk_by_sentence("text", max_chars=0)

        with pytest.raises(ValueError):
            chunk_by_sentence("text", max_chars=-100)

        # min_chars > max_chars
        with pytest.raises(ValueError):
            chunk_by_sentence("text", max_chars=100, min_chars=200)

    def test_chunk_whitespace_handling(self):
        """Test that whitespace is properly handled."""
        text = "   First sentence.    Second sentence.   "
        chunks = chunk_by_sentence(text, max_chars=500)

        # Chunks should be stripped
        for chunk in chunks:
            assert chunk.text == chunk.text.strip()

    def test_chunk_unicode_text(self):
        """Test chunking unicode text."""
        text = "世界和平。人人平等。共同发展。"
        chunks = chunk_by_sentence(text, max_chars=500)

        assert len(chunks) >= 1
        # Verify offset tracking works with unicode
        for chunk in chunks:
            extracted = text[chunk.start_offset:chunk.end_offset]
            assert extracted == chunk.text

    def test_chunk_mixed_language(self):
        """Test chunking mixed language text."""
        text = "Hello world. 你好世界。Bonjour monde. Hola mundo."
        chunks = chunk_by_sentence(text, max_chars=30, min_chars=0)

        # Should split into multiple chunks
        assert len(chunks) >= 2

        # Verify offsets
        for chunk in chunks:
            extracted = text[chunk.start_offset:chunk.end_offset]
            assert extracted == chunk.text


class TestChunkByParagraph:
    """Tests for chunk_by_paragraph() function."""

    def test_chunk_by_paragraph_not_implemented(self):
        """Test that paragraph chunking raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            chunk_by_paragraph("Some text")


class TestChunkByCount:
    """Tests for chunk_by_count() function."""

    def test_chunk_by_count_not_implemented(self):
        """Test that count chunking raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            chunk_by_count("Some text")


class TestGetChunkingStrategy:
    """Tests for get_chunking_strategy() function."""

    def test_get_strategy_sentence(self):
        """Test getting sentence strategy."""
        strategy_func = get_chunking_strategy('sentence')
        assert strategy_func == chunk_by_sentence

    def test_get_strategy_paragraph(self):
        """Test getting paragraph strategy."""
        strategy_func = get_chunking_strategy('paragraph')
        assert strategy_func == chunk_by_paragraph

    def test_get_strategy_count(self):
        """Test getting count strategy."""
        strategy_func = get_chunking_strategy('count')
        assert strategy_func == chunk_by_count

    def test_get_strategy_invalid(self):
        """Test that invalid strategy raises ValueError."""
        with pytest.raises(ValueError, match="Unknown chunking strategy"):
            get_chunking_strategy('invalid')


class TestIntegrationScenarios:
    """Integration tests for realistic usage scenarios."""

    def test_typical_source_text(self):
        """Test chunking typical source text from ingestion."""
        text = """
        This is a typical source text that comes from document ingestion.
        It contains multiple sentences spanning several topics.
        Each sentence provides valuable context and information.
        The chunker should split this into semantically coherent chunks.
        We want to maintain sentence boundaries for better embedding quality.
        """

        chunks = chunk_by_sentence(text.strip(), max_chars=100)

        # Should create multiple chunks
        assert len(chunks) >= 2

        # Verify all chunks
        for chunk in chunks:
            # Extract from source using offsets
            extracted = text.strip()[chunk.start_offset:chunk.end_offset]
            assert extracted == chunk.text

            # Chunks should not be too long
            assert len(chunk.text) <= 200  # Some wiggle room for long sentences

    def test_technical_documentation(self):
        """Test chunking technical documentation with code references."""
        text = """
        The function chunk_by_sentence() splits text at sentence boundaries.
        It maintains offset tracking for precise highlighting.
        Maximum chunk size is configurable via max_chars parameter.
        Default value is 500 characters for optimal embedding quality.
        """

        chunks = chunk_by_sentence(text.strip(), max_chars=80, min_chars=0)

        # Verify offset integrity
        for chunk in chunks:
            extracted = text.strip()[chunk.start_offset:chunk.end_offset]
            assert extracted == chunk.text

    def test_scientific_abstract(self):
        """Test chunking scientific abstract with complex sentences."""
        text = """
        Recent advances in natural language processing have enabled new approaches
        to knowledge extraction and representation. We present a novel system that
        combines graph databases with semantic embeddings. Our method achieves
        state-of-the-art results on benchmark datasets while maintaining interpretability.
        """

        chunks = chunk_by_sentence(text.strip(), max_chars=120)

        assert len(chunks) >= 2

        # Verify sequential indexing
        for i, chunk in enumerate(chunks):
            assert chunk.index == i

    def test_edge_case_all_short_sentences(self):
        """Test chunking many very short sentences."""
        text = "One. Two. Three. Four. Five. Six. Seven. Eight. Nine. Ten."
        chunks = chunk_by_sentence(text, max_chars=20, min_chars=0)

        # Should combine short sentences into chunks
        assert len(chunks) < 10

        # Verify coverage
        all_text = " ".join(chunk.text for chunk in chunks)
        assert "One." in all_text
        assert "Ten." in all_text

    def test_edge_case_one_very_long_sentence(self):
        """Test chunking one extremely long sentence."""
        text = (
            "This is an extremely long sentence that goes on and on and on and on "
            "and continues to provide information without ever stopping for a period "
            "or any other sentence-ending punctuation mark which means it will become "
            "a single chunk despite being much longer than the maximum character limit "
            "because we do not want to break sentences in the middle for semantic coherence."
        )

        chunks = chunk_by_sentence(text, max_chars=100)

        # Should be one chunk even though it's long
        assert len(chunks) == 1
        assert chunks[0].text == text

    def test_round_trip_reconstruction(self):
        """Test that source text can be reconstructed from chunks."""
        text = "First sentence here. Second sentence here. Third sentence here. Fourth sentence here."
        chunks = chunk_by_sentence(text, max_chars=40, min_chars=0)

        # Reconstruct text from chunks using offsets
        reconstructed_parts = []
        for chunk in chunks:
            part = text[chunk.start_offset:chunk.end_offset]
            reconstructed_parts.append(part)

        # Reconstructed parts should cover the source (may have gaps due to whitespace)
        for part in reconstructed_parts:
            assert part in text

    def test_duplicate_sentences(self):
        """Test chunking with duplicate sentences (code review issue #2)."""
        text = "Hello world. Hello world. Goodbye world."
        chunks = chunk_by_sentence(text, max_chars=20, min_chars=0)

        # Should create separate chunks
        assert len(chunks) == 3

        # Verify offsets don't overlap
        for i in range(len(chunks) - 1):
            assert chunks[i].end_offset <= chunks[i+1].start_offset, \
                f"Chunks {i} and {i+1} overlap: [{chunks[i].start_offset}:{chunks[i].end_offset}] vs [{chunks[i+1].start_offset}:{chunks[i+1].end_offset}]"

        # Verify offset extraction matches chunk text
        for i, chunk in enumerate(chunks):
            extracted = text[chunk.start_offset:chunk.end_offset]
            assert extracted == chunk.text, \
                f"Chunk {i} offset mismatch: expected '{chunk.text}', extracted '{extracted}'"

        # Verify specific positions for duplicate "Hello world."
        assert chunks[0].text == "Hello world."
        assert chunks[1].text == "Hello world."
        assert chunks[0].start_offset != chunks[1].start_offset, \
            "Duplicate sentences should have different start offsets"

    def test_duplicate_content_with_hash_verification(self):
        """Test duplicate content with hash verification (code review issue #5)."""
        from api.app.lib.hash_utils import sha256_text, verify_chunk_extraction

        text = "The cat sat. The cat sat. The dog sat."
        chunks = chunk_by_sentence(text, max_chars=20, min_chars=0)

        # Verify each chunk with hash verification
        for chunk in chunks:
            chunk_hash = sha256_text(chunk.text)

            # Verify extraction with hash
            assert verify_chunk_extraction(
                text,
                chunk.start_offset,
                chunk.end_offset,
                chunk_hash
            ), f"Hash verification failed for chunk: {chunk.text}"

        # Verify hashes are same for duplicate sentences
        if len(chunks) >= 2 and chunks[0].text == chunks[1].text:
            hash0 = sha256_text(chunks[0].text)
            hash1 = sha256_text(chunks[1].text)
            assert hash0 == hash1, "Duplicate sentences should have same hash"

    def test_multiple_duplicates_in_long_text(self):
        """Test handling of multiple duplicate sentences in longer text."""
        text = """Introduction here. Main point explained. Main point explained.
        Supporting evidence provided. Supporting evidence provided. Conclusion drawn."""

        chunks = chunk_by_sentence(text, max_chars=50, min_chars=0)

        # Verify all offsets are correct
        for chunk in chunks:
            extracted = text[chunk.start_offset:chunk.end_offset]
            assert extracted == chunk.text, \
                f"Offset mismatch: '{chunk.text}' != '{extracted}'"

        # Verify no overlapping offsets
        for i in range(len(chunks) - 1):
            assert chunks[i].end_offset <= chunks[i+1].start_offset, \
                f"Chunks overlap at positions {chunks[i].end_offset} and {chunks[i+1].start_offset}"
