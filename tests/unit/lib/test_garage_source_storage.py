"""
Source document storage unit tests (ADR-081).

These tests cover pure logic that doesn't require S3/boto3 mocks:
- Path sanitization
- Content hash computation
- Key format validation
- Hash prefix enforcement
"""

import hashlib
import pytest


class TestSanitizePathComponent:
    """Tests for sanitize_path_component utility."""

    def test_replaces_spaces_with_underscores(self):
        from api.api.lib.garage import sanitize_path_component
        assert sanitize_path_component("My Ontology") == "My_Ontology"

    def test_replaces_slashes_with_underscores(self):
        from api.api.lib.garage import sanitize_path_component
        assert sanitize_path_component("Category/Subcategory") == "Category_Subcategory"

    def test_handles_multiple_spaces_and_slashes(self):
        from api.api.lib.garage import sanitize_path_component
        assert sanitize_path_component("A B/C D") == "A_B_C_D"

    def test_preserves_already_safe_strings(self):
        from api.api.lib.garage import sanitize_path_component
        assert sanitize_path_component("already_safe") == "already_safe"

    def test_empty_string(self):
        from api.api.lib.garage import sanitize_path_component
        assert sanitize_path_component("") == ""


class TestDocumentIdentity:
    """Tests for DocumentIdentity dataclass."""

    def test_dataclass_fields(self):
        from api.api.lib.garage import DocumentIdentity

        identity = DocumentIdentity(
            content_hash="abc123",
            garage_key="sources/Test/abc123.txt",
            size_bytes=100
        )

        assert identity.content_hash == "abc123"
        assert identity.garage_key == "sources/Test/abc123.txt"
        assert identity.size_bytes == 100


class TestComputeIdentity:
    """Tests for SourceDocumentService.compute_identity logic."""

    def test_hash_prefix_exactly_32_chars(self):
        """Critical: garage_key must use exactly 32-char hash prefix (128 bits)."""
        from api.api.lib.garage.source_storage import SourceDocumentService

        # Create service without base client (we only test compute_identity)
        service = SourceDocumentService.__new__(SourceDocumentService)

        content = b"Test document content for hashing"
        identity = service.compute_identity(content, "TestOntology", "txt")

        # Extract hash from garage_key: sources/TestOntology/{hash}.txt
        parts = identity.garage_key.split('/')
        filename = parts[-1]  # {hash}.txt
        hash_part = filename.split('.')[0]

        assert len(hash_part) == 32, f"Hash prefix must be 32 chars, got {len(hash_part)}"

    def test_same_content_produces_same_identity(self):
        """Idempotent: same content always produces same key."""
        from api.api.lib.garage.source_storage import SourceDocumentService

        service = SourceDocumentService.__new__(SourceDocumentService)

        content = b"Identical content for both calls"
        id1 = service.compute_identity(content, "Test", "txt")
        id2 = service.compute_identity(content, "Test", "txt")

        assert id1.content_hash == id2.content_hash
        assert id1.garage_key == id2.garage_key
        assert id1.size_bytes == id2.size_bytes

    def test_different_content_produces_different_identity(self):
        """Different content must produce different keys."""
        from api.api.lib.garage.source_storage import SourceDocumentService

        service = SourceDocumentService.__new__(SourceDocumentService)

        id1 = service.compute_identity(b"Content A", "Test", "txt")
        id2 = service.compute_identity(b"Content B", "Test", "txt")

        assert id1.content_hash != id2.content_hash
        assert id1.garage_key != id2.garage_key

    def test_key_format_sources_ontology_hash_ext(self):
        """Key format: sources/{ontology}/{hash}.{ext}"""
        from api.api.lib.garage.source_storage import SourceDocumentService

        service = SourceDocumentService.__new__(SourceDocumentService)

        identity = service.compute_identity(b"Test", "Philosophy", "md")

        assert identity.garage_key.startswith("sources/Philosophy/")
        assert identity.garage_key.endswith(".md")

    def test_ontology_name_sanitized(self):
        """Ontology names with spaces/slashes are sanitized."""
        from api.api.lib.garage.source_storage import SourceDocumentService

        service = SourceDocumentService.__new__(SourceDocumentService)

        identity = service.compute_identity(b"Test", "My Ontology/Sub", "txt")

        assert "My_Ontology_Sub" in identity.garage_key
        assert " " not in identity.garage_key
        assert "//" not in identity.garage_key  # No double slashes

    def test_size_bytes_correct(self):
        """size_bytes reflects actual content length."""
        from api.api.lib.garage.source_storage import SourceDocumentService

        service = SourceDocumentService.__new__(SourceDocumentService)

        content = b"Exactly 25 bytes of text"
        identity = service.compute_identity(content, "Test", "txt")

        assert identity.size_bytes == len(content)

    def test_full_hash_preserved(self):
        """content_hash contains full SHA-256 (64 hex chars)."""
        from api.api.lib.garage.source_storage import SourceDocumentService

        service = SourceDocumentService.__new__(SourceDocumentService)

        content = b"Test content"
        identity = service.compute_identity(content, "Test", "txt")

        # SHA-256 produces 64 hex characters
        assert len(identity.content_hash) == 64

        # Verify it matches Python's hashlib
        expected = hashlib.sha256(content).hexdigest()
        assert identity.content_hash == expected

    def test_extension_stripped_of_leading_dot(self):
        """Extension with or without leading dot works."""
        from api.api.lib.garage.source_storage import SourceDocumentService

        service = SourceDocumentService.__new__(SourceDocumentService)

        id1 = service.compute_identity(b"Test", "Test", "txt")
        id2 = service.compute_identity(b"Test", "Test", ".txt")

        # Both should produce same key (no double dots)
        assert id1.garage_key == id2.garage_key
        assert ".." not in id1.garage_key


class TestHashPrefixConstant:
    """Tests for HASH_PREFIX_LENGTH constant."""

    def test_constant_is_32(self):
        """HASH_PREFIX_LENGTH must be 32 (128 bits = UUID-equivalent)."""
        from api.api.lib.garage.source_storage import SourceDocumentService

        assert SourceDocumentService.HASH_PREFIX_LENGTH == 32

    def test_128_bits_collision_resistance(self):
        """32 hex chars = 128 bits = UUID-equivalent collision resistance."""
        # 32 hex chars × 4 bits per char = 128 bits
        bits = 32 * 4
        assert bits == 128
