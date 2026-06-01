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
from typing import Dict, Any, Optional
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

# ADR-102 P5: epoch reconciliation modes (restore-time selector).
#   simple   — collapse the backup's history into ONE restore event (default, all modes)
#   faithful — replay the carried graph_epochs as new local events (clone-only)
EPOCH_SIMPLE = "simple"
EPOCH_FAITHFUL = "faithful"
_EPOCH_MODES = (EPOCH_SIMPLE, EPOCH_FAITHFUL)


def _validate_epoch_mode(value) -> str:
    """Validate the epoch reconciliation mode, defaulting to simple."""
    v = (value or EPOCH_SIMPLE).lower()
    if v not in _EPOCH_MODES:
        raise ValueError(f"Unknown epoch mode {value!r}; expected one of {_EPOCH_MODES}")
    return v


def _max_carried_concept_epoch(backup_data: Dict[str, Any]):
    """Max of concepts' carried created_at/last_seen epochs, or None if none.

    P5-faithful sets the target's document_ingestion_counter to this so the
    restored concepts' carried epochs do not read as 'from the future'.
    """
    reader = KgBackupV2Reader(backup_data)
    hi = None
    for c in reader.concepts():
        for key in ("created_at_epoch", "last_seen_epoch"):
            v = c.get(key)
            if v is not None and (hi is None or v > hi):
                hi = v
    return hi


def _target_is_empty(client: AGEClient) -> bool:
    """True if the target holds no graph nodes AND no epoch history.

    Faithful epoch replay (ADR-102) mints fresh local event_ids but only makes
    sense when reconstructing a graph from scratch — merging a full foreign
    history into a graph that already has its own would interleave two unrelated
    timelines. Both the node graph and the graph_epochs log must be empty.
    """
    for label in ("Concept", "Source", "Instance"):
        row = client._execute_cypher(f"MATCH (n:{label}) RETURN count(n) AS n", fetch_one=True)
        if row and int(str(row.get("n", 0)).strip('"')) > 0:
            return False
    conn = client.pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('kg_api.graph_epochs') IS NOT NULL")
            if cur.fetchone()[0]:
                cur.execute("SELECT count(*) FROM kg_api.graph_epochs")
                if int(cur.fetchone()[0]) > 0:
                    return False
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        client.pool.putconn(conn)
    return True

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
    epoch_mode = _validate_epoch_mode(job_data.get("epoch", EPOCH_SIMPLE))
    backup_stats = job_data.get("backup_stats", {})
    archive_temp_dir = job_data.get("archive_temp_dir")  # For archive restores
    is_archive = job_data.get("is_archive", False)

    checkpoint_path = None
    client = None
    lane_prior = None         # ADR-102 A14: prior lane-enabled state, restored on exit
    restore_event_id = None   # ADR-102 P5 epoch-simple: the single restore event
    replayed_event_ids = None  # ADR-102 P5-faithful: ids minted by the epoch replay
    quiesced = True          # ADR-102 A14: did frozen lanes drain before the timeout?

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
        # Fail-open: a False return means we proceeded over un-drained in-flight
        # work. Surface it in the job result so an operator can correlate later.
        quiesced = wait_for_quiesce(job_queue, RESTORE_FREEZE_LANES)

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

        # ADR-102 P5-faithful eligibility gate (fail fast, before checkpoint/import).
        # Faithful epoch replay is clone-only: it requires idempotent mode AND an
        # empty target. Reject otherwise with the actionable alternatives rather
        # than silently downgrading (faithful is an explicit opt-in).
        if epoch_mode == EPOCH_FAITHFUL:
            if mode != RestoreMode.IDEMPOTENT:
                raise ValueError(
                    f"epoch=faithful requires --mode idempotent (got {mode!r}). "
                    f"Faithful replay preserves per-event history against preserved "
                    f"node ids; adjacent/integration mint new ids. Use --epoch simple, "
                    f"or --mode idempotent into an empty target."
                )
            if not _target_is_empty(client):
                raise ValueError(
                    "epoch=faithful requires an EMPTY target (no concepts/sources/"
                    "instances and no epoch history) — it reconstructs a graph's full "
                    "history from scratch. For a populated target use --epoch simple, "
                    "or --mode integration to merge into the existing graph."
                )

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

        # ADR-102 P5: epoch reconciliation. Both modes record graph_epochs as
        # in_progress so the committed watermark sits below them and the graph reads
        # STALE during the import; they resolve to 'completed' after the import lands.
        logger.info(f"[{job_id}] Epoch mode: {epoch_mode}")
        epoch_restamp = None
        event_id_map = None

        if epoch_mode == EPOCH_FAITHFUL:
            # Faithful (clone-only): replay the carried graph_epochs as NEW local
            # events (fresh ids, carried occurred_at/kind/actor/metadata), then stamp
            # each Instance via the old→new map. Concepts carry their ORIGINAL epochs;
            # the counter is advanced after import so vitality stays consistent.
            #
            # Raw INSERT (not record_epoch) so we can carry occurred_at + mint N rows
            # in one pass — watermark-equivalent to the simple path's stored-function
            # in_progress event. A crash between this commit and the resolve below
            # leaves N rows in_progress (the simple path leaves 1); the orphaned-epoch
            # reconciliation sweep that fixes both is tracked in issue #485.
            reader = KgBackupV2Reader(prepared_backup)
            DataImporter._ensure_epoch_kinds(client, reader)
            event_id_map = DataImporter._replay_graph_epochs(
                client, reader, status="in_progress", owner_job_id=job_id)
            replayed_event_ids = list(event_id_map.values())
            logger.info(f"[{job_id}] Faithful replay minted {len(replayed_event_ids)} epoch events")
        else:
            # epoch-simple: record ONE restore event up front so its id stamps every
            # imported node. The carried bulk.graph_epochs are NOT replayed.
            #
            # ADR-102 A13: a failed record_epoch is FATAL (not log-and-continue) —
            # without an event id, restored data could read FRESH against stale
            # derivations and every Instance would be untagged.
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
            # (ADR-200), not graph_epochs.event_id — so they restamp to the target's
            # CURRENT concept epoch. DELIBERATE collapse: every restored concept gets
            # the same created_at == last_seen == now (relative age lost until
            # re-annealing). P5-faithful preserves the original epochs instead.
            epoch_restamp = {
                "event_id": restore_event_id,
                "concept_epoch": client.get_current_epoch(),
            }

        # Stage 3: Execute restore with progress tracking
        restore_stats = _execute_restore(
            client=client,
            backup_data=prepared_backup,
            job_id=job_id,
            job_queue=job_queue,
            epoch_restamp=epoch_restamp,
            event_id_map=event_id_map,
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

        # ADR-207/#386 + ADR-102 P5: resolve the restore epoch(s) as COMPLETED. Until
        # now they held the committed watermark just below them, so every derivation
        # correctly read stale during the import. Completing advances the universal
        # freshness tick (get_committed_epoch) past every restored node's stamp;
        # otherwise the catalog index and the grounding / confidence / artifact
        # caches would keep serving pre-restore data as "fresh".
        if epoch_mode == EPOCH_FAITHFUL:
            DataImporter._resolve_replayed_epochs(client, replayed_event_ids, "completed")
            # Faithful carries concepts' ORIGINAL epochs — advance the concept counter
            # to the max carried so vitality math + future ingestion stay monotonic.
            max_concept_epoch = _max_carried_concept_epoch(prepared_backup)
            if max_concept_epoch is not None:
                DataImporter._set_ingestion_counter(client, max_concept_epoch)
            logger.info(
                f"[{job_id}] Faithful replay resolved {len(replayed_event_ids)} epochs; "
                f"ingestion counter >= {max_concept_epoch}"
            )
        else:
            client.complete_epoch(restore_event_id, "completed")
            logger.info(f"[{job_id}] Restore epoch {restore_event_id} completed")

        # The record_epoch/complete_epoch pair (and the faithful INSERT/resolve path)
        # do NOT co-advance the in-memory graph_accel sub-counter (the docstring
        # co-advance caveat / issue #465) — only record_mutation does. So invalidate
        # the accelerator and refresh the graph_change_counter snapshot explicitly.
        try:
            client.graph.invalidate()
        except Exception as e:
            # Usually "extension not loaded on this connection" — benign. But this
            # is the ONLY graph_accel co-advance (issue #465), so log it: a failure
            # for any OTHER reason silently desyncs the accelerator.
            logger.debug(f"[{job_id}] graph.invalidate() after restore skipped: {e}")
        try:
            client.refresh_epoch()
        except Exception as e:
            logger.warning(f"[{job_id}] refresh_epoch after restore failed: {e}")
        logger.info(f"[{job_id}] Freshness tick advanced ({epoch_mode} epoch reconciliation)")

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
            "epoch_mode": epoch_mode,
            "restore_epoch_event_id": restore_event_id,
            "faithful_epochs_replayed": len(replayed_event_ids) if replayed_event_ids else 0,
            "rehydration_job_id": rehydrate_job_id,
            "quiesce_timed_out": not quiesced,
            "checkpoint_created": True,
            "checkpoint_deleted": checkpoint_deleted,
            "temp_file_cleaned": False  # Will be cleaned in finally block
        }

    except Exception as e:
        logger.error(f"[{job_id}] Restore failed: {str(e)}")

        # ADR-102 P5: resolve the restore epoch as FAILED so it stops holding the
        # committed watermark below its event_id (a phantom in-flight event would
        # stall freshness for the whole graph). A FAILED event still counts toward
        # the committed watermark (migration 076), keeping the graph reading STALE.
        # The rollback below is now a TRUE replace (issue #483 fixed —
        # _restore_from_checkpoint clears before re-importing), so failed-restore
        # node orphans are removed. The failed epoch ROWS themselves remain in
        # graph_epochs referencing nothing (reads stale = safe; faithful leaves N).
        if client is not None:
            if restore_event_id is not None:  # epoch-simple
                client.complete_epoch(restore_event_id, "failed")
            if replayed_event_ids:            # P5-faithful
                try:
                    DataImporter._resolve_replayed_epochs(client, replayed_event_ids, "failed")
                except Exception as ee:
                    logger.error(f"[{job_id}] Failed to mark replayed epochs failed: {ee}")

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
    epoch_restamp: Optional[Dict[str, int]] = None,
    event_id_map: Optional[Dict[int, int]] = None
) -> Dict[str, int]:
    """
    Execute restore of an already-mode-prepared kg-backup/2 object, with progress.

    The object has already been transformed for its restore mode (idempotent =
    unchanged; adjacent/integration = ids rewritten). The writer always uses
    overwrite_existing=True: idempotent updates matching nodes in place, while
    adjacent/integration ids are fresh or attach to existing targets.

    ``epoch_restamp`` (epoch-simple) / ``event_id_map`` (faithful) control how
    instance/concept epoch stamps are reconciled — see ``DataImporter.import_backup``.

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
        epoch_restamp=epoch_restamp,
        event_id_map=event_id_map
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

    # Issue #483: TRUE-REPLACE rollback. A MERGE-only re-import leaves behind any
    # node the failed restore created that the checkpoint does not contain (orphans,
    # stamped with the failed restore epoch). Clear the concept graph first so the
    # rollback reconstructs EXACTLY the pre-restore state. The checkpoint was a
    # known-good full export captured at restore start; if the re-import below fails
    # after the clear, the checkpoint file is preserved on disk (see below) and the
    # caller flags "manual intervention required" — so a clear+failed-reimport is
    # recoverable, whereas silent orphans are not. _clear_database preserves
    # vocabulary + graph_epochs (the checkpoint's instance event-id stamps still
    # resolve against the retained epoch rows).
    logger.info(f"[{job_id}] Clearing concept graph before checkpoint re-import (true replace)")
    _clear_database(client, job_id)

    # Restore from checkpoint using DataImporter.import_backup() (MERGE-by-id into
    # the now-cleared graph; carries the checkpoint's own epoch stamps, no restamp).
    logger.info(f"[{job_id}] Restoring checkpoint data")
    DataImporter.import_backup(client, checkpoint_data, overwrite_existing=True)

    logger.info(f"[{job_id}] Checkpoint rollback complete")

    # Keep checkpoint file for inspection
    logger.info(f"[{job_id}] Checkpoint file preserved at {checkpoint_path} for inspection")
