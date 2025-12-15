"""
Source Document Storage Service - Original document preservation (ADR-081, ADR-080).

This service handles storage of original source documents before ingestion.
Documents are stored content-addressed using SHA-256 hashes, enabling:
- Deduplication (same content = same key)
- Model evolution insurance (re-extract with future LLMs)
- FUSE filesystem support (ADR-069)

Key format: sources/{ontology}/{content_hash[:32]}.{ext}

The 32-character hash prefix (128 bits) provides UUID-equivalent collision
resistance for a future sharded universe of knowledge graphs.
"""

import hashlib
import logging
from typing import Optional, Dict, List, Any
from dataclasses import dataclass

from .base import GarageBaseClient, sanitize_path_component

logger = logging.getLogger(__name__)


def normalize_content_hash(hash_value: str) -> str:
    """
    Normalize content hash to raw hex format (no prefix).

    Handles both formats:
    - "sha256:abc123..." → "abc123..."
    - "abc123..." → "abc123..."

    Args:
        hash_value: Hash with or without "sha256:" prefix

    Returns:
        Raw 64-character hex hash

    Raises:
        ValueError: If hash is None, empty, wrong length, or not valid hex
    """
    if not hash_value:
        raise ValueError("Hash value cannot be None or empty")

    if hash_value.startswith("sha256:"):
        normalized = hash_value[7:]  # Strip "sha256:" prefix
    else:
        normalized = hash_value

    if len(normalized) != 64:
        raise ValueError(f"Invalid hash length: expected 64 chars, got {len(normalized)}")

    try:
        int(normalized, 16)  # Verify it's valid hex
    except ValueError:
        raise ValueError(f"Invalid hex format in hash: {normalized[:20]}...")

    return normalized


@dataclass
class DocumentIdentity:
    """Content-based identity for a document."""
    content_hash: str       # Full SHA-256 hex digest
    garage_key: str         # Object key in Garage
    size_bytes: int         # Document size


@dataclass
class SourceMetadata:
    """
    Rich metadata for source documents (FUSE-friendly).

    This metadata is stored in S3 object headers for fast retrieval
    without database queries. Useful for FUSE filesystem operations
    where stat() calls need file attributes quickly.

    All fields are optional - only non-None values are stored.
    """
    user_id: Optional[int] = None           # User ID who ingested
    username: Optional[str] = None          # Username for display
    source_type: Optional[str] = None       # file, url, or text
    file_path: Optional[str] = None         # Original file path
    source_url: Optional[str] = None        # Source URL (for url type)
    hostname: Optional[str] = None          # Source machine hostname
    ingested_at: Optional[str] = None       # ISO 8601 timestamp


class SourceDocumentService:
    """
    Source document storage for ingestion pipeline (ADR-081).

    Stores original documents in Garage BEFORE ingestion, enabling:
    - Re-extraction with improved models (model evolution insurance)
    - Strategy experimentation (re-ingest with different matching modes)
    - FUSE filesystem document retrieval (ADR-069)

    Documents are content-addressed using SHA-256 hashes for natural
    deduplication and collision-resistant keys.
    """

    def __init__(self, base: GarageBaseClient):
        """
        Initialize source document storage service.

        Args:
            base: GarageBaseClient instance for S3 operations
        """
        self.base = base

    # Hash prefix length for garage keys (128 bits = 32 hex chars)
    # This provides UUID-equivalent collision resistance for a sharded universe.
    # SHA-256 always produces 64 hex chars, so [:32] is always valid.
    HASH_PREFIX_LENGTH = 32

    def compute_identity(
        self,
        content: bytes,
        ontology: str,
        extension: str = "txt",
        precomputed_hash: Optional[str] = None
    ) -> DocumentIdentity:
        """
        Compute content-based identity for a document.

        The garage_key uses the first 32 characters of the SHA-256 hash
        (128 bits = UUID-equivalent collision resistance).

        Args:
            content: Document content as bytes
            ontology: Ontology name
            extension: File extension (default: txt)
            precomputed_hash: Optional pre-computed hash (with or without "sha256:" prefix)
                             Avoids recomputing hash if already known from dedup check.

        Returns:
            DocumentIdentity with hash, garage_key, and size
        """
        if precomputed_hash:
            # Use provided hash, normalizing to raw format
            content_hash = normalize_content_hash(precomputed_hash)
        else:
            # Compute fresh hash
            content_hash = hashlib.sha256(content).hexdigest()

        safe_ontology = sanitize_path_component(ontology)
        ext = extension.lstrip(".")

        # Enforce exact hash prefix length (defense against accidental changes)
        hash_prefix = content_hash[:self.HASH_PREFIX_LENGTH]
        assert len(hash_prefix) == self.HASH_PREFIX_LENGTH, \
            f"Hash prefix must be exactly {self.HASH_PREFIX_LENGTH} chars, got {len(hash_prefix)}"

        garage_key = f"sources/{safe_ontology}/{hash_prefix}.{ext}"

        return DocumentIdentity(
            content_hash=content_hash,
            garage_key=garage_key,
            size_bytes=len(content)
        )

    def store(
        self,
        content: bytes,
        ontology: str,
        original_filename: Optional[str] = None,
        extension: str = "txt",
        precomputed_hash: Optional[str] = None,
        source_metadata: Optional[SourceMetadata] = None
    ) -> DocumentIdentity:
        """
        Store a source document in Garage.

        This should be called BEFORE ingestion begins (pre-ingestion storage).
        The garage_key can then be associated with Source nodes created
        during extraction.

        Args:
            content: Document content as bytes
            ontology: Ontology name
            original_filename: Original filename for metadata (optional)
            extension: File extension (default: txt)
            precomputed_hash: Optional pre-computed hash (with or without "sha256:" prefix)
                             Avoids recomputing hash if already known from dedup check.
            source_metadata: Optional rich metadata for FUSE filesystem support.
                            Includes user_id, username, source_type, file_path,
                            source_url, hostname, ingested_at.

        Returns:
            DocumentIdentity with hash and garage_key

        Raises:
            ClientError: If storage fails
        """
        identity = self.compute_identity(content, ontology, extension, precomputed_hash)

        # Build S3 metadata - only include non-None values
        metadata = {
            'ontology': ontology,
            'content-hash': identity.content_hash,
            'size-bytes': str(identity.size_bytes)
        }
        if original_filename:
            metadata['original-filename'] = original_filename

        # Add rich metadata for FUSE support (only non-None values)
        if source_metadata:
            if source_metadata.user_id is not None:
                metadata['user-id'] = str(source_metadata.user_id)
            if source_metadata.username:
                metadata['username'] = source_metadata.username
            if source_metadata.source_type:
                metadata['source-type'] = source_metadata.source_type
            if source_metadata.file_path:
                metadata['file-path'] = source_metadata.file_path
            if source_metadata.source_url:
                metadata['source-url'] = source_metadata.source_url
            if source_metadata.hostname:
                metadata['hostname'] = source_metadata.hostname
            if source_metadata.ingested_at:
                metadata['ingested-at'] = source_metadata.ingested_at

        # Determine content type
        content_type = 'text/plain'
        if extension in ('md', 'markdown'):
            content_type = 'text/markdown'
        elif extension == 'json':
            content_type = 'application/json'
        elif extension == 'html':
            content_type = 'text/html'

        self.base.put_object(identity.garage_key, content, content_type, metadata)
        logger.info(f"Stored source document: {identity.garage_key} ({identity.size_bytes} bytes)")

        return identity

    def get(self, garage_key: str) -> Optional[bytes]:
        """
        Retrieve a source document from Garage.

        Args:
            garage_key: Object key (from DocumentIdentity or Source node)

        Returns:
            Document content as bytes, or None if not found
        """
        data = self.base.get_object(garage_key)
        if data:
            logger.info(f"Retrieved source document: {garage_key} ({len(data)} bytes)")
        return data

    def get_by_hash(self, ontology: str, content_hash: str, extension: str = "txt") -> Optional[bytes]:
        """
        Retrieve a source document by its content hash.

        Args:
            ontology: Ontology name
            content_hash: Full or partial (32+ chars) SHA-256 hash
            extension: File extension (default: txt)

        Returns:
            Document content as bytes, or None if not found
        """
        safe_ontology = sanitize_path_component(ontology)
        hash_prefix = content_hash[:self.HASH_PREFIX_LENGTH]
        garage_key = f"sources/{safe_ontology}/{hash_prefix}.{extension.lstrip('.')}"
        return self.get(garage_key)

    def exists(self, garage_key: str) -> bool:
        """
        Check if a source document exists without downloading it.

        Args:
            garage_key: Object key

        Returns:
            True if document exists
        """
        metadata = self.base.head_object(garage_key)
        return metadata is not None

    def exists_by_hash(self, ontology: str, content_hash: str, extension: str = "txt") -> bool:
        """
        Check if a source document exists by its content hash.

        Useful for deduplication checks before ingestion.

        Args:
            ontology: Ontology name
            content_hash: Full or partial (32+ chars) SHA-256 hash
            extension: File extension (default: txt)

        Returns:
            True if document exists
        """
        safe_ontology = sanitize_path_component(ontology)
        hash_prefix = content_hash[:self.HASH_PREFIX_LENGTH]
        garage_key = f"sources/{safe_ontology}/{hash_prefix}.{extension.lstrip('.')}"
        return self.exists(garage_key)

    def delete(self, garage_key: str) -> bool:
        """
        Delete a source document from Garage.

        Args:
            garage_key: Object key

        Returns:
            True if deleted, False if not found
        """
        result = self.base.delete_object(garage_key)
        if result:
            logger.info(f"Deleted source document: {garage_key}")
        return result

    def delete_by_ontology(self, ontology: str) -> List[str]:
        """
        Delete all source documents for an ontology.

        Args:
            ontology: Ontology name

        Returns:
            List of deleted object keys
        """
        safe_ontology = sanitize_path_component(ontology)
        prefix = f"sources/{safe_ontology}/"
        deleted = self.base.delete_by_prefix(prefix)
        logger.info(f"Deleted {len(deleted)} source documents for ontology '{ontology}'")
        return deleted

    def list(self, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List source documents, optionally filtered by ontology.

        Args:
            ontology: Optional ontology name to filter by

        Returns:
            List of dicts with object metadata
        """
        if ontology:
            safe_ontology = sanitize_path_component(ontology)
            prefix = f"sources/{safe_ontology}/"
        else:
            prefix = "sources/"

        objects = self.base.list_objects(prefix)
        logger.info(f"Listed {len(objects)} source documents (ontology: {ontology or 'all'})")
        return objects

    def get_metadata(self, garage_key: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a source document without downloading it.

        Args:
            garage_key: Object key

        Returns:
            Dict with metadata or None if not found
        """
        return self.base.head_object(garage_key)


# TODO (ADR-081 Future Considerations): Graph → Garage Reconstruction
#
# The offset information stored in Source nodes (char_offset_start,
# char_offset_end, chunk_index) theoretically enables reconstructing
# original documents from graph chunks. This would allow recovery if
# Garage is lost but the graph is intact.
#
# Not implemented because:
# - Rare scenario (Garage lost, graph intact, no Garage backup)
# - Garage backups are simpler and more reliable
# - Adds complexity without clear near-term value
#
# If needed later, the implementation would:
# 1. Query all Source nodes for a garage_key, ordered by chunk_index
# 2. Handle chunk overlaps using char_offset_start to deduplicate
# 3. Concatenate to reconstruct original document
#
# See ADR-081 "Future Considerations" section for details.
