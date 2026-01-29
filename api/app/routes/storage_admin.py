"""
Storage Admin Routes - Read-only diagnostics for S3-compatible object storage.

Provides independent visibility into the storage layer (Garage/S3):
- Health checks
- Usage statistics by category
- Object listing and metadata inspection
- Integrity checks (S3 vs graph cross-reference)
- Retention policy visibility

All endpoints are read-only, gated behind storage:read permission.
Storage-agnostic naming — no implementation-specific references in the API surface.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends, status

from ..dependencies.auth import CurrentUser, require_permission
from ..lib.garage import get_base_client, get_retention_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/storage", tags=["storage-admin"])


@router.get("/health")
async def storage_health(
    current_user: CurrentUser,
    _: None = Depends(require_permission("storage", "read"))
):
    """
    Check storage backend liveness.

    Verifies the S3-compatible storage is accessible and the
    configured bucket exists.

    **Authorization:** Requires `storage:read` permission
    """
    try:
        client = get_base_client()
        healthy = client.health_check()
        return {
            "healthy": healthy,
            "bucket": client.bucket_name,
            "endpoint": client.endpoint
        }
    except Exception as e:
        logger.error(f"Storage health check failed: {e}")
        return {
            "healthy": False,
            "bucket": None,
            "endpoint": None,
            "error": str(e)
        }


@router.get("/stats")
async def storage_stats(
    current_user: CurrentUser,
    _: None = Depends(require_permission("storage", "read"))
):
    """
    Get aggregate storage statistics by category.

    Returns object counts and total bytes for each storage category:
    sources, images, projections, artifacts.

    **Authorization:** Requires `storage:read` permission
    """
    try:
        retention = get_retention_manager()
        stats = retention.get_storage_stats()
        return {
            "total_objects": stats.total_objects,
            "total_bytes": stats.total_bytes,
            "by_category": stats.by_category
        }
    except Exception as e:
        logger.error(f"Failed to get storage stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get storage stats: {str(e)}"
        )


@router.get("/objects")
async def list_storage_objects(
    current_user: CurrentUser,
    _: None = Depends(require_permission("storage", "read")),
    prefix: Optional[str] = Query(
        default="",
        description="S3 key prefix filter (e.g. 'sources/', 'images/My_Ontology/')"
    ),
    limit: int = Query(default=50, ge=1, le=500, description="Page size"),
    offset: int = Query(default=0, ge=0, description="Number of objects to skip")
):
    """
    List objects in storage with optional prefix filter and pagination.

    Objects are returned sorted by key. Use prefix to scope to a category
    (sources/, images/, projections/, artifacts/) or a specific ontology
    within a category (sources/My_Ontology/).

    **Authorization:** Requires `storage:read` permission
    """
    try:
        client = get_base_client()
        all_objects = client.list_objects(prefix or "")

        total = len(all_objects)
        page = all_objects[offset:offset + limit]

        # Serialize datetime objects for JSON response
        serialized = []
        for obj in page:
            entry = {
                "key": obj["key"],
                "size": obj["size"],
                "last_modified": obj["last_modified"].isoformat() if hasattr(obj["last_modified"], "isoformat") else str(obj["last_modified"]),
                "etag": obj["etag"]
            }
            serialized.append(entry)

        return {
            "objects": serialized,
            "total": total,
            "prefix": prefix or "",
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Failed to list storage objects: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list storage objects: {str(e)}"
        )


@router.get("/objects/metadata")
async def get_object_metadata(
    current_user: CurrentUser,
    _: None = Depends(require_permission("storage", "read")),
    key: str = Query(..., description="Exact S3 object key")
):
    """
    Get metadata for a single object without downloading its content.

    Returns S3 headers including size, content type, last modified time,
    ETag, and any custom metadata attached during upload (e.g. ontology,
    content-hash, original-filename, username).

    **Authorization:** Requires `storage:read` permission
    """
    try:
        client = get_base_client()
        metadata = client.head_object(key)

        if metadata is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Object not found: {key}"
            )

        # Serialize datetime
        if hasattr(metadata.get("last_modified"), "isoformat"):
            metadata["last_modified"] = metadata["last_modified"].isoformat()

        return metadata
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get object metadata for {key}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get object metadata: {str(e)}"
        )


@router.get("/integrity")
async def check_storage_integrity(
    current_user: CurrentUser,
    _: None = Depends(require_permission("storage", "read")),
    ontology: Optional[str] = Query(
        default=None,
        description="Scope check to a specific ontology (checks all if omitted)"
    ),
    category: str = Query(
        default="sources",
        description="Storage category to check: sources, images"
    )
):
    """
    Cross-reference S3 objects against graph nodes to find discrepancies.

    Compares what exists in object storage against what the graph database
    references. Reports:
    - **orphaned_in_s3**: Objects in S3 with no corresponding graph node
    - **missing_from_s3**: Graph nodes referencing S3 keys that don't exist

    Useful for verifying cascade deletes and debugging storage issues.

    **Authorization:** Requires `storage:read` permission
    """
    from ..lib.age_client import AGEClient
    from ..lib.garage.base import sanitize_path_component

    if category not in ("sources", "images"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Integrity check supports categories: sources, images. Got: {category}"
        )

    try:
        client = get_base_client()

        # Build S3 prefix
        if ontology:
            safe_ontology = sanitize_path_component(ontology)
            s3_prefix = f"{category}/{safe_ontology}/"
        else:
            s3_prefix = f"{category}/"

        # Get all S3 keys
        s3_objects = client.list_objects(s3_prefix)
        s3_keys = {obj["key"] for obj in s3_objects}

        # Get all graph references to S3 keys
        # Each category stores its S3 key in a different Source node property
        key_property = {"sources": "garage_key", "images": "object_key"}[category]

        age_client = AGEClient()
        try:
            results = age_client._execute_cypher(
                f"""
                MATCH (s:Source)
                WHERE s.{key_property} IS NOT NULL
                  AND s.{key_property} STARTS WITH $prefix
                RETURN s.{key_property} as key
                """,
                params={"prefix": s3_prefix}
            )
            graph_keys = {r["key"] for r in (results or [])}

        finally:
            age_client.close()

        # Compute set differences
        orphaned_in_s3 = sorted(s3_keys - graph_keys)
        missing_from_s3 = sorted(graph_keys - s3_keys)

        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "ontology": ontology,
            "category": category,
            "s3_objects": len(s3_keys),
            "graph_references": len(graph_keys),
            "orphaned_in_s3": orphaned_in_s3,
            "missing_from_s3": missing_from_s3,
            "is_consistent": len(orphaned_in_s3) == 0 and len(missing_from_s3) == 0
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Integrity check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Integrity check failed: {str(e)}"
        )


@router.get("/retention")
async def get_retention_policies(
    current_user: CurrentUser,
    _: None = Depends(require_permission("storage", "read"))
):
    """
    Get current retention policy configuration.

    Shows the retention rules applied to each storage category:
    - projections: history count limits and max age
    - sources: keep-always policy
    - images: keep-always policy

    **Authorization:** Requires `storage:read` permission
    """
    try:
        retention = get_retention_manager()
        return {
            "policies": retention.policies
        }
    except Exception as e:
        logger.error(f"Failed to get retention policies: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get retention policies: {str(e)}"
        )
