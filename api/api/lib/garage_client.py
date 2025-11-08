"""
Garage Client - S3-compatible object storage for image assets (ADR-057)

This module provides a clean interface for storing and retrieving images in Garage.
Uses source-ID based object keys for 1:1 mapping with database records.

Object Key Structure:
    images/{ontology}/{source_id}.{ext}

Examples:
    images/Research Notes/src_abc123.jpg
    images/Meeting Notes/src_xyz789.png

Security:
    Garage credentials are stored encrypted in PostgreSQL (ADR-031) using the same
    pattern as OpenAI/Anthropic API keys. This ensures consistent security model
    across all service credentials.

Migration Note:
    Replaced MinIO with Garage (March 2025) after MinIO gutted admin UI to Enterprise
    edition ($96k/year). Garage provides cooperative governance with no Enterprise trap.
"""

import os
import logging
from typing import Optional, Dict, List
from io import BytesIO
import mimetypes

import boto3
from botocore.exceptions import ClientError, BotoCoreError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _get_garage_credentials() -> tuple[str, str]:
    """
    Get Garage credentials from encrypted key store or environment.

    Tries encrypted database storage first (ADR-031), falls back to environment
    variables for backward compatibility.

    Returns:
        Tuple of (access_key_id, secret_access_key)

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

            # Garage stores credentials as "access_key:secret_key" in single encrypted value
            credentials = get_system_api_key(conn, 'garage', service_token)

            if credentials:
                if ':' in credentials:
                    access_key, secret_key = credentials.split(':', 1)
                    logger.debug("Loaded Garage credentials from encrypted key store")
                    return access_key, secret_key
                else:
                    logger.warning("Garage credentials in database have invalid format (expected 'access:secret')")
        finally:
            client.pool.putconn(conn)

    except ValueError as e:
        # Key not found in database - expected during migration
        logger.debug(f"Garage credentials not in encrypted key store: {e}")

    except Exception as e:
        logger.warning(f"Failed to load Garage credentials from encrypted store: {e}")

    # Fall back to environment variables
    access_key = os.getenv("GARAGE_ACCESS_KEY_ID")
    secret_key = os.getenv("GARAGE_SECRET_ACCESS_KEY")

    if access_key and secret_key:
        logger.debug("Loaded Garage credentials from environment variables")
        return access_key, secret_key

    raise ValueError(
        "Garage credentials not found. "
        "Run 'scripts/setup/initialize-platform.sh' to configure encrypted credentials, "
        "or set GARAGE_ACCESS_KEY_ID and GARAGE_SECRET_ACCESS_KEY in .env"
    )


class GarageClient:
    """
    Garage client for image storage operations.

    Thread-safe singleton pattern - all methods use stateless connections.
    """

    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None
    ):
        """
        Initialize Garage client.

        Credentials are loaded from encrypted key store (ADR-031) if available,
        falling back to environment variables for backward compatibility.

        Args:
            endpoint: Garage S3 endpoint (default: from GARAGE_S3_ENDPOINT env)
            access_key: Garage access key (default: from encrypted store or env)
            secret_key: Garage secret key (default: from encrypted store or env)
            bucket_name: Bucket name (default: from GARAGE_BUCKET env)
            region: AWS region (default: from GARAGE_REGION env or garage)

        Raises:
            ValueError: If credentials not found
        """
        # Load endpoint configuration from environment
        self.endpoint = endpoint or os.getenv("GARAGE_S3_ENDPOINT", "http://localhost:3900")
        self.bucket_name = bucket_name or os.getenv("GARAGE_BUCKET", "knowledge-graph-images")
        self.region = region or os.getenv("GARAGE_REGION", "garage")

        # Load credentials from encrypted store or environment
        if access_key and secret_key:
            # Explicit credentials provided (for testing)
            self.access_key = access_key
            self.secret_key = secret_key
            logger.debug("Using explicitly provided Garage credentials")
        else:
            # Load from encrypted store or environment
            self.access_key, self.secret_key = _get_garage_credentials()

        # Initialize boto3 S3 client for Garage
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        )

        logger.info(f"Garage client initialized: {self.endpoint}, bucket: {self.bucket_name}, region: {self.region}")

    def ensure_bucket_exists(self) -> None:
        """
        Ensure the configured bucket exists, create if it doesn't.

        Raises:
            ClientError: If bucket creation fails
        """
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.debug(f"Bucket already exists: {self.bucket_name}")
        except ClientError as e:
            # Bucket doesn't exist, try to create it
            if e.response['Error']['Code'] == '404':
                try:
                    self.client.create_bucket(Bucket=self.bucket_name)
                    logger.info(f"Created bucket: {self.bucket_name}")
                except ClientError as create_error:
                    logger.error(f"Failed to create bucket: {create_error}")
                    raise
            else:
                logger.error(f"Failed to check bucket existence: {e}")
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

        # Prepare metadata
        upload_metadata = metadata.copy() if metadata else {}
        upload_metadata['original-filename'] = filename

        try:
            # Upload to Garage via S3 API
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=object_key,
                Body=BytesIO(image_bytes),
                ContentType=content_type,
                Metadata=upload_metadata
            )

            logger.info(f"Uploaded image: {object_key} ({len(image_bytes)} bytes)")
            return object_key

        except ClientError as e:
            logger.error(f"Failed to upload image {object_key}: {e}")
            raise

    def download_image(self, object_key: str) -> bytes:
        """
        Download an image from Garage.

        Args:
            object_key: Object key (from upload_image return value or database)

        Returns:
            Image binary data

        Raises:
            ClientError: If download fails or object not found
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=object_key)
            image_bytes = response['Body'].read()

            logger.info(f"Downloaded image: {object_key} ({len(image_bytes)} bytes)")
            return image_bytes

        except ClientError as e:
            logger.error(f"Failed to download image {object_key}: {e}")
            raise

    def delete_image(self, object_key: str) -> None:
        """
        Delete an image from Garage.

        Args:
            object_key: Object key to delete

        Raises:
            ClientError: If deletion fails
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_key)
            logger.info(f"Deleted image: {object_key}")

        except ClientError as e:
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
            ClientError: If deletion fails
        """
        deleted_keys = []

        try:
            # List all objects with prefix
            paginator = self.client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            # Delete each object
            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    try:
                        self.client.delete_object(Bucket=self.bucket_name, Key=obj['Key'])
                        deleted_keys.append(obj['Key'])
                        logger.debug(f"Deleted: {obj['Key']}")
                    except ClientError as e:
                        logger.error(f"Failed to delete {obj['Key']}: {e}")

            logger.info(f"Deleted {len(deleted_keys)} images with prefix '{prefix}'")
            return deleted_keys

        except ClientError as e:
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
            paginator = self.client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            results = []
            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    results.append({
                        'object_name': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'etag': obj['ETag'].strip('"')
                    })

            logger.info(f"Listed {len(results)} images (prefix: '{prefix}')")
            return results

        except ClientError as e:
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
            - metadata: Custom metadata dict

        Raises:
            ClientError: If object not found
        """
        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=object_key)

            return {
                'object_name': object_key,
                'size': response['ContentLength'],
                'content_type': response.get('ContentType', 'application/octet-stream'),
                'last_modified': response['LastModified'],
                'etag': response['ETag'].strip('"'),
                'metadata': response.get('Metadata', {})
            }

        except ClientError as e:
            logger.error(f"Failed to get metadata for {object_key}: {e}")
            raise

    def health_check(self) -> bool:
        """
        Check if Garage is accessible and bucket exists.

        Returns:
            True if healthy, False otherwise
        """
        try:
            # Check if bucket exists
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.debug(f"Garage health check passed: bucket '{self.bucket_name}' accessible")
            return True

        except Exception as e:
            logger.error(f"Garage health check failed: {e}")
            return False


# Global singleton instance
_garage_client: Optional[GarageClient] = None


def get_garage_client() -> GarageClient:
    """
    Get or create the global Garage client instance.

    Returns:
        GarageClient instance
    """
    global _garage_client

    if _garage_client is None:
        _garage_client = GarageClient()
        _garage_client.ensure_bucket_exists()

    return _garage_client
