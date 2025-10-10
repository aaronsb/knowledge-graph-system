"""Ingestion API routes"""

from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Form, Depends
from fastapi.responses import JSONResponse
from typing import Optional
import json
import base64
from datetime import datetime, timedelta
import tempfile
from pathlib import Path

from ..services.job_queue import get_job_queue
from ..services.content_hasher import ContentHasher
from ..services.job_analysis import JobAnalyzer
from ..models.ingest import IngestionOptions
from ..models.job import JobSubmitResponse, DuplicateJobResponse
from ..middleware.auth import get_current_user

router = APIRouter(prefix="/ingest", tags=["ingestion"])


async def run_job_analysis(job_id: str, auto_approve: bool = False):
    """
    Background task to analyze job and optionally auto-approve.

    ADR-014 workflow:
    1. Analyze job (fast, no LLM calls)
    2. Update job with analysis and status -> awaiting_approval
    3. If auto_approve, immediately approve and execute
    """
    queue = get_job_queue()
    analyzer = JobAnalyzer()

    try:
        job = queue.get_job(job_id)
        if not job:
            return

        # Decode content to temp file for analysis
        content = base64.b64decode(job["job_data"]["content"])

        with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.txt') as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            # Prepare analysis data
            analysis_data = {
                "file_path": tmp_path,
                "ontology": job["job_data"]["ontology"],
                **job["job_data"]["options"]
            }

            # Run analysis (fast - no LLM calls)
            analysis = analyzer.analyze_ingestion_job(analysis_data)

            # Calculate expiration (24 hours from now)
            expires_at = (datetime.now() + timedelta(hours=24)).isoformat()

            # Update job with analysis
            queue.update_job(job_id, {
                "status": "awaiting_approval",
                "analysis": analysis,
                "expires_at": expires_at
            })

            # Auto-approve if requested
            if auto_approve:
                queue.update_job(job_id, {
                    "status": "approved",
                    "approved_at": datetime.now().isoformat(),
                    "approved_by": "auto"
                })
                # Execute immediately
                queue.execute_job(job_id)

        finally:
            # Clean up temp file
            Path(tmp_path).unlink(missing_ok=True)

    except Exception as e:
        # If analysis fails, mark job as failed
        queue.update_job(job_id, {
            "status": "failed",
            "error": f"Analysis failed: {str(e)}"
        })


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
    auto_approve: bool = Form(False, description="Auto-approve job (skip approval step)"),
    processing_mode: str = Form("serial", description="Processing mode: serial or parallel (default: serial for clean concept matching)"),
    target_words: int = Form(1000, description="Target words per chunk"),
    min_words: Optional[int] = Form(None, description="Minimum words per chunk"),
    max_words: Optional[int] = Form(None, description="Maximum words per chunk"),
    overlap_words: int = Form(200, description="Overlap between chunks"),
    current_user: dict = Depends(get_current_user)  # Auth placeholder
):
    """
    Submit a document for async ingestion into the knowledge graph (ADR-014).

    **Approval Workflow:**
    1. Job queued with status `pending` (analysis runs automatically)
    2. Analysis complete → status `awaiting_approval` (check cost estimates)
    3. Manual approval required (POST /jobs/{job_id}/approve)
    4. OR use `auto_approve=true` to skip approval step

    **Deduplication:**
    - Documents are hashed to detect duplicates
    - If same content already ingested into same ontology, returns existing job
    - Use `force=true` to override duplicate detection

    **Returns:**
    - If new: job_id and "pending" status
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
        "content": base64.b64encode(content).decode('utf-8'),  # Base64 encode for JSON serialization
        "content_hash": content_hash,
        "ontology": ontology,
        "filename": use_filename,
        "client_id": current_user["client_id"],  # Track job owner
        "processing_mode": processing_mode,
        "options": {
            "target_words": options.target_words,
            "min_words": options.get_min_words(),
            "max_words": options.get_max_words(),
            "overlap_words": options.overlap_words
        }
    }

    # Enqueue job (status: "pending")
    job_id = queue.enqueue("ingestion", job_data)

    # ADR-014: Trigger analysis instead of immediate execution
    background_tasks.add_task(run_job_analysis, job_id, auto_approve)

    # Return job info
    status_msg = "pending (analyzing)" if not auto_approve else "pending (analyzing, will auto-approve)"
    return JobSubmitResponse(
        job_id=job_id,
        status=status_msg,
        content_hash=content_hash,
        position=None,  # Phase 1: no queue position tracking
        message="Job queued. Analysis running. Poll /jobs/{job_id} for status and cost estimates."
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
    auto_approve: bool = Form(False, description="Auto-approve job (skip approval step)"),
    processing_mode: str = Form("serial", description="Processing mode: serial or parallel (default: serial for clean concept matching)"),
    target_words: int = Form(1000, description="Target words per chunk"),
    overlap_words: int = Form(200, description="Overlap between chunks"),
    current_user: dict = Depends(get_current_user)  # Auth placeholder
):
    """
    Submit raw text for ingestion (ADR-014 approval workflow).

    **Approval Workflow:**
    1. Job queued with status `pending` (analysis runs automatically)
    2. Analysis complete → status `awaiting_approval` (check cost estimates)
    3. Manual approval required OR use `auto_approve=true`

    **Useful for:**
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
        "content": base64.b64encode(content).decode('utf-8'),  # Base64 encode for JSON serialization
        "content_hash": content_hash,
        "ontology": ontology,
        "filename": use_filename,
        "client_id": current_user["client_id"],  # Track job owner
        "processing_mode": processing_mode,
        "options": {
            "target_words": target_words,
            "min_words": int(target_words * 0.8),
            "max_words": int(target_words * 1.5),
            "overlap_words": overlap_words
        }
    }

    # Enqueue job (status: "pending")
    job_id = queue.enqueue("ingestion", job_data)

    # ADR-014: Trigger analysis instead of immediate execution
    background_tasks.add_task(run_job_analysis, job_id, auto_approve)

    # Return job info
    status_msg = "pending (analyzing)" if not auto_approve else "pending (analyzing, will auto-approve)"
    return JobSubmitResponse(
        job_id=job_id,
        status=status_msg,
        content_hash=content_hash,
        position=None,
        message="Job queued. Analysis running. Poll /jobs/{job_id} for status and cost estimates."
    )
