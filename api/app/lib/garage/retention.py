"""
Retention Policy Manager - Storage lifecycle management (ADR-080).

This module manages retention policies for different artifact types stored
in Garage, preventing unbounded storage growth while preserving important data.

Default Policies:
- Projections: Keep latest + 10 historical snapshots, delete older than 30 days
- Sources: Keep always (model evolution insurance)
- Images: Keep always (original evidence)
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field

from .base import GarageBaseClient, sanitize_path_component

logger = logging.getLogger(__name__)


@dataclass
class CleanupResult:
    """Result of a retention cleanup operation."""
    deleted_count: int = 0
    deleted_keys: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    skipped_count: int = 0


@dataclass
class StorageStats:
    """Storage usage statistics."""
    total_objects: int = 0
    total_bytes: int = 0
    by_category: Dict[str, Dict[str, int]] = field(default_factory=dict)


class RetentionPolicyManager:
    """
    Manage artifact retention and cleanup for Garage storage.

    Applies configurable retention policies to different artifact types:
    - Projections: Historical snapshots subject to count/age limits
    - Sources: Always kept (re-extraction capability)
    - Images: Always kept (original evidence)
    """

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

    def __init__(
        self,
        base: GarageBaseClient,
        policies: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize retention policy manager.

        Args:
            base: GarageBaseClient instance for S3 operations
            policies: Custom retention policies (merged with defaults)
        """
        self.base = base
        self.policies = self.DEFAULT_POLICIES.copy()
        if policies:
            for category, settings in policies.items():
                if category in self.policies:
                    self.policies[category].update(settings)
                else:
                    self.policies[category] = settings

    def cleanup_projections(self, ontology: str) -> CleanupResult:
        """
        Apply retention policy to projection history for an ontology.

        Keeps latest.json and the most recent N snapshots (by history_count),
        deletes snapshots older than history_max_age_days.

        Args:
            ontology: Ontology name

        Returns:
            CleanupResult with deletion details
        """
        result = CleanupResult()
        policy = self.policies.get("projections", {})

        if policy.get("keep_always"):
            logger.debug(f"Projections retention: keep_always enabled, skipping {ontology}")
            return result

        safe_ontology = sanitize_path_component(ontology)
        history_count = policy.get("history_count", 10)
        max_age_days = policy.get("history_max_age_days", 30)
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)

        # List all projection objects for this ontology
        prefix = f"projections/{safe_ontology}/"
        objects = self.base.list_objects(prefix)

        # Separate latest from historical snapshots
        snapshots = []
        for obj in objects:
            if obj['key'].endswith('latest.json'):
                result.skipped_count += 1
                continue
            snapshots.append(obj)

        # Sort by last_modified descending (newest first)
        snapshots.sort(key=lambda x: x['last_modified'], reverse=True)

        # Determine which to delete
        for i, snapshot in enumerate(snapshots):
            should_delete = False

            # Delete if beyond history_count
            if i >= history_count:
                should_delete = True
                reason = f"exceeds history_count ({history_count})"

            # Delete if older than max_age_days
            elif snapshot['last_modified'] < cutoff_date:
                should_delete = True
                reason = f"older than {max_age_days} days"

            if should_delete:
                try:
                    self.base.delete_object(snapshot['key'])
                    result.deleted_count += 1
                    result.deleted_keys.append(snapshot['key'])
                    logger.debug(f"Deleted projection snapshot: {snapshot['key']} ({reason})")
                except Exception as e:
                    result.errors.append(f"{snapshot['key']}: {e}")
                    logger.warning(f"Failed to delete {snapshot['key']}: {e}")
            else:
                result.skipped_count += 1

        logger.info(f"Projection cleanup for {ontology}: deleted {result.deleted_count}, skipped {result.skipped_count}")
        return result

    def cleanup_all_projections(self) -> Dict[str, CleanupResult]:
        """
        Run projection cleanup across all ontologies.

        Gracefully handles failures - individual ontology cleanup errors
        don't prevent cleanup of other ontologies.

        Returns:
            Dict mapping ontology names to CleanupResult
        """
        results = {}

        # List all projection directories
        try:
            objects = self.base.list_objects("projections/")
        except Exception as e:
            logger.error(f"Failed to list projection objects: {e}")
            return results  # Return empty results rather than crashing

        # Extract unique ontology names from keys
        ontologies = set()
        for obj in objects:
            parts = obj['key'].split('/')
            if len(parts) >= 2:
                ontologies.add(parts[1])  # projections/{ontology}/...

        for ontology in ontologies:
            try:
                results[ontology] = self.cleanup_projections(ontology)
            except Exception as e:
                # Record failure but continue with other ontologies
                logger.error(f"Failed to cleanup projections for {ontology}: {e}")
                results[ontology] = CleanupResult(errors=[f"Cleanup failed: {e}"])

        total_deleted = sum(r.deleted_count for r in results.values())
        logger.info(f"Total projection cleanup: deleted {total_deleted} snapshots across {len(ontologies)} ontologies")

        return results

    def get_storage_stats(self) -> StorageStats:
        """
        Get storage usage statistics by category.

        Returns:
            StorageStats with counts and sizes
        """
        stats = StorageStats()

        categories = {
            'images': 'images/',
            'projections': 'projections/',
            'sources': 'sources/'
        }

        for category, prefix in categories.items():
            objects = self.base.list_objects(prefix)
            count = len(objects)
            total_size = sum(obj['size'] for obj in objects)

            stats.by_category[category] = {
                'count': count,
                'size_bytes': total_size
            }
            stats.total_objects += count
            stats.total_bytes += total_size

        logger.info(f"Storage stats: {stats.total_objects} objects, {stats.total_bytes} bytes")
        return stats

    def get_policy(self, category: str) -> Dict[str, Any]:
        """
        Get the retention policy for a category.

        Args:
            category: Category name (projections, sources, images)

        Returns:
            Policy dict
        """
        return self.policies.get(category, {})

    def set_policy(self, category: str, settings: Dict[str, Any]) -> None:
        """
        Update the retention policy for a category.

        Args:
            category: Category name
            settings: New policy settings (merged with existing)
        """
        if category not in self.policies:
            self.policies[category] = {}
        self.policies[category].update(settings)
        logger.info(f"Updated retention policy for {category}: {settings}")
