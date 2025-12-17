"""
Artifact Storage Service - Multi-tier artifact persistence (ADR-083).

This service handles storage and retrieval of computed artifacts with
automatic routing between inline (SQL) and Garage (S3) based on size.

Key format:
    artifacts/{artifact_type}/{artifact_id}.json

Size routing:
    - Small artifacts (<10KB): Stored inline in kg_api.artifacts.inline_result
    - Large artifacts (>=10KB): Stored in Garage, pointer in kg_api.artifacts.garage_key
"""

import json
import logging
from typing import Optional, Dict, Any, Tuple

from .base import GarageBaseClient

logger = logging.getLogger(__name__)

# Threshold for inline vs Garage storage (10KB)
INLINE_THRESHOLD_BYTES = 10 * 1024


class ArtifactStorageService:
    """
    Artifact storage service for computed results (ADR-083).

    Provides multi-tier storage with automatic routing based on payload size:
    - Small payloads stored inline in PostgreSQL for fast access
    - Large payloads stored in Garage with pointer in PostgreSQL

    Thread-safe - uses stateless operations on shared GarageBaseClient.
    """

    def __init__(self, base: GarageBaseClient):
        """
        Initialize artifact storage service.

        Args:
            base: GarageBaseClient instance for S3 operations
        """
        self.base = base

    def _build_key(self, artifact_type: str, artifact_id: int) -> str:
        """
        Build object key for an artifact.

        Format: artifacts/{artifact_type}/{artifact_id}.json

        Args:
            artifact_type: Type of artifact (e.g., polarity_analysis, projection)
            artifact_id: Unique artifact ID from database

        Returns:
            Object key string
        """
        return f"artifacts/{artifact_type}/{artifact_id}.json"

    def should_store_inline(self, payload: Dict[str, Any]) -> bool:
        """
        Determine if payload should be stored inline or in Garage.

        Args:
            payload: The artifact payload to evaluate

        Returns:
            True if payload should be stored inline (< 10KB), False for Garage
        """
        json_bytes = json.dumps(payload).encode('utf-8')
        return len(json_bytes) < INLINE_THRESHOLD_BYTES

    def prepare_for_storage(
        self,
        artifact_type: str,
        artifact_id: int,
        payload: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Prepare artifact for storage, routing to inline or Garage.

        This method determines where to store the payload and returns
        the appropriate values for the database record.

        Args:
            artifact_type: Type of artifact
            artifact_id: Unique artifact ID
            payload: The artifact payload

        Returns:
            Tuple of (inline_result, garage_key):
            - For small payloads: (payload_dict, None)
            - For large payloads: (None, garage_key_string)

        Raises:
            ClientError: If Garage storage fails for large payloads
        """
        json_data = json.dumps(payload)
        json_bytes = json_data.encode('utf-8')
        size_bytes = len(json_bytes)

        if size_bytes < INLINE_THRESHOLD_BYTES:
            # Store inline - return payload for database storage
            logger.info(
                f"Artifact {artifact_id} ({artifact_type}): "
                f"storing inline ({size_bytes} bytes)"
            )
            return (payload, None)
        else:
            # Store in Garage
            garage_key = self._build_key(artifact_type, artifact_id)
            metadata = {
                'artifact-type': artifact_type,
                'artifact-id': str(artifact_id),
                'size-bytes': str(size_bytes)
            }

            self.base.put_object(garage_key, json_bytes, 'application/json', metadata)
            logger.info(
                f"Artifact {artifact_id} ({artifact_type}): "
                f"stored in Garage ({size_bytes} bytes) at {garage_key}"
            )
            return (None, garage_key)

    def store(
        self,
        artifact_type: str,
        artifact_id: int,
        payload: Dict[str, Any]
    ) -> str:
        """
        Store an artifact payload in Garage (always, ignoring size threshold).

        Use this when you want to force Garage storage regardless of size,
        or when updating an existing Garage-stored artifact.

        Args:
            artifact_type: Type of artifact
            artifact_id: Unique artifact ID
            payload: The artifact payload

        Returns:
            Object key of stored artifact

        Raises:
            ClientError: If storage fails
        """
        garage_key = self._build_key(artifact_type, artifact_id)
        json_data = json.dumps(payload, indent=2)
        json_bytes = json_data.encode('utf-8')

        metadata = {
            'artifact-type': artifact_type,
            'artifact-id': str(artifact_id),
            'size-bytes': str(len(json_bytes))
        }

        self.base.put_object(garage_key, json_bytes, 'application/json', metadata)
        logger.info(f"Stored artifact: {garage_key} ({len(json_bytes)} bytes)")

        return garage_key

    def get(self, garage_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve an artifact payload from Garage.

        Args:
            garage_key: Object key from kg_api.artifacts.garage_key

        Returns:
            Artifact payload dict or None if not found
        """
        data = self.base.get_object(garage_key)

        if data is None:
            logger.debug(f"Artifact not found: {garage_key}")
            return None

        logger.info(f"Retrieved artifact: {garage_key} ({len(data)} bytes)")
        return json.loads(data)

    def get_by_id(
        self,
        artifact_type: str,
        artifact_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve an artifact payload by type and ID.

        Convenience method that builds the key from components.

        Args:
            artifact_type: Type of artifact
            artifact_id: Unique artifact ID

        Returns:
            Artifact payload dict or None if not found
        """
        garage_key = self._build_key(artifact_type, artifact_id)
        return self.get(garage_key)

    def delete(self, garage_key: str) -> bool:
        """
        Delete an artifact from Garage.

        Args:
            garage_key: Object key to delete

        Returns:
            True if deleted, False if not found
        """
        result = self.base.delete_object(garage_key)

        if result:
            logger.info(f"Deleted artifact: {garage_key}")
        return result

    def delete_by_id(self, artifact_type: str, artifact_id: int) -> bool:
        """
        Delete an artifact by type and ID.

        Convenience method that builds the key from components.

        Args:
            artifact_type: Type of artifact
            artifact_id: Unique artifact ID

        Returns:
            True if deleted, False if not found
        """
        garage_key = self._build_key(artifact_type, artifact_id)
        return self.delete(garage_key)

    def delete_by_type(self, artifact_type: str) -> int:
        """
        Delete all artifacts of a given type.

        Args:
            artifact_type: Type of artifacts to delete

        Returns:
            Number of objects deleted
        """
        prefix = f"artifacts/{artifact_type}/"
        deleted = self.base.delete_by_prefix(prefix)
        logger.info(f"Deleted {len(deleted)} artifacts of type {artifact_type}")
        return len(deleted)

    def list_by_type(self, artifact_type: str, limit: int = 100) -> list:
        """
        List artifacts of a given type stored in Garage.

        Args:
            artifact_type: Type of artifacts to list
            limit: Maximum number to return

        Returns:
            List of object metadata dicts
        """
        prefix = f"artifacts/{artifact_type}/"
        objects = self.base.list_objects(prefix)

        # Sort by last_modified descending (newest first)
        objects.sort(
            key=lambda x: x['last_modified'],
            reverse=True
        )
        return objects[:limit]

    def exists(self, garage_key: str) -> bool:
        """
        Check if an artifact exists in Garage.

        Args:
            garage_key: Object key to check

        Returns:
            True if exists, False otherwise
        """
        return self.base.head_object(garage_key) is not None

    def get_metadata(self, garage_key: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for an artifact without downloading the payload.

        Args:
            garage_key: Object key

        Returns:
            Metadata dict or None if not found
        """
        return self.base.head_object(garage_key)
