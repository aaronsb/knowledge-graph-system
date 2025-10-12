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
import sqlite3
import threading
from pathlib import Path
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
import os


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
        limit: int = 50
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


class InMemoryJobQueue(JobQueue):
    """
    Phase 1: FastAPI BackgroundTasks + SQLite persistence.

    - Jobs stored in memory for fast access
    - SQLite for persistence across restarts
    - Thread-safe operations
    - Simple, no external dependencies
    """

    def __init__(self, db_path: str = "data/jobs.db"):
        self.jobs: Dict[str, Dict] = {}
        self.db_path = db_path
        self.lock = threading.Lock()
        self.worker_registry: Dict[str, Callable] = {}
        self.serial_queue: list = []  # Queue for serial jobs
        self.serial_running: bool = False  # Track if a serial job is running

        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize SQLite
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._init_db()

        # Load active jobs from DB on startup
        self._load_active_jobs()

    def _init_db(self):
        """Create jobs table if it doesn't exist"""
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                content_hash TEXT,
                ontology TEXT,
                client_id TEXT,
                status TEXT NOT NULL,
                progress TEXT,
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                job_data TEXT NOT NULL
            )
        """)

        # Index for deduplication queries
        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_content_hash
            ON jobs(content_hash, ontology, status)
        """)

        self.db.execute("""
            CREATE INDEX IF NOT EXISTS idx_status
            ON jobs(status)
        """)

        # Migration: Add ADR-014 approval workflow fields
        # Check if columns exist before adding (SQLite doesn't have IF NOT EXISTS for ALTER)
        cursor = self.db.execute("PRAGMA table_info(jobs)")
        existing_columns = {row[1] for row in cursor.fetchall()}

        if "analysis" not in existing_columns:
            self.db.execute("ALTER TABLE jobs ADD COLUMN analysis TEXT")
        if "approved_at" not in existing_columns:
            self.db.execute("ALTER TABLE jobs ADD COLUMN approved_at TEXT")
        if "approved_by" not in existing_columns:
            self.db.execute("ALTER TABLE jobs ADD COLUMN approved_by TEXT")
        if "expires_at" not in existing_columns:
            self.db.execute("ALTER TABLE jobs ADD COLUMN expires_at TEXT")
        if "processing_mode" not in existing_columns:
            self.db.execute("ALTER TABLE jobs ADD COLUMN processing_mode TEXT DEFAULT 'serial'")

        self.db.commit()

    def _load_active_jobs(self):
        """Load active jobs into memory on startup"""
        # ADR-014: Include new workflow states
        cursor = self.db.execute(
            "SELECT * FROM jobs WHERE status IN ('pending', 'awaiting_approval', 'approved', 'queued', 'processing')"
        )

        for row in cursor.fetchall():
            job = self._row_to_dict(row)
            self.jobs[job["job_id"]] = job

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """Convert SQLite row to job dict"""
        # Helper to safely get optional fields from sqlite3.Row
        def safe_get(row, key, default=None):
            try:
                return row[key]
            except (KeyError, IndexError):
                return default

        return {
            "job_id": row["job_id"],
            "job_type": row["job_type"],
            "content_hash": row["content_hash"],
            "ontology": row["ontology"],
            "client_id": safe_get(row, "client_id", "anonymous"),  # Phase 2 field
            "status": row["status"],
            "progress": json.loads(row["progress"]) if row["progress"] else None,
            "result": json.loads(row["result"]) if row["result"] else None,
            "error": row["error"],
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "completed_at": row["completed_at"],
            "job_data": json.loads(row["job_data"]),
            "processing_mode": safe_get(row, "processing_mode", "serial"),
            # ADR-014: Approval workflow fields
            "analysis": json.loads(safe_get(row, "analysis")) if safe_get(row, "analysis") else None,
            "approved_at": safe_get(row, "approved_at"),
            "approved_by": safe_get(row, "approved_by"),
            "expires_at": safe_get(row, "expires_at")
        }

    def _save_to_db(self, job: Dict):
        """Persist job to SQLite"""
        self.db.execute("""
            INSERT OR REPLACE INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job["job_id"],
            job["job_type"],
            job.get("content_hash"),
            job.get("ontology"),
            job.get("client_id", "anonymous"),  # Phase 2 field
            job["status"],
            json.dumps(job["progress"]) if job["progress"] else None,
            json.dumps(job["result"]) if job["result"] else None,
            job.get("error"),
            job["created_at"],
            job.get("started_at"),
            job.get("completed_at"),
            json.dumps(job.get("job_data", {})),
            # ADR-014: Approval workflow fields
            json.dumps(job.get("analysis")) if job.get("analysis") else None,
            job.get("approved_at"),
            job.get("approved_by"),
            job.get("expires_at"),
            job.get("processing_mode", "serial")
        ))
        self.db.commit()

    def register_worker(self, job_type: str, worker_func: Callable):
        """Register a worker function for a job type"""
        self.worker_registry[job_type] = worker_func

    def enqueue(self, job_type: str, job_data: Dict) -> str:
        """Add job to queue"""
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        with self.lock:
            job = {
                "job_id": job_id,
                "job_type": job_type,
                "content_hash": job_data.get("content_hash"),
                "ontology": job_data.get("ontology"),
                "client_id": job_data.get("client_id", "anonymous"),  # Phase 2 field
                "status": "pending",  # ADR-014: Start as "pending" for analysis
                "progress": None,
                "result": None,
                "error": None,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "started_at": None,
                "completed_at": None,
                "job_data": job_data,
                "processing_mode": job_data.get("processing_mode", "serial"),
                # ADR-014: Approval workflow fields
                "analysis": None,  # Will be populated by JobAnalyzer
                "approved_at": None,
                "approved_by": None,
                "expires_at": None  # Will be set when status -> awaiting_approval
            }

            # Store in memory and DB
            self.jobs[job_id] = job
            self._save_to_db(job)

        return job_id

    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get job status"""
        with self.lock:
            # Check in-memory first
            if job_id in self.jobs:
                return self.jobs[job_id].copy()

            # Check DB for completed jobs
            cursor = self.db.execute(
                "SELECT * FROM jobs WHERE job_id = ?",
                (job_id,)
            )
            row = cursor.fetchone()
            return self._row_to_dict(row) if row else None

    def update_job(self, job_id: str, updates: Dict) -> bool:
        """Update job status/progress"""
        with self.lock:
            if job_id not in self.jobs:
                return False

            # Update in-memory
            self.jobs[job_id].update(updates)

            # Update timestamps
            if updates.get("status") == "processing" and not self.jobs[job_id].get("started_at"):
                self.jobs[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()

            if updates.get("status") in ["completed", "failed"]:
                self.jobs[job_id]["completed_at"] = datetime.now(timezone.utc).isoformat()

            # Persist to DB
            self._save_to_db(self.jobs[job_id])

            return True

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job (if not already processing)"""
        with self.lock:
            job = self.jobs.get(job_id)
            if not job:
                return False

            # ADR-014: Can cancel pending/awaiting_approval/approved/queued, but not processing
            cancellable_states = ["pending", "awaiting_approval", "approved", "queued"]
            if job["status"] not in cancellable_states:
                return False  # Can't cancel running jobs in Phase 1

            job["status"] = "cancelled"
            job["completed_at"] = datetime.now(timezone.utc).isoformat()
            self._save_to_db(job)

            return True

    def list_jobs(
        self,
        status: Optional[str] = None,
        client_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """List jobs from DB, optionally filtered by status and/or client_id"""
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)

        if client_id:
            conditions.append("client_id = ?")
            params.append(client_id)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        query = f"SELECT * FROM jobs WHERE {where_clause} ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self.db.execute(query, tuple(params))
        return [self._row_to_dict(row) for row in cursor.fetchall()]

    def delete_job(self, job_id: str) -> bool:
        """
        Permanently delete a job from database.
        Used by scheduler for cleanup of old jobs.
        """
        with self.lock:
            # Remove from memory
            if job_id in self.jobs:
                del self.jobs[job_id]

            # Delete from database
            self.db.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            self.db.commit()

            return True

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
        cursor = self.db.execute("""
            SELECT * FROM jobs
            WHERE content_hash = ?
              AND ontology = ?
              AND status IN ('completed', 'processing', 'queued')
            ORDER BY created_at DESC
            LIMIT 1
        """, (content_hash, ontology))

        row = cursor.fetchone()
        if not row:
            return None

        return self._row_to_dict(row)

    def delete_jobs_by_ontology(self, ontology: str) -> int:
        """Delete all jobs for a specific ontology"""
        with self.lock:
            # Count jobs before deleting
            cursor = self.db.execute(
                "SELECT COUNT(*) FROM jobs WHERE ontology = ?",
                (ontology,)
            )
            count = cursor.fetchone()[0]

            if count == 0:
                return 0

            # Get job IDs to remove from memory
            cursor = self.db.execute(
                "SELECT job_id FROM jobs WHERE ontology = ?",
                (ontology,)
            )
            job_ids = [row[0] for row in cursor.fetchall()]

            # Remove from memory
            for job_id in job_ids:
                if job_id in self.jobs:
                    del self.jobs[job_id]

            # Delete from database
            self.db.execute("DELETE FROM jobs WHERE ontology = ?", (ontology,))
            self.db.commit()

            return count

    def clear_all_jobs(self) -> int:
        """
        Clear ALL jobs from the database and memory.
        Used during database reset to keep jobs in sync with graph.

        Returns:
            Number of jobs deleted
        """
        with self.lock:
            # Count jobs before clearing
            cursor = self.db.execute("SELECT COUNT(*) FROM jobs")
            count = cursor.fetchone()[0]

            # Clear memory
            self.jobs.clear()
            self.serial_queue.clear()
            self.serial_running = False

            # Clear database
            self.db.execute("DELETE FROM jobs")
            self.db.commit()

            return count

    def execute_job(self, job_id: str):
        """
        Execute a job (called by BackgroundTasks).
        This is the bridge between FastAPI and worker functions.
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

        # Update to processing
        self.update_job(job_id, {"status": "processing"})

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
            # If this was a serial job, mark serial_running as False and process next
            if job.get("processing_mode") == "serial":
                with self.lock:
                    self.serial_running = False
                    self._process_next_serial_job()

    def queue_serial_job(self, job_id: str):
        """
        Queue a serial job for execution.
        If no serial job is running, start it immediately.
        Otherwise, add to queue.
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
        """Process the next serial job in the queue (called with lock held)"""
        if self.serial_queue:
            next_job_id = self.serial_queue.pop(0)
            self.serial_running = True
            # Execute in background
            import threading
            threading.Thread(target=self.execute_job, args=(next_job_id,)).start()


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

    def _get_connection(self):
        """Get connection from pool"""
        return self.pool.getconn()

    def _return_connection(self, conn):
        """Return connection to pool"""
        self.pool.putconn(conn)

    def register_worker(self, job_type: str, worker_func: Callable):
        """Register a worker function for a job type"""
        self.worker_registry[job_type] = worker_func

    def enqueue(self, job_type: str, job_data: Dict) -> str:
        """Add job to PostgreSQL queue"""
        job_id = f"job_{uuid.uuid4().hex[:12]}"

        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO kg_api.ingestion_jobs (
                        job_id, job_type, status, ontology, client_id,
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
                    job_data.get("client_id", "anonymous"),
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
                        job_id, job_type, status, ontology, client_id,
                        content_hash, job_data, progress, result, analysis,
                        processing_mode, error_message,
                        created_at, started_at, completed_at,
                        approved_at, approved_by, expires_at
                    FROM kg_api.ingestion_jobs
                    WHERE job_id = %s
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

                # Rename error_message to error for consistency
                job['error'] = job.pop('error_message', None)

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
                        # Map 'error' to 'error_message' column
                        set_clauses.append("error_message = %s")
                        params.append(value)
                    elif key in ['progress', 'result', 'analysis']:
                        # JSONB fields
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
                    UPDATE kg_api.ingestion_jobs
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
                    UPDATE kg_api.ingestion_jobs
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
        client_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """List jobs from PostgreSQL, optionally filtered"""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                conditions = []
                params = []

                if status:
                    conditions.append("status = %s")
                    params.append(status)

                if client_id:
                    conditions.append("client_id = %s")
                    params.append(client_id)

                where_clause = " AND ".join(conditions) if conditions else "1=1"
                params.append(limit)

                cur.execute(f"""
                    SELECT
                        job_id, job_type, status, ontology, client_id,
                        content_hash, job_data, progress, result, analysis,
                        processing_mode, error_message,
                        created_at, started_at, completed_at,
                        approved_at, approved_by, expires_at
                    FROM kg_api.ingestion_jobs
                    WHERE {where_clause}
                    ORDER BY created_at DESC
                    LIMIT %s
                """, params)

                jobs = []
                for row in cur.fetchall():
                    job = dict(row)

                    # Convert timestamps to ISO strings
                    for field in ['created_at', 'started_at', 'completed_at', 'approved_at', 'expires_at']:
                        if job.get(field):
                            job[field] = job[field].isoformat()

                    # Rename error_message to error
                    job['error'] = job.pop('error_message', None)

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
                    DELETE FROM kg_api.ingestion_jobs
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
                        job_id, job_type, status, ontology, client_id,
                        content_hash, job_data, progress, result, analysis,
                        processing_mode, error_message,
                        created_at, started_at, completed_at,
                        approved_at, approved_by, expires_at
                    FROM kg_api.ingestion_jobs
                    WHERE content_hash = %s
                      AND ontology = %s
                      AND status IN ('completed', 'running', 'queued')
                    ORDER BY created_at DESC
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

                # Rename error_message to error for consistency
                job['error'] = job.pop('error_message', None)

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
                    SELECT COUNT(*) FROM kg_api.ingestion_jobs
                    WHERE ontology = %s
                """, (ontology,))
                count = cur.fetchone()[0]

                # Delete jobs for this ontology
                cur.execute("""
                    DELETE FROM kg_api.ingestion_jobs
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
                cur.execute("SELECT COUNT(*) FROM kg_api.ingestion_jobs")
                count = cur.fetchone()[0]

                cur.execute("DELETE FROM kg_api.ingestion_jobs")
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


def init_job_queue(queue_type: str = "inmemory", **kwargs) -> JobQueue:
    """
    Factory function to initialize job queue.

    Args:
        queue_type: "inmemory" (Phase 1), "postgresql" (ADR-024), or "redis" (Phase 2)
        **kwargs: Implementation-specific config
    """
    global _job_queue_instance

    if queue_type == "inmemory":
        _job_queue_instance = InMemoryJobQueue(
            db_path=kwargs.get("db_path", "data/jobs.db")
        )
    elif queue_type == "postgresql":
        # ADR-024: PostgreSQL job queue with connection pooling
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
        # Phase 2: Will add RedisJobQueue here
        raise NotImplementedError("Redis queue not implemented yet (Phase 2)")
    else:
        raise ValueError(f"Unknown queue type: {queue_type}")

    return _job_queue_instance


def get_job_queue() -> JobQueue:
    """Get the current job queue instance"""
    if _job_queue_instance is None:
        raise RuntimeError("Job queue not initialized. Call init_job_queue() first.")
    return _job_queue_instance
