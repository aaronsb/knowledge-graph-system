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
from ..lib.backup_archive import restore_documents_to_garage, cleanup_extracted_archive
from ...lib.serialization import DataImporter, KgBackupV2Reader
from ..lib.restore_modes import RestoreMode, prepare_backup

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
            - mode: str - Restore merge mode (idempotent | adjacent | integration)
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
    mode = RestoreMode.validate(job_data.get("mode", RestoreMode.DEFAULT))
    backup_stats = job_data.get("backup_stats", {})
    archive_temp_dir = job_data.get("archive_temp_dir")  # For archive restores
    is_archive = job_data.get("is_archive", False)

    checkpoint_path = None
    client = None

    try:
        # ADR-100: Check for cancellation before restore
        if job_queue.is_job_cancelled(job_id):
            logger.info(f"Restore job {job_id} cancelled before start")
            return {"status": "cancelled"}

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

        # Stage 2.5: ADR-102 P4 — transform the backup for the chosen restore MODE
        # (a restore-time request param; the backup file carries no policy).
        #   idempotent  → MERGE-by-id in place (into an empty target: a faithful clone)
        #   adjacent    → fresh ids everywhere (independent copy + mapping table)
        #   integration → match concepts to existing target & attach; mint the rest
        target_state = "empty" if _target_is_empty(client) else "populated"
        logger.info(f"[{job_id}] Restore mode: {mode} (target {target_state})")
        prepared_backup, mapping_table = prepare_backup(backup_data, mode, client)

        # Stage 3: Execute restore with progress tracking
        restore_stats = _execute_restore(
            client=client,
            backup_data=prepared_backup,
            job_id=job_id,
            job_queue=job_queue
        )

        # Stage 4: Restore documents to Garage (for archive backups)
        doc_stats = {"uploaded": 0, "skipped": 0, "failed": 0}
        if is_archive and archive_temp_dir:
            logger.info(f"[{job_id}] Restoring documents to Garage from archive")
            job_queue.update_job(job_id, {
                "progress": {
                    "stage": "restoring_documents",
                    "percent": 95,
                    "message": "Restoring documents to Garage storage"
                }
            })

            # Use the PREPARED object: adjacent/integration recompute storage_keys,
            # so media must land under the same keys the restored source nodes now
            # reference. overwrite=False skips media already present (same content).
            doc_stats = restore_documents_to_garage(
                temp_dir=archive_temp_dir,
                manifest_data=prepared_backup,
                overwrite=False
            )

            logger.info(
                f"[{job_id}] Document restore: {doc_stats['uploaded']} uploaded, "
                f"{doc_stats['skipped']} skipped, {doc_stats['failed']} failed"
            )

        # Stage 5: Integrity check (future enhancement)
        # TODO: Add database integrity check after restore
        logger.info(f"[{job_id}] Restore completed successfully")
        job_queue.update_job(job_id, {
            "progress": {
                "stage": "completed",
                "percent": 100,
                "message": "Restore completed successfully"
            }
        })

        # ADR-207/#386: a restore wholesale replaces the graph — the single
        # largest possible mutation. Announce it via record_mutation so the
        # universal freshness tick (get_committed_epoch) advances past every
        # derivation's stamp; otherwise the catalog index and the grounding /
        # confidence / artifact caches keep serving pre-restore data as "fresh".
        # record_mutation records a completed epoch event (advances the tick),
        # invalidates graph_accel, AND refreshes the graph_change_counter
        # snapshot — subsuming the bare refresh_graph_metrics() this replaced.
        try:
            metrics_client = AGEClient()
            try:
                metrics_client.record_mutation(
                    "ingestion",
                    actor="restore",
                    metadata={"restore": True, "job_id": job_id},
                )
                logger.info(f"[{job_id}] Recorded restore as a graph mutation (freshness tick advanced)")
            finally:
                metrics_client.close()
        except Exception as e:
            logger.warning(f"[{job_id}] Failed to record restore mutation: {e}")

        # Success: Delete checkpoint
        if checkpoint_path and checkpoint_path.exists():
            logger.info(f"[{job_id}] Deleting checkpoint backup (restore successful)")
            checkpoint_path.unlink()
            checkpoint_deleted = True
        else:
            checkpoint_deleted = False

        # Mapping table is the transposition artifact for adjacent/integration
        # (old→new ids). Empty for idempotent — omit it then to keep results small.
        remapped = any(mapping_table.get(k) for k in ("concepts", "sources", "instances"))
        return {
            "status": "completed",
            "restore_mode": mode,
            "restore_stats": restore_stats,
            "mapping_table": mapping_table if remapped else None,
            "document_stats": doc_stats if is_archive else None,
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

        # Cleanup: Always delete extracted archive directory
        if archive_temp_dir:
            logger.info(f"[{job_id}] Cleaning up archive temp directory {archive_temp_dir}")
            cleanup_extracted_archive(archive_temp_dir)

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

    # Export full database backup (single model: kg-backup/2)
    from ...lib.serialization import DataExporter
    backup_data = DataExporter.export_kg_backup_v2(client)

    # Save checkpoint
    with open(checkpoint_path, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2)

    logger.info(f"[{job_id}] Checkpoint backup created: {checkpoint_path} ({checkpoint_path.stat().st_size} bytes)")

    return checkpoint_path


def _clear_database(client: AGEClient, job_id: str) -> None:
    """
    Clear concept graph data from the database.

    Used when restoring a full backup to ensure clean slate.
    Deletes concept graph nodes (Concept, Source, Instance) and their relationships.

    Note (ADR-048): Preserves vocabulary metadata (VocabType, VocabCategory) nodes.
    These live in a separate namespace and should not be cleared during restore.
    """
    logger.info(f"[{job_id}] Clearing concept graph data")

    # DETACH DELETE removes nodes and relationships atomically
    # AGE doesn't support WHERE with label OR, so use 3 separate queries
    # Still faster than original 6 queries (no separate relationship deletion needed)
    client._execute_cypher("MATCH (n:Concept) DETACH DELETE n")
    client._execute_cypher("MATCH (n:Source) DETACH DELETE n")
    client._execute_cypher("MATCH (n:Instance) DETACH DELETE n")

    logger.info(f"[{job_id}] Concept graph cleared successfully (vocabulary preserved)")


def _target_is_empty(client: AGEClient) -> bool:
    """Return True if the concept graph holds no Concept/Source/Instance nodes.

    The ADR-102 clone/merge gate: an empty target is restored by CLONE (ids
    preserved 1:1); a populated target is a MERGE. A label whose backing table does
    not exist yet (fresh database) counts as empty.
    """
    for label in ("Concept", "Source", "Instance"):
        try:
            row = client._execute_cypher(
                f"MATCH (n:{label}) RETURN count(n) AS c", fetch_one=True
            )
        except Exception:
            continue  # label table absent → no such nodes
        if row and int(str(row.get("c", 0)).strip('"')) > 0:
            return False
    return True


def _execute_restore(
    client: AGEClient,
    backup_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, int]:
    """
    Execute restore of an already-mode-prepared kg-backup/2 object, with progress.

    The object has already been transformed for its restore mode (idempotent =
    unchanged; adjacent/integration = ids rewritten). The writer always uses
    overwrite_existing=True: idempotent updates matching nodes in place, while
    adjacent/integration ids are fresh or attach to existing targets.

    Returns:
        Dict with restore statistics
    """
    counts = KgBackupV2Reader(backup_data).counts()
    n_concepts = counts["concepts"]
    n_sources = counts["sources"]
    n_instances = counts["instances"]
    n_relationships = counts["relationships"]

    total_items = n_concepts + n_sources + n_instances + n_relationships

    if total_items == 0:
        return {"concepts": 0, "sources": 0, "instances": 0, "relationships": 0}

    # Track cumulative progress across all stages
    items_processed_cumulative = 0

    def progress_callback(stage: str, current: int, total: int, percent: float):
        """
        Progress callback for DataImporter (ADR-018 Phase 2)

        Called every N items during import to update job progress.
        Calculates overall progress across all stages.
        """
        nonlocal items_processed_cumulative

        # Calculate cumulative items based on stage
        if stage == "concepts":
            items_processed_cumulative = current
        elif stage == "sources":
            items_processed_cumulative = n_concepts + current
        elif stage == "instances":
            items_processed_cumulative = n_concepts + n_sources + current
        elif stage == "relationships":
            items_processed_cumulative = n_concepts + n_sources + n_instances + current

        # Calculate overall percent (0-100)
        overall_percent = int((items_processed_cumulative / total_items) * 100) if total_items > 0 else 0

        # Update job progress
        job_queue.update_job(job_id, {
            "progress": {
                "stage": f"restoring_{stage}",
                "percent": overall_percent,
                "items_total": total_items,
                "items_processed": items_processed_cumulative,
                "message": f"Restoring {stage}: {current}/{total} ({int(percent)}%)"
            }
        })

    # Import all data using DataImporter with progress callback
    stats = DataImporter.import_backup(
        client,
        backup_data,
        overwrite_existing=True,
        progress_callback=progress_callback
    )

    return {
        "concepts": stats.get("concepts_created", 0),
        "sources": stats.get("sources_created", 0),
        "instances": stats.get("instances_created", 0),
        "relationships": stats.get("relationships_created", 0)
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

    # Restore from checkpoint using DataImporter.import_backup()
    # No need to clear database - import_backup() uses MERGE which handles overwrites
    logger.info(f"[{job_id}] Restoring checkpoint data")
    DataImporter.import_backup(client, checkpoint_data, overwrite_existing=True)

    logger.info(f"[{job_id}] Checkpoint rollback complete")

    # Keep checkpoint file for inspection
    logger.info(f"[{job_id}] Checkpoint file preserved at {checkpoint_path} for inspection")
