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

from .services.job_queue import init_job_queue, get_job_queue
from .workers.ingestion_worker import run_ingestion_worker
from .routes import ingest, jobs, queries, database, ontology, admin
from .logging_config import setup_logging

# Load environment variables
load_dotenv()

# Setup logging
logger = setup_logging(log_level=os.getenv("LOG_LEVEL", "INFO"))

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


# Lifecycle events
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("🚀 Starting Knowledge Graph API...")

    # Initialize job queue
    queue_type = os.getenv("QUEUE_TYPE", "inmemory")
    db_path = os.getenv("JOB_DB_PATH", "data/jobs.db")

    queue = init_job_queue(queue_type=queue_type, db_path=db_path)
    logger.info(f"✅ Job queue initialized: {queue_type} (db: {db_path})")

    # Register worker functions
    queue.register_worker("ingestion", run_ingestion_worker)
    logger.info("✅ Workers registered: ingestion")

    logger.info("🎉 API ready!")
    logger.info(f"📚 Docs: http://localhost:8000/docs")
    logger.info(f"📚 ReDoc: http://localhost:8000/redoc")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("👋 Shutting down API...")
    # TODO: Gracefully finish pending jobs
    logger.info("Shutdown complete")


# Include routers
app.include_router(ingest.router)
app.include_router(jobs.router)
app.include_router(queries.router)
app.include_router(database.router)
app.include_router(ontology.router)
app.include_router(admin.router)


# Root endpoint
@app.get("/", tags=["health"])
async def root():
    """API health check and info"""
    try:
        queue = get_job_queue()

        # Get queue stats
        queued = queue.list_jobs(status="queued", limit=1000)
        processing = queue.list_jobs(status="processing", limit=1000)

        return {
            "service": "Knowledge Graph API",
            "version": "0.1.0",
            "status": "healthy",
            "queue": {
                "type": "inmemory",  # Phase 1
                "queued": len(queued),
                "processing": len(processing)
            },
            "docs": "/docs",
            "endpoints": {
                "ingest": "POST /ingest (upload file) or POST /ingest/text (raw text)",
                "jobs": "GET /jobs/{job_id} for status"
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
