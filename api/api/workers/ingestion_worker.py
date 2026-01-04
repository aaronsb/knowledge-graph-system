"""
Async ingestion worker.

Wraps the existing chunked ingestion pipeline to run as a background job,
reporting progress back to the job queue.
"""

import os
import logging
import tempfile
import base64
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

from api.api.lib.chunker import SmartChunker, ChunkingConfig
from api.api.lib.markdown_preprocessor import MarkdownPreprocessor
from api.api.lib.checkpoint import IngestionCheckpoint
from api.api.lib.age_client import AGEClient
from api.api.lib.ingestion import ChunkedIngestionStats, process_chunk
from api.api.lib.ai_providers import get_provider

logger = logging.getLogger(__name__)


def run_ingestion_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Execute document ingestion as a background job.

    Handles both text and image ingestion:
    - Text jobs: content field contains text bytes
    - Image jobs: image_bytes field contains raw image, worker generates prose

    Args:
        job_data: Job parameters
            - content: bytes - Document content (text jobs)
            OR
            - image_bytes: bytes - Raw image content (image jobs)
            - ontology: str - Ontology name
            - options: dict - Chunking config
            - filename: str (optional) - Original filename
        job_id: Job ID for progress tracking
        job_queue: Queue instance for progress updates

    Returns:
        Result dict with stats and cost info

    Raises:
        Exception: If ingestion fails
    """
    ontology = job_data["ontology"]
    options = job_data.get("options", {})

    # Check if this is an image job (ADR-057)
    is_image_job = "image_bytes" in job_data

    if is_image_job:
        logger.info(f"Processing image job {job_id}...")

        # Decode image bytes
        image_b64 = job_data["image_bytes"]
        image_bytes = base64.b64decode(image_b64)

        # Step 1: Generate visual embedding (Nomic Vision v1.5)
        logger.info("Generating visual embedding with Nomic Vision v1.5...")
        from api.api.lib.visual_embeddings import generate_visual_embedding
        try:
            visual_embedding = generate_visual_embedding(image_bytes)
            logger.info(f"Visual embedding generated: 768-dim")
        except Exception as e:
            logger.error(f"Failed to generate visual embedding: {e}")
            raise Exception(f"Visual embedding generation failed: {str(e)}")

        # Step 2: Convert image to prose description (Vision Provider)
        logger.info("Converting image to prose with vision AI...")
        from api.api.lib.vision_providers import get_vision_provider, LITERAL_DESCRIPTION_PROMPT
        try:
            vision_provider_name = job_data.get("vision_provider", "openai")
            vision_model_name = job_data.get("vision_model")

            vision_provider = get_vision_provider(
                provider=vision_provider_name,
                model=vision_model_name
            )

            description_response = vision_provider.describe_image(
                image_bytes=image_bytes,
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
            raise Exception(f"Image description failed: {str(e)}")

        # Step 3: Upload image to Garage
        logger.info("Uploading image to Garage...")
        from api.api.lib.garage_client import get_garage_client
        from api.api.lib.datetime_utils import timedelta_from_now, to_iso
        import uuid

        try:
            garage_client = get_garage_client()

            # Generate temporary source_id (will be replaced with actual source_id during graph upsert)
            temp_source_id = f"src_{uuid.uuid4().hex[:12]}"

            storage_key = garage_client.upload_image(
                ontology=ontology,
                source_id=temp_source_id,
                image_bytes=image_bytes,
                filename=job_data.get("original_filename", "image"),
                metadata={
                    "uploaded_by": job_data.get("uploaded_by", "system"),
                    "upload_time": to_iso(timedelta_from_now()),
                    "job_id": job_id
                }
            )
            logger.info(f"Image stored in Garage: {storage_key}")
        except Exception as e:
            logger.error(f"Failed to store image in Garage: {e}")
            raise Exception(f"Image storage failed: {str(e)}")

        # Step 4: Store image metadata in job_data for graph upsert
        job_data["storage_key"] = storage_key
        job_data["visual_embedding"] = visual_embedding
        job_data["vision_metadata"] = {
            "provider": vision_provider.get_provider_name(),
            "model": vision_provider.get_model_name(),
            "vision_tokens": vision_tokens,
            "visual_embedding_model": "nomic-ai/nomic-embed-vision-v1.5",
            "visual_embedding_dimension": 768,
            "prose_length": len(prose_description)
        }

        # Convert prose to bytes for text ingestion pipeline
        content = prose_description.encode('utf-8')
        logger.info(f"Image processing complete, proceeding with text ingestion of {len(content)} byte prose description")
    else:
        # Text job: decode base64-encoded content
        content_b64 = job_data["content"]
        content = base64.b64decode(content_b64)
    filename = job_data.get("filename", f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

    # ADR-081: Pre-ingestion source document storage
    # Store document in Garage BEFORE chunking for:
    # - Model evolution insurance (re-extract with future LLMs)
    # - FUSE filesystem support (ADR-069)
    # - Bidirectional recovery capability
    if not is_image_job:
        # ADR-081: Pre-ingestion Garage storage is REQUIRED
        # If Garage fails, something is fundamentally wrong with the platform.
        # Fail fast to alert the operator rather than silently degrading.
        from api.api.lib.garage import get_source_storage, SourceMetadata
        source_storage = get_source_storage()

        # Determine file extension from filename
        ext = Path(filename).suffix.lstrip('.') or 'txt'

        # Reuse hash from dedup check (already computed by ContentHasher)
        # This avoids recomputing SHA-256 and ensures format consistency
        existing_hash = job_data.get("content_hash")

        # Build rich metadata for FUSE filesystem support
        source_metadata = SourceMetadata(
            user_id=job_data.get("user_id"),
            username=job_data.get("username"),
            source_type=job_data.get("source_type"),
            file_path=job_data.get("source_path"),
            source_url=job_data.get("source_url"),  # For URL ingestion
            hostname=job_data.get("source_hostname"),
            ingested_at=datetime.utcnow().isoformat() + "Z"
        )

        # Store document and get content-addressed identity
        doc_identity = source_storage.store(
            content=content,
            ontology=ontology,
            original_filename=filename,
            extension=ext,
            precomputed_hash=existing_hash,
            source_metadata=source_metadata
        )

        # Save for Source node association during chunk processing
        # Note: doc_identity.content_hash is raw format (no "sha256:" prefix)
        job_data["source_garage_key"] = doc_identity.garage_key
        job_data["source_content_hash"] = doc_identity.content_hash

        logger.info(f"📦 Stored source document in Garage: {doc_identity.garage_key} ({doc_identity.size_bytes} bytes)")

    # Extract options
    target_words = options.get("target_words", 1000)
    min_words = options.get("min_words", int(target_words * 0.8))
    max_words = options.get("max_words", int(target_words * 1.5))
    overlap_words = options.get("overlap_words", 200)

    # Get AI provider for cost calculation and translation
    try:
        provider = get_provider()
        extraction_model = provider.get_extraction_model()
        embedding_model = provider.get_embedding_model()
    except Exception as e:
        logger.warning(f"⚠️  Failed to get AI provider: {e}")
        provider = None
        extraction_model = None
        embedding_model = None

    # Write content to temp file
    with tempfile.NamedTemporaryFile(
        mode='wb',
        suffix='.txt',
        delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Load text
        with open(tmp_path, 'r', encoding='utf-8') as f:
            full_text = f.read()

        # Route to appropriate chunker based on file type
        is_markdown = filename.lower().endswith('.md')

        if is_markdown:
            # Markdown: Use semantic AST-based chunking with code block translation
            logger.info(f"📝 Using markdown preprocessor (semantic AST chunking)")
            preprocessor = MarkdownPreprocessor(max_workers=3, ai_provider=provider)
            chunks = preprocessor.preprocess_to_chunks(
                full_text,
                target_words=target_words,
                min_words=min_words,
                max_words=max_words
            )
        else:
            # Plain text: Use legacy word-based chunker
            logger.info(f"📄 Using legacy chunker (word-based boundaries)")
            config = ChunkingConfig(
                target_words=target_words,
                min_words=min_words,
                max_words=max_words,
                overlap_words=overlap_words
            )
            chunker = SmartChunker(config)
            chunks = chunker.chunk_text(full_text, start_position=0)

        if not chunks:
            return {
                "status": "completed",
                "message": "No chunks to process",
                "stats": {}
            }

        # Check for resume: if job was interrupted, job_data may have chunks and resume point
        resume_from_chunk = job_data.get("resume_from_chunk", 0)
        is_resuming = resume_from_chunk > 0

        if is_resuming:
            logger.info(f"🔄 Resuming job from chunk {resume_from_chunk + 1}/{len(chunks)}")
            # Load saved stats from previous run
            saved_stats = job_data.get("stats", {})
            stats = ChunkedIngestionStats()
            stats.concepts_created = saved_stats.get("concepts_created", 0)
            stats.concepts_linked = saved_stats.get("concepts_linked", 0)
            stats.sources_created = saved_stats.get("sources_created", 0)
            stats.instances_created = saved_stats.get("instances_created", 0)
            stats.relationships_created = saved_stats.get("relationships_created", 0)
            stats.llm_calls = saved_stats.get("llm_calls", 0)
            stats.embedding_calls = saved_stats.get("embedding_calls", 0)
            recent_concept_ids = job_data.get("recent_concept_ids", [])
        else:
            logger.info(f"📊 Starting fresh ingestion: {len(chunks)} chunks")
            # Initialize stats
            stats = ChunkedIngestionStats()
            recent_concept_ids = []

        # Update progress: chunking complete (or resuming)
        job_queue.update_job(job_id, {
            "progress": {
                "stage": "chunking_complete" if not is_resuming else "resuming",
                "chunks_total": len(chunks),
                "chunks_processed": resume_from_chunk,
                "percent": int((resume_from_chunk / len(chunks)) * 100) if is_resuming else 0,
                "resume_from_chunk": resume_from_chunk
            }
        })

        # Initialize AGE client
        age_client = AGEClient()

        # Get existing concepts for context
        existing_concepts, has_empty_warnings = age_client.get_document_concepts(
            document_name=ontology,
            recent_chunks_only=3,  # Last 3 chunks for context
            warn_on_empty=True  # Let warnings flow through to logs
        )

        # Log database state (empty is fine - just informational)
        if len(existing_concepts) == 0:
            logger.info(f"ℹ️  Starting with empty database (first ingestion for '{ontology}') - all concepts will be new")
        else:
            logger.info(f"ℹ️  Found {len(existing_concepts)} existing concepts in '{ontology}' for context")

        # Process each chunk (resume from checkpoint if needed)
        for i, chunk in enumerate(chunks, 1):
            # Skip already-processed chunks on resume
            if i <= resume_from_chunk:
                logger.debug(f"⏭️  Skipping chunk {i} (already processed)")
                continue

            # Process chunk
            recent_concept_ids = process_chunk(
                chunk=chunk,
                ontology_name=ontology,
                filename=filename,
                file_path=tmp_path,
                age_client=age_client,
                stats=stats,
                existing_concepts=existing_concepts,
                recent_concept_ids=recent_concept_ids,
                verbose=False,  # Suppress detailed output in background
                # ADR-051: Pass provenance metadata for edge tracking
                job_id=job_id,
                document_id=job_data["content_hash"],
                user_id=job_data.get("user_id"),
                # ADR-057: Pass image metadata for multimodal sources
                content_type=job_data.get("content_type", "document"),
                storage_key=job_data.get("storage_key"),
                visual_embedding=job_data.get("visual_embedding"),
                text_embedding=None,  # Will be generated during concept extraction
                # ADR-081: Pass source document storage metadata
                garage_key=job_data.get("source_garage_key"),
                content_hash=job_data.get("source_content_hash")
            )

            # Update progress with detailed stats AND save resume checkpoint
            percent = int((i / len(chunks)) * 100)
            job_queue.update_job(job_id, {
                "progress": {
                    "stage": "processing",
                    "chunks_total": len(chunks),
                    "chunks_processed": i,
                    "percent": percent,
                    "current_chunk": i,
                    "resume_from_chunk": i,  # Save checkpoint after each chunk
                    "concepts_created": stats.concepts_created,
                    "concepts_linked": stats.concepts_linked,  # Hit rate: existing concepts reused
                    "sources_created": stats.sources_created,
                    "instances_created": stats.instances_created,
                    "relationships_created": stats.relationships_created
                },
                # Save stats and context for resume
                "job_data": {
                    **job_data,
                    "resume_from_chunk": i,
                    "stats": stats.to_dict(),
                    "recent_concept_ids": recent_concept_ids[-50:]  # Keep last 50 for context
                }
            })

        # ADR-051: Create DocumentMeta node after successful ingestion
        # This makes the graph the source of truth for deduplication,
        # preventing job deletion from breaking duplicate detection
        try:
            # Reconstruct source_ids using document_id pattern (ADR-051)
            # Must match pattern in ingestion.py: {document_id[:12]}_chunk{n}
            document_id = job_data["content_hash"]
            source_ids = [
                f"{document_id[:12]}_chunk{i}"
                for i in range(1, len(chunks) + 1)
            ]

            # Create DocumentMeta node and link to all Source nodes
            age_client.create_document_meta(
                document_id=job_data["content_hash"],  # Hash-based ID
                content_hash=job_data["content_hash"],
                ontology=ontology,
                source_count=stats.sources_created,
                ingested_by=job_data.get("user_id", "unknown"),
                job_id=job_id,
                filename=filename,
                source_type=job_data.get("source_type"),       # "file" | "stdin" | "mcp" | "api"
                file_path=job_data.get("source_path"),         # Full path (not tmp_path)
                hostname=job_data.get("source_hostname"),      # Hostname where ingested
                source_ids=source_ids,
                # ADR-081: Link to source document in Garage
                garage_key=job_data.get("source_garage_key")
            )
            logger.info(f"✓ Created DocumentMeta node: {job_data['content_hash'][:16]}... ({stats.sources_created} sources)")
        except Exception as e:
            # Log but don't fail the job - graph metadata is nice-to-have
            logger.warning(f"Failed to create DocumentMeta node: {e}")
            # Job still succeeds - metadata creation failure shouldn't kill the ingestion

        # Sync any new vocabulary types (ADR-077)
        # Edge types may be used in the graph during ingestion but not registered
        # in the vocabulary table. This ensures all types are registered.
        try:
            sync_result = age_client.sync_missing_edge_types(dry_run=False)
            if sync_result['synced']:
                logger.info(f"✓ Synced {len(sync_result['synced'])} new vocabulary types")
        except Exception as e:
            # Non-fatal - log but don't fail the job
            logger.warning(f"Failed to sync vocabulary: {e}")

        # Refresh graph metrics after ingestion (ADR-079: cache invalidation)
        # This updates the counters used for projection cache invalidation
        try:
            conn = age_client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT refresh_graph_metrics()")
                conn.commit()
                logger.debug(f"[{job_id}] Refreshed graph metrics after ingestion")
            finally:
                age_client.pool.putconn(conn)
        except Exception as e:
            logger.warning(f"[{job_id}] Failed to refresh graph metrics: {e}")

        # Close AGE connection
        age_client.close()

        # Calculate costs
        extraction_cost = stats.calculate_extraction_cost(extraction_model)
        embedding_cost = stats.calculate_embedding_cost(embedding_model)
        total_cost = extraction_cost + embedding_cost

        # Return results
        return {
            "status": "completed",
            "stats": stats.to_dict(),
            "cost": {
                "extraction": f"${extraction_cost:.2f}",
                "embeddings": f"${embedding_cost:.2f}",
                "total": f"${total_cost:.2f}",
                "extraction_model": extraction_model,
                "embedding_model": embedding_model
            },
            "ontology": ontology,
            "filename": filename,
            "chunks_processed": len(chunks)
        }

    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except:
            pass
