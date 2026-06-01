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
from ..lib.lane_control import (
    RESTORE_FREEZE_LANES,
    freeze_lanes,
    thaw_lanes,
    wait_for_quiesce,
)

# ADR-102 P5: epoch-simple restore records a single graph_epochs event of this
# kind (migration 077) so the freshness clock advances and restored nodes carry
# a real, local event id.
RESTORE_EPOCH_KIND = "restore"

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
    lane_prior = None       # ADR-102 A14: prior lane-enabled state, restored on exit
    restore_event_id = None  # ADR-102 P5: the single restore graph_epochs event

    try:
        # ADR-100: Check for cancellation before restore
        if job_queue.is_job_cancelled(job_id):
            logger.info(f"Restore job {job_id} cancelled before start")
            return {"status": "cancelled"}

        # ADR-102 A14: freeze mutating lanes (interactive/maintenance) and wait
        # for their in-flight jobs to drain, so nothing writes the graph while we
        # checkpoint + import. The system lane (which runs THIS job and the
        # post-restore rehydration) stays enabled. Fail-open: proceed after the
        # quiesce timeout with a warning rather than blocking the restore.
        logger.info(f"[{job_id}] Freezing worker lanes {RESTORE_FREEZE_LANES} for restore")
        job_queue.update_job(job_id, {
            "progress": {
                "stage": "quiescing",
                "percent": 2,
                "message": f"Freezing worker lanes {RESTORE_FREEZE_LANES} and draining in-flight jobs"
            }
        })
        lane_prior = freeze_lanes(job_queue, RESTORE_FREEZE_LANES)
        wait_for_quiesce(job_queue, RESTORE_FREEZE_LANES)

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
        logger.info(f"[{job_id}] Restore mode: {mode}")
        prepared_backup, mapping_table = prepare_backup(backup_data, mode, client)

        # ADR-102 P5 (epoch-simple): record ONE restore epoch event up front so its
        # event_id can stamp every imported node. The carried bulk.graph_epochs are
        # NOT replayed (that is P5-faithful, clone-only). record_epoch inserts an
        # in_progress event that holds the committed watermark just below it until
        # complete_epoch resolves it — exactly the long-job tagging pattern the
        # ingestion worker uses.
        #
        # ADR-102 A13: a failed record_epoch is FATAL here (not log-and-continue).
        # Without an event id every restored Instance would be untagged AND the
        # post-restore watermark advance below would be meaningless — restored
        # data could read FRESH against stale derivations. Fail loudly instead.
        restore_event_id = client.record_epoch(
            kind=RESTORE_EPOCH_KIND,
            actor="restore",
            metadata={"job_id": job_id, "mode": mode, "restore": True},
        )
        if restore_event_id is None:
            raise RuntimeError(
                "record_epoch returned None — cannot stamp restored nodes with a "
                "graph epoch (the freshness clock would be left inconsistent). "
                "Check kg_api.graph_epochs health (grep 'record_epoch failed')."
            )
        logger.info(f"[{job_id}] Restore epoch event_id={restore_event_id}")

        # Concept epochs live in the separate document_ingestion_counter space
        # (ADR-200), not the graph_epochs.event_id space — so they restamp to the
        # target's CURRENT concept epoch, not the restore event_id.
        restore_concept_epoch = client.get_current_epoch()

        # Stage 3: Execute restore with progress tracking
        restore_stats = _execute_restore(
            client=client,
            backup_data=prepared_backup,
            job_id=job_id,
            job_queue=job_queue,
            epoch_restamp={
                "event_id": restore_event_id,
                "concept_epoch": restore_concept_epoch,
            },
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

        # ADR-207/#386 + ADR-102 P5: resolve the restore epoch as COMPLETED. Until
        # now it held the committed watermark just below its event_id, so every
        # derivation correctly read stale during the import. Completing it advances
        # the universal freshness tick (get_committed_epoch) past every restored
        # node's stamp; otherwise the catalog index and the grounding / confidence
        # / artifact caches would keep serving pre-restore data as "fresh".
        #
        # The record_epoch/complete_epoch pair does NOT co-advance the in-memory
        # graph_accel sub-counter on its own (the docstring co-advance caveat /
        # issue #465) — only record_mutation does. So invalidate the accelerator
        # and refresh the graph_change_counter snapshot explicitly, matching what
        # record_mutation would have done.
        client.complete_epoch(restore_event_id, "completed")
        try:
            client.graph.invalidate()
        except Exception:
            pass  # extension may not be loaded on this connection
        try:
            client.refresh_epoch()
        except Exception as e:
            logger.warning(f"[{job_id}] refresh_epoch after restore failed: {e}")
        logger.info(f"[{job_id}] Restore epoch {restore_event_id} completed (freshness tick advanced)")

        # ADR-102 P5 rehydration: source text/visual embeddings do NOT travel in
        # the backup (concept + vocab embeddings do, and scores/catalog/grounding
        # self-heal off the freshness tick just advanced). Enqueue ONE bulk
        # only-missing source-embedding job — it runs in the system lane AFTER this
        # restore releases the slot, and skips any source that already has
        # embeddings. Best-effort: a failure to enqueue must not fail a completed
        # restore (the operator can run the regeneration endpoint manually).
        rehydrate_job_id = None
        try:
            rehydrate_job_id = job_queue.enqueue("source_embedding", {
                "rehydrate_missing": True,
                "reason": "post_restore_rehydration",
                "restore_job_id": job_id,
            })
            # Auto-approve as a system job (ADR-050) so the system lane claims it
            # — enqueue() lands jobs as 'pending' (user-upload approval workflow),
            # but this is internally triggered, not a user upload.
            job_queue.update_job(rehydrate_job_id, {
                "is_system_job": True,
                "job_source": "post_restore_rehydration",
                "created_by": f"system:restore:{job_id}",
                "status": "approved",
                "approved_at": datetime.now().isoformat(),
                "approved_by": "system:restore",
            })
            logger.info(f"[{job_id}] Enqueued source-embedding rehydration job {rehydrate_job_id}")
        except Exception as e:
            logger.warning(f"[{job_id}] Failed to enqueue source-embedding rehydration: {e}")

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
            "restore_epoch_event_id": restore_event_id,
            "rehydration_job_id": rehydrate_job_id,
            "checkpoint_created": True,
            "checkpoint_deleted": checkpoint_deleted,
            "temp_file_cleaned": False  # Will be cleaned in finally block
        }

    except Exception as e:
        logger.error(f"[{job_id}] Restore failed: {str(e)}")

        # ADR-102 P5: resolve the restore epoch as FAILED so it stops holding the
        # committed watermark below its event_id (a phantom in-flight event would
        # stall freshness for the whole graph). The rollback below re-imports the
        # checkpoint with its OWN carried stamps (no restamp), so this failed event
        # tags nothing that survives.
        if restore_event_id is not None and client is not None:
            client.complete_epoch(restore_event_id, "failed")

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
        # ADR-102 A14: ALWAYS thaw the lanes we froze, restoring their prior
        # enabled state (a lane an operator had already disabled stays disabled).
        # thaw_lanes is best-effort and never raises, so it cannot mask the
        # restore's own outcome.
        if lane_prior:
            thaw_lanes(job_queue, lane_prior)

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


def _execute_restore(
    client: AGEClient,
    backup_data: Dict[str, Any],
    job_id: str,
    job_queue,
    epoch_restamp: Dict[str, int] = None
) -> Dict[str, int]:
    """
    Execute restore of an already-mode-prepared kg-backup/2 object, with progress.

    The object has already been transformed for its restore mode (idempotent =
    unchanged; adjacent/integration = ids rewritten). The writer always uses
    overwrite_existing=True: idempotent updates matching nodes in place, while
    adjacent/integration ids are fresh or attach to existing targets.

    ``epoch_restamp`` (ADR-102 P5 epoch-simple) overrides carried epoch stamps
    with local clocks — see ``DataImporter.import_backup``.

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
        progress_callback=progress_callback,
        epoch_restamp=epoch_restamp
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
