"""
IngestionMixin — Write-back queue, ingestion submission, and job polling.

Handles the background flush task, API submission, active job polling,
and cache invalidation after ingestion completes. Also defines module-level
constants shared by other mixins (WRITE_BACK_DELAY, MAX_INGESTION_SIZE,
IMAGE_EXTENSIONS).
"""

import logging
import os
import time

import pyfuse3

log = logging.getLogger(__name__)

# Maximum file size for ingestion (50MB)
MAX_INGESTION_SIZE = 50 * 1024 * 1024

# Write-back delay (seconds) before flushing to ingestion API.
# Zero = flush on next background tick (~1s). Non-zero gives editors time
# to finish their create→write→release→rename dance before we commit.
WRITE_BACK_DELAY = 0

# How often to poll active jobs for completion (seconds).
# Balances responsiveness (flag files disappear promptly) against API load.
JOB_POLL_INTERVAL = 5

# Supported image extensions (matches API's _is_image_file and CLI's isImageFile)
IMAGE_EXTENSIONS = frozenset({'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'})


def _is_image_file(filename: str) -> bool:
    """Check if filename has a supported image extension."""
    ext = os.path.splitext(filename)[1].lower()
    return ext in IMAGE_EXTENSIONS


class IngestionMixin:
    """Write-back queue and ingestion submission."""

    async def _flush_pending_ingestions(self):
        """Background task: flush pending ingestions.

        Runs every second and ingests anything in the queue. With
        WRITE_BACK_DELAY=0 this is effectively immediate (~1s max).
        """
        import trio
        while True:
            await trio.sleep(1)
            now = time.monotonic()
            ready = [
                (key, entry) for key, entry in self._pending_ingestions.items()
                if now - entry["timestamp"] >= WRITE_BACK_DELAY
            ]
            for key, entry in ready:
                del self._pending_ingestions[key]
                await self._ingest_and_notify(entry)

    async def _poll_active_jobs(self):
        """Background task: poll tracked jobs for completion.

        Without this, .ingesting flag files only clear when explicitly read.
        This loop polls the API every JOB_POLL_INTERVAL seconds for any
        tracked jobs and marks terminal ones for removal, so the next
        directory listing drops the flag file.
        """
        import trio
        from ..job_tracker import TERMINAL_JOB_STATUSES

        while True:
            await trio.sleep(JOB_POLL_INTERVAL)
            # Snapshot job list to avoid mutation during iteration
            jobs = list(self._job_tracker._jobs.values())
            if not jobs:
                continue

            for job in jobs:
                if job.marked_for_removal:
                    continue
                try:
                    data = await self._api.get(f"/jobs/{job.job_id}")
                    status = data.get("status", "unknown")
                    if status in TERMINAL_JOB_STATUSES:
                        self._job_tracker.mark_job_status(job.job_id, status)
                        log.info(f"Job {job.job_id} completed ({status}), clearing flag")
                        # Invalidate ingest dir so next readdir drops the file
                        for find_fn in (self._find_ingest_dir_inode, self._find_documents_dir_inode):
                            dir_inode = find_fn(job.ontology)
                            if dir_inode:
                                self._invalidate_cache(dir_inode)
                                try:
                                    pyfuse3.invalidate_inode(dir_inode, attr_only=False)
                                except Exception:
                                    pass
                except Exception as e:
                    # Job may have been deleted or API unreachable
                    log.debug(f"Poll failed for job {job.job_id}: {e}")
                    self._job_tracker.mark_job_not_found(job.job_id)

    async def _ingest_and_notify(self, entry: dict):
        """Submit a write-back entry to the ingestion API and invalidate caches."""
        ontology = entry["ontology"]
        filename = entry["filename"]
        content = entry["content"]

        # Clean up the temporary inode now that we're committing
        stale_inode = entry.get("inode")
        if stale_inode and stale_inode in self._inodes:
            parent_inode = self._inodes[stale_inode].parent
            del self._inodes[stale_inode]
            self._free_inode(stale_inode)
            if parent_inode:
                self._invalidate_cache(parent_inode)

        log.info(f"Write-back flush: ingesting {filename} ({len(content)} bytes) into {ontology}")
        try:
            if _is_image_file(filename):
                await self._image_handler.ingest_image(ontology, filename, content)
            else:
                await self._ingest_document(ontology, filename, content)
            log.info(f"Ingestion submitted successfully: {filename}")

            if ontology in self._pending_ontologies:
                self._pending_ontologies.discard(ontology)
                log.info(f"Ontology {ontology} is no longer pending")

            # Invalidate ingest dir (job status files change) and documents dir
            # (new content will appear there after processing completes)
            for find_fn in (self._find_ingest_dir_inode, self._find_documents_dir_inode):
                dir_inode = find_fn(ontology)
                if dir_inode:
                    self._invalidate_cache(dir_inode)
                    try:
                        pyfuse3.invalidate_inode(dir_inode, attr_only=False)
                    except Exception:
                        pass  # Kernel notify is best-effort

        except Exception as e:
            log.error(f"Write-back ingestion failed for {filename}: {e}")

    async def _ingest_document(self, ontology: str, filename: str, content: bytes) -> dict:
        """Submit document to ingestion API and track the job."""
        # Use multipart form upload
        files = {"file": (filename, content)}
        data = {
            "ontology": ontology,
            "auto_approve": "true",  # Auto-approve for FUSE ingestions
        }

        result = await self._api.post("/ingest", data=data, files=files)
        log.info(f"Ingestion response: {result}")

        # Track the job so it shows as a .ingesting file until complete
        job_id = result.get("job_id")
        if job_id:
            self._job_tracker.track_job(job_id, ontology, filename)

        return result
