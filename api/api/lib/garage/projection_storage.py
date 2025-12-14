"""
Projection Storage Service - Embedding landscape projections (ADR-079, ADR-080).

This service handles storage and retrieval of projection artifacts - the 3D
coordinate mappings of concept embeddings for visualization.

Key format:
    projections/{ontology}/{embedding_source}/latest.json
    projections/{ontology}/{embedding_source}/{timestamp}.json (historical)
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Any

from .base import GarageBaseClient, sanitize_path_component

logger = logging.getLogger(__name__)


class ProjectionStorageService:
    """
    Projection artifact storage for embedding landscape visualization (ADR-079).

    Stores both the latest projection and timestamped historical snapshots
    for tracking semantic landscape evolution over time.
    """

    def __init__(self, base: GarageBaseClient):
        """
        Initialize projection storage service.

        Args:
            base: GarageBaseClient instance for S3 operations
        """
        self.base = base

    def _build_key(
        self,
        ontology: str,
        embedding_source: str,
        timestamp: Optional[str] = None
    ) -> str:
        """
        Build object key for a projection artifact.

        Format:
            projections/{ontology}/{embedding_source}/latest.json
            projections/{ontology}/{embedding_source}/{timestamp}.json

        Args:
            ontology: Ontology name
            embedding_source: Source type (concepts, sources, vocabulary, combined)
            timestamp: ISO timestamp for historical snapshots (None for latest)

        Returns:
            Object key string
        """
        safe_ontology = sanitize_path_component(ontology)
        if timestamp:
            return f"projections/{safe_ontology}/{embedding_source}/{timestamp}.json"
        return f"projections/{safe_ontology}/{embedding_source}/latest.json"

    def store(
        self,
        ontology: str,
        embedding_source: str,
        projection_data: Dict[str, Any],
        keep_history: bool = True
    ) -> str:
        """
        Store a projection to Garage.

        Stores both the latest version and optionally a timestamped snapshot
        for historical analysis.

        Args:
            ontology: Ontology name
            embedding_source: Source type (concepts, sources, vocabulary, combined)
            projection_data: Projection dataset dict
            keep_history: If True, also store timestamped snapshot (default: True)

        Returns:
            Object key of stored latest projection

        Raises:
            ClientError: If storage fails
        """
        json_data = json.dumps(projection_data, indent=2)
        json_bytes = json_data.encode('utf-8')
        stored_at = datetime.utcnow().isoformat() + 'Z'

        # Store as latest
        latest_key = self._build_key(ontology, embedding_source)
        metadata = {
            'ontology': ontology,
            'embedding-source': embedding_source,
            'stored-at': stored_at
        }

        self.base.put_object(latest_key, json_bytes, 'application/json', metadata)
        logger.info(f"Stored projection: {latest_key} ({len(json_bytes)} bytes)")

        # Optionally store timestamped snapshot
        if keep_history:
            timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
            history_key = self._build_key(ontology, embedding_source, timestamp)
            try:
                self.base.put_object(history_key, json_bytes, 'application/json', metadata)
                logger.debug(f"Stored projection snapshot: {history_key}")
            except Exception as e:
                # Non-fatal - historical snapshot failure shouldn't fail main storage
                logger.warning(f"Failed to store projection snapshot {history_key}: {e}")

        return latest_key

    def get(
        self,
        ontology: str,
        embedding_source: str = "concepts"
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve the latest projection for an ontology.

        Args:
            ontology: Ontology name
            embedding_source: Source type (default: concepts)

        Returns:
            Projection dataset dict or None if not found
        """
        object_key = self._build_key(ontology, embedding_source)
        data = self.base.get_object(object_key)

        if data is None:
            logger.debug(f"Projection not found: {object_key}")
            return None

        logger.info(f"Retrieved projection: {object_key} ({len(data)} bytes)")
        return json.loads(data)

    def get_history(
        self,
        ontology: str,
        embedding_source: str = "concepts",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        List historical projection snapshots for an ontology.

        Args:
            ontology: Ontology name
            embedding_source: Source type (default: concepts)
            limit: Maximum snapshots to return (default: 10)

        Returns:
            List of snapshot metadata dicts (sorted newest first)
        """
        safe_ontology = sanitize_path_component(ontology)
        prefix = f"projections/{safe_ontology}/{embedding_source}/"

        objects = self.base.list_objects(prefix)

        # Filter out latest.json and convert to expected format
        snapshots = []
        for obj in objects:
            if obj['key'].endswith('latest.json'):
                continue
            snapshots.append({
                'object_key': obj['key'],
                'key': obj['key'],  # Alias for compatibility
                'size': obj['size'],
                'last_modified': obj['last_modified'].isoformat() if hasattr(obj['last_modified'], 'isoformat') else obj['last_modified'],
                'etag': obj['etag']
            })

        # Sort by last_modified descending
        snapshots.sort(key=lambda x: x['last_modified'], reverse=True)
        return snapshots[:limit]

    def delete(self, ontology: str, embedding_source: str = "concepts") -> bool:
        """
        Delete the latest projection for an ontology.

        Note: Does not delete historical snapshots.

        Args:
            ontology: Ontology name
            embedding_source: Source type (default: concepts)

        Returns:
            True if deleted, False if not found
        """
        object_key = self._build_key(ontology, embedding_source)
        result = self.base.delete_object(object_key)

        if result:
            logger.info(f"Deleted projection: {object_key}")
        return result

    def delete_all(self, ontology: str) -> int:
        """
        Delete all projections (latest + history) for an ontology.

        Args:
            ontology: Ontology name

        Returns:
            Number of objects deleted
        """
        safe_ontology = sanitize_path_component(ontology)
        prefix = f"projections/{safe_ontology}/"
        deleted = self.base.delete_by_prefix(prefix)
        logger.info(f"Deleted {len(deleted)} projection objects for {ontology}")
        return len(deleted)
