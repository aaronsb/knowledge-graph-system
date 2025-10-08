"""
Abstract job queue interface with multiple implementations.

Allows swapping between in-memory (Phase 1) and Redis (Phase 2) without
changing route handlers.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Callable
from datetime import datetime
import uuid
import json
import sqlite3
import threading
from pathlib import Path


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
            # ADR-014: Approval workflow fields
            "analysis": json.loads(safe_get(row, "analysis")) if safe_get(row, "analysis") else None,
            "approved_at": safe_get(row, "approved_at"),
            "approved_by": safe_get(row, "approved_by"),
            "expires_at": safe_get(row, "expires_at")
        }

    def _save_to_db(self, job: Dict):
        """Persist job to SQLite"""
        self.db.execute("""
            INSERT OR REPLACE INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            job.get("expires_at")
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
                "created_at": datetime.now().isoformat(),
                "started_at": None,
                "completed_at": None,
                "job_data": job_data,
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
                self.jobs[job_id]["started_at"] = datetime.now().isoformat()

            if updates.get("status") in ["completed", "failed"]:
                self.jobs[job_id]["completed_at"] = datetime.now().isoformat()

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
            job["completed_at"] = datetime.now().isoformat()
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


# Singleton instance (will be initialized in main.py)
_job_queue_instance: Optional[JobQueue] = None


def init_job_queue(queue_type: str = "inmemory", **kwargs) -> JobQueue:
    """
    Factory function to initialize job queue.

    Args:
        queue_type: "inmemory" (Phase 1) or "redis" (Phase 2)
        **kwargs: Implementation-specific config
    """
    global _job_queue_instance

    if queue_type == "inmemory":
        _job_queue_instance = InMemoryJobQueue(
            db_path=kwargs.get("db_path", "data/jobs.db")
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
