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

from api.app.lib.chunker import SmartChunker, ChunkingConfig
from api.app.lib.markdown_preprocessor import MarkdownPreprocessor
from api.app.lib.checkpoint import IngestionCheckpoint
from api.app.lib.age_client import AGEClient
from api.app.lib.ingestion import ChunkedIngestionStats, process_chunk
from api.app.lib.ai_providers import get_provider

logger = logging.getLogger(__name__)


# Distinct error strings so the job-list API can show, and tests / clients
# can match, the three structurally different failure modes (#402 B1 + B2):
#   * tombstoned    → operator deliberately removed, do not recreate
#   * frozen        → exists but read-only
#   * vanished      → existed at submit, missing at execute, no tombstone:
#                     A-veto + executor re-check should make this unreachable
#                     under normal operation, so reaching it indicates a real
#                     anomaly worth surfacing rather than silently recreating.
ONTOLOGY_VANISHED_MID_FLIGHT_ERROR = (
    "target ontology '{name}' existed at job submit but was missing at "
    "execute, with no operator tombstone — annealing veto + proposal "
    "re-check should make this unreachable, so the anomaly is surfaced "
    "rather than silently recreated. Job not retried."
)
ONTOLOGY_FROZEN_ERROR = (
    "Ontology '{name}' is frozen (read-only). Job rejected. "
    "Set lifecycle state to 'active' before ingesting."
)
ONTOLOGY_TOMBSTONED_ERROR = (
    "target ontology '{name}' was deliberately removed by an operator "
    "(tombstone present in kg_api.ontology_tombstones) — ingest job not "
    "retried. Remove the tombstone explicitly to re-enable this name."
)


def _ontology_tombstone(age_client, name: str):
    """Return the tombstone row for `name` or None if no tombstone exists.

    The tombstone is the positive operator-intent signal that distinguishes
    "deliberately removed by an operator" from "dissolved by background
    annealing" (#402 Defect B2). Read-only — the operator-delete and
    operator-dissolve routes write; the create-ontology route clears;
    nothing else touches it.

    On DB read failure, returns None (treat as "no tombstone"). Combined
    with the post-PR-404 layered defense, this fallback is still
    acceptable:

      * existed_at_submit=True + missing target: the worker raises
        ONTOLOGY_VANISHED_MID_FLIGHT_ERROR before consulting the
        tombstone-failed result for recreation — the operator-deleted
        case still fails loudly, just with a slightly less specific
        error string than TOMBSTONED.
      * existed_at_submit=False + missing target: first-ever ingest into
        a new name, recreate is correct. A residual risk exists if the
        operator deleted the name *before* the ingest was submitted AND
        the tombstone-read fails — in that narrow case the worker
        silently recreates. The alternative (fail every first ingest
        when the tombstone table is unreachable) is a worse operational
        hazard.
    """
    try:
        conn = age_client.pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT name, removed_at, removed_by, reason "
                    "FROM kg_api.ontology_tombstones "
                    "WHERE name = %s",
                    (name,),
                )
                row = cur.fetchone()
            conn.commit()
            if not row:
                return None
            return {
                "name": row[0],
                "removed_at": row[1],
                "removed_by": row[2],
                "reason": row[3],
            }
        finally:
            age_client.pool.putconn(conn)
    except Exception as e:
        logger.error(
            f"Failed to read ontology tombstone for '{name}': {e}",
            exc_info=True,
        )
        return None


def _validate_target_ontology(
    age_client,
    ontology: str,
    existed_at_submit: bool,
    created_by: str = None,
    job_id: str = None,
):
    """Resolve the ingestion target's Ontology node, failing loudly when
    the operator's intent has been deliberately countermanded (#402 B1+B2).

    Returns the ontology node dict on success. Raises Exception when:

    - Tombstone present (operator deliberately removed the ontology) →
      ONTOLOGY_TOMBSTONED_ERROR. Checked unconditionally (before reading
      the graph node) so the operator-delete route can write the tombstone
      *before* the graph delete; a worker dequeuing in the window where
      both the node and the tombstone exist still fails loudly instead of
      writing orphan content into a graph the operator is removing.
    - Frozen lifecycle → ONTOLOGY_FROZEN_ERROR.
    - Existed at submit + missing at execute + no tombstone →
      ONTOLOGY_VANISHED_MID_FLIGHT_ERROR. With Defect A's queue veto and
      the proposal-executor re-check in place, an annealing dissolve of a
      queued target should not occur; reaching this branch indicates a
      real anomaly (rename without job migration, manual graph surgery,
      or a residual race window) that operators should see.

    When the ontology is missing, no tombstone is present, AND the
    ontology did NOT exist at submit (first-ever ingest into a new
    name), the worker creates the ontology and proceeds, with an
    auditable log line naming the job and the actor.
    """
    tombstone = _ontology_tombstone(age_client, ontology)
    if tombstone:
        logger.warning(
            f"Ingest job blocked by tombstone for '{ontology}' "
            f"(removed_at={tombstone['removed_at']}, "
            f"removed_by={tombstone['removed_by']}, "
            f"reason={tombstone['reason']})"
        )
        raise Exception(ONTOLOGY_TOMBSTONED_ERROR.format(name=ontology))

    ont_node = age_client.get_ontology_node(ontology)

    if ont_node is None:
        if existed_at_submit:
            raise Exception(
                ONTOLOGY_VANISHED_MID_FLIGHT_ERROR.format(name=ontology)
            )

        # First-ever ingest into a brand-new name (existed_at_submit=False):
        # creating the ontology IS the operator's intent. Audit-log the
        # event with job + actor for traceability.
        ont_node = age_client.ensure_ontology_exists(
            ontology, created_by=created_by
        )
        logger.info(
            f"Ontology '{ontology}' created for ingest job "
            f"job_id={job_id} actor={created_by} "
            f"existed_at_submit={existed_at_submit}"
        )

    if ont_node.get("lifecycle_state") == "frozen":
        raise Exception(ONTOLOGY_FROZEN_ERROR.format(name=ontology))

    return ont_node


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

        # Step 1: Generate visual embedding from active profile
        from api.app.lib.visual_embeddings import get_visual_embedding_generator, generate_visual_embedding
        vis_gen = get_visual_embedding_generator()
        logger.info(f"Generating visual embedding with {vis_gen.get_model_name()}...")
        try:
            visual_embedding = generate_visual_embedding(image_bytes)
            logger.info(f"Visual embedding generated: {len(visual_embedding)}-dim")
        except Exception as e:
            logger.error(f"Failed to generate visual embedding: {e}")
            raise Exception(f"Visual embedding generation failed: {str(e)}")

        # Step 2: Convert image to prose description (ADR-057 literal path).
        #
        # The vision capability slot resolves INDEPENDENTLY of extraction
        # (ADR-802 §2 / #378): resolve_vision_selection picks the provider/model
        # (per-job override → active vision config → vision-capable extraction
        # default → fail loud), then we build that provider and call the unified
        # describe_image. We deliberately do NOT call get_provider() bare —
        # that returns the *extraction* provider and would re-slave vision to
        # extraction. The explicit args reproduce the research-validated literal
        # settings: LITERAL prompt, detail=None (OpenAI "auto"), temperature 0.1.
        logger.info("Converting image to prose with vision AI...")
        # NOTE: get_provider is already imported at module level (top of file).
        # Do NOT re-import it locally here — a function-local `from ... import
        # get_provider` would make get_provider a local for the WHOLE function,
        # so the text-extraction path's get_provider() call (later in this same
        # function) would hit UnboundLocalError on non-image code paths.
        from api.app.lib.vision_providers import resolve_vision_selection, LITERAL_DESCRIPTION_PROMPT
        try:
            vision_provider_name, vision_model_name = resolve_vision_selection(
                provider=job_data.get("vision_provider"),
                model=job_data.get("vision_model"),
            )

            vision_provider = get_provider(vision_provider_name)
            description_response = vision_provider.describe_image(
                image_bytes,
                LITERAL_DESCRIPTION_PROMPT,
                model=vision_model_name,
                detail=None,
                temperature=0.1,
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
        from api.app.lib.garage import get_image_storage
        from api.app.lib.datetime_utils import timedelta_from_now, to_iso
        import uuid

        try:
            images = get_image_storage()

            # Generate temporary source_id (will be replaced with actual source_id during graph upsert)
            temp_source_id = f"src_{uuid.uuid4().hex[:12]}"

            storage_key = images.upload(
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
        # Read image model info from the visual embedding generator (profile-driven)
        from api.app.lib.visual_embeddings import get_visual_embedding_generator
        try:
            vis_gen = get_visual_embedding_generator()
            visual_model_name = vis_gen.get_model_name()
            visual_model_dim = vis_gen.get_embedding_dimension()
        except Exception:
            visual_model_name = "unknown"
            visual_model_dim = len(visual_embedding) if visual_embedding else 768

        job_data["storage_key"] = storage_key
        job_data["visual_embedding"] = visual_embedding
        job_data["vision_metadata"] = {
            # Record the provider/model that actually performed image->prose,
            # straight from the describe_image response (#457). The collapsed
            # AIProvider has no get_model_name(), and its get_provider_name()
            # is capitalized; the response carries the real lowercase provider
            # + resolved vision model, which is what we want stored.
            "provider": description_response.get("provider"),
            "model": description_response.get("model"),
            "vision_tokens": vision_tokens,
            "visual_embedding_model": visual_model_name,
            "visual_embedding_dimension": visual_model_dim,
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
        from api.app.lib.garage import get_source_storage, SourceMetadata
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

    # ADR-207/#384: the epoch event recorded mid-run (below) must be resolved on
    # every exit path — success, cancel, or failure — or it stays in_progress
    # and holds the committed watermark (kg_api.get_committed_epoch()) behind a
    # phantom in-flight job, freezing freshness for every derivation.
    event_id = None
    age_client = None
    epoch_resolved = False

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

        ont_node = _validate_target_ontology(
            age_client,
            ontology,
            existed_at_submit=job_data.get("ontology_existed_at_submit", True),
            created_by=job_data.get("username"),
            job_id=job_id,
        )

        # Generate embedding for ontology node if missing (best-effort).
        if not ont_node.get("embedding") and provider:
            try:
                ont_text = ontology
                desc = ont_node.get("description")
                if desc:
                    ont_text = f"{ontology}: {desc}"
                emb_result = provider.generate_embedding(ont_text)
                emb_vector = emb_result if isinstance(emb_result, list) else emb_result.get("embedding", [])
                if emb_vector:
                    age_client.update_ontology_embedding(ontology, emb_vector)
                    logger.info(f"Generated embedding for Ontology '{ontology}'")
            except Exception as e:
                logger.debug(f"Skipped ontology embedding: {e}")

        # ADR-203: Record this ingestion as a graph epoch event so every
        # Instance created during the run carries a stable event_id. On resume,
        # a fresh event is recorded with resume metadata — honest record that
        # the work spanned multiple sessions.
        epoch_metadata = {
            "job_id": job_id,
            "ontology": ontology,
        }
        if is_resuming:
            epoch_metadata["resumed_from_chunk"] = resume_from_chunk
        event_id = age_client.record_epoch(
            kind="ingestion",
            actor=job_data.get("user_id") or job_data.get("username"),
            metadata=epoch_metadata,
        )
        if event_id is not None:
            logger.info(f"📍 Recorded graph epoch event_id={event_id} for this ingestion")
        else:
            logger.warning("⚠️  record_epoch returned None — Instances will be untagged")

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

            # ADR-100: Check for cancellation at chunk boundary
            if job_queue.is_job_cancelled(job_id):
                logger.info(f"Job {job_id} cancelled at chunk {i}/{len(chunks)}")
                # ADR-207: resolve the epoch (counts toward the watermark either
                # way — partial per-chunk commits are real graph changes).
                age_client.complete_epoch(event_id, "failed")
                epoch_resolved = True
                return {
                    "status": "cancelled",
                    "chunks_processed": i - 1,
                    "chunks_total": len(chunks),
                    "stats": stats.to_dict()
                }

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
                content_hash=job_data.get("source_content_hash"),
                # ADR-203: Tag Instances created during this chunk with the job's epoch
                event_id=event_id,
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
                garage_key=job_data.get("source_garage_key"),
                content_type=job_data.get("content_type", "document"),
                # ADR-057: Image binary location in Garage
                storage_key=job_data.get("storage_key"),
            )
            logger.info(f"✓ Created DocumentMeta node: {job_data['content_hash'][:16]}... ({stats.sources_created} sources)")
        except Exception as e:
            # Log but don't fail the job - graph metadata is nice-to-have
            logger.warning(f"Failed to create DocumentMeta node: {e}")
            # Job still succeeds - metadata creation failure shouldn't kill the ingestion

        # ADR-200: Create SCOPED_BY edges from Source nodes to Ontology node
        # TODO(ADR-200 Phase 4): This is N+1 — one DB round-trip per source.
        # Batch into a single Cypher query when implementing batch reassignment.
        try:
            scoped_count = 0
            for sid in source_ids:
                if age_client.create_scoped_by_edge(sid, ontology):
                    scoped_count += 1
            if scoped_count > 0:
                logger.info(f"✓ Created {scoped_count} SCOPED_BY edges → '{ontology}'")
        except Exception as e:
            logger.warning(f"Failed to create SCOPED_BY edges: {e}")
            # Non-fatal: s.document on Source nodes still provides ontology membership

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

        # Increment document ingestion epoch (ADR-200: annealing lifecycle)
        try:
            conn = age_client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT increment_counter('document_ingestion_counter')")
                conn.commit()
                logger.debug(f"[{job_id}] Incremented document ingestion epoch")
            finally:
                age_client.pool.putconn(conn)
        except Exception as e:
            logger.warning(f"[{job_id}] Failed to increment ingestion epoch: {e}")

        # ADR-200 Phase 3b: Check if annealing cycle should run
        # Launcher self-manages epoch interval — just ask it to check
        try:
            from api.app.launchers.annealing import AnnealingLauncher
            from api.app.services.job_queue import get_job_queue
            annealing_job_id = AnnealingLauncher(get_job_queue()).launch()
            if annealing_job_id:
                logger.info(f"[{job_id}] Annealing cycle launched: {annealing_job_id}")
        except Exception as e:
            logger.warning(f"[{job_id}] Annealing launcher check failed: {e}")

        # ADR-207: graph mutations for this ingestion are committed — resolve
        # the epoch so the committed watermark advances past it. Done before
        # close()/cost-calc so the connection pool is still open.
        age_client.complete_epoch(event_id, "completed")
        epoch_resolved = True

        # ADR-201: Invalidate graph_accel cache after graph mutations
        try:
            age_client.graph.invalidate()
        except Exception:
            pass  # Non-fatal — extension may not be installed

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

    except Exception:
        # ADR-207: a crashed run must resolve its epoch as failed so it stops
        # holding the committed watermark behind a phantom in-flight event.
        # (Failed still counts toward the watermark — partial commits are real.)
        if age_client is not None and not epoch_resolved:
            age_client.complete_epoch(event_id, "failed")
        raise

    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except:
            pass
