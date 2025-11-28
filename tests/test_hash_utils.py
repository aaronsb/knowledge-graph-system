"""
Unit tests for hash utilities (ADR-068).

Tests SHA256 hashing and verification for source text embeddings.
"""

import pytest
from api.api.lib.hash_utils import (
    sha256_text,
    verify_source_hash,
    verify_chunk_hash,
    verify_chunk_extraction
)


class TestSha256Text:
    """Tests for sha256_text() function."""

    def test_sha256_text_basic(self):
        """Test basic SHA256 hashing."""
        text = "Hello, world!"
        hash_val = sha256_text(text)

        # SHA256 produces 64-character hex string
        assert len(hash_val) == 64
        assert all(c in '0123456789abcdef' for c in hash_val)

    def test_sha256_text_deterministic(self):
        """Test that same input produces same hash."""
        text = "Sample text for hashing"
        hash1 = sha256_text(text)
        hash2 = sha256_text(text)

        assert hash1 == hash2

    def test_sha256_text_different_inputs(self):
        """Test that different inputs produce different hashes."""
        text1 = "First text"
        text2 = "Second text"

        hash1 = sha256_text(text1)
        hash2 = sha256_text(text2)

        assert hash1 != hash2

    def test_sha256_text_empty_string(self):
        """Test hashing empty string."""
        hash_val = sha256_text("")

        # Empty string has known SHA256 hash
        expected = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert hash_val == expected

    def test_sha256_text_unicode(self):
        """Test hashing unicode text."""
        text = "Hello 世界 🌍"
        hash_val = sha256_text(text)

        # Should produce valid 64-char hex string
        assert len(hash_val) == 64
        assert all(c in '0123456789abcdef' for c in hash_val)

    def test_sha256_text_multiline(self):
        """Test hashing multiline text."""
        text = """Line 1
Line 2
Line 3"""
        hash_val = sha256_text(text)

        # Should produce valid hash
        assert len(hash_val) == 64

    def test_sha256_text_whitespace_sensitive(self):
        """Test that whitespace differences produce different hashes."""
        text1 = "Hello world"
        text2 = "Hello  world"  # Extra space

        hash1 = sha256_text(text1)
        hash2 = sha256_text(text2)

        assert hash1 != hash2

    def test_sha256_text_type_error(self):
        """Test that non-string input raises TypeError."""
        with pytest.raises(TypeError):
            sha256_text(123)

        with pytest.raises(TypeError):
            sha256_text(None)

        with pytest.raises(TypeError):
            sha256_text(b"bytes")


class TestVerifySourceHash:
    """Tests for verify_source_hash() function."""

    def test_verify_source_hash_valid(self):
        """Test verification with matching hash."""
        text = "Sample source text"
        hash_val = sha256_text(text)

        assert verify_source_hash(text, hash_val) is True

    def test_verify_source_hash_invalid(self):
        """Test verification with wrong hash."""
        text = "Sample source text"
        wrong_hash = sha256_text("Different text")

        assert verify_source_hash(text, wrong_hash) is False

    def test_verify_source_hash_none(self):
        """Test verification with None hash returns False."""
        text = "Sample source text"

        assert verify_source_hash(text, None) is False

    def test_verify_source_hash_empty_string(self):
        """Test verification with empty string."""
        text = ""
        hash_val = sha256_text(text)

        assert verify_source_hash(text, hash_val) is True

    def test_verify_source_hash_type_error_text(self):
        """Test that non-string source_text raises TypeError."""
        with pytest.raises(TypeError):
            verify_source_hash(123, "some_hash")

    def test_verify_source_hash_type_error_hash(self):
        """Test that non-string hash raises TypeError."""
        with pytest.raises(TypeError):
            verify_source_hash("text", 123)


class TestVerifyChunkHash:
    """Tests for verify_chunk_hash() function."""

    def test_verify_chunk_hash_valid(self):
        """Test verification with matching hash."""
        text = "Sample chunk text"
        hash_val = sha256_text(text)

        assert verify_chunk_hash(text, hash_val) is True

    def test_verify_chunk_hash_invalid(self):
        """Test verification with wrong hash."""
        text = "Sample chunk text"
        wrong_hash = sha256_text("Different text")

        assert verify_chunk_hash(text, wrong_hash) is False

    def test_verify_chunk_hash_none(self):
        """Test verification with None hash returns False."""
        text = "Sample chunk text"

        assert verify_chunk_hash(text, None) is False

    def test_verify_chunk_hash_empty_string(self):
        """Test verification with empty string."""
        text = ""
        hash_val = sha256_text(text)

        assert verify_chunk_hash(text, hash_val) is True

    def test_verify_chunk_hash_type_error_text(self):
        """Test that non-string chunk_text raises TypeError."""
        with pytest.raises(TypeError):
            verify_chunk_hash(123, "some_hash")

    def test_verify_chunk_hash_type_error_hash(self):
        """Test that non-string hash raises TypeError."""
        with pytest.raises(TypeError):
            verify_chunk_hash("text", 123)


class TestVerifyChunkExtraction:
    """Tests for verify_chunk_extraction() function."""

    def test_verify_chunk_extraction_valid(self):
        """Test verification with valid offsets and hash."""
        source = "The quick brown fox jumps over the lazy dog"
        chunk = source[4:9]  # "quick"
        chunk_hash = sha256_text(chunk)

        assert verify_chunk_extraction(source, 4, 9, chunk_hash) is True

    def test_verify_chunk_extraction_invalid_hash(self):
        """Test verification with wrong hash."""
        source = "The quick brown fox jumps over the lazy dog"
        wrong_hash = sha256_text("wrong")

        assert verify_chunk_extraction(source, 4, 9, wrong_hash) is False

    def test_verify_chunk_extraction_full_text(self):
        """Test extraction of entire source text."""
        source = "Complete source text"
        chunk_hash = sha256_text(source)

        assert verify_chunk_extraction(source, 0, len(source), chunk_hash) is True

    def test_verify_chunk_extraction_single_char(self):
        """Test extraction of single character."""
        source = "ABCDEFGH"
        chunk = source[3:4]  # "D"
        chunk_hash = sha256_text(chunk)

        assert verify_chunk_extraction(source, 3, 4, chunk_hash) is True

    def test_verify_chunk_extraction_negative_start(self):
        """Test that negative start_offset raises ValueError."""
        source = "Sample text"

        with pytest.raises(ValueError, match="start_offset must be >= 0"):
            verify_chunk_extraction(source, -1, 5, "hash")

    def test_verify_chunk_extraction_negative_end(self):
        """Test that negative end_offset raises ValueError."""
        source = "Sample text"

        with pytest.raises(ValueError, match="end_offset must be >= 0"):
            verify_chunk_extraction(source, 0, -1, "hash")

    def test_verify_chunk_extraction_inverted_offsets(self):
        """Test that start >= end raises ValueError."""
        source = "Sample text"

        with pytest.raises(ValueError, match="start_offset .* must be < end_offset"):
            verify_chunk_extraction(source, 5, 5, "hash")

        with pytest.raises(ValueError, match="start_offset .* must be < end_offset"):
            verify_chunk_extraction(source, 10, 5, "hash")

    def test_verify_chunk_extraction_end_exceeds_length(self):
        """Test that end_offset > len(source) raises ValueError."""
        source = "Sample text"  # Length 11

        with pytest.raises(ValueError, match="end_offset .* exceeds source_text length"):
            verify_chunk_extraction(source, 0, 100, "hash")

    def test_verify_chunk_extraction_unicode(self):
        """Test extraction with unicode text."""
        source = "Hello 世界 🌍 from Earth"
        chunk = source[6:8]  # "世界"
        chunk_hash = sha256_text(chunk)

        assert verify_chunk_extraction(source, 6, 8, chunk_hash) is True

    def test_verify_chunk_extraction_multiline(self):
        """Test extraction with multiline text."""
        source = """Line 1
Line 2
Line 3"""
        # Extract "Line 2\n"
        start = source.index("Line 2")
        end = start + len("Line 2\n")
        chunk = source[start:end]
        chunk_hash = sha256_text(chunk)

        assert verify_chunk_extraction(source, start, end, chunk_hash) is True

    def test_verify_chunk_extraction_type_error_source(self):
        """Test that non-string source_text raises TypeError."""
        with pytest.raises(TypeError):
            verify_chunk_extraction(123, 0, 5, "hash")

    def test_verify_chunk_extraction_type_error_hash(self):
        """Test that non-string hash raises TypeError."""
        with pytest.raises(TypeError):
            verify_chunk_extraction("text", 0, 4, 123)


class TestIntegrationScenarios:
    """Integration tests for realistic usage scenarios."""

    def test_source_embedding_workflow(self):
        """Test typical source embedding generation workflow."""
        # Source text from ingestion
        source_text = """This is a longer source text that would come from document ingestion.
It contains multiple sentences. Each sentence could be a separate chunk.
We'll extract a chunk and verify its hash matches the source."""

        # Generate source hash (stored in Source.content_hash)
        source_hash = sha256_text(source_text)

        # Extract chunk (e.g., second sentence)
        start = source_text.index("It contains")
        end = source_text.index("chunk.") + len("chunk.")
        chunk_text = source_text[start:end]

        # Generate chunk hash (stored in source_embeddings.chunk_hash)
        chunk_hash = sha256_text(chunk_text)

        # Verify source hash
        assert verify_source_hash(source_text, source_hash) is True

        # Verify chunk hash
        assert verify_chunk_hash(chunk_text, chunk_hash) is True

        # Verify chunk extraction
        assert verify_chunk_extraction(source_text, start, end, chunk_hash) is True

    def test_stale_embedding_detection(self):
        """Test detection of stale embeddings after source text changes."""
        # Original source text
        original_text = "This is the original source text."
        original_hash = sha256_text(original_text)

        # Source text changed
        modified_text = "This is the MODIFIED source text."
        modified_hash = sha256_text(modified_text)

        # Verify original hash against original text
        assert verify_source_hash(original_text, original_hash) is True

        # Verify original hash against modified text (should fail = stale)
        assert verify_source_hash(modified_text, original_hash) is False

        # Verify modified hash against modified text
        assert verify_source_hash(modified_text, modified_hash) is True

    def test_chunk_corruption_detection(self):
        """Test detection of chunk corruption."""
        source_text = "The quick brown fox jumps over the lazy dog"

        # Extract chunk correctly
        chunk_text = source_text[10:19]  # "brown fox"
        chunk_hash = sha256_text(chunk_text)

        # Verify correct chunk
        assert verify_chunk_extraction(source_text, 10, 19, chunk_hash) is True

        # Verify wrong offsets with same hash (corruption)
        assert verify_chunk_extraction(source_text, 11, 20, chunk_hash) is False

    def test_empty_source_with_chunks(self):
        """Test edge case of empty source (should not have chunks)."""
        source_text = ""
        source_hash = sha256_text(source_text)

        # Verify empty source hash
        assert verify_source_hash(source_text, source_hash) is True

        # Cannot extract chunks from empty source
        with pytest.raises(ValueError):
            verify_chunk_extraction(source_text, 0, 1, "hash")
