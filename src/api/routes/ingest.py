"""Ingestion API routes"""

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Form
from fastapi.responses import JSONResponse
from typing import Optional
import json

from ..services.job_queue import get_job_queue
from ..services.content_hasher import ContentHasher
from ..models.ingest import IngestionOptions
from ..models.job import JobSubmitResponse, DuplicateJobResponse

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post(
    "",
    response_model=JobSubmitResponse | DuplicateJobResponse,
    summary="Submit document for async ingestion"
)
async def ingest_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Document file to ingest"),
    ontology: str = Form(..., description="Ontology/collection name"),
    filename: Optional[str] = Form(None, description="Override filename"),
    force: bool = Form(False, description="Force re-ingestion even if duplicate"),
    target_words: int = Form(1000, description="Target words per chunk"),
    min_words: Optional[int] = Form(None, description="Minimum words per chunk"),
    max_words: Optional[int] = Form(None, description="Maximum words per chunk"),
    overlap_words: int = Form(200, description="Overlap between chunks")
):
    """
    Submit a document for async ingestion into the knowledge graph.

    The document is queued for processing and a job_id is returned immediately.
    Use the /jobs/{job_id} endpoint to poll for status and results.

    **Deduplication:**
    - Documents are hashed to detect duplicates
    - If same content already ingested into same ontology, returns existing job
    - Use `force=true` to override duplicate detection

    **Returns:**
    - If new: job_id and "queued" status
    - If duplicate: existing job info with suggestion to use force flag
    """
    queue = get_job_queue()
    hasher = ContentHasher(queue)

    # Read file content
    content = await file.read()

    # Hash content for deduplication
    content_hash = hasher.hash_content(content)

    # Check for duplicates
    existing_job = hasher.check_duplicate(content_hash, ontology)

    if existing_job:
        allowed, reason = hasher.should_allow_reingestion(existing_job, force)

        if not allowed:
            # Return duplicate info
            duplicate_info = hasher.get_duplicate_info(existing_job)
            return JSONResponse(
                status_code=200,  # Not an error, just informational
                content=duplicate_info
            )

    # Prepare job data
    use_filename = filename or file.filename or "uploaded_document"

    # Build options
    options = IngestionOptions(
        target_words=target_words,
        min_words=min_words,
        max_words=max_words,
        overlap_words=overlap_words
    )

    job_data = {
        "content": content,
        "content_hash": content_hash,
        "ontology": ontology,
        "filename": use_filename,
        "options": {
            "target_words": options.target_words,
            "min_words": options.get_min_words(),
            "max_words": options.get_max_words(),
            "overlap_words": options.overlap_words
        }
    }

    # Enqueue job
    job_id = queue.enqueue("ingestion", job_data)

    # Schedule background execution
    background_tasks.add_task(queue.execute_job, job_id)

    # Return job info
    return JobSubmitResponse(
        job_id=job_id,
        status="queued",
        content_hash=content_hash,
        position=None,  # Phase 1: no queue position tracking
        message="Job queued for processing. Poll /jobs/{job_id} for status."
    )


@router.post(
    "/text",
    response_model=JobSubmitResponse | DuplicateJobResponse,
    summary="Submit text content for async ingestion"
)
async def ingest_text(
    background_tasks: BackgroundTasks,
    text: str = Form(..., description="Text content to ingest"),
    ontology: str = Form(..., description="Ontology/collection name"),
    filename: Optional[str] = Form(None, description="Filename for source tracking"),
    force: bool = Form(False, description="Force re-ingestion even if duplicate"),
    target_words: int = Form(1000, description="Target words per chunk"),
    overlap_words: int = Form(200, description="Overlap between chunks")
):
    """
    Submit raw text for ingestion (alternative to file upload).

    Useful for:
    - Pasting text directly
    - Sending text from other systems
    - Testing with small documents
    """
    queue = get_job_queue()
    hasher = ContentHasher(queue)

    # Convert text to bytes
    content = text.encode('utf-8')

    # Hash for deduplication
    content_hash = hasher.hash_content(content)

    # Check duplicates
    existing_job = hasher.check_duplicate(content_hash, ontology)

    if existing_job:
        allowed, reason = hasher.should_allow_reingestion(existing_job, force)

        if not allowed:
            duplicate_info = hasher.get_duplicate_info(existing_job)
            return JSONResponse(
                status_code=200,
                content=duplicate_info
            )

    # Prepare job
    use_filename = filename or "text_input"

    job_data = {
        "content": content,
        "content_hash": content_hash,
        "ontology": ontology,
        "filename": use_filename,
        "options": {
            "target_words": target_words,
            "min_words": int(target_words * 0.8),
            "max_words": int(target_words * 1.5),
            "overlap_words": overlap_words
        }
    }

    # Enqueue
    job_id = queue.enqueue("ingestion", job_data)
    background_tasks.add_task(queue.execute_job, job_id)

    return JobSubmitResponse(
        job_id=job_id,
        status="queued",
        content_hash=content_hash,
        position=None,
        message="Job queued for processing."
    )
