"""
Image Storage Service - Multimodal image storage (ADR-057, ADR-080).

This service handles image upload, download, and management for the
multimodal ingestion pipeline. Images are stored with source-ID based
object keys for direct association with Source nodes.

Key format: images/{ontology}/{source_id}.{ext}
"""

import os
import logging
import mimetypes
from typing import Optional, Dict, List, Any

from .base import GarageBaseClient, sanitize_path_component

logger = logging.getLogger(__name__)


class ImageStorageService:
    """
    Image storage operations for multimodal ingestion (ADR-057).

    Provides upload, download, delete, and listing operations for images
    associated with Source nodes in the knowledge graph.
    """

    def __init__(self, base: GarageBaseClient):
        """
        Initialize image storage service.

        Args:
            base: GarageBaseClient instance for S3 operations
        """
        self.base = base

    def _build_object_key(self, ontology: str, source_id: str, file_extension: str) -> str:
        """
        Build object key for an image.

        Format: images/{ontology}/{source_id}.{ext}

        Args:
            ontology: Ontology name
            source_id: Source ID from database
            file_extension: File extension (jpg, png, etc.)

        Returns:
            Object key string
        """
        safe_ontology = sanitize_path_component(ontology)
        ext = file_extension.lstrip(".")
        return f"images/{safe_ontology}/{source_id}.{ext}"

    def _detect_content_type(self, filename: str, image_bytes: bytes) -> str:
        """
        Detect content type from filename and/or magic bytes.

        Args:
            filename: Original filename
            image_bytes: Image binary data

        Returns:
            MIME type string (e.g., 'image/jpeg')
        """
        # Try to detect from filename extension
        content_type, _ = mimetypes.guess_type(filename)

        if content_type and content_type.startswith("image/"):
            return content_type

        # Fall back to magic byte detection
        if image_bytes.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        elif image_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        elif image_bytes.startswith(b'GIF87a') or image_bytes.startswith(b'GIF89a'):
            return 'image/gif'
        elif image_bytes.startswith(b'RIFF') and len(image_bytes) > 12 and image_bytes[8:12] == b'WEBP':
            return 'image/webp'
        elif image_bytes.startswith(b'BM'):
            return 'image/bmp'

        logger.warning(f"Could not detect content type for {filename}, defaulting to image/jpeg")
        return 'image/jpeg'

    def upload(
        self,
        ontology: str,
        source_id: str,
        image_bytes: bytes,
        filename: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload an image to Garage.

        Args:
            ontology: Ontology name
            source_id: Source ID from database
            image_bytes: Image binary data
            filename: Original filename (used for content-type detection)
            metadata: Optional custom metadata

        Returns:
            Object key of uploaded image

        Raises:
            ClientError: If upload fails
        """
        content_type = self._detect_content_type(filename, image_bytes)

        # Extract file extension
        file_extension = os.path.splitext(filename)[1].lstrip(".")
        if not file_extension:
            extension_map = {
                'image/jpeg': 'jpg',
                'image/png': 'png',
                'image/gif': 'gif',
                'image/webp': 'webp',
                'image/bmp': 'bmp'
            }
            file_extension = extension_map.get(content_type, 'jpg')

        object_key = self._build_object_key(ontology, source_id, file_extension)

        upload_metadata = metadata.copy() if metadata else {}
        upload_metadata['original-filename'] = filename

        self.base.put_object(object_key, image_bytes, content_type, upload_metadata)
        logger.info(f"Uploaded image: {object_key} ({len(image_bytes)} bytes)")

        return object_key

    def download(self, object_key: str) -> bytes:
        """
        Download an image from Garage.

        Args:
            object_key: Object key (from upload return value or database)

        Returns:
            Image binary data

        Raises:
            ClientError: If download fails or object not found
        """
        data = self.base.get_object(object_key)
        if data is None:
            from botocore.exceptions import ClientError
            raise ClientError(
                {'Error': {'Code': 'NoSuchKey', 'Message': 'Object not found'}},
                'GetObject'
            )

        logger.info(f"Downloaded image: {object_key} ({len(data)} bytes)")
        return data

    def delete(self, object_key: str) -> None:
        """
        Delete an image from Garage.

        Args:
            object_key: Object key to delete

        Raises:
            ClientError: If deletion fails
        """
        self.base.delete_object(object_key)
        logger.info(f"Deleted image: {object_key}")

    def delete_by_ontology(self, ontology: str) -> List[str]:
        """
        Delete all images for an ontology.

        Args:
            ontology: Ontology name

        Returns:
            List of deleted object keys
        """
        safe_ontology = sanitize_path_component(ontology)
        prefix = f"images/{safe_ontology}/"
        deleted = self.base.delete_by_prefix(prefix)
        logger.info(f"Deleted {len(deleted)} images for ontology '{ontology}'")
        return deleted

    def list(self, ontology: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        List images, optionally filtered by ontology.

        Args:
            ontology: Optional ontology name to filter by

        Returns:
            List of dicts with object metadata
        """
        if ontology:
            safe_ontology = sanitize_path_component(ontology)
            prefix = f"images/{safe_ontology}/"
        else:
            prefix = "images/"

        objects = self.base.list_objects(prefix)
        logger.info(f"Listed {len(objects)} images (ontology: {ontology or 'all'})")
        return objects

    def get_metadata(self, object_key: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for an image without downloading it.

        Args:
            object_key: Object key

        Returns:
            Dict with metadata or None if not found
        """
        return self.base.head_object(object_key)
