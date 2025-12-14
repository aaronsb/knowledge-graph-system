"""
Garage Storage Services - Modular object storage for the knowledge graph (ADR-080).

This package provides focused storage services following the Single Responsibility
Principle. Each service handles one domain:

- GarageBaseClient: Core S3 operations, credentials, bucket management
- ImageStorageService: Image upload/download for multimodal ingestion (ADR-057)
- ProjectionStorageService: Embedding landscape projections (ADR-079)
- SourceDocumentService: Original document preservation (ADR-081)
- RetentionPolicyManager: Storage lifecycle and cleanup

Usage:
    # Preferred: Use service factory functions
    from api.api.lib.garage import get_image_storage, get_projection_storage

    images = get_image_storage()
    images.upload(ontology, source_id, image_bytes, filename)

    projections = get_projection_storage()
    data = projections.get(ontology)

    # Direct access (for testing or custom configuration)
    from api.api.lib.garage import GarageBaseClient, ImageStorageService

    base = GarageBaseClient(endpoint="http://custom:3900")
    images = ImageStorageService(base)

Backward Compatibility:
    The get_garage_client() function returns a GarageClient wrapper that
    provides the same interface as the original monolithic client.
"""

from typing import Optional

from .base import GarageBaseClient, sanitize_path_component
from .image_storage import ImageStorageService
from .projection_storage import ProjectionStorageService
from .source_storage import SourceDocumentService, DocumentIdentity, normalize_content_hash
from .retention import RetentionPolicyManager, CleanupResult, StorageStats


# Singleton instances
_base_client: Optional[GarageBaseClient] = None
_image_service: Optional[ImageStorageService] = None
_projection_service: Optional[ProjectionStorageService] = None
_source_service: Optional[SourceDocumentService] = None
_retention_manager: Optional[RetentionPolicyManager] = None


def get_base_client() -> GarageBaseClient:
    """
    Get or create the base Garage client singleton.

    Returns:
        GarageBaseClient instance
    """
    global _base_client
    if _base_client is None:
        _base_client = GarageBaseClient()
        _base_client.ensure_bucket_exists()
    return _base_client


def get_image_storage() -> ImageStorageService:
    """
    Get or create the image storage service singleton.

    Returns:
        ImageStorageService instance
    """
    global _image_service
    if _image_service is None:
        _image_service = ImageStorageService(get_base_client())
    return _image_service


def get_projection_storage() -> ProjectionStorageService:
    """
    Get or create the projection storage service singleton.

    Returns:
        ProjectionStorageService instance
    """
    global _projection_service
    if _projection_service is None:
        _projection_service = ProjectionStorageService(get_base_client())
    return _projection_service


def get_source_storage() -> SourceDocumentService:
    """
    Get or create the source document storage service singleton.

    Returns:
        SourceDocumentService instance
    """
    global _source_service
    if _source_service is None:
        _source_service = SourceDocumentService(get_base_client())
    return _source_service


def get_retention_manager() -> RetentionPolicyManager:
    """
    Get or create the retention policy manager singleton.

    Returns:
        RetentionPolicyManager instance
    """
    global _retention_manager
    if _retention_manager is None:
        _retention_manager = RetentionPolicyManager(get_base_client())
    return _retention_manager


class GarageClient:
    """
    Backward-compatible wrapper for the modular Garage services.

    This class provides the same interface as the original monolithic
    GarageClient, delegating to the appropriate service internally.

    New code should use the modular services directly via:
    - get_image_storage()
    - get_projection_storage()
    - get_source_storage()
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None
    ):
        """Initialize with custom configuration or use defaults."""
        self._base = GarageBaseClient(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket_name=bucket_name,
            region=region
        )
        self._images = ImageStorageService(self._base)
        self._projections = ProjectionStorageService(self._base)
        self._sources = SourceDocumentService(self._base)

    @property
    def client(self):
        """Access underlying boto3 client (for compatibility)."""
        return self._base.client

    @property
    def bucket_name(self):
        """Bucket name (for compatibility)."""
        return self._base.bucket_name

    @property
    def endpoint(self):
        """Endpoint URL (for compatibility)."""
        return self._base.endpoint

    # Bucket management
    def ensure_bucket_exists(self) -> None:
        self._base.ensure_bucket_exists()

    def health_check(self) -> bool:
        return self._base.health_check()

    # Image operations (ADR-057)
    def _build_object_key(self, ontology: str, source_id: str, file_extension: str) -> str:
        return self._images._build_object_key(ontology, source_id, file_extension)

    def _detect_content_type(self, filename: str, image_bytes: bytes) -> str:
        return self._images._detect_content_type(filename, image_bytes)

    def upload_image(self, ontology: str, source_id: str, image_bytes: bytes,
                     filename: str, metadata=None) -> str:
        return self._images.upload(ontology, source_id, image_bytes, filename, metadata)

    def download_image(self, object_key: str) -> bytes:
        return self._images.download(object_key)

    def delete_image(self, object_key: str) -> None:
        self._images.delete(object_key)

    def delete_images_by_prefix(self, prefix: str):
        return self._base.delete_by_prefix(prefix)

    def list_images(self, ontology=None):
        return self._images.list(ontology)

    def get_image_metadata(self, object_key: str):
        return self._images.get_metadata(object_key)

    # Projection operations (ADR-079)
    def _build_projection_key(self, ontology: str, embedding_source: str, timestamp=None) -> str:
        return self._projections._build_key(ontology, embedding_source, timestamp)

    def store_projection(self, ontology: str, embedding_source: str,
                        projection_data: dict, keep_history: bool = True) -> str:
        return self._projections.store(ontology, embedding_source, projection_data, keep_history)

    def get_projection(self, ontology: str, embedding_source: str = "concepts"):
        return self._projections.get(ontology, embedding_source)

    def get_projection_history(self, ontology: str, embedding_source: str = "concepts", limit: int = 10):
        return self._projections.get_history(ontology, embedding_source, limit)

    def delete_projection(self, ontology: str, embedding_source: str = "concepts") -> bool:
        return self._projections.delete(ontology, embedding_source)

    def delete_all_projections(self, ontology: str) -> int:
        return self._projections.delete_all(ontology)


def get_garage_client() -> GarageClient:
    """
    Get or create a backward-compatible Garage client.

    This function exists for backward compatibility. New code should use:
    - get_image_storage() for image operations
    - get_projection_storage() for projection operations
    - get_source_storage() for source document operations

    Returns:
        GarageClient instance (wrapper around modular services)
    """
    # Create a new wrapper each time (it uses the singleton base internally)
    client = GarageClient()
    client.ensure_bucket_exists()
    return client


__all__ = [
    # Base client
    'GarageBaseClient',
    'sanitize_path_component',

    # Services
    'ImageStorageService',
    'ProjectionStorageService',
    'SourceDocumentService',
    'RetentionPolicyManager',

    # Data classes
    'DocumentIdentity',
    'CleanupResult',
    'StorageStats',

    # Factory functions (preferred)
    'get_base_client',
    'get_image_storage',
    'get_projection_storage',
    'get_source_storage',
    'get_retention_manager',

    # Backward compatibility
    'GarageClient',
    'get_garage_client',
]
