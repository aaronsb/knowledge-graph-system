"""
Image Ingestion API routes (ADR-057)

Dedicated endpoint for multimodal image ingestion with visual embeddings and
context injection. Follows the "hairpin pattern": image → prose → concepts.
"""

import logging
import base64
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException, Form, Depends
from fastapi.responses import JSONResponse
from typing import Optional
from datetime import datetime, timedelta
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

from ..services.job_queue import get_job_queue
from ..services.content_hasher import ContentHasher
from ..services.job_analysis import JobAnalyzer
from ..models.ingest import IngestionOptions
from ..models.job import JobSubmitResponse, DuplicateJobResponse
from ..dependencies.auth import get_current_active_user
from ..models.auth import UserInDB

# ADR-057: Vision and embedding modules
from ..lib.vision_providers import get_vision_provider, LITERAL_DESCRIPTION_PROMPT
from ..lib.visual_embeddings import generate_visual_embedding, check_visual_embedding_health
from ..lib.minio_client import get_minio_client

router = APIRouter(prefix="/ingest", tags=["ingestion"])


SUPPORTED_IMAGE_FORMATS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}


def _validate_image_file(filename: str, content: bytes) -> tuple[bool, Optional[str]]:
    """
    Validate image file format and size.

    Args:
        filename: Name of uploaded file
        content: File bytes

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check extension
    if not filename:
        return False, "Filename is required"

    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_IMAGE_FORMATS:
        return False, f"Unsupported image format: {ext}. Supported: {', '.join(SUPPORTED_IMAGE_FORMATS)}"

    # Check file size (10MB limit)
    max_size = 10 * 1024 * 1024  # 10MB
    if len(content) > max_size:
        return False, f"Image too large: {len(content)} bytes (max {max_size} bytes / 10MB)"

    # Check minimum size (100 bytes)
    if len(content) < 100:
        return False, f"Image too small: {len(content)} bytes (min 100 bytes)"

    return True, None


async def run_image_job_analysis(job_id: str, auto_approve: bool = False):
    """
    Background task to analyze image ingestion job and optionally auto-approve.

    Similar to text ingestion but accounts for vision processing costs.

    ADR-014 workflow:
    1. Analyze job (estimates vision + extraction costs)
    2. Update job status → awaiting_approval
    3. If auto_approve, immediately approve and execute
    """
    queue = get_job_queue()
    analyzer = JobAnalyzer()

    try:
        job = queue.get_job(job_id)
        if not job:
            return

        # Get job metadata
        job_data = job.get("job_data", {})

        # Estimate costs
        # - Vision API: ~$0.01 per image (GPT-4o)
        # - Extraction: Standard LLM costs based on prose length
        # For now, use standard analysis (will be enhanced in future)

        # Prepare analysis data
        analysis_data = {
            "ontology": job_data.get("ontology"),
            "content_type": "image",
            "vision_model": job_data.get("vision_model", "gpt-4o"),
            **job_data.get("options", {})
        }

        # Run analysis
        # Note: For images, we don't have the prose yet, so this is a rough estimate
        analysis = {
            "chunks": 1,  # Images are single-chunk
            "estimated_tokens": 2000,  # Rough estimate for vision + extraction
            "estimated_cost": 0.02,  # ~$0.01 vision + ~$0.01 extraction
            "estimated_time_seconds": 10,  # ~5s vision + ~5s extraction
            "content_type": "image"
        }

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
            # Execute immediately (ADR-031: Non-blocking execution)
            queue.execute_job_async(job_id)

    except Exception as e:
        # If analysis fails, mark job as failed
        queue.update_job(job_id, {
            "status": "failed",
            "error": f"Image analysis failed: {str(e)}"
        })


@router.post(
    "/image",
    response_model=JobSubmitResponse | DuplicateJobResponse,
    summary="Submit image for multimodal ingestion (ADR-057)"
)
async def ingest_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Image file to ingest (PNG, JPEG, GIF, WebP, BMP)"),
    ontology: str = Form(..., description="Ontology/collection name"),
    filename: Optional[str] = Form(None, description="Override filename"),
    force: bool = Form(False, description="Force re-ingestion even if duplicate"),
    auto_approve: bool = Form(False, description="Auto-approve job (skip approval step)"),
    processing_mode: str = Form("serial", description="Processing mode: serial or parallel"),
    vision_provider: Optional[str] = Form(None, description="Vision provider: openai (default), anthropic, ollama"),
    vision_model: Optional[str] = Form(None, description="Vision model name (optional, uses provider default)"),
    # ADR-051: Source metadata (optional)
    source_type: Optional[str] = Form(None, description="Source type: file, mcp, api"),
    source_path: Optional[str] = Form(None, description="Full filesystem path (file ingestion only)"),
    source_hostname: Optional[str] = Form(None, description="Hostname where ingestion initiated"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Submit an image for multimodal ingestion using vision AI and visual embeddings.

    **ADR-057 Multimodal Ingestion Pipeline (Hairpin Pattern):**

    1. **Image Upload**: Accept PNG, JPEG, GIF, WebP, BMP (max 10MB)
    2. **Visual Embedding**: Generate 768-dim embedding with Nomic Vision v1.5
    3. **Vision Processing**: Convert image to literal prose with GPT-4o Vision
    4. **Hairpin to Text Pipeline**: Feed prose into existing text upsert
    5. **Concept Extraction**: LLM extracts concepts from prose description
    6. **Semantic Upsert**: Merge/create concepts with relationships

    **Vision Providers (validated in research):**
    - `openai`: GPT-4o Vision (default, recommended) - 100% reliable, ~$0.01/image
    - `anthropic`: Claude 3.5 Sonnet Vision - Similar quality
    - `ollama`: Local Granite/LLaVA - Optional fallback (inconsistent quality)

    **Visual Embeddings:**
    - Nomic Embed Vision v1.5 (768-dim, local via transformers)
    - 0.847 clustering quality (27% better than CLIP)
    - Same vector space as text embeddings

    **Workflow (ADR-014):**
    1. Submit image → Job created with status `pending`
    2. Analysis runs (estimates vision + extraction costs)
    3. Job status → `awaiting_approval` with cost/time estimates
    4. Manual approval via POST /jobs/{job_id}/approve
    5. OR use `auto_approve=true` to skip approval
    6. Processing: vision → prose → concepts
    7. Watch progress via GET /jobs/{job_id}/stream

    **Content Deduplication:**
    - SHA-256 hash of image bytes detects duplicates
    - Same image in same ontology returns existing job_id
    - Use `force=true` to re-process anyway

    **Returns:**
    - New job: `job_id`, status, poll endpoint
    - Duplicate: Existing job_id with `force=true` suggestion

    **Example:**
    ```bash
    curl -X POST http://localhost:8000/api/ingest/image \\
      -F "file=@diagram.png" \\
      -F "ontology=Architecture Docs" \\
      -F "auto_approve=true"
    ```

    **Research Validation:**
    See docs/research/vision-testing/ for comprehensive findings:
    - GPT-4o: 100% reliable literal descriptions
    - Nomic Vision: 0.847 avg top-3 similarity
    - CLIP: 0.666 (27% worse than Nomic)
    """
    from ..lib.age_client import AGEClient

    queue = get_job_queue()
    age_client = AGEClient()
    hasher = ContentHasher(queue, age_client)

    # Read image content
    content = await file.read()

    # Validate image
    is_valid, error_msg = _validate_image_file(file.filename, content)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    logger.info(
        f"Image ingestion request: {file.filename} ({len(content)} bytes) "
        f"→ ontology '{ontology}'"
    )

    # Step 1: Generate visual embedding (Nomic Vision v1.5)
    try:
        logger.info("Generating visual embedding with Nomic Vision v1.5...")
        visual_embedding = generate_visual_embedding(content)
        logger.info(f"Visual embedding generated: 768-dim (hash: {hash(tuple(visual_embedding)) % 10000})")
    except Exception as e:
        logger.error(f"Failed to generate visual embedding: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Visual embedding generation failed: {str(e)}"
        )

    # Step 2: Convert image to prose description (Vision Provider)
    try:
        # Get vision provider (GPT-4o by default)
        provider = get_vision_provider(
            provider=vision_provider,
            model=vision_model
        )

        logger.info(
            f"Converting image to prose with {provider.get_provider_name()} "
            f"({provider.get_model_name()})..."
        )

        # Use literal description prompt (validated in research)
        description_response = provider.describe_image(
            image_bytes=content,
            prompt=LITERAL_DESCRIPTION_PROMPT
        )

        prose_description = description_response["text"]
        vision_tokens = description_response.get("tokens", {})

        logger.info(
            f"Image described: {len(prose_description)} chars, "
            f"{vision_tokens.get('total_tokens', 0)} tokens"
        )

    except Exception as e:
        logger.error(f"Failed to describe image with vision provider: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Image description failed: {str(e)}"
        )

    # Step 3: Store image in MinIO (before job creation to avoid large job payloads)
    try:
        minio_client = get_minio_client()

        # Generate temporary source_id (will be replaced with actual source_id during ingestion)
        import uuid
        temp_source_id = f"src_{uuid.uuid4().hex[:12]}"

        logger.info(f"Uploading image to MinIO: {ontology}/{temp_source_id}...")
        minio_object_key = minio_client.upload_image(
            ontology=ontology,
            source_id=temp_source_id,
            image_bytes=content,
            filename=file.filename,
            metadata={
                "uploaded_by": current_user.username,
                "upload_time": datetime.now().isoformat()
            }
        )
        logger.info(f"Image stored in MinIO: {minio_object_key}")

    except Exception as e:
        logger.error(f"Failed to store image in MinIO: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Image storage failed: {str(e)}"
        )

    # Step 4: Hash content for deduplication (use image bytes, not prose)
    content_hash = hasher.hash_content(content)

    # Check for duplicates
    existing_job = hasher.check_duplicate(content_hash, ontology)

    if existing_job:
        allowed, reason = hasher.should_allow_reingestion(existing_job, force)

        if not allowed:
            # Return duplicate info
            duplicate_info = hasher.get_duplicate_info(existing_job)
            return JSONResponse(
                status_code=200,
                content=duplicate_info
            )

    # Step 5: Prepare job data for hairpin pattern (prose → text pipeline)
    # The prose description will be processed like any text document
    use_filename = filename or file.filename or "uploaded_image"

    # Build options (minimal for images - single chunk)
    options = IngestionOptions(
        target_words=1000,  # Not used for images (single chunk)
        overlap_words=0,  # No chunking for images
    )

    job_data = {
        "content": base64.b64encode(prose_description.encode('utf-8')).decode('utf-8'),  # Store prose, not image
        "content_hash": content_hash,
        "ontology": ontology,
        "filename": use_filename,
        "user_id": current_user.id,  # Track job owner (user ID from kg_auth.users)
        "processing_mode": processing_mode,
        "options": {
            "target_words": options.target_words,
            "min_words": options.get_min_words(),
            "max_words": options.get_max_words(),
            "overlap_words": options.overlap_words
        },
        # ADR-051: Source metadata (optional, best-effort provenance)
        "source_type": source_type or "api",
        "source_path": source_path,
        "source_hostname": source_hostname,
        # Image-specific metadata (stored in job_data for tracking)
        "content_type": "image",  # Mark as image for tracking
        "original_filename": file.filename,
        "minio_object_key": minio_object_key,  # MinIO path for retrieval
        "visual_embedding": visual_embedding,  # Already a list from generate_visual_embedding()
        "vision_metadata": {
            "provider": provider.get_provider_name(),
            "model": provider.get_model_name(),
            "vision_tokens": vision_tokens,
            "visual_embedding_model": "nomic-ai/nomic-embed-vision-v1.5",
            "visual_embedding_dimension": 768,
            "prose_length": len(prose_description)
        }
    }

    # Create job
    job_id = queue.enqueue(
        "ingest_image",  # Job type matches worker registration
        job_data
    )

    # Run analysis in background
    background_tasks.add_task(run_image_job_analysis, job_id, auto_approve)

    return JobSubmitResponse(
        job_id=job_id,
        status="pending (analyzing)",
        content_hash=content_hash,
        message=f"Image job queued. Analysis running. Poll /jobs/{job_id} for status."
    )


@router.get(
    "/image/health",
    summary="Check visual embedding system health"
)
async def check_image_ingestion_health():
    """
    Health check for multimodal image ingestion system.

    Checks:
    - Visual embedding generation (Nomic Vision v1.5)
    - VRAM availability (GPU vs CPU)
    - Model loading status

    Returns:
    - Status: healthy or unhealthy
    - Model info, device, VRAM stats
    - Error details if unhealthy
    """
    health = check_visual_embedding_health()

    if health['status'] == 'unhealthy':
        raise HTTPException(
            status_code=503,
            detail=f"Visual embedding system unhealthy: {health.get('error')}"
        )

    return JSONResponse(
        status_code=200,
        content={
            "status": "healthy",
            "visual_embeddings": health,
            "vision_providers": {
                "available": ["openai", "anthropic", "ollama"],
                "default": "openai",
                "note": "Research validated GPT-4o as primary (100% reliable)"
            }
        }
    )
