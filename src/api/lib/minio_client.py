"""
MinIO Client - S3-compatible object storage for image assets (ADR-057)

This module provides a clean interface for storing and retrieving images in MinIO.
Uses source-ID based object keys for 1:1 mapping with database records.

Object Key Structure:
    images/{ontology}/{source_id}.{ext}

Examples:
    images/Research Notes/src_abc123.jpg
    images/Meeting Notes/src_xyz789.png

Security:
    MinIO credentials are stored encrypted in PostgreSQL (ADR-031) using the same
    pattern as OpenAI/Anthropic API keys. This ensures consistent security model
    across all service credentials.
"""

import os
import logging
from typing import Optional, BinaryIO, Dict, List
from io import BytesIO
import mimetypes

from minio import Minio
from minio.error import S3Error
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _get_minio_credentials() -> tuple[str, str]:
    """
    Get MinIO credentials from encrypted key store or environment.

    Tries encrypted database storage first (ADR-031), falls back to environment
    variables for backward compatibility.

    Returns:
        Tuple of (access_key, secret_key)

    Raises:
        ValueError: If credentials not found in either location
    """
    # Try encrypted key store first
    try:
        from .encrypted_keys import get_system_api_key
        from .age_client import AGEClient
        from .secrets import get_internal_key_service_secret

        client = AGEClient()
        conn = client.pool.getconn()

        try:
            service_token = get_internal_key_service_secret()

            # MinIO stores credentials as "access_key:secret_key" in single encrypted value
            credentials = get_system_api_key(conn, 'minio', service_token)

            if credentials:
                if ':' in credentials:
                    access_key, secret_key = credentials.split(':', 1)
                    logger.debug("Loaded MinIO credentials from encrypted key store")
                    return access_key, secret_key
                else:
                    logger.warning("MinIO credentials in database have invalid format (expected 'access:secret')")
        finally:
            client.pool.putconn(conn)

    except ValueError as e:
        # Key not found in database - expected during migration
        logger.debug(f"MinIO credentials not in encrypted key store: {e}")

    except Exception as e:
        logger.warning(f"Failed to load MinIO credentials from encrypted store: {e}")

    # Fall back to environment variables
    access_key = os.getenv("MINIO_ROOT_USER")
    secret_key = os.getenv("MINIO_ROOT_PASSWORD")

    if access_key and secret_key:
        logger.debug("Loaded MinIO credentials from environment variables")
        return access_key, secret_key

    raise ValueError(
        "MinIO credentials not found. "
        "Run 'scripts/setup/initialize-platform.sh' to configure encrypted credentials, "
        "or set MINIO_ROOT_USER and MINIO_ROOT_PASSWORD in .env"
    )


class MinIOClient:
    """
    MinIO client for image storage operations.

    Thread-safe singleton pattern - all methods use stateless connections.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        secure: bool = False,
        region: Optional[str] = None
    ):
        """
        Initialize MinIO client.

        Credentials are loaded from encrypted key store (ADR-031) if available,
        falling back to environment variables for backward compatibility.

        Args:
            endpoint: MinIO endpoint (default: from MINIO_HOST:MINIO_PORT env)
            access_key: MinIO access key (default: from encrypted store or env)
            secret_key: MinIO secret key (default: from encrypted store or env)
            bucket_name: Bucket name (default: from MINIO_BUCKET env)
            secure: Use HTTPS (default: from MINIO_SECURE env)
            region: AWS region (default: from MINIO_REGION env or us-east-1)

        Raises:
            ValueError: If credentials not found
        """
        # Load endpoint configuration from environment
        self.endpoint = endpoint or os.getenv("MINIO_HOST", "localhost") + ":" + os.getenv("MINIO_PORT", "9000")
        self.bucket_name = bucket_name or os.getenv("MINIO_BUCKET", "images")
        self.secure = secure or os.getenv("MINIO_SECURE", "false").lower() == "true"
        self.region = region or os.getenv("MINIO_REGION", "us-east-1")

        # Load credentials from encrypted store or environment
        if access_key and secret_key:
            # Explicit credentials provided (for testing)
            self.access_key = access_key
            self.secret_key = secret_key
            logger.debug("Using explicitly provided MinIO credentials")
        else:
            # Load from encrypted store or environment
            self.access_key, self.secret_key = _get_minio_credentials()

        # Initialize MinIO client with explicit region for signature v4
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
            region=self.region
        )

        logger.info(f"MinIO client initialized: {self.endpoint}, bucket: {self.bucket_name}, region: {self.region}, secure: {self.secure}")

    def ensure_bucket_exists(self) -> None:
        """
        Ensure the configured bucket exists, create if it doesn't.

        Raises:
            S3Error: If bucket creation fails
        """
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
                logger.info(f"Created bucket: {self.bucket_name}")
            else:
                logger.debug(f"Bucket already exists: {self.bucket_name}")
        except S3Error as e:
            logger.error(f"Failed to ensure bucket exists: {e}")
            raise

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
        # Sanitize ontology name (replace spaces/special chars with underscores)
        safe_ontology = ontology.replace(" ", "_").replace("/", "_")

        # Ensure extension doesn't have leading dot
        ext = file_extension.lstrip(".")

        return f"{safe_ontology}/{source_id}.{ext}"

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
        elif image_bytes.startswith(b'RIFF') and image_bytes[8:12] == b'WEBP':
            return 'image/webp'
        elif image_bytes.startswith(b'BM'):
            return 'image/bmp'

        # Default to jpeg if unknown
        logger.warning(f"Could not detect content type for {filename}, defaulting to image/jpeg")
        return 'image/jpeg'

    def upload_image(
        self,
        ontology: str,
        source_id: str,
        image_bytes: bytes,
        filename: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Upload an image to MinIO.

        Args:
            ontology: Ontology name
            source_id: Source ID from database
            image_bytes: Image binary data
            filename: Original filename (used for content-type detection)
            metadata: Optional custom metadata (do NOT include 'content-type' - use content_type param)

        Returns:
            Object key of uploaded image

        Raises:
            S3Error: If upload fails

        Note:
            Content-Type is set via content_type parameter (HTTP header), NOT metadata.
            Including 'content-type' in metadata dict causes S3 signature mismatch.
        """
        # Detect content type
        content_type = self._detect_content_type(filename, image_bytes)

        # Extract file extension from filename
        file_extension = os.path.splitext(filename)[1].lstrip(".")
        if not file_extension:
            # Derive from content type
            extension_map = {
                'image/jpeg': 'jpg',
                'image/png': 'png',
                'image/gif': 'gif',
                'image/webp': 'webp',
                'image/bmp': 'bmp'
            }
            file_extension = extension_map.get(content_type, 'jpg')

        # Build object key
        object_key = self._build_object_key(ontology, source_id, file_extension)

        # Prepare metadata (exclude content-type to avoid signature issues)
        upload_metadata = metadata.copy() if metadata else {}
        upload_metadata['original-filename'] = filename

        # CRITICAL: Do NOT add 'content-type' to metadata dict
        # Content-Type is set via content_type parameter (HTTP header)
        # Duplicating it in metadata causes S3 signature mismatch
        if 'content-type' in upload_metadata:
            logger.warning("Removing 'content-type' from metadata (use content_type param instead)")
            del upload_metadata['content-type']

        try:
            # Upload to MinIO
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_key,
                data=BytesIO(image_bytes),
                length=len(image_bytes),
                content_type=content_type,
                metadata=upload_metadata
            )

            logger.info(f"Uploaded image: {object_key} ({len(image_bytes)} bytes)")
            return object_key

        except S3Error as e:
            logger.error(f"Failed to upload image {object_key}: {e}")
            raise

    def download_image(self, object_key: str) -> bytes:
        """
        Download an image from MinIO.

        Args:
            object_key: Object key (from upload_image return value or database)

        Returns:
            Image binary data

        Raises:
            S3Error: If download fails or object not found
        """
        try:
            response = self.client.get_object(self.bucket_name, object_key)
            image_bytes = response.read()
            response.close()
            response.release_conn()

            logger.info(f"Downloaded image: {object_key} ({len(image_bytes)} bytes)")
            return image_bytes

        except S3Error as e:
            logger.error(f"Failed to download image {object_key}: {e}")
            raise

    def delete_image(self, object_key: str) -> None:
        """
        Delete an image from MinIO.

        Args:
            object_key: Object key to delete

        Raises:
            S3Error: If deletion fails
        """
        try:
            self.client.remove_object(self.bucket_name, object_key)
            logger.info(f"Deleted image: {object_key}")

        except S3Error as e:
            logger.error(f"Failed to delete image {object_key}: {e}")
            raise

    def delete_images_by_prefix(self, prefix: str) -> List[str]:
        """
        Delete all images matching a prefix (used for ontology deletion).

        Args:
            prefix: Object key prefix (e.g., "Research_Notes/" to delete all images in ontology)

        Returns:
            List of deleted object keys

        Raises:
            S3Error: If deletion fails
        """
        deleted_keys = []

        try:
            # List all objects with prefix
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)

            # Delete each object
            for obj in objects:
                try:
                    self.client.remove_object(self.bucket_name, obj.object_name)
                    deleted_keys.append(obj.object_name)
                    logger.debug(f"Deleted: {obj.object_name}")
                except S3Error as e:
                    logger.error(f"Failed to delete {obj.object_name}: {e}")

            logger.info(f"Deleted {len(deleted_keys)} images with prefix '{prefix}'")
            return deleted_keys

        except S3Error as e:
            logger.error(f"Failed to list/delete images with prefix {prefix}: {e}")
            raise

    def list_images(self, ontology: Optional[str] = None) -> List[Dict[str, any]]:
        """
        List images in bucket, optionally filtered by ontology.

        Args:
            ontology: Optional ontology name to filter by

        Returns:
            List of dicts with object metadata (object_name, size, last_modified)
        """
        prefix = f"{ontology.replace(' ', '_').replace('/', '_')}/" if ontology else ""

        try:
            objects = self.client.list_objects(self.bucket_name, prefix=prefix, recursive=True)

            results = []
            for obj in objects:
                results.append({
                    'object_name': obj.object_name,
                    'size': obj.size,
                    'last_modified': obj.last_modified,
                    'etag': obj.etag
                })

            logger.info(f"Listed {len(results)} images (prefix: '{prefix}')")
            return results

        except S3Error as e:
            logger.error(f"Failed to list images: {e}")
            raise

    def get_image_metadata(self, object_key: str) -> Dict[str, any]:
        """
        Get metadata for an image without downloading it.

        Args:
            object_key: Object key

        Returns:
            Dict with:
            - object_name: Object key
            - size: Size in bytes
            - content_type: MIME type
            - last_modified: Last modified timestamp
            - etag: ETag hash
            - metadata: Custom metadata dict (x-amz-meta-* prefix stripped)

        Raises:
            S3Error: If object not found
        """
        try:
            stat = self.client.stat_object(self.bucket_name, object_key)

            # Extract custom metadata (strip x-amz-meta- prefix)
            custom_metadata = {}
            if stat.metadata:
                for key, value in stat.metadata.items():
                    if key.startswith('x-amz-meta-'):
                        # Strip prefix: x-amz-meta-original-filename -> original-filename
                        clean_key = key[11:]  # len('x-amz-meta-') = 11
                        custom_metadata[clean_key] = value

            return {
                'object_name': stat.object_name,
                'size': stat.size,
                'content_type': stat.content_type,
                'last_modified': stat.last_modified,
                'etag': stat.etag,
                'metadata': custom_metadata
            }

        except S3Error as e:
            logger.error(f"Failed to get metadata for {object_key}: {e}")
            raise

    def health_check(self) -> bool:
        """
        Check if MinIO is accessible and bucket exists.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Check if bucket exists
            exists = self.client.bucket_exists(self.bucket_name)

            if exists:
                logger.debug(f"MinIO health check passed: bucket '{self.bucket_name}' accessible")
                return True
            else:
                logger.warning(f"MinIO health check failed: bucket '{self.bucket_name}' not found")
                return False

        except Exception as e:
            logger.error(f"MinIO health check failed: {e}")
            return False


# Global singleton instance
_minio_client: Optional[MinIOClient] = None


def get_minio_client() -> MinIOClient:
    """
    Get or create the global MinIO client instance.

    Returns:
        MinIOClient instance
    """
    global _minio_client

    if _minio_client is None:
        _minio_client = MinIOClient()
        _minio_client.ensure_bucket_exists()

    return _minio_client
