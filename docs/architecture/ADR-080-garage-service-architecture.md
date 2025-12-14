# ADR-080: Garage Service Architecture

**Status:** Proposed
**Date:** 2025-12-14
**Deciders:** @aaronsb, @claude
**Related ADRs:** ADR-057 (Multimodal Image Ingestion), ADR-079 (Projection Artifact Storage), ADR-081 (Source Document Lifecycle)
**Closes:** #175

## Context

The `GarageClient` class has grown to 732 lines handling multiple distinct responsibilities:
- Image storage (ADR-057)
- Projection storage (ADR-079)
- Credential management
- S3 client initialization

This violates the Single Responsibility Principle (#175) and makes the code harder to maintain and test.

This ADR focuses on **clean code refactoring** - establishing a modular service architecture that future features (like source document storage in ADR-081) can build upon.

**Scope clarification:**
- **ADR-080 (this)**: Service architecture, SRP refactor, retention policies
- **ADR-081**: Source document lifecycle, deduplication, versioning, regeneration

## Decision

### 1. Modular Service Architecture

Refactor `garage_client.py` (732 lines) into focused service modules:

```
api/api/lib/garage/
├── __init__.py                 # Re-exports for backward compatibility
├── base.py                     # GarageBaseClient (S3 ops, credentials)
├── image_storage.py            # ImageStorageService (ADR-057)
├── projection_storage.py       # ProjectionStorageService (ADR-079)
├── source_storage.py           # SourceDocumentService (NEW)
└── retention.py                # RetentionPolicyManager (NEW)
```

Each service follows the **Facade pattern** established by `GraphQueryFacade` (ADR-048).

### 2. GarageBaseClient

Core S3 operations shared by all services:

```python
class GarageBaseClient:
    """
    Base Garage client providing core S3 operations.

    All storage services depend on this client for:
    - Credential management (encrypted store or env fallback)
    - S3 client initialization with retry config
    - Bucket management
    - Health checks
    """

    def __init__(self, endpoint=None, bucket_name=None):
        # Load credentials (not stored as instance attrs)
        # Initialize boto3 with retry config
        pass

    @property
    def client(self) -> boto3.client:
        """S3 client instance."""
        pass

    def ensure_bucket_exists(self) -> None:
        """Create bucket if it doesn't exist."""
        pass

    def health_check(self) -> bool:
        """Verify Garage connectivity."""
        pass

    def put_object(self, key: str, data: bytes, content_type: str) -> None:
        """Store object with standard error handling."""
        pass

    def get_object(self, key: str) -> Optional[bytes]:
        """Retrieve object, returns None if not found."""
        pass

    def delete_object(self, key: str) -> bool:
        """Delete object, returns success status."""
        pass

    def list_objects(self, prefix: str) -> List[Dict]:
        """List objects with prefix."""
        pass
```

### 3. Storage Services

Each service encapsulates domain-specific logic:

```python
class ImageStorageService:
    """Image storage operations (ADR-057)."""

    def __init__(self, base: GarageBaseClient):
        self.base = base

    def upload_image(self, ontology, source_id, image_bytes, filename) -> str
    def download_image(self, object_key) -> bytes
    def delete_image(self, object_key) -> None
    def list_images(self, ontology=None) -> List[Dict]
    def get_image_metadata(self, object_key) -> Dict


class ProjectionStorageService:
    """Projection artifact storage (ADR-079)."""

    def __init__(self, base: GarageBaseClient):
        self.base = base

    def store(self, ontology, embedding_source, data, keep_history=True) -> str
    def get(self, ontology, embedding_source="concepts") -> Optional[Dict]
    def get_history(self, ontology, embedding_source="concepts", limit=10) -> List
    def delete(self, ontology, embedding_source="concepts") -> bool
    def delete_all(self, ontology) -> int


class SourceDocumentService:
    """Source document storage (NEW - #172)."""

    def __init__(self, base: GarageBaseClient):
        self.base = base

    def store(self, ontology, source_id, content, filename=None) -> str
    def get(self, ontology, source_id) -> Optional[str]
    def delete(self, ontology, source_id) -> bool
    def list(self, ontology) -> List[Dict]
```

### 4. Source Document Storage

Store original text documents in Garage alongside images:

**Key format:**
```
sources/{ontology}/{source_id}.txt
sources/{ontology}/{source_id}.md
sources/{ontology}/{source_id}.json  # For structured content
```

**Use cases:**
- Re-process documents with improved extraction
- Audit trail for ingested content
- Export/backup original materials
- Enable document search and retrieval

**Integration with Source nodes:**
```cypher
// Source node gains optional garage_key property
(:Source {
    source_id: "src-123",
    document: "Philosophy",
    full_text: "...",              // Still stored in graph for queries
    garage_key: "sources/Philosophy/src-123.txt"  // Optional link to original
})
```

### 5. Retention Policies

Configure retention for different artifact types:

```python
class RetentionPolicyManager:
    """Manage artifact retention and cleanup."""

    DEFAULT_POLICIES = {
        "projections": {
            "keep_latest": True,           # Always keep latest.json
            "history_count": 10,           # Keep last N snapshots
            "history_max_age_days": 30,    # Delete older than N days
        },
        "sources": {
            "keep_always": True,           # Never auto-delete sources
        },
        "images": {
            "keep_always": True,           # Never auto-delete images
        }
    }

    def __init__(self, base: GarageBaseClient, policies=None):
        self.base = base
        self.policies = policies or self.DEFAULT_POLICIES

    def cleanup_projections(self, ontology: str) -> CleanupResult:
        """Apply retention policy to projection history."""
        pass

    def cleanup_all(self) -> Dict[str, CleanupResult]:
        """Run cleanup across all ontologies."""
        pass

    def get_storage_stats(self) -> StorageStats:
        """Get storage usage by category."""
        pass
```

**Cleanup can be triggered:**
- Manually via API endpoint
- Scheduled via job launcher (like ProjectionLauncher)
- After ingestion jobs complete

### 6. Backward Compatibility

Maintain `get_garage_client()` function for existing code:

```python
# api/api/lib/garage/__init__.py

from .base import GarageBaseClient
from .image_storage import ImageStorageService
from .projection_storage import ProjectionStorageService
from .source_storage import SourceDocumentService
from .retention import RetentionPolicyManager

# Singleton instances
_base_client: Optional[GarageBaseClient] = None
_image_service: Optional[ImageStorageService] = None
_projection_service: Optional[ProjectionStorageService] = None
_source_service: Optional[SourceDocumentService] = None


def get_garage_client() -> GarageBaseClient:
    """Get base Garage client (backward compatible)."""
    global _base_client
    if _base_client is None:
        _base_client = GarageBaseClient()
    return _base_client


def get_image_storage() -> ImageStorageService:
    """Get image storage service."""
    global _image_service
    if _image_service is None:
        _image_service = ImageStorageService(get_garage_client())
    return _image_service


def get_projection_storage() -> ProjectionStorageService:
    """Get projection storage service."""
    global _projection_service
    if _projection_service is None:
        _projection_service = ProjectionStorageService(get_garage_client())
    return _projection_service


def get_source_storage() -> SourceDocumentService:
    """Get source document storage service."""
    global _source_service
    if _source_service is None:
        _source_service = SourceDocumentService(get_garage_client())
    return _source_service
```

### 7. API Endpoints

New endpoints for source document and retention management:

```python
# Source documents
GET  /sources/{ontology}/{source_id}/document  # Retrieve original document
POST /sources/{ontology}/{source_id}/document  # Store document (during ingestion)

# Retention/cleanup
GET  /admin/storage/stats                      # Storage usage by category
POST /admin/storage/cleanup                    # Run retention cleanup
GET  /admin/storage/retention                  # Get retention policies
PUT  /admin/storage/retention                  # Update retention policies
```

## Implementation Plan

### Phase 1: Refactor (SRP)
1. Create `api/api/lib/garage/` module structure
2. Extract `GarageBaseClient` from current code
3. Extract `ImageStorageService`
4. Extract `ProjectionStorageService`
5. Add backward-compatible `get_garage_client()`
6. Update all import sites
7. Verify existing tests pass

### Phase 2: Source Documents
1. Implement `SourceDocumentService`
2. Add `garage_key` property to Source node schema
3. Update ingestion worker to optionally store source docs
4. Add API endpoints for document retrieval
5. Add tests

### Phase 3: Retention
1. Implement `RetentionPolicyManager`
2. Add retention configuration to system settings
3. Create cleanup job launcher
4. Add admin API endpoints
5. Add tests

## Consequences

### Positive
1. **Single Responsibility**: Each service has one reason to change
2. **Testability**: Services can be unit tested in isolation
3. **Extensibility**: Easy to add new storage services
4. **Source Preservation**: Original documents available for re-processing
5. **Storage Management**: Retention policies prevent unbounded growth

### Negative
1. **Migration Effort**: Need to update all import sites
2. **More Files**: 6 files instead of 1 (but each is focused)
3. **Indirection**: Slightly more complex initialization

### Neutral
1. **Same External API**: `get_garage_client()` still works
2. **Same Storage Format**: No changes to S3 key structure
3. **Additive**: Source storage is optional, not required

## Migration

No database migration needed. Changes are code-only:

1. Create new module structure
2. Move code to appropriate services
3. Update imports (can be done incrementally)
4. Old `garage_client.py` becomes thin wrapper during transition

## References

- Issue #172: Expand Garage storage for projections and source documents
- Issue #175: Refactor GarageClient to follow Single Responsibility Principle
- ADR-048: GraphQueryFacade (similar pattern)
- ADR-057: Multimodal Image Ingestion
- ADR-079: Projection Artifact Storage
