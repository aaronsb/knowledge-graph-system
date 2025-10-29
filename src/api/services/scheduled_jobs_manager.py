"""
Job Scheduler for automated maintenance tasks (ADR-050).

Simple scheduler that triggers launchers based on cron schedules stored in
PostgreSQL. Uses advisory locks for multi-worker safety and distinguishes
between normal skips and actual failures.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from croniter import croniter
from typing import Dict, Type, Optional
import psycopg2

logger = logging.getLogger(__name__)


class JobScheduler:
    """
    Simple scheduler that triggers launchers based on cron schedules.

    Features:
    - PostgreSQL-backed schedule configuration
    - Multi-worker safety via advisory locks
    - Exponential backoff on failures
    - Distinguishes skip (normal) from failure (retry)
    - 60-second check interval
    """

    def __init__(self, job_queue, launcher_registry: Dict[str, Type]):
        """
        Initialize scheduler.

        Args:
            job_queue: JobQueue instance for enqueuing jobs
            launcher_registry: Dict mapping launcher class names to classes
        """
        self.job_queue = job_queue
        self.launcher_registry = launcher_registry
        self.running = False
        self.task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the scheduler loop"""
        if self.running:
            logger.warning("⚠️  Scheduler already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._schedule_loop())
        logger.info("✅ Job scheduler started")

    async def stop(self):
        """Stop the scheduler loop"""
        if not self.running:
            return

        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Job scheduler stopped")

    async def _schedule_loop(self):
        """
        Main scheduler loop.

        Checks schedules every 60 seconds, triggers launchers when due.
        Uses advisory lock to ensure only one worker runs in multi-worker deployments.
        """
        while self.running:
            try:
                await self._check_schedules()
            except Exception as e:
                logger.error(f"❌ Scheduler error: {e}", exc_info=True)

            # Sleep 60 seconds before next check
            await asyncio.sleep(60)

    async def _check_schedules(self):
        """
        Check all enabled schedules and trigger if due.

        Uses PostgreSQL advisory lock to ensure only one worker checks
        schedules in multi-worker deployments (e.g., Gunicorn -w 4).
        """
        logger.info("🔍 Scheduler check cycle starting")

        # Get database connection from job queue
        conn = self.job_queue._get_connection()

        try:
            with conn.cursor() as cur:
                # --- MULTI-WORKER SAFETY ---
                # Try to acquire a unique, non-blocking advisory lock.
                # Only one worker across all processes can hold this lock.
                # Key: 1050 (arbitrary unique integer for scheduler)
                cur.execute("SELECT pg_try_advisory_lock(1050)")
                got_lock = cur.fetchone()[0]

                if not got_lock:
                    # Another worker has the lock and is checking schedules.
                    # This worker should do nothing to avoid duplicate job creation.
                    logger.info(
                        "   Scheduler lock held by another worker, skipping this cycle"
                    )
                    return

                # If we're here, we are the ONLY worker running schedule checks
                logger.info("   Acquired scheduler lock, checking schedules")
                # --- END MULTI-WORKER SAFETY ---

                cur.execute("""
                    SELECT id, name, launcher_class, schedule_cron,
                           retry_count, max_retries, last_run, next_run
                    FROM kg_api.scheduled_jobs
                    WHERE enabled = TRUE
                    ORDER BY next_run ASC NULLS FIRST
                """)

                schedules = cur.fetchall()
                now = datetime.now()

                logger.info(f"   Found {len(schedules)} enabled schedule(s), current time: {now}")

                for schedule in schedules:
                    schedule_id, name, launcher_class, cron_expr, \
                    retry_count, max_retries, last_run, next_run = schedule

                    logger.info(f"   Schedule '{name}': next_run={next_run}, launcher={launcher_class}")

                    # Calculate next run if not set
                    if not next_run:
                        cron = croniter(cron_expr, now)
                        next_run = cron.get_next(datetime)

                        logger.info(f"   Initializing next_run for '{name}' to {next_run}")
                        cur.execute("""
                            UPDATE kg_api.scheduled_jobs
                            SET next_run = %s
                            WHERE id = %s
                        """, (next_run, schedule_id))
                        conn.commit()
                        continue

                    # Check if due
                    if next_run <= now:
                        logger.info(f"⏰ Schedule '{name}' is due, triggering launcher")

                        # Get launcher class
                        launcher_cls = self.launcher_registry.get(launcher_class)
                        if not launcher_cls:
                            logger.error(f"❌ Unknown launcher: {launcher_class}")
                            continue

                        # Create launcher instance
                        launcher = launcher_cls(self.job_queue, max_retries)

                        # Trigger launcher (three possible outcomes)
                        job_id = None
                        launch_failed = False

                        try:
                            # launch() returns job_id, None (for skip),
                            # or raises Exception (for failure)
                            job_id = launcher.launch()
                        except Exception as e:
                            logger.error(
                                f"❌ Schedule '{name}' launcher failed: {e}",
                                exc_info=True
                            )
                            launch_failed = True

                        # Calculate next run time for schedule advancement
                        cron = croniter(cron_expr, now)
                        next_next_run = cron.get_next(datetime)

                        if job_id:
                            # Outcome 1: Success - Job enqueued
                            # Reset retry_count, update last_success
                            cur.execute("""
                                UPDATE kg_api.scheduled_jobs
                                SET last_run = %s,
                                    last_success = %s,
                                    next_run = %s,
                                    retry_count = 0
                                WHERE id = %s
                            """, (now, now, next_next_run, schedule_id))
                            logger.info(f"✅ Schedule '{name}' triggered job {job_id}")

                        elif not launch_failed:
                            # Outcome 2: Normal skip - Conditions not met
                            # This is healthy, reset retry_count, advance schedule
                            # Don't update last_success (no job ran)
                            cur.execute("""
                                UPDATE kg_api.scheduled_jobs
                                SET last_run = %s,
                                    next_run = %s,
                                    retry_count = 0
                                WHERE id = %s
                            """, (now, next_next_run, schedule_id))
                            logger.info(f"⏭️  Schedule '{name}' skipped (conditions not met)")

                        else:
                            # Outcome 3: Launcher failure - Exception raised
                            # Increment retry_count, apply exponential backoff
                            new_retry_count = retry_count + 1

                            if new_retry_count >= max_retries:
                                # Max retries exceeded, disable schedule
                                logger.error(
                                    f"❌ Schedule '{name}' max retries exceeded, disabling"
                                )
                                cur.execute("""
                                    UPDATE kg_api.scheduled_jobs
                                    SET last_run = %s,
                                        last_failure = %s,
                                        retry_count = %s,
                                        enabled = FALSE
                                    WHERE id = %s
                                """, (now, now, new_retry_count, schedule_id))
                            else:
                                # Exponential backoff: retry sooner
                                backoff_minutes = min(2 ** new_retry_count, 60)
                                retry_time = now + timedelta(minutes=backoff_minutes)

                                logger.warning(
                                    f"⚠️  Schedule '{name}' failed (retry {new_retry_count}/{max_retries}), "
                                    f"retrying in {backoff_minutes}min"
                                )
                                cur.execute("""
                                    UPDATE kg_api.scheduled_jobs
                                    SET last_run = %s,
                                        last_failure = %s,
                                        next_run = %s,
                                        retry_count = %s
                                    WHERE id = %s
                                """, (now, now, retry_time, new_retry_count, schedule_id))

                        conn.commit()

        finally:
            # --- MULTI-WORKER SAFETY ---
            # Always release the advisory lock, even if we failed.
            # This allows another worker to take over on the next 60s poll.
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(1050)")
            except Exception as e:
                logger.error(f"⚠️  Failed to release scheduler lock: {e}")
            # --- END MULTI-WORKER SAFETY ---
            self.job_queue._return_connection(conn)
