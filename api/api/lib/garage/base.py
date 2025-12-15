"""
Garage Base Client - Core S3 operations and credential management (ADR-080).

This module provides the foundational S3 client that all storage services depend on.
It handles:
- Credential loading from encrypted store or environment
- S3 client initialization with retry configuration
- Bucket management
- Health checks
- Core put/get/delete/list operations

All domain-specific storage logic (images, projections, sources) is delegated
to specialized service classes that use this base client.
"""

import os
import logging
from typing import Optional, Dict, List, Any
from io import BytesIO

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError
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
        from ..encrypted_keys import get_system_api_key
        from ..age_client import AGEClient
        from ..secrets import get_internal_key_service_secret

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


class GarageBaseClient:
    """
    Base Garage client providing core S3 operations.

    All storage services depend on this client for:
    - Credential management (encrypted store or env fallback)
    - S3 client initialization with retry config
    - Bucket management
    - Health checks
    - Core object operations (put, get, delete, list)

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
        Initialize Garage base client.

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
        self.bucket_name = bucket_name or os.getenv("GARAGE_BUCKET", "kg-storage")
        self.region = region or os.getenv("GARAGE_REGION", "garage")

        # Load credentials - don't store as instance attributes for security
        if access_key and secret_key:
            _access_key, _secret_key = access_key, secret_key
            logger.debug("Using explicitly provided Garage credentials")
        else:
            _access_key, _secret_key = _get_garage_credentials()

        # Configure retry logic for resilience
        retry_config = BotoConfig(
            retries={
                'max_attempts': 3,
                'mode': 'adaptive'
            },
            connect_timeout=5,
            read_timeout=30
        )

        # Initialize boto3 S3 client
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=_access_key,
            aws_secret_access_key=_secret_key,
            region_name=self.region,
            config=retry_config
        )

        logger.info(f"Garage base client initialized: {self.endpoint}, bucket: {self.bucket_name}")

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

    def health_check(self) -> bool:
        """
        Check if Garage is accessible and bucket exists.

        Returns:
            True if healthy, False otherwise
        """
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
            logger.debug(f"Garage health check passed: bucket '{self.bucket_name}' accessible")
            return True
        except Exception as e:
            logger.error(f"Garage health check failed: {e}")
            return False

    def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Store an object in Garage.

        Args:
            key: Object key
            data: Binary data to store
            content_type: MIME type
            metadata: Optional custom metadata

        Raises:
            ClientError: If storage fails
        """
        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=BytesIO(data),
                ContentType=content_type,
                Metadata=metadata or {}
            )
            logger.debug(f"Stored object: {key} ({len(data)} bytes)")
        except ClientError as e:
            logger.error(f"Failed to store object {key}: {e}")
            raise

    def get_object(self, key: str) -> Optional[bytes]:
        """
        Retrieve an object from Garage.

        Args:
            key: Object key

        Returns:
            Binary data or None if not found
        """
        try:
            response = self.client.get_object(Bucket=self.bucket_name, Key=key)
            data = response['Body'].read()
            logger.debug(f"Retrieved object: {key} ({len(data)} bytes)")
            return data
        except ClientError as e:
            if e.response['Error']['Code'] in ('NoSuchKey', '404'):
                logger.debug(f"Object not found: {key}")
                return None
            logger.error(f"Failed to get object {key}: {e}")
            raise

    def delete_object(self, key: str) -> bool:
        """
        Delete an object from Garage.

        Args:
            key: Object key

        Returns:
            True if deleted, False if not found
        """
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=key)
            logger.debug(f"Deleted object: {key}")
            return True
        except ClientError as e:
            if e.response['Error']['Code'] in ('NoSuchKey', '404'):
                return False
            logger.error(f"Failed to delete object {key}: {e}")
            raise

    def list_objects(self, prefix: str = "") -> List[Dict[str, Any]]:
        """
        List objects with a given prefix.

        Args:
            prefix: Object key prefix

        Returns:
            List of dicts with object metadata
        """
        try:
            paginator = self.client.get_paginator('list_objects_v2')
            pages = paginator.paginate(Bucket=self.bucket_name, Prefix=prefix)

            results = []
            for page in pages:
                if 'Contents' not in page:
                    continue

                for obj in page['Contents']:
                    results.append({
                        'key': obj['Key'],
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'etag': obj['ETag'].strip('"')
                    })

            logger.debug(f"Listed {len(results)} objects (prefix: '{prefix}')")
            return results

        except ClientError as e:
            logger.error(f"Failed to list objects: {e}")
            raise

    def head_object(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for an object without downloading it.

        Args:
            key: Object key

        Returns:
            Dict with metadata or None if not found
        """
        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=key)
            return {
                'key': key,
                'size': response['ContentLength'],
                'content_type': response.get('ContentType', 'application/octet-stream'),
                'last_modified': response['LastModified'],
                'etag': response['ETag'].strip('"'),
                'metadata': response.get('Metadata', {})
            }
        except ClientError as e:
            if e.response['Error']['Code'] in ('NoSuchKey', '404'):
                return None
            logger.error(f"Failed to get metadata for {key}: {e}")
            raise

    def delete_by_prefix(self, prefix: str) -> List[str]:
        """
        Delete all objects matching a prefix.

        Args:
            prefix: Object key prefix

        Returns:
            List of deleted object keys
        """
        deleted_keys = []

        try:
            objects = self.list_objects(prefix)
            for obj in objects:
                if self.delete_object(obj['key']):
                    deleted_keys.append(obj['key'])

            logger.info(f"Deleted {len(deleted_keys)} objects with prefix '{prefix}'")
            return deleted_keys

        except ClientError as e:
            logger.error(f"Failed to delete objects with prefix {prefix}: {e}")
            raise


def sanitize_path_component(name: str) -> str:
    """
    Sanitize a string for use in object key paths.

    Replaces spaces and slashes with underscores.

    Args:
        name: String to sanitize

    Returns:
        Sanitized string safe for object keys
    """
    return name.replace(" ", "_").replace("/", "_")
