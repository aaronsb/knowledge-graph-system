"""
Async restore worker (ADR-015 Phase 2)

Executes database restore operations as background jobs with:
- Checkpoint backup safety pattern
- Progress tracking (nodes, relationships, percent)
- Automatic rollback on failure
- Temp file cleanup
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from ..lib.age_client import AGEClient
from ..lib.backup_streaming import create_backup_stream
from ...lib.serialization import DataImporter

logger = logging.getLogger(__name__)


def run_restore_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Execute database restore as a background job.

    Implements ADR-015 Checkpoint Backup Safety Pattern:
    1. Create checkpoint backup (current database state)
    2. Execute restore operation
    3. Run integrity check
    4. On success → delete checkpoint
    5. On failure → restore from checkpoint

    Args:
        job_data: Job parameters
            - temp_file: str - Path to uploaded backup file
            - temp_file_id: str - UUID of temp file
            - overwrite: bool - Overwrite existing data
            - handle_external_deps: str - How to handle external dependencies
            - backup_stats: dict - Statistics from backup file
            - integrity_warnings: int - Number of validation warnings
        job_id: Job ID for progress tracking
        job_queue: Queue instance for progress updates

    Returns:
        Result dict with restore stats and checkpoint info

    Raises:
        Exception: If restore fails (after checkpoint rollback)
    """
    temp_file = Path(job_data["temp_file"])
    temp_file_id = job_data["temp_file_id"]
    overwrite = job_data.get("overwrite", False)
    handle_external_deps = job_data.get("handle_external_deps", "prune")
    backup_stats = job_data.get("backup_stats", {})

    checkpoint_path = None
    client = None

    try:
        # Stage 1: Create checkpoint backup (ADR-015 Safety Pattern)
        logger.info(f"[{job_id}] Creating checkpoint backup before restore")
        job_queue.update_job(job_id, {
            "progress": {
                "stage": "creating_checkpoint",
                "percent": 5,
                "message": "Creating checkpoint backup of current database state"
            }
        })

        client = AGEClient()
        checkpoint_path = _create_checkpoint_backup(client, job_id)

        logger.info(f"[{job_id}] Checkpoint created at {checkpoint_path}")

        # Stage 2: Load backup file
        logger.info(f"[{job_id}] Loading backup file {temp_file}")
        job_queue.update_job(job_id, {
            "progress": {
                "stage": "loading_backup",
                "percent": 10,
                "message": f"Loading backup file ({backup_stats.get('concepts', 0)} concepts)"
            }
        })

        with open(temp_file, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)

        # Stage 3: Execute restore with progress tracking
        logger.info(f"[{job_id}] Starting restore operation (overwrite={overwrite})")

        restore_stats = _execute_restore(
            client=client,
            backup_data=backup_data,
            overwrite=overwrite,
            handle_external_deps=handle_external_deps,
            job_id=job_id,
            job_queue=job_queue
        )

        # Stage 4: Integrity check (future enhancement)
        # TODO: Add database integrity check after restore
        logger.info(f"[{job_id}] Restore completed successfully")
        job_queue.update_job(job_id, {
            "progress": {
                "stage": "completed",
                "percent": 100,
                "message": "Restore completed successfully"
            }
        })

        # Success: Delete checkpoint
        if checkpoint_path and checkpoint_path.exists():
            logger.info(f"[{job_id}] Deleting checkpoint backup (restore successful)")
            checkpoint_path.unlink()
            checkpoint_deleted = True
        else:
            checkpoint_deleted = False

        return {
            "status": "completed",
            "restore_stats": restore_stats,
            "checkpoint_created": True,
            "checkpoint_deleted": checkpoint_deleted,
            "temp_file_cleaned": False  # Will be cleaned in finally block
        }

    except Exception as e:
        logger.error(f"[{job_id}] Restore failed: {str(e)}")

        # Failure: Restore from checkpoint
        if checkpoint_path and checkpoint_path.exists():
            logger.warning(f"[{job_id}] Attempting rollback from checkpoint")
            job_queue.update_job(job_id, {
                "progress": {
                    "stage": "rollback",
                    "percent": 0,
                    "message": "Restore failed - rolling back to checkpoint"
                }
            })

            try:
                _restore_from_checkpoint(client or AGEClient(), checkpoint_path, job_id, job_queue)
                logger.info(f"[{job_id}] Successfully rolled back to checkpoint")
                rollback_success = True
            except Exception as rollback_error:
                logger.error(f"[{job_id}] Rollback failed: {str(rollback_error)}")
                rollback_success = False
        else:
            rollback_success = False

        # Re-raise original exception with context
        raise Exception(
            f"Restore failed: {str(e)}. "
            f"{'Database rolled back to checkpoint.' if rollback_success else 'Checkpoint rollback also failed - manual intervention required!'}"
        )

    finally:
        # Cleanup: Always delete temp file
        if temp_file.exists():
            logger.info(f"[{job_id}] Cleaning up temp file {temp_file}")
            try:
                temp_file.unlink()
            except Exception as e:
                logger.warning(f"[{job_id}] Failed to delete temp file: {e}")

        # Close database connection
        if client:
            client.close()


def _create_checkpoint_backup(client: AGEClient, job_id: str) -> Path:
    """
    Create checkpoint backup of current database state.

    Returns:
        Path to checkpoint file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    checkpoint_filename = f".checkpoint_{job_id}_{timestamp}.json"
    checkpoint_path = Path.home() / ".local" / "share" / "kg" / "backups" / checkpoint_filename

    # Ensure backup directory exists
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    # Export full database backup
    from ...lib.serialization import DataExporter
    backup_data = DataExporter.export_full_backup(client)

    # Save checkpoint
    with open(checkpoint_path, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2)

    logger.info(f"[{job_id}] Checkpoint backup created: {checkpoint_path} ({checkpoint_path.stat().st_size} bytes)")

    return checkpoint_path


def _execute_restore(
    client: AGEClient,
    backup_data: Dict[str, Any],
    overwrite: bool,
    handle_external_deps: str,
    job_id: str,
    job_queue
) -> Dict[str, int]:
    """
    Execute restore operation with progress tracking.

    Returns:
        Dict with restore statistics
    """
    data_section = backup_data.get("data", {})
    concepts = data_section.get("concepts", [])
    sources = data_section.get("sources", [])
    instances = data_section.get("instances", [])
    relationships = data_section.get("relationships", [])

    total_items = len(concepts) + len(sources) + len(instances) + len(relationships)

    if total_items == 0:
        return {"concepts": 0, "sources": 0, "instances": 0, "relationships": 0}

    # Use DataImporter to restore
    importer = DataImporter(client)

    # Restore concepts
    job_queue.update_job(job_id, {
        "progress": {
            "stage": "restoring_concepts",
            "percent": 20,
            "items_total": len(concepts),
            "items_processed": 0,
            "message": f"Restoring {len(concepts)} concepts"
        }
    })

    concepts_restored = 0
    for i, concept in enumerate(concepts, 1):
        importer.import_concept(concept)
        concepts_restored += 1

        if i % 10 == 0:  # Update every 10 concepts
            percent = 20 + int((i / len(concepts)) * 20)
            job_queue.update_job(job_id, {
                "progress": {
                    "stage": "restoring_concepts",
                    "percent": percent,
                    "items_total": len(concepts),
                    "items_processed": i
                }
            })

    # Restore sources
    job_queue.update_job(job_id, {
        "progress": {
            "stage": "restoring_sources",
            "percent": 40,
            "items_total": len(sources),
            "items_processed": 0,
            "message": f"Restoring {len(sources)} sources"
        }
    })

    sources_restored = 0
    for i, source in enumerate(sources, 1):
        importer.import_source(source)
        sources_restored += 1

        if i % 10 == 0:
            percent = 40 + int((i / len(sources)) * 20)
            job_queue.update_job(job_id, {
                "progress": {
                    "stage": "restoring_sources",
                    "percent": percent,
                    "items_total": len(sources),
                    "items_processed": i
                }
            })

    # Restore instances
    job_queue.update_job(job_id, {
        "progress": {
            "stage": "restoring_instances",
            "percent": 60,
            "items_total": len(instances),
            "items_processed": 0,
            "message": f"Restoring {len(instances)} instances"
        }
    })

    instances_restored = 0
    for i, instance in enumerate(instances, 1):
        importer.import_instance(instance)
        instances_restored += 1

        if i % 10 == 0:
            percent = 60 + int((i / len(instances)) * 20)
            job_queue.update_job(job_id, {
                "progress": {
                    "stage": "restoring_instances",
                    "percent": percent,
                    "items_total": len(instances),
                    "items_processed": i
                }
            })

    # Restore relationships
    job_queue.update_job(job_id, {
        "progress": {
            "stage": "restoring_relationships",
            "percent": 80,
            "items_total": len(relationships),
            "items_processed": 0,
            "message": f"Restoring {len(relationships)} relationships"
        }
    })

    relationships_restored = 0
    for i, rel in enumerate(relationships, 1):
        importer.import_relationship(rel)
        relationships_restored += 1

        if i % 10 == 0:
            percent = 80 + int((i / len(relationships)) * 15)
            job_queue.update_job(job_id, {
                "progress": {
                    "stage": "restoring_relationships",
                    "percent": percent,
                    "items_total": len(relationships),
                    "items_processed": i
                }
            })

    return {
        "concepts": concepts_restored,
        "sources": sources_restored,
        "instances": instances_restored,
        "relationships": relationships_restored
    }


def _restore_from_checkpoint(client: AGEClient, checkpoint_path: Path, job_id: str, job_queue) -> None:
    """
    Restore database from checkpoint backup (rollback).

    This is called when the main restore operation fails.
    """
    logger.info(f"[{job_id}] Rolling back to checkpoint {checkpoint_path}")

    # Load checkpoint
    with open(checkpoint_path, 'r', encoding='utf-8') as f:
        checkpoint_data = json.load(f)

    # Clear current database
    logger.info(f"[{job_id}] Clearing database before checkpoint restore")
    client.clear_graph()

    # Restore from checkpoint (no progress tracking - this is emergency rollback)
    importer = DataImporter(client)

    data_section = checkpoint_data.get("data", {})

    for concept in data_section.get("concepts", []):
        importer.import_concept(concept)

    for source in data_section.get("sources", []):
        importer.import_source(source)

    for instance in data_section.get("instances", []):
        importer.import_instance(instance)

    for rel in data_section.get("relationships", []):
        importer.import_relationship(rel)

    logger.info(f"[{job_id}] Checkpoint rollback complete")

    # Keep checkpoint file for inspection
    logger.info(f"[{job_id}] Checkpoint file preserved at {checkpoint_path} for inspection")
