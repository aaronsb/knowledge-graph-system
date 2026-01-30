"""Ingestion API routes"""

import logging
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Form, Depends
from fastapi.responses import JSONResponse
from typing import Optional
import json
import base64
from datetime import timedelta
from api.app.lib.datetime_utils import timedelta_from_now, to_iso
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

from ..services.job_queue import get_job_queue
from ..services.content_hasher import ContentHasher
from ..services.job_analysis import JobAnalyzer
from ..models.ingest import IngestionOptions
from ..models.job import JobSubmitResponse, DuplicateJobResponse
from ..dependencies.auth import CurrentUser

router = APIRouter(prefix="/ingest", tags=["ingestion"])


def _is_image_file(filename: str) -> bool:
    """
    Check if file is a supported image format.

    Supported formats: PNG, JPEG, GIF, WebP, BMP

    Args:
        filename: Name of the file to check

    Returns:
        True if file extension indicates an image, False otherwise
    """
    if not filename:
        return False
    ext = filename.lower().split('.')[-1]
    return ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']


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
            expires_at = to_iso(timedelta_from_now(hours=24))

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
                    "approved_at": to_iso(timedelta_from_now()),
                    "approved_by": "auto"
                })
                # Execute immediately (ADR-031: Non-blocking execution)
                queue.execute_job_async(job_id)

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
    current_user: CurrentUser,
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
    # ADR-051: Source metadata (optional, best-effort provenance tracking)
    source_type: Optional[str] = Form(None, description="Source type: file, stdin, mcp, api"),
    source_path: Optional[str] = Form(None, description="Full filesystem path (file ingestion only)"),
    source_hostname: Optional[str] = Form(None, description="Hostname where ingestion initiated")
):
    """
    Submit a document for async ingestion into the knowledge graph with approval workflow.

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `ingest:create` permission

    Implements ADR-014 job approval workflow with cost estimation before processing.
    Documents are chunked, analyzed by LLM for concept extraction, and upserted to
    the graph with semantic relationships.

    **Workflow (ADR-014):**
    1. Submit document → Job created with status `pending`
    2. Analysis runs automatically (fast, estimates costs without LLM calls)
    3. Job status → `awaiting_approval` with cost/time estimates
    4. Manual approval required via POST /jobs/{job_id}/approve
    5. OR use `auto_approve=true` to skip approval and process immediately
    6. Processing begins → Watch progress via GET /jobs/{job_id}/stream

    **Content Deduplication:**
    - SHA-256 content hash detects duplicate ingestions
    - If same content already exists in same ontology, returns existing job_id
    - Use `force=true` to override and re-process anyway
    - Useful for re-ingestion after system updates or to different ontologies

    **Processing Modes:**
    - `serial`: Process chunks one-by-one for clean concept matching (recommended, default)
    - `parallel`: Process chunks concurrently for speed (may create duplicate concepts)

    **Chunking Parameters:**
    - `target_words`: Ideal chunk size (default 1000, range 500-2000)
    - `overlap_words`: Word overlap between chunks for context (default 200)
    - Auto-calculated: min_words = target_words * 0.8, max_words = target_words * 1.5

    **Returns:**
    - New job: `job_id`, status "pending (analyzing)", poll endpoint
    - Duplicate: Existing `job_id` with suggestion to use `force=true` if desired

    **Example Response:**
    ```json
    {
      "job_id": "abc123",
      "status": "pending (analyzing)",
      "content_hash": "sha256:...",
      "message": "Job queued. Analysis running. Poll /jobs/abc123 for status."
    }
    ```
    """
    from ..lib.age_client import AGEClient

    queue = get_job_queue()
    age_client = AGEClient()
    hasher = ContentHasher(queue, age_client)  # ADR-051: Pass age_client for graph checks

    # ADR-200 Phase 2: Frozen ontologies reject ingestion
    if age_client.is_ontology_frozen(ontology):
        raise HTTPException(
            status_code=403,
            detail=f"Ontology '{ontology}' is frozen (read-only). Set lifecycle state to 'active' before ingesting."
        )

    # Read file content
    content = await file.read()

    # ADR-033: Multimodal image ingestion
    # If this is an image, use vision AI to describe it, then process description as text
    if _is_image_file(file.filename):
        from ..lib.ai_providers import get_provider, IMAGE_DESCRIPTION_PROMPT

        logger.info(f"Detected image file: {file.filename}. Using vision AI for description...")

        try:
            provider = get_provider()
            description_response = provider.describe_image(
                image_data=content,
                prompt=IMAGE_DESCRIPTION_PROMPT
            )

            # Replace image bytes with text description
            original_size = len(content)
            content = description_response["text"].encode('utf-8')
            vision_tokens = description_response.get("tokens", 0)

            logger.info(
                f"Image described successfully: {original_size} bytes → "
                f"{len(content)} bytes description ({vision_tokens} tokens)"
            )

            # TODO Phase 2: Store vision_tokens for cost tracking in job analysis
            # For now, vision tokens will be counted in the extraction phase

        except Exception as e:
            logger.error(f"Failed to describe image: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Image description failed: {str(e)}"
            )

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
        "user_id": current_user.id,  # Track job owner (user ID from kg_auth.users)
        "username": current_user.username,  # For Garage metadata (FUSE support)
        "processing_mode": processing_mode,
        "options": {
            "target_words": options.target_words,
            "min_words": options.get_min_words(),
            "max_words": options.get_max_words(),
            "overlap_words": options.overlap_words
        },
        # ADR-051: Source metadata (optional, best-effort provenance)
        "source_type": source_type,
        "source_path": source_path,
        "source_hostname": source_hostname
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
    current_user: CurrentUser,
    text: str = Form(..., description="Text content to ingest"),
    ontology: str = Form(..., description="Ontology/collection name"),
    filename: Optional[str] = Form(None, description="Filename for source tracking"),
    force: bool = Form(False, description="Force re-ingestion even if duplicate"),
    auto_approve: bool = Form(False, description="Auto-approve job (skip approval step)"),
    processing_mode: str = Form("serial", description="Processing mode: serial or parallel (default: serial for clean concept matching)"),
    target_words: int = Form(1000, description="Target words per chunk"),
    overlap_words: int = Form(200, description="Overlap between chunks"),
    # ADR-051: Source metadata (optional, best-effort provenance tracking)
    source_type: Optional[str] = Form(None, description="Source type: file, stdin, mcp, api"),
    source_path: Optional[str] = Form(None, description="Full filesystem path (file ingestion only)"),
    source_hostname: Optional[str] = Form(None, description="Hostname where ingestion initiated")
):
    """
    Submit raw text content for async ingestion into the knowledge graph.

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `ingest:create` permission

    Alternative to file upload for direct text submission. Implements the same
    ADR-014 approval workflow and deduplication as the file-based endpoint.

    **When to Use:**
    - Pasting text directly from clipboard or editor
    - Programmatic ingestion from other systems (APIs, scraping, etc.)
    - Quick testing with small text snippets
    - Ingesting generated or synthetic content

    **Workflow:**
    1. Submit text → Job created with status `pending`
    2. Analysis runs (estimates costs and processing time)
    3. Job status → `awaiting_approval` with estimates
    4. Manual approval required OR use `auto_approve=true`
    5. Processing begins → Stream progress via GET /jobs/{job_id}/stream

    **Same Features as File Upload:**
    - Content deduplication via SHA-256 hashing
    - Cost estimation before processing
    - Serial/parallel processing modes
    - Configurable chunking parameters
    - 24-hour approval expiration

    **Parameters:**
    - `text`: Raw text content (UTF-8 encoded)
    - `filename`: Optional source name for tracking (defaults to "text_input")
    - `ontology`: Collection name for organizing concepts
    - `force`: Override duplicate detection
    - `auto_approve`: Skip approval step for immediate processing

    **Returns:**
    - New job: `job_id` and status "pending (analyzing)"
    - Duplicate: Existing `job_id` with `force=true` suggestion
    """
    from ..lib.age_client import AGEClient

    queue = get_job_queue()
    age_client = AGEClient()
    hasher = ContentHasher(queue, age_client)  # ADR-051: Pass age_client for graph checks

    # ADR-200 Phase 2: Frozen ontologies reject ingestion
    if age_client.is_ontology_frozen(ontology):
        raise HTTPException(
            status_code=403,
            detail=f"Ontology '{ontology}' is frozen (read-only). Set lifecycle state to 'active' before ingesting."
        )

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
        "user_id": current_user.id,  # Track job owner (user ID from kg_auth.users)
        "username": current_user.username,  # For Garage metadata (FUSE support)
        "processing_mode": processing_mode,
        "options": {
            "target_words": target_words,
            "min_words": int(target_words * 0.8),
            "max_words": int(target_words * 1.5),
            "overlap_words": overlap_words
        },
        # ADR-051: Source metadata (optional, best-effort provenance)
        "source_type": source_type,
        "source_path": source_path,
        "source_hostname": source_hostname
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
