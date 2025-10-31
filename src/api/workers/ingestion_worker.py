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

from src.api.lib.chunker import SmartChunker, ChunkingConfig
from src.api.lib.markdown_preprocessor import MarkdownPreprocessor
from src.api.lib.checkpoint import IngestionCheckpoint
from src.api.lib.age_client import AGEClient
from src.api.lib.ingestion import ChunkedIngestionStats, process_chunk
from src.api.lib.ai_providers import get_provider

logger = logging.getLogger(__name__)


def run_ingestion_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Execute document ingestion as a background job.

    Args:
        job_data: Job parameters
            - content: bytes - Document content
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
    # Decode base64-encoded content
    content_b64 = job_data["content"]
    content = base64.b64decode(content_b64)

    ontology = job_data["ontology"]
    options = job_data.get("options", {})
    filename = job_data.get("filename", f"upload_{datetime.now().strftime('%Y%m%d_%H%M%S')}")

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
                user_id=job_data.get("user_id")
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
            # Reconstruct source_ids (deterministic pattern from process_chunk)
            source_ids = [
                f"{filename.replace(' ', '_').lower()}_chunk{i}"
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
                source_ids=source_ids
            )
            logger.info(f"✓ Created DocumentMeta node: {job_data['content_hash'][:16]}... ({stats.sources_created} sources)")
        except Exception as e:
            # Log but don't fail the job - graph metadata is nice-to-have
            logger.warning(f"Failed to create DocumentMeta node: {e}")
            # Job still succeeds - metadata creation failure shouldn't kill the ingestion

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
