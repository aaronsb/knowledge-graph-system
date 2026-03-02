"""
Database-driven worker lane manager (ADR-100).

Replaces in-memory thread dispatch (execute_job_async, queue_serial_job)
with poll-and-claim loops. Each lane polls PostgreSQL for claimable work
using atomic UPDATE...RETURNING with FOR UPDATE SKIP LOCKED.

Lane configuration is read from kg_api.worker_lanes on every poll cycle,
so changes (slot counts, intervals, enabled/disabled) take effect within
one interval — no container restart needed.
"""

import asyncio
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

# Unique worker ID for this process (survives lane restarts, changes on container restart)
WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"


@dataclass
class LaneConfig:
    """Snapshot of a lane's configuration from the database."""
    name: str
    job_types: list[str]
    max_slots: int
    poll_interval_ms: int
    stale_timeout_minutes: int
    enabled: bool


class LaneManager:
    """Manages worker lanes that poll for and execute jobs.  @verified (new)"""

    def __init__(self, job_queue):
        """Initialize with a reference to the job queue (for execute_job and DB pool)."""
        self._queue = job_queue
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._tasks: dict[str, asyncio.Task] = {}
        # All mutations to _active_jobs happen on the event loop thread.
        # Worker threads use call_soon_threadsafe to schedule slot release.
        self._active_jobs: dict[str, set[str]] = {}  # lane_name → {job_id, ...}
        # Shared executor for running sync workers in threads
        max_workers = int(os.getenv("MAX_CONCURRENT_JOBS", "4"))
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="kg-lane-"
        )

    async def start(self) -> None:
        """Start poll loops for all enabled lanes.  @verified (new)"""
        self._running = True
        self._loop = asyncio.get_running_loop()
        lane_names = await self._get_lane_names()
        for name in lane_names:
            self._active_jobs[name] = set()
            task = asyncio.create_task(self._lane_loop(name))
            self._tasks[name] = task
            logger.info(f"Started lane loop: {name}")
        logger.info(f"LaneManager started with {len(lane_names)} lanes (worker_id={WORKER_ID})")

    async def stop(self) -> None:
        """Gracefully stop all lane loops. Running jobs finish naturally.  @verified (new)"""
        self._running = False
        for name, task in self._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            logger.info(f"Stopped lane loop: {name}")
        self._tasks.clear()
        self._executor.shutdown(wait=False, cancel_futures=True)
        logger.info("LaneManager stopped")

    def get_lane_status(self) -> dict:
        """Return current slot utilization per lane.  @verified (new)"""
        status = {}
        for name, active in self._active_jobs.items():
            status[name] = {
                "active_jobs": list(active),
                "active_count": len(active),
            }
        return status

    # -------------------------------------------------------------------------
    # Internal: lane loop
    # -------------------------------------------------------------------------

    async def _lane_loop(self, lane_name: str) -> None:
        """Poll loop for a single lane. Runs until stop() is called."""
        logger.debug(f"Lane {lane_name}: poll loop started")
        while self._running:
            try:
                config = await self._load_lane_config(lane_name)
                if config is None:
                    # Lane was deleted from DB — stop this loop
                    logger.warning(f"Lane {lane_name}: config not found, stopping loop")
                    break

                if not config.enabled:
                    await asyncio.sleep(config.poll_interval_ms / 1000)
                    continue

                # Check if we have free slots
                active_count = len(self._active_jobs.get(lane_name, set()))
                if active_count >= config.max_slots:
                    await asyncio.sleep(config.poll_interval_ms / 1000)
                    continue

                # Try to claim a job
                job = await self._claim_next_job(config.job_types)
                if job:
                    job_id = job["job_id"]
                    job_type = job["job_type"]
                    logger.info(f"Lane {lane_name}: claimed {job_type} job {job_id}")
                    self._active_jobs[lane_name].add(job_id)

                    # Run the worker in the thread pool (track future for shutdown drain)
                    loop = asyncio.get_running_loop()
                    future = loop.run_in_executor(
                        self._executor,
                        self._run_and_release,
                        lane_name,
                        job_id,
                    )
                    future.add_done_callback(self._on_job_done)
                else:
                    # No work available — sleep for the poll interval
                    await asyncio.sleep(config.poll_interval_ms / 1000)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception(f"Lane {lane_name}: error in poll loop")
                await asyncio.sleep(5)  # back off on errors

    @staticmethod
    def _on_job_done(future) -> None:
        """Callback for executor futures — log any unhandled exceptions."""
        exc = future.exception()
        if exc is not None:
            logger.error(f"Unhandled exception in job executor: {exc}", exc_info=exc)

    def _run_and_release(self, lane_name: str, job_id: str) -> None:
        """Execute a job and release the lane slot when done. Runs in a thread."""
        try:
            self._queue.execute_job(job_id)
        except Exception:
            logger.exception(f"Lane {lane_name}: unhandled error executing {job_id}")
        finally:
            # Release the slot on the event loop thread (all _active_jobs mutations
            # happen on the event loop to avoid cross-thread set mutation).
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(
                    self._active_jobs.get(lane_name, set()).discard, job_id
                )
            else:
                # Fallback during shutdown when loop may be closing
                self._active_jobs.get(lane_name, set()).discard(job_id)

    # -------------------------------------------------------------------------
    # Internal: database operations (run in executor to avoid blocking)
    # -------------------------------------------------------------------------

    async def _get_lane_names(self) -> list[str]:
        """Fetch all lane names from the database."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_lane_names_sync)

    def _get_lane_names_sync(self) -> list[str]:
        conn = self._queue._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT name FROM kg_api.worker_lanes ORDER BY name")
                return [row[0] for row in cur.fetchall()]
        finally:
            self._queue._return_connection(conn)

    async def _load_lane_config(self, lane_name: str) -> Optional[LaneConfig]:
        """Load lane config from database. Returns None if lane doesn't exist."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._load_lane_config_sync, lane_name)

    def _load_lane_config_sync(self, lane_name: str) -> Optional[LaneConfig]:
        conn = self._queue._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM kg_api.worker_lanes WHERE name = %s",
                    (lane_name,)
                )
                row = cur.fetchone()
                if not row:
                    return None
                return LaneConfig(
                    name=row["name"],
                    job_types=row["job_types"],
                    max_slots=row["max_slots"],
                    poll_interval_ms=row["poll_interval_ms"],
                    stale_timeout_minutes=row["stale_timeout_minutes"],
                    enabled=row["enabled"],
                )
        finally:
            self._queue._return_connection(conn)

    async def _claim_next_job(self, job_types: list[str]) -> Optional[dict]:
        """Atomically claim the highest-priority approved job matching the given types."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._claim_next_job_sync, job_types)

    def _claim_next_job_sync(self, job_types: list[str]) -> Optional[dict]:
        conn = self._queue._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    UPDATE kg_api.jobs
                    SET status = 'running',
                        claimed_by = %s,
                        claimed_at = NOW(),
                        started_at = NOW()
                    WHERE job_id = (
                        SELECT job_id FROM kg_api.jobs
                        WHERE status = 'approved'
                          AND job_type = ANY(%s)
                        ORDER BY priority DESC, created_at ASC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    )
                    RETURNING *
                """, (WORKER_ID, job_types))
                row = cur.fetchone()
                conn.commit()
                return dict(row) if row else None
        except Exception:
            conn.rollback()
            raise
        finally:
            self._queue._return_connection(conn)
