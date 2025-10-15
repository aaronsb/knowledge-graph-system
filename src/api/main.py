"""
Knowledge Graph API Server

FastAPI-based REST API for the knowledge graph system with async job processing.

Features:
- Async document ingestion with progress tracking
- Content-based deduplication
- Job queue management
- Future: Concept search, Cypher proxy, etc.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import logging
import time

# Load environment variables FIRST (before any imports that might need them)
load_dotenv()

# Setup logging EARLY (before importing application modules that might log)
from .logging_config import setup_logging
logger = setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))

# Now import application modules (these may log during import, so logging must be configured)
from .services.job_queue import init_job_queue, get_job_queue, PostgreSQLJobQueue
from .services.job_scheduler import init_job_scheduler, get_job_scheduler
from .workers.ingestion_worker import run_ingestion_worker
from .workers.restore_worker import run_restore_worker
from .routes import ingest, jobs, queries, database, ontology, admin, auth, rbac, vocabulary

# Initialize FastAPI app
app = FastAPI(
    title="Knowledge Graph API",
    description="REST API for knowledge graph ingestion and querying with async job processing",
    version="0.1.0 (Phase 1)",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware (adjust for production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing"""
    start_time = time.time()

    # Log request
    logger.info(f"→ {request.method} {request.url.path}")
    if request.query_params:
        logger.debug(f"  Query params: {dict(request.query_params)}")

    # Process request
    try:
        response = await call_next(request)
        duration = time.time() - start_time

        # Log response
        logger.info(f"← {request.method} {request.url.path} - {response.status_code} ({duration:.3f}s)")

        return response
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"← {request.method} {request.url.path} - ERROR ({duration:.3f}s): {e}", exc_info=True)
        raise


# Helper functions
def _cleanup_abandoned_temp_files():
    """
    Cleanup abandoned restore temp files on startup (ADR-015 Phase 2).

    Deletes temp files matching /tmp/restore_*.json that are older than 24 hours.
    These files are left behind if the server crashes during restore upload.
    """
    import glob
    import tempfile
    from pathlib import Path
    from datetime import datetime, timedelta

    temp_dir = Path(tempfile.gettempdir())
    pattern = str(temp_dir / "restore_*.json")

    cutoff_time = datetime.now() - timedelta(hours=24)
    cleaned = 0

    for temp_file_path in glob.glob(pattern):
        try:
            temp_file = Path(temp_file_path)
            if not temp_file.exists():
                continue

            # Check file age
            mtime = datetime.fromtimestamp(temp_file.stat().st_mtime)
            if mtime < cutoff_time:
                temp_file.unlink()
                cleaned += 1
                logger.info(f"🧹 Cleaned abandoned temp file: {temp_file.name} (age: {datetime.now() - mtime})")
        except Exception as e:
            logger.warning(f"Failed to clean temp file {temp_file_path}: {e}")

    if cleaned > 0:
        logger.info(f"✅ Cleaned {cleaned} abandoned temp file(s)")
    else:
        logger.debug("No abandoned temp files to clean")


# Lifecycle events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("🚀 Starting Knowledge Graph API...")

    # ADR-015: Cleanup abandoned restore temp files on startup
    _cleanup_abandoned_temp_files()

    # Initialize job queue (ADR-024: PostgreSQL by default)
    queue_type = os.getenv("QUEUE_TYPE", "postgresql")

    if queue_type == "postgresql":
        queue = init_job_queue(queue_type="postgresql")
        logger.info(f"✅ Job queue initialized: postgresql (kg_api.ingestion_jobs)")
    else:
        # Fallback to SQLite (for development/testing only)
        db_path = os.getenv("JOB_DB_PATH", "data/jobs.db")
        queue = init_job_queue(queue_type=queue_type, db_path=db_path)
        logger.info(f"✅ Job queue initialized: {queue_type} (db: {db_path})")

    # Register worker functions
    queue.register_worker("ingestion", run_ingestion_worker)
    queue.register_worker("restore", run_restore_worker)
    logger.info("✅ Workers registered: ingestion, restore")

    # ADR-014: Initialize and start job scheduler
    scheduler = init_job_scheduler()
    scheduler.start()
    logger.info("✅ Job scheduler started (lifecycle management enabled)")

    logger.info("🎉 API ready!")
    logger.info(f"📚 Docs: http://localhost:8000/docs")
    logger.info(f"📚 ReDoc: http://localhost:8000/redoc")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("👋 Shutting down API...")

    # ADR-014: Stop scheduler gracefully
    try:
        scheduler = get_job_scheduler()
        await scheduler.stop()
        logger.info("✅ Job scheduler stopped")
    except RuntimeError:
        pass  # Scheduler not initialized

    # TODO: Gracefully finish pending jobs
    logger.info("Shutdown complete")


# Include routers
app.include_router(auth.router)  # ADR-027: Authentication endpoints
app.include_router(auth.admin_router)  # ADR-027: Admin user management
app.include_router(rbac.router)  # ADR-028: RBAC management endpoints
app.include_router(ingest.router)
app.include_router(jobs.router)
app.include_router(queries.router)
app.include_router(database.router)
app.include_router(ontology.router)
app.include_router(admin.router)
app.include_router(vocabulary.router)  # ADR-032: Vocabulary management


# Root endpoint
@app.get("/", tags=["health"])
async def root():
    """API health check and info"""
    try:
        queue = get_job_queue()

        # Get queue stats (ADR-014: include new states)
        pending = queue.list_jobs(status="pending", limit=1000)
        awaiting_approval = queue.list_jobs(status="awaiting_approval", limit=1000)
        approved = queue.list_jobs(status="approved", limit=1000)
        queued = queue.list_jobs(status="queued", limit=1000)
        processing = queue.list_jobs(status="processing", limit=1000)

        # Determine queue type from instance
        queue_type_name = "postgresql" if isinstance(queue, PostgreSQLJobQueue) else "inmemory"

        return {
            "service": "Knowledge Graph API",
            "version": "0.1.0 (ADR-024: PostgreSQL Job Queue)",
            "status": "healthy",
            "queue": {
                "type": queue_type_name,
                "pending": len(pending),
                "awaiting_approval": len(awaiting_approval),
                "approved": len(approved),
                "queued": len(queued),
                "processing": len(processing)
            },
            "docs": "/docs",
            "endpoints": {
                "ingest": "POST /ingest (upload file) or POST /ingest/text (raw text)",
                "jobs": "GET /jobs/{job_id} for status, POST /jobs/{job_id}/approve to start processing"
            }
        }
    except Exception as e:
        logger.error(f"Error in root endpoint: {e}", exc_info=True)
        raise


@app.get("/health", tags=["health"])
async def health():
    """Simple health check"""
    return {"status": "healthy"}


# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Development only
        log_level="info"
    )
