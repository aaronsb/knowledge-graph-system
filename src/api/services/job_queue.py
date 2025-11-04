"""
Abstract job queue interface with multiple implementations.

Allows swapping between in-memory (Phase 1) and Redis (Phase 2) without
changing route handlers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Callable
from datetime import datetime, timezone
import uuid
import json
import threading
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import os
import logging

logger = logging.getLogger(__name__)


class JobQueue(ABC):
    """Abstract job queue interface - swap implementations easily"""

    @abstractmethod
    def enqueue(self, job_type: str, job_data: Dict) -> str:
        """
        Submit a job to the queue.

        Args:
            job_type: Type of job (e.g., "ingestion", "backup")
            job_data: Job-specific data

        Returns:
            job_id: Unique identifier for tracking
        """
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> Optional[Dict]:
        """
        Get job status and results.

        Returns:
            Job dict with status, progress, result, etc.
            None if job not found.
        """
        pass

    @abstractmethod
    def update_job(self, job_id: str, updates: Dict) -> bool:
        """Update job status/progress (called by worker)"""
        pass

    @abstractmethod
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued or processing job"""
        pass

    @abstractmethod
    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """List jobs, optionally filtered by status"""
        pass

    @abstractmethod
    def delete_job(self, job_id: str) -> bool:
        """Permanently delete a job from the queue"""
        pass

    @abstractmethod
    def check_duplicate(self, content_hash: str, ontology: str) -> Optional[Dict]:
        """
        Check if content already ingested into this ontology.

        Args:
            content_hash: SHA-256 hash of content
            ontology: Target ontology name

        Returns:
            None: Not seen before, safe to proceed
            Dict: Existing job info with status/result
        """
        pass

    @abstractmethod
    def delete_jobs_by_ontology(self, ontology: str) -> int:
        """
        Delete all jobs associated with an ontology.

        Used when ontology is deleted to clean up job history.

        Args:
            ontology: Ontology name

        Returns:
            Number of jobs deleted
        """
        pass


class PostgreSQLJobQueue(JobQueue):
    """
    PostgreSQL-backed job queue (ADR-024).

    Benefits over SQLite:
    - MVCC: No write-lock contention
    - Connection pooling: Handle concurrent operations
    - JSONB: Native JSON support (not serialized strings)
    - Atomic transactions across graph + jobs
    - Better query performance with proper indexes
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "knowledge_graph",
        user: str = "admin",
        password: str = "password",
        min_connections: int = 1,
        max_connections: int = 10
    ):
        """
        Initialize PostgreSQL job queue with connection pooling.

        Args:
            host: PostgreSQL host
            port: PostgreSQL port
            database: Database name
            user: Database user
            password: Database password
            min_connections: Minimum pool size
            max_connections: Maximum pool size
        """
        self.lock = threading.Lock()
        self.worker_registry: Dict[str, Callable] = {}
        self.serial_queue: list = []
        self.serial_running: bool = False

        # Create connection pool
        self.pool = psycopg2.pool.ThreadedConnectionPool(
            min_connections,
            max_connections,
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )

        # Create thread pool for worker execution (ADR-031: Non-blocking workers)
        import concurrent.futures
        import os

        # Configurable worker count for rate limit management
        # Lower values (2-3) reduce API rate limit pressure
        # Higher values (4-6) increase throughput but may hit rate limits
        max_workers = int(os.getenv("MAX_CONCURRENT_JOBS", "4"))
        logger.info(f"Job queue configured with max_workers={max_workers}")

        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="kg-worker-"
        )

    def _get_connection(self):
        """Get connection from pool"""
        return self.pool.getconn()

    def _return_connection(self, conn):
        """Return connection to pool"""
        self.pool.putconn(conn)

    def register_worker(self, job_type: str, worker_func: Callable):
        """Register a worker function for a job type"""
        self.worker_registry[job_type] = worker_func

    def execute_job_async(self, job_id: str):
        """
        Execute job in thread pool (non-blocking) - ADR-031.

        This submits the job to a thread pool executor, allowing the FastAPI
        event loop to continue processing other requests while the job runs.

        Benefits:
        - True concurrency: Multiple jobs can run in parallel
        - Non-blocking API: Other requests processed while job runs
        - Bounded resources: Thread pool limits concurrent jobs

        Args:
            job_id: Job ID to execute
        """
        self.executor.submit(self.execute_job, job_id)

    def enqueue(self, job_type: str, job_data: Dict) -> str:
        """Add job to PostgreSQL queue"""
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO kg_api.jobs (
                        job_id, job_type, status, ontology, user_id,
                        content_hash, job_data, progress, result, analysis,
                        processing_mode, created_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, NOW()
                    )
                """, (
                    job_id,
                    job_type,
                    "pending",  # ADR-014: Start as pending for analysis
                    job_data.get("ontology"),
                    job_data.get("user_id", "anonymous"),
                    job_data.get("content_hash"),
                    json.dumps(job_data),
                    None,  # progress
                    None,  # result
                    None,  # analysis
                    job_data.get("processing_mode", "serial")
                ))
            conn.commit()
            return job_id
        finally:
            self._return_connection(conn)

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job status from PostgreSQL"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        j.job_id, j.job_type, j.status, j.ontology, j.user_id,
                        j.content_hash, j.job_data, j.progress, j.result, j.analysis,
                        j.processing_mode, j.error,
                        j.created_at, j.started_at, j.completed_at,
                        j.approved_at, j.approved_by, j.expires_at,
                        u.username
                    FROM kg_api.jobs j
                    LEFT JOIN kg_auth.users u ON j.user_id = u.id
                    WHERE j.job_id = %s
                """, (job_id,))

                row = cur.fetchone()
                if not row:
                    return None

                # Convert to dict and handle timestamps
                job = dict(row)

                # Convert timestamp objects to ISO strings
                for field in ['created_at', 'started_at', 'completed_at', 'approved_at', 'expires_at']:
                    if job.get(field):
                        job[field] = job[field].isoformat()

                # Parse JSONB columns from strings to dicts (psycopg2 returns JSONB as strings)
                for json_field in ['progress', 'result', 'analysis', 'job_data']:
                    if job.get(json_field) and isinstance(job[json_field], str):
                        try:
                            job[json_field] = json.loads(job[json_field])
                        except json.JSONDecodeError:
                            # If parsing fails, leave as None
                            job[json_field] = None

                # ADR-051: Extract source provenance fields from job_data for display
                if job.get('job_data'):
                    job['filename'] = job['job_data'].get('filename')
                    job['source_type'] = job['job_data'].get('source_type')
                    job['source_path'] = job['job_data'].get('source_path')
                    job['source_hostname'] = job['job_data'].get('source_hostname')

                # Rename error to error for consistency
                job['error'] = job.pop('error', None)

                return job
        finally:
            self._return_connection(conn)

    def update_job(self, job_id: str, updates: Dict) -> bool:
        """Update job status/progress in PostgreSQL"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # Build dynamic UPDATE based on what fields are provided
                set_clauses = []
                params = []

                for key, value in updates.items():
                    if key == 'error':
                        # Map 'error' to 'error' column
                        set_clauses.append("error = %s")
                        params.append(value)
                    elif key in ['progress', 'result', 'analysis', 'job_data']:
                        # JSONB fields (added job_data for checkpoint support)
                        set_clauses.append(f"{key} = %s::jsonb")
                        params.append(json.dumps(value) if value else None)
                    elif key in ['status', 'processing_mode', 'approved_by']:
                        # String fields
                        set_clauses.append(f"{key} = %s")
                        params.append(value)

                # Auto-update timestamps based on status changes
                if updates.get("status") == "running":
                    set_clauses.append("started_at = NOW()")

                if updates.get("status") in ["completed", "failed", "cancelled"]:
                    set_clauses.append("completed_at = NOW()")

                if not set_clauses:
                    return True  # No updates needed

                params.append(job_id)
                query = f"""
                    UPDATE kg_api.jobs
                    SET {', '.join(set_clauses)}
                    WHERE job_id = %s
                """

                cur.execute(query, params)
                conn.commit()
                return cur.rowcount > 0
        finally:
            self._return_connection(conn)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job (if not already running)"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # Can only cancel if in cancellable state
                cur.execute("""
                    UPDATE kg_api.jobs
                    SET status = 'cancelled', completed_at = NOW()
                    WHERE job_id = %s
                      AND status IN ('pending', 'awaiting_approval', 'approved', 'queued')
                    RETURNING job_id
                """, (job_id,))

                conn.commit()
                return cur.rowcount > 0
        finally:
            self._return_connection(conn)

    def list_jobs(
        self,
        status: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """List jobs from PostgreSQL, optionally filtered"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                conditions = []
                params = []

                if status:
                    conditions.append("j.status = %s")
                    params.append(status)

                if user_id:
                    conditions.append("j.user_id = %s")
                    params.append(user_id)

                where_clause = " AND ".join(conditions) if conditions else "1=1"
                params.append(limit)
                params.append(offset)

                cur.execute(f"""
                    SELECT
                        j.job_id, j.job_type, j.status, j.ontology, j.user_id,
                        j.content_hash, j.job_data, j.progress, j.result, j.analysis,
                        j.processing_mode, j.error,
                        j.created_at, j.started_at, j.completed_at,
                        j.approved_at, j.approved_by, j.expires_at,
                        u.username
                    FROM kg_api.jobs j
                    LEFT JOIN kg_auth.users u ON j.user_id = u.id
                    WHERE {where_clause}
                    ORDER BY j.created_at DESC
                    LIMIT %s OFFSET %s
                """, params)

                jobs = []
                for row in cur.fetchall():
                    job = dict(row)

                    # Convert timestamps to ISO strings
                    for field in ['created_at', 'started_at', 'completed_at', 'approved_at', 'expires_at']:
                        if job.get(field):
                            job[field] = job[field].isoformat()

                    # Parse JSONB columns from strings to dicts (psycopg2 returns JSONB as strings)
                    import json
                    for json_field in ['progress', 'result', 'analysis', 'job_data']:
                        if job.get(json_field) and isinstance(job[json_field], str):
                            try:
                                job[json_field] = json.loads(job[json_field])
                            except json.JSONDecodeError:
                                # If parsing fails, leave as None
                                job[json_field] = None

                    # ADR-051: Extract source provenance fields from job_data for display
                    if job.get('job_data'):
                        job['filename'] = job['job_data'].get('filename')
                        job['source_type'] = job['job_data'].get('source_type')
                        job['source_path'] = job['job_data'].get('source_path')
                        job['source_hostname'] = job['job_data'].get('source_hostname')

                    # Rename error to error
                    job['error'] = job.pop('error', None)

                    jobs.append(job)

                return jobs
        finally:
            self._return_connection(conn)

    def delete_job(self, job_id: str) -> bool:
        """Permanently delete a job from PostgreSQL"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM kg_api.jobs
                    WHERE job_id = %s
                """, (job_id,))
                conn.commit()
                return cur.rowcount > 0
        finally:
            self._return_connection(conn)

    def check_duplicate(self, content_hash: str, ontology: str) -> Optional[Dict]:
        """
        Check if content already ingested into this ontology.

        Args:
            content_hash: SHA-256 hash of content
            ontology: Target ontology name

        Returns:
            None: Not seen before, safe to proceed
            Dict: Existing job info with status/result
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        j.job_id, j.job_type, j.status, j.ontology, j.user_id,
                        j.content_hash, j.job_data, j.progress, j.result, j.analysis,
                        j.processing_mode, j.error,
                        j.created_at, j.started_at, j.completed_at,
                        j.approved_at, j.approved_by, j.expires_at,
                        u.username
                    FROM kg_api.jobs j
                    LEFT JOIN kg_auth.users u ON j.user_id = u.id
                    WHERE j.content_hash = %s
                      AND j.ontology = %s
                      AND j.status IN ('completed', 'running', 'queued')
                    ORDER BY j.created_at DESC
                    LIMIT 1
                """, (content_hash, ontology))

                row = cur.fetchone()
                if not row:
                    return None

                # Convert to dict and handle timestamps
                job = dict(row)

                # Convert timestamp objects to ISO strings
                for field in ['created_at', 'started_at', 'completed_at', 'approved_at', 'expires_at']:
                    if job.get(field):
                        job[field] = job[field].isoformat()

                # Parse JSONB columns from strings to dicts (psycopg2 returns JSONB as strings)
                for json_field in ['progress', 'result', 'analysis', 'job_data']:
                    if job.get(json_field) and isinstance(job[json_field], str):
                        try:
                            job[json_field] = json.loads(job[json_field])
                        except json.JSONDecodeError:
                            # If parsing fails, leave as None
                            job[json_field] = None

                # ADR-051: Extract source provenance fields from job_data for display
                if job.get('job_data'):
                    job['filename'] = job['job_data'].get('filename')
                    job['source_type'] = job['job_data'].get('source_type')
                    job['source_path'] = job['job_data'].get('source_path')
                    job['source_hostname'] = job['job_data'].get('source_hostname')

                # Rename error to error for consistency
                job['error'] = job.pop('error', None)

                return job
        finally:
            self._return_connection(conn)

    def delete_jobs_by_ontology(self, ontology: str) -> int:
        """Delete all jobs for a specific ontology from PostgreSQL"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                # Count jobs before deleting
                cur.execute("""
                    SELECT COUNT(*) FROM kg_api.jobs
                    WHERE ontology = %s
                """, (ontology,))
                count = cur.fetchone()[0]

                # Delete jobs for this ontology
                cur.execute("""
                    DELETE FROM kg_api.jobs
                    WHERE ontology = %s
                """, (ontology,))
                conn.commit()

                return count
        finally:
            self._return_connection(conn)

    def clear_all_jobs(self) -> int:
        """Clear ALL jobs from PostgreSQL (use with caution!)"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM kg_api.jobs")
                count = cur.fetchone()[0]

                cur.execute("DELETE FROM kg_api.jobs")
                conn.commit()

                # Clear in-memory queue state
                with self.lock:
                    self.serial_queue.clear()
                    self.serial_running = False

                return count
        finally:
            self._return_connection(conn)

    def execute_job(self, job_id: str):
        """
        Execute a job (called by BackgroundTasks).
        Bridge between FastAPI and worker functions.
        """
        job = self.get_job(job_id)
        if not job:
            return

        # Get worker function
        worker_func = self.worker_registry.get(job["job_type"])
        if not worker_func:
            self.update_job(job_id, {
                "status": "failed",
                "error": f"No worker registered for job type: {job['job_type']}"
            })
            return

        # Update to running
        self.update_job(job_id, {"status": "running"})

        try:
            # Execute worker (pass queue ref for progress updates)
            result = worker_func(job["job_data"], job_id, self)

            # Mark completed
            self.update_job(job_id, {
                "status": "completed",
                "result": result
            })

        except Exception as e:
            # Mark failed
            self.update_job(job_id, {
                "status": "failed",
                "error": str(e)
            })
        finally:
            # If this was a serial job, process next in queue
            if job.get("processing_mode") == "serial":
                with self.lock:
                    self.serial_running = False
                    self._process_next_serial_job()

    def queue_serial_job(self, job_id: str):
        """
        Queue a serial job for execution.
        If no serial job is running, start immediately.
        """
        with self.lock:
            if not self.serial_running:
                # No serial job running, start this one
                self.serial_running = True
                self.execute_job(job_id)
            else:
                # Serial job already running, add to queue
                self.serial_queue.append(job_id)
                self.update_job(job_id, {"status": "queued"})

    def _process_next_serial_job(self):
        """Process the next serial job in queue (called with lock held)"""
        if self.serial_queue:
            next_job_id = self.serial_queue.pop(0)
            self.serial_running = True
            # Execute in background
            threading.Thread(target=self.execute_job, args=(next_job_id,)).start()


# Singleton instance (will be initialized in main.py)
_job_queue_instance: Optional[JobQueue] = None


def init_job_queue(queue_type: str = "postgresql", **kwargs) -> JobQueue:
    """
    Factory function to initialize job queue.

    Args:
        queue_type: "postgresql" (default, ADR-024+050) or "redis" (future)
        **kwargs: Implementation-specific config
    """
    global _job_queue_instance

    if queue_type == "postgresql":
        # ADR-024+050: PostgreSQL job queue with unified kg_api.jobs table
        _job_queue_instance = PostgreSQLJobQueue(
            host=kwargs.get("host", os.getenv("POSTGRES_HOST", "localhost")),
            port=kwargs.get("port", int(os.getenv("POSTGRES_PORT", "5432"))),
            database=kwargs.get("database", os.getenv("POSTGRES_DB", "knowledge_graph")),
            user=kwargs.get("user", os.getenv("POSTGRES_USER", "admin")),
            password=kwargs.get("password", os.getenv("POSTGRES_PASSWORD", "password")),
            min_connections=kwargs.get("min_connections", 1),
            max_connections=kwargs.get("max_connections", 10)
        )
    elif queue_type == "redis":
        # Future: Will add RedisJobQueue here
        raise NotImplementedError("Redis queue not implemented yet")
    else:
        raise ValueError(f"Unknown queue type: {queue_type}. Only 'postgresql' is supported.")

    return _job_queue_instance


def get_job_queue() -> JobQueue:
    """Get the current job queue instance"""
    if _job_queue_instance is None:
        raise RuntimeError("Job queue not initialized. Call init_job_queue() first.")
    return _job_queue_instance
