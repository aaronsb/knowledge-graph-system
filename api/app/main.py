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
from .services.scheduled_jobs_manager import JobScheduler as ScheduledJobsManager
from .services.worker_registry import register_all_workers, get_all_job_types, validate_lane_uniqueness
from .services.lane_manager import LaneManager
from .launchers import CategoryRefreshLauncher, VocabConsolidationLauncher, EpistemicRemeasurementLauncher, VocabEmbeddingLauncher, ProjectionLauncher, ArtifactCleanupLauncher, AnnealingLauncher
from .routes import ingest, ingest_image, jobs, queries, database, ontology, admin, auth, rbac, vocabulary, vocabulary_config, embedding, extraction, oauth, sources, projection, artifacts, grants, query_definitions, documents, concepts, edges, graph, storage_admin, programs, admin_workers, models, epochs
from .services.embedding_worker import get_embedding_worker
from .lib.age_client import AGEClient
from .lib.ai_providers import get_provider
# Module-level variables
scheduled_jobs_manager = None
lane_manager = None
_is_dispatch_leader = False
_dispatch_lock_conn = None  # Held for process lifetime to maintain advisory lock


def _try_acquire_dispatch_lock(queue) -> bool:
    """Try to acquire PostgreSQL advisory lock for dispatch leadership.

    With --workers N, multiple uvicorn processes run startup_event(). Only one
    should run the lane manager, scheduler, and scheduled jobs. We use a session-level
    advisory lock (pg_try_advisory_lock) which is held for the connection lifetime.

    Returns True if this process acquired the lock (is the leader).
    """
    global _dispatch_lock_conn
    LOCK_ID = 100_000_001  # ADR-100 dispatch leader lock

    try:
        conn = queue._get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_ID,))
            acquired = cur.fetchone()[0]

        if acquired:
            # Keep connection alive — releasing it drops the lock
            _dispatch_lock_conn = conn
            logger.info(f"Acquired dispatch leader lock (advisory lock {LOCK_ID})")
            return True
        else:
            queue._return_connection(conn)
            logger.info(f"Dispatch leader lock held by another worker")
            return False
    except Exception as e:
        logger.warning(f"Failed to acquire dispatch leader lock: {e}")
        return False


# Held for the lifetime of the cold-start owner process — releasing it
# drops the advisory lock and would let another worker claim cold-start
# on a future restart, which is the intended behavior. During this
# process's lifetime, the lock stays held so subsequent startup_event
# runs (if any) skip cold-start.
_cold_start_lock_conn = None


def _try_acquire_cold_start_lock(queue) -> bool:
    """Try to acquire the cold-start advisory lock.

    Cold-start fires `regenerate_missing_if_vocab_changed` which inserts
    into embedding_generation_jobs and calls the LLM provider for every
    missing type. With --workers N, every uvicorn process would otherwise
    do this in parallel — doubling LLM spend on fresh boots after a
    migration that seeded new builtin types.

    Returns True if this process owns cold-start (and should run it),
    False if another worker holds the lock (and we should skip).
    """
    global _cold_start_lock_conn
    LOCK_ID = 100_000_002  # PR #425 cold-start owner lock

    try:
        conn = queue._get_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_ID,))
            acquired = cur.fetchone()[0]

        if acquired:
            _cold_start_lock_conn = conn
            logger.info(f"Acquired cold-start owner lock (advisory lock {LOCK_ID})")
            return True
        else:
            queue._return_connection(conn)
            logger.info("Cold-start owner lock held by another worker — skipping")
            return False
    except Exception as e:
        logger.warning(f"Failed to acquire cold-start owner lock: {e}")
        # Fall through to running cold-start: a missing lock is a softer
        # failure than skipping cold-start entirely on a fresh DB.
        return True

# Initialize FastAPI app
app = FastAPI(
    title="Knowledge Graph API",
    description="REST API for knowledge graph ingestion and querying with async job processing",
    version="0.1.0 (Phase 1)",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware — origins from ALLOWED_ORIGINS env var (comma-separated)
_allowed_origins = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()
] or ["http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing"""
    start_time = time.time()

    # Use debug level for high-frequency polling endpoints to reduce noise
    is_polling = request.url.path in ("/health", "/database/epoch")
    log_level = logger.debug if is_polling else logger.info

    # Log request
    log_level(f"→ {request.method} {request.url.path}")
    if request.query_params:
        logger.debug(f"  Query params: {dict(request.query_params)}")

    # Process request
    try:
        response = await call_next(request)
        duration = time.time() - start_time

        # Log response
        log_level(f"← {request.method} {request.url.path} - {response.status_code} ({duration:.3f}s)")

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

    # Initialize job queue (ADR-024+050: PostgreSQL only, unified kg_api.jobs table)
    queue = init_job_queue(queue_type="postgresql")
    logger.info(f"✅ Job queue initialized: postgresql (kg_api.jobs)")

    # Register worker functions (ADR-100: single source of truth in worker_registry.py)
    validate_lane_uniqueness()  # Fail fast if a job type is in multiple lanes
    register_all_workers(queue)
    logger.info(f"✅ Workers registered: {', '.join(get_all_job_types())}")

    # ADR-100: elect the dispatch leader early — before model load — so the
    # non-leader (under --workers N) can skip GPU-heavy resources it would
    # never use. The leader runs ingestion jobs (which need the visual
    # model); non-leaders only handle HTTP, which uses text embeddings for
    # query encoding. Skipping visual on non-leaders saves ~350MB weights
    # + accelerate/processor overhead per non-leader process.
    global _is_dispatch_leader
    _is_dispatch_leader = _try_acquire_dispatch_lock(queue)

    # IMPORTANT: Initialize embedding infrastructure BEFORE starting any jobs
    # (fixes race condition where jobs start before EmbeddingWorker is ready)

    # ADR-039: Initialize embedding model manager (if local embeddings configured)
    # ADR-101: init_embedding_model_manager() already attempts a CPU fallback when
    # the requested accelerator is unavailable. If this still raises, the local
    # provider is unusable and downstream code will fail — log the truth instead
    # of pretending we fell back to an API provider.
    try:
        from .lib.embedding_model_manager import init_embedding_model_manager
        model_manager = await init_embedding_model_manager()
        if model_manager:
            logger.info(f"✅ Embedding model manager initialized: {model_manager.get_model_name()} ({model_manager.get_dimensions()} dims)")
        else:
            logger.info("📍 Using API-based embeddings (OpenAI or configured provider)")
    except Exception as e:
        logger.error(f"❌ Failed to initialize local embedding model (including CPU fallback): {e}")
        logger.error(
            "   Active embedding profile is 'local' but no model could be loaded. "
            "Ingestion and semantic search will fail until this is resolved. "
            "Fix: switch the active profile to an API provider via the operator, "
            "or repair the local model configuration."
        )

    # Initialize visual embedding generator (profile-driven, migration 055).
    # Only the dispatch leader loads this: visual embeddings are produced by
    # ingestion jobs, which only run on the leader. Non-leader workers would
    # claim ~350MB+ of VRAM (weights + processor + accelerate runtime) for a
    # model they would never call.
    if _is_dispatch_leader:
        try:
            from .lib.visual_embeddings import init_visual_embedding_generator
            visual_gen = await init_visual_embedding_generator()
            if visual_gen:
                logger.info(f"✅ Visual embedding generator initialized: {visual_gen.get_model_name()} ({visual_gen.get_embedding_dimension()} dims)")
            else:
                logger.info("📍 Visual embeddings: disabled (text-only profile or API-based)")
        except Exception as e:
            # ADR-101: parity with the text-embedding honesty fix at line 199.
            # "Features may be limited" obscured the actual state — the profile
            # asks for visual embeddings, the load failed, so every image ingest
            # will raise. State that, instead of softening.
            logger.error(f"❌ Failed to initialize visual embedding generator: {e}")
            logger.error(
                "   Visual embedding profile is active but the generator could not load. "
                "Image ingestion will fail until this is resolved. "
                "Fix: switch to a text-only profile, or repair the visual model configuration."
            )
    else:
        logger.info("ℹ️  Non-leader worker — skipping visual embedding generator (ingestion runs on leader)")

    # ADR-041: Validate API keys at startup (non-blocking)
    try:
        from .lib.api_key_validator import validate_api_keys_at_startup
        validate_api_keys_at_startup()
    except Exception as e:
        logger.warning(f"⚠️  API key validation failed: {e}")
        logger.info("   System will continue without validated keys")

    # ADR-045: Initialize EmbeddingWorker (required before any jobs can run)
    try:
        logger.info("🔧 Initializing EmbeddingWorker...")
        age_client = AGEClient()
        ai_provider = get_provider()

        # Initialize singleton
        embedding_worker = get_embedding_worker(age_client, ai_provider)

        if embedding_worker:
            # With --workers N, gate cold-start behind a session-level
            # advisory lock so only one process fires the LLM-heavy
            # initialize_builtin_embeddings path.
            if _try_acquire_cold_start_lock(queue):
                logger.info("🌡️  Checking builtin vocabulary embeddings (cold start)...")
                cold_start_result = await embedding_worker.initialize_builtin_embeddings()

                if cold_start_result.target_count > 0:
                    logger.info(
                        f"✅ Cold start complete: {cold_start_result.processed_count}/{cold_start_result.target_count} "
                        f"builtin types initialized in {cold_start_result.duration_ms}ms"
                    )
                    if cold_start_result.failed_count > 0:
                        logger.warning(f"⚠️  {cold_start_result.failed_count} types failed during cold start")
                else:
                    logger.info("✓  Builtin vocabulary embeddings already initialized")
            else:
                logger.info("✓  Cold start owned by another worker — skipping")
        else:
            logger.warning("⚠️  EmbeddingWorker initialization failed - embedding features may be limited")

    except Exception as e:
        # Integrity errors (FK / NOT NULL / unique violations — SQLSTATE
        # class 23xxx) at startup leave the embedding subsystem in a
        # stuck state, not a softly-degraded one. Surface those at ERROR
        # with a full traceback so the next analogous regression isn't
        # masked as a benign warning for months the way PR #425's bug was.
        import psycopg2.errors
        if isinstance(e, psycopg2.errors.IntegrityError):
            logger.error(
                f"❌ EmbeddingWorker initialization failed with integrity violation: {e}. "
                f"This indicates a schema/data drift — cold-start cannot proceed and "
                f"embedding-dependent features will not work until resolved.",
                exc_info=True,
            )
        else:
            logger.warning(f"⚠️  EmbeddingWorker initialization failed: {e}")
            logger.info("   System will continue without embedding worker (manual initialization may be needed)")

    # Resume interrupted jobs (jobs that were processing when server stopped)
    # Note: SQLite queue uses "processing", PostgreSQL queue uses "running"
    try:
        # Check both "processing" (SQLite) and "running" (PostgreSQL) statuses
        processing_jobs = queue.list_jobs(status="processing", limit=500)
        running_jobs = queue.list_jobs(status="running", limit=500)
        interrupted_jobs = processing_jobs + running_jobs

        resumed_count = 0
        for job in interrupted_jobs:
            job_id = job["job_id"]
            progress = job.get("progress") or {}  # Handle NULL progress
            chunks_total = progress.get("chunks_total", 0)
            chunks_processed = progress.get("resume_from_chunk", 0)

            # Safety: Track resume attempts to prevent infinite loops
            job_data = job.get("job_data") or {}
            resume_attempts = job_data.get("resume_attempts", 0)
            MAX_RESUME_ATTEMPTS = 3

            if resume_attempts >= MAX_RESUME_ATTEMPTS:
                # Too many resume attempts - mark as failed
                queue.update_job(job_id, {
                    "status": "failed",
                    "error": f"Job failed after {resume_attempts} resume attempts (possible infinite loop or persistent crash)"
                })
                logger.error(f"❌ Job failed after {resume_attempts} resume attempts: {job_id}")
                continue

            if chunks_total == 0:
                # Job was interrupted before processing started - reset to approved to start fresh
                updated_job_data = {**job_data, "resume_attempts": resume_attempts + 1}
                queue.update_job(job_id, {
                    "status": "approved",
                    "job_data": updated_job_data
                })
                logger.info(f"🔄 Queued interrupted job (never started, attempt {resume_attempts + 1}/{MAX_RESUME_ATTEMPTS}): {job_id}")
                resumed_count += 1
            elif chunks_processed < chunks_total:
                # Job was interrupted mid-processing - reset to approved for resume
                updated_job_data = {**job_data, "resume_attempts": resume_attempts + 1}
                queue.update_job(job_id, {
                    "status": "approved",
                    "job_data": updated_job_data
                })
                logger.info(f"🔄 Queued interrupted job for resume (attempt {resume_attempts + 1}/{MAX_RESUME_ATTEMPTS}): {job_id} (chunk {chunks_processed + 1}/{chunks_total})")
                resumed_count += 1
            else:
                # Job finished all chunks but didn't mark complete - mark it now
                queue.update_job(job_id, {"status": "completed"})
                logger.info(f"✅ Marked completed job: {job_id}")

        # ADR-100: Approved jobs are no longer pushed to threads here.
        # The lane manager's poll loops will claim them automatically.

        if resumed_count > 0:
            logger.info(f"✅ Resumed {resumed_count} interrupted job(s) (will be claimed by lane loops)")

    except Exception as e:
        logger.error(f"⚠️  Failed to resume interrupted jobs: {e}", exc_info=True)

    # ADR-100: Only one uvicorn worker should run the lane manager, scheduler,
    # and scheduled jobs manager. Leader was elected earlier (before model
    # load) so non-leaders can skip GPU-heavy resources; here we just branch
    # on the existing election result.
    if _is_dispatch_leader:
        # ADR-100: Start lane manager (poll-and-claim dispatch)
        global lane_manager
        lane_manager = LaneManager(queue)
        await lane_manager.start()
        logger.info("✅ Lane manager started (database-driven job dispatch)")

        # ADR-014: Initialize and start job scheduler (lifecycle management)
        scheduler = init_job_scheduler()
        scheduler.start()
        logger.info("✅ Job scheduler started (lifecycle management enabled)")

        # ADR-050: Initialize and start scheduled jobs manager (maintenance tasks)
        global scheduled_jobs_manager
        launcher_registry = {
            'CategoryRefreshLauncher': CategoryRefreshLauncher,
            'VocabConsolidationLauncher': VocabConsolidationLauncher,
            'EpistemicRemeasurementLauncher': EpistemicRemeasurementLauncher,
            'VocabEmbeddingLauncher': VocabEmbeddingLauncher,  # Migration 069: vocab embedding regen
            'ProjectionLauncher': ProjectionLauncher,  # ADR-078: Embedding projections
            'ArtifactCleanupLauncher': ArtifactCleanupLauncher,  # ADR-083: Artifact cleanup
            'AnnealingLauncher': AnnealingLauncher,  # ADR-200: Ontology annealing cycle
        }
        scheduled_jobs_manager = ScheduledJobsManager(queue, launcher_registry)
        await scheduled_jobs_manager.start()
        logger.info("✅ Scheduled jobs manager started (maintenance tasks enabled)")
    else:
        logger.info("ℹ️  Another worker is the dispatch leader — skipping lane manager, scheduler, scheduled jobs")

    logger.info("🎉 API ready!")
    logger.info(f"📚 Docs: http://localhost:8000/docs")
    logger.info(f"📚 ReDoc: http://localhost:8000/redoc")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("👋 Shutting down API...")

    # Only the dispatch leader runs these services
    if _is_dispatch_leader:
        # ADR-014: Stop lifecycle scheduler gracefully
        try:
            scheduler = get_job_scheduler()
            await scheduler.stop()
            logger.info("✅ Job scheduler stopped (lifecycle management)")
        except RuntimeError:
            pass  # Scheduler not initialized

        # ADR-100: Stop lane manager (drain lanes, let running jobs finish)
        global lane_manager
        if lane_manager:
            await lane_manager.stop()
            logger.info("✅ Lane manager stopped")

        # ADR-050: Stop scheduled jobs manager gracefully
        global scheduled_jobs_manager
        if scheduled_jobs_manager:
            await scheduled_jobs_manager.stop()
            logger.info("✅ Scheduled jobs manager stopped (maintenance tasks)")

        # Release dispatch leader lock
        global _dispatch_lock_conn
        if _dispatch_lock_conn:
            try:
                _dispatch_lock_conn.close()
            except Exception:
                pass
            _dispatch_lock_conn = None

    # Shut down job queue executor and connection pool
    try:
        queue = get_job_queue()
        queue.shutdown(wait=False)
        logger.info("✅ Job queue shut down")
    except RuntimeError:
        pass  # Queue not initialized

    logger.info("Shutdown complete")

    # Detach stream handlers so draining worker threads don't crash
    # writing to closed stderr/stdout (common in test teardown).
    root = logging.getLogger()
    for handler in root.handlers[:]:
        if isinstance(handler, logging.StreamHandler):
            root.removeHandler(handler)


# Include routers
app.include_router(auth.router)  # ADR-027: Authentication endpoints
app.include_router(auth.admin_router)  # ADR-027: Admin user management
app.include_router(oauth.router)  # ADR-054: OAuth 2.0 client management and token flows
app.include_router(rbac.router)  # ADR-028: RBAC management endpoints
app.include_router(ingest.router)
app.include_router(ingest_image.router)  # ADR-057: Multimodal image ingestion
app.include_router(sources.router)  # ADR-057: Source retrieval (images from MinIO)
app.include_router(jobs.router)
app.include_router(queries.router)
app.include_router(database.router)
app.include_router(ontology.router)
app.include_router(admin.router)
app.include_router(vocabulary.router)  # ADR-032: Vocabulary management
app.include_router(vocabulary_config.public_router)  # Vocabulary config (public)
app.include_router(vocabulary_config.admin_router)  # Vocabulary config (admin)
app.include_router(embedding.public_router)  # ADR-039: Public embedding config
app.include_router(embedding.admin_router)  # ADR-039: Admin embedding management
app.include_router(extraction.public_router)  # ADR-041: Public extraction config
app.include_router(extraction.admin_router)  # ADR-041: Admin extraction management
app.include_router(projection.router)  # ADR-078: Embedding landscape projections
app.include_router(artifacts.router)  # ADR-083: Artifact persistence
app.include_router(grants.router)  # ADR-082: Groups and resource grants
app.include_router(query_definitions.router)  # ADR-083: Query definitions
app.include_router(programs.router)  # ADR-500: Program notarization
app.include_router(documents.router)  # ADR-084: Document content retrieval
app.include_router(documents.query_router)  # ADR-084: Document search
app.include_router(concepts.router)  # ADR-089: Deterministic concept CRUD
app.include_router(epochs.router)  # ADR-203: Graph epoch event log read surface
app.include_router(edges.router)  # ADR-089: Deterministic edge CRUD
app.include_router(graph.router)  # ADR-089: Batch graph operations
app.include_router(storage_admin.router)  # Storage diagnostics
app.include_router(admin_workers.router)  # ADR-100: Worker lane management
app.include_router(models.admin_router)  # ADR-800: Model catalog management


# Root endpoint
@app.get("/", tags=["health"])
def root():
    """API health check and info"""
    try:
        queue = get_job_queue()

        # Get queue stats (ADR-014: include new states)
        pending = queue.list_jobs(status="pending", limit=1000)
        awaiting_approval = queue.list_jobs(status="awaiting_approval", limit=1000)
        approved = queue.list_jobs(status="approved", limit=1000)
        queued = queue.list_jobs(status="queued", limit=1000)
        processing = queue.list_jobs(status="processing", limit=1000)

        # Queue type is always PostgreSQL now (ADR-050: SQLite removed)
        queue_type_name = "postgresql"

        # Get epoch from graph_metrics (ADR-200)
        epoch = 0
        try:
            from .lib.age_client import AGEClient
            client = AGEClient()
            try:
                epoch = client.get_current_epoch()
            finally:
                client.close()
        except Exception:
            pass  # epoch stays 0 if unavailable

        return {
            "service": "Knowledge Graph API",
            "version": "0.1.0 (ADR-024: PostgreSQL Job Queue)",
            "status": "healthy",
            "epoch": epoch,
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
                "ingest_image": "POST /ingest/image (multimodal image ingestion, ADR-057)",
                "jobs": "GET /jobs/{job_id} for status, POST /jobs/{job_id}/approve to start processing"
            }
        }
    except Exception as e:
        logger.error(f"Error in root endpoint: {e}", exc_info=True)
        raise


@app.get("/health", tags=["health"])
def health():
    """
    Health check endpoint with component status.

    Checks:
    - Database (PostgreSQL + AGE) connectivity
    - Garage (S3 storage) bucket accessibility

    Returns 200 with status details. Individual component failures
    are reported in the response but don't fail the overall check
    (allows partial operation / graceful degradation).
    """
    components = {}

    # API is healthy if we're responding
    components["api"] = {"status": "healthy"}

    # Check database
    try:
        from .lib.age_client import AGEClient
        client = AGEClient()
        client._execute_cypher("RETURN 1 as ping", fetch_one=True)
        client.close()
        components["database"] = {"status": "healthy"}
    except Exception as e:
        components["database"] = {"status": "unhealthy", "error": str(e)}

    # Check Garage storage (use singleton base client to avoid log spam)
    try:
        from .lib.garage import get_base_client
        garage = get_base_client()
        if garage.health_check():
            components["garage"] = {"status": "healthy", "bucket": garage.bucket_name}
        else:
            components["garage"] = {"status": "unhealthy", "bucket": garage.bucket_name}
    except Exception as e:
        components["garage"] = {"status": "unhealthy", "error": str(e)}

    # Overall status - healthy if at least database is up
    all_healthy = all(c.get("status") == "healthy" for c in components.values())

    return {
        "status": "healthy" if all_healthy else "degraded",
        "components": components
    }


# For running with uvicorn directly
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Development only
        log_level="info"
    )
