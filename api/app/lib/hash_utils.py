"""
Hash utilities for source text embeddings (ADR-068).

Provides SHA256 hashing and verification functions for:
- Source text content (full_text)
- Embedding chunk content (chunk_text)

Used for referential integrity and stale embedding detection.
"""

import hashlib
from typing import Optional


def sha256_text(text: str) -> str:
    """
    Calculate SHA256 hash of text content.

    Args:
        text: Text content to hash

    Returns:
        Hex-encoded SHA256 hash string (64 characters)

    Example:
        >>> sha256_text("Hello, world!")
        '315f5bdb76d078c43b8ac0064e4a0164612b1fce77c869345bfc94c75894edd3'
    """
    if not isinstance(text, str):
        raise TypeError(f"Expected str, got {type(text).__name__}")

    # Encode to UTF-8 bytes and hash
    text_bytes = text.encode('utf-8')
    hash_obj = hashlib.sha256(text_bytes)

    return hash_obj.hexdigest()


def verify_source_hash(source_text: str, expected_hash: Optional[str]) -> bool:
    """
    Verify that source text matches expected hash.

    Args:
        source_text: Full source text to verify
        expected_hash: Expected SHA256 hash (or None)

    Returns:
        True if hash matches, False otherwise
        If expected_hash is None, returns False (no hash to verify)

    Example:
        >>> text = "Sample source text"
        >>> hash_val = sha256_text(text)
        >>> verify_source_hash(text, hash_val)
        True
        >>> verify_source_hash(text, "wrong_hash")
        False
        >>> verify_source_hash(text, None)
        False
    """
    if expected_hash is None:
        return False

    if not isinstance(source_text, str):
        raise TypeError(f"Expected str for source_text, got {type(source_text).__name__}")

    if not isinstance(expected_hash, str):
        raise TypeError(f"Expected str for expected_hash, got {type(expected_hash).__name__}")

    actual_hash = sha256_text(source_text)
    return actual_hash == expected_hash


def verify_chunk_hash(chunk_text: str, expected_hash: Optional[str]) -> bool:
    """
    Verify that chunk text matches expected hash.

    Args:
        chunk_text: Chunk text to verify
        expected_hash: Expected SHA256 hash (or None)

    Returns:
        True if hash matches, False otherwise
        If expected_hash is None, returns False (no hash to verify)

    Example:
        >>> text = "Sample chunk text"
        >>> hash_val = sha256_text(text)
        >>> verify_chunk_hash(text, hash_val)
        True
        >>> verify_chunk_hash(text, "wrong_hash")
        False
        >>> verify_chunk_hash(text, None)
        False
    """
    # Same implementation as verify_source_hash (semantic naming for clarity)
    if expected_hash is None:
        return False

    if not isinstance(chunk_text, str):
        raise TypeError(f"Expected str for chunk_text, got {type(chunk_text).__name__}")

    if not isinstance(expected_hash, str):
        raise TypeError(f"Expected str for expected_hash, got {type(expected_hash).__name__}")

    actual_hash = sha256_text(chunk_text)
    return actual_hash == expected_hash


def verify_chunk_extraction(
    source_text: str,
    start_offset: int,
    end_offset: int,
    expected_chunk_hash: str
) -> bool:
    """
    Verify that chunk extracted from source matches expected hash.

    This combines offset extraction and hash verification in one call.
    Useful for validating stored embeddings against current source text.

    Args:
        source_text: Full source text
        start_offset: Start character offset (0-based, inclusive)
        end_offset: End character offset (0-based, exclusive)
        expected_chunk_hash: Expected SHA256 hash of extracted chunk

    Returns:
        True if extracted chunk matches expected hash, False otherwise

    Raises:
        ValueError: If offsets are invalid (negative, out of bounds, or inverted)

    Example:
        >>> source = "The quick brown fox jumps over the lazy dog"
        >>> chunk = source[4:9]  # "quick"
        >>> chunk_hash = sha256_text(chunk)
        >>> verify_chunk_extraction(source, 4, 9, chunk_hash)
        True
        >>> verify_chunk_extraction(source, 4, 9, "wrong_hash")
        False
    """
    if not isinstance(source_text, str):
        raise TypeError(f"Expected str for source_text, got {type(source_text).__name__}")

    if not isinstance(expected_chunk_hash, str):
        raise TypeError(f"Expected str for expected_chunk_hash, got {type(expected_chunk_hash).__name__}")

    # Validate offsets
    if start_offset < 0:
        raise ValueError(f"start_offset must be >= 0, got {start_offset}")

    if end_offset < 0:
        raise ValueError(f"end_offset must be >= 0, got {end_offset}")

    if start_offset >= end_offset:
        raise ValueError(f"start_offset ({start_offset}) must be < end_offset ({end_offset})")

    if end_offset > len(source_text):
        raise ValueError(f"end_offset ({end_offset}) exceeds source_text length ({len(source_text)})")

    # Extract chunk
    extracted_chunk = source_text[start_offset:end_offset]

    # Verify hash
    return verify_chunk_hash(extracted_chunk, expected_chunk_hash)
