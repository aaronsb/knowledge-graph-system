"""
Source Embedding Worker (ADR-068 Phase 2).

Generates embeddings for source text chunks with offset tracking and hash verification.

Two usage patterns:
1. **Synchronous (ingestion)**: Call generate_source_embeddings() directly
2. **Async (regeneration)**: Dispatch job, run_source_embedding_worker() processes it

Phase 1: ✅ Skeleton (migration, hash utils, chunker, worker skeleton)
Phase 2: ✅ Full implementation with embedding generation and storage
"""

import logging
import os
import struct
from typing import Dict, Any, Optional

import psycopg2
import numpy as np

from api.api.lib.hash_utils import sha256_text
from api.api.lib.source_chunker import get_chunking_strategy
from api.api.lib.embedding_config import load_active_embedding_config
from api.api.services.embedding_worker import get_embedding_worker
from api.api.lib.age_client import AGEClient

logger = logging.getLogger(__name__)


def run_source_embedding_worker(
    job_data: Dict[str, Any],
    job_id: str,
    job_queue
) -> Dict[str, Any]:
    """
    Generate embeddings for source text chunks as a background job.

    Args:
        job_data: Job parameters
            - source_id: str - Source node ID to generate embeddings for
            - ontology: str - Ontology name (for context)
            - chunk_strategy: str - Chunking strategy ('sentence', 'paragraph', 'count')
            - max_chars: int - Maximum characters per chunk (default: 500)
            - regenerate: bool - Force regeneration even if embeddings exist (default: False)
        job_id: Job ID for progress tracking
        job_queue: Queue instance for progress updates

    Returns:
        Result dict with generation stats:
            - success: bool
            - source_id: str
            - chunks_created: int
            - embedding_model: str
            - embedding_dimension: int
            - total_chars: int
            - chunk_strategy: str

    Raises:
        Exception: If embedding generation fails
    """
    try:
        logger.info(f"📝 Source embedding worker started: {job_id}")

        # Update progress
        job_queue.update_job(job_id, {
            "status": "processing",
            "progress": {
                "stage": "initializing",
                "message": "Source embedding worker started"
            }
        })

        # Extract parameters
        source_id = job_data.get("source_id")
        if not source_id:
            raise ValueError("source_id is required in job_data")

        ontology = job_data.get("ontology", "unknown")
        chunk_strategy = job_data.get("chunk_strategy", "sentence")
        max_chars = job_data.get("max_chars", 500)
        regenerate = job_data.get("regenerate", False)

        # Validate parameters
        valid_strategies = {"sentence", "paragraph", "count", "semantic"}
        if chunk_strategy not in valid_strategies:
            raise ValueError(
                f"Invalid chunk_strategy '{chunk_strategy}'. "
                f"Valid strategies: {', '.join(sorted(valid_strategies))}"
            )

        if not isinstance(max_chars, int) or max_chars <= 0:
            raise ValueError(f"max_chars must be positive integer, got {max_chars}")

        if max_chars > 10000:
            logger.warning(
                f"max_chars ({max_chars}) is very large. "
                f"Recommended range: 100-1000 characters"
            )

        logger.info(
            f"Source embedding params: source_id={source_id}, "
            f"strategy={chunk_strategy}, max_chars={max_chars}, "
            f"regenerate={regenerate}"
        )

        # Load active embedding configuration
        # This ensures source embeddings use same dimensions as concept embeddings
        embedding_config = load_active_embedding_config()

        if not embedding_config:
            raise RuntimeError(
                "No active embedding configuration found. "
                "Configure embeddings via: docker exec kg-operator python /workspace/operator/configure.py embedding"
            )

        embedding_model = embedding_config.get("model_name")
        embedding_dimension = embedding_config.get("embedding_dimensions")
        embedding_provider = embedding_config.get("provider")

        logger.info(
            f"Using embedding config: model={embedding_model}, "
            f"dimensions={embedding_dimension}, provider={embedding_provider}"
        )

        # Update progress
        job_queue.update_job(job_id, {
            "progress": {
                "stage": "loading_config",
                "message": f"Loaded embedding config: {embedding_model} ({embedding_dimension}d)",
                "embedding_model": embedding_model,
                "embedding_dimension": embedding_dimension
            }
        })

        # ====================================================================
        # Phase 2: Fetch Source and generate embeddings
        # ====================================================================

        # Update progress
        job_queue.update_job(job_id, {
            "progress": {
                "stage": "fetching_source",
                "message": f"Fetching Source node: {source_id}"
            }
        })

        # Fetch Source node from AGE to get full_text
        with AGEClient() as age_client:
            # Use facade for namespace-safe query (ADR-048)
            result_set = age_client.facade.execute_raw("""
                MATCH (s:Source {source_id: $source_id})
                RETURN s.source_id, s.full_text, s.document, s.paragraph
            """, params={"source_id": source_id}, namespace="source_embedding")

            if not result_set:
                raise ValueError(f"Source not found: {source_id}")

            source_data = result_set[0]
            source_text = source_data[1]  # full_text

            if not source_text:
                raise ValueError(f"Source {source_id} has no full_text")

            logger.info(f"Fetched Source: {len(source_text)} chars")

        # Update progress
        job_queue.update_job(job_id, {
            "progress": {
                "stage": "generating_embeddings",
                "message": f"Generating embeddings for {len(source_text)} chars"
            }
        })

        # Call core embedding generation function
        result = generate_source_embeddings(
            source_id=source_id,
            source_text=source_text,
            chunk_strategy=chunk_strategy,
            max_chars=max_chars,
            embedding_config=embedding_config
        )

        # Add job metadata to result
        result["ontology"] = ontology
        result["regenerate"] = regenerate

        # Update progress
        job_queue.update_job(job_id, {
            "progress": {
                "stage": "completed",
                "message": f"Generated {result['chunks_created']} embeddings",
                "chunks_created": result["chunks_created"]
            }
        })

        logger.info(
            f"✓ Source embedding worker completed: {source_id} "
            f"({result['chunks_created']} chunks, {result['total_chars']} chars)"
        )

        return result

    except Exception as e:
        logger.error(f"❌ Source embedding worker failed: {str(e)}", exc_info=True)

        # Update job with error
        job_queue.update_job(job_id, {
            "status": "failed",
            "error": str(e)
        })

        raise


def generate_source_embeddings(
    source_id: str,
    source_text: str,
    chunk_strategy: str = "sentence",
    max_chars: int = 500,
    embedding_config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generate embeddings for source text chunks (Phase 2 implementation).

    Core function called by both:
    - Ingestion worker (synchronous - during document processing)
    - Source embedding worker (async - for regeneration jobs)

    Args:
        source_id: Source node ID
        source_text: Full source text to chunk and embed
        chunk_strategy: Chunking strategy ('sentence', 'paragraph', 'count')
        max_chars: Maximum characters per chunk
        embedding_config: Active embedding configuration (or load if None)

    Returns:
        Dict with generation results:
            - success: bool
            - chunks_created: int
            - source_hash: str
            - embedding_ids: List[int]
            - total_chars: int
            - embedding_model: str
            - embedding_dimension: int

    Raises:
        ValueError: If invalid parameters
        RuntimeError: If embedding generation fails
    """
    try:
        # Load embedding config if not provided
        if embedding_config is None:
            embedding_config = load_active_embedding_config()
            if not embedding_config:
                raise RuntimeError(
                    "No active embedding configuration found. "
                    "Configure embeddings via operator."
                )

        embedding_model = embedding_config.get("model_name")
        embedding_dimension = embedding_config.get("embedding_dimensions")
        embedding_provider = embedding_config.get("provider")

        logger.debug(
            f"Generating embeddings for source {source_id}: "
            f"model={embedding_model}, dims={embedding_dimension}"
        )

        # Step 1: Calculate source hash
        source_hash = sha256_text(source_text)
        logger.debug(f"Source hash: {source_hash[:16]}...")

        # Step 2: Chunk the source text
        chunker = get_chunking_strategy(chunk_strategy)
        chunks = chunker(source_text, max_chars=max_chars, min_chars=0)

        if not chunks:
            logger.warning(f"No chunks generated for source {source_id}")
            return {
                "success": True,
                "chunks_created": 0,
                "source_hash": source_hash,
                "embedding_ids": [],
                "total_chars": len(source_text),
                "embedding_model": embedding_model,
                "embedding_dimension": embedding_dimension
            }

        logger.debug(f"Created {len(chunks)} chunks (strategy: {chunk_strategy})")

        # Step 3: Get embedding worker
        embedding_worker = get_embedding_worker()

        # Step 4: Generate embeddings for each chunk and store
        embedding_ids = []

        # Connect to PostgreSQL for source_embeddings table
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            port=int(os.getenv("POSTGRES_PORT", 5432)),
            database=os.getenv("POSTGRES_DB", "knowledge_graph"),
            user=os.getenv("POSTGRES_USER", "admin"),
            password=os.getenv("POSTGRES_PASSWORD")
        )

        try:
            with conn.cursor() as cursor:
                # All inserts in single transaction for atomicity
                for chunk in chunks:
                    # Calculate chunk hash
                    chunk_hash = sha256_text(chunk.text)

                    # Generate embedding for this chunk
                    embedding_response = embedding_worker.generate_concept_embedding(chunk.text)
                    embedding_vector = embedding_response["embedding"]

                    # Convert embedding to binary format (PostgreSQL BYTEA)
                    # Convert to numpy array and then to bytes
                    embedding_array = np.array(embedding_vector, dtype=np.float32)
                    embedding_bytes = embedding_array.tobytes()

                    # Insert into source_embeddings table
                    cursor.execute("""
                        INSERT INTO kg_api.source_embeddings (
                            source_id,
                            chunk_index,
                            chunk_strategy,
                            start_offset,
                            end_offset,
                            chunk_text,
                            chunk_hash,
                            source_hash,
                            embedding,
                            embedding_model,
                            embedding_dimension,
                            embedding_provider
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING embedding_id
                    """, (
                        source_id,
                        chunk.index,
                        chunk_strategy,
                        chunk.start_offset,
                        chunk.end_offset,
                        chunk.text,
                        chunk_hash,
                        source_hash,
                        psycopg2.Binary(embedding_bytes),
                        embedding_model,
                        embedding_dimension,
                        embedding_provider
                    ))

                    embedding_id = cursor.fetchone()[0]
                    embedding_ids.append(embedding_id)

                    logger.debug(
                        f"Chunk {chunk.index}: embedding_id={embedding_id}, "
                        f"offsets=[{chunk.start_offset}:{chunk.end_offset}], "
                        f"hash={chunk_hash[:16]}..."
                    )

                # Commit all inserts (atomic transaction)
                conn.commit()
                logger.debug(f"Stored {len(embedding_ids)} embeddings in database")

        except Exception as e:
            # Rollback transaction on any error
            conn.rollback()
            logger.error(f"Failed to store embeddings, transaction rolled back: {str(e)}")
            raise
        finally:
            conn.close()

        # Step 5: Update Source.content_hash in AGE graph
        with AGEClient() as age_client:
            # Use facade for namespace-safe query (ADR-048)
            age_client.facade.execute_raw("""
                MATCH (s:Source {source_id: $source_id})
                SET s.content_hash = $content_hash
                RETURN s.source_id
            """, params={
                "source_id": source_id,
                "content_hash": source_hash
            }, namespace="source_embedding")
            logger.debug(f"Updated Source.content_hash in AGE: {source_hash[:16]}...")

        # Return success result
        result = {
            "success": True,
            "chunks_created": len(chunks),
            "source_hash": source_hash,
            "embedding_ids": embedding_ids,
            "total_chars": len(source_text),
            "embedding_model": embedding_model,
            "embedding_dimension": embedding_dimension,
            "chunk_strategy": chunk_strategy
        }

        logger.info(
            f"✓ Generated {len(chunks)} embeddings for source {source_id} "
            f"({len(source_text)} chars, hash={source_hash[:16]}...)"
        )

        return result

    except Exception as e:
        logger.error(f"Failed to generate source embeddings: {str(e)}", exc_info=True)
        raise RuntimeError(f"Source embedding generation failed: {str(e)}") from e


async def get_embedding_status(ontology: Optional[str] = None) -> Dict[str, Any]:
    """
    Get comprehensive embedding status report for all graph text entities.

    Shows count and percentage of entities with/without embeddings by category:
    - Concepts (AGE graph nodes)
    - Sources (source_embeddings table with hash verification)
    - Vocabulary (relationship types in vocabulary_embeddings table)
    - Images (future - from ADR-057)

    **Compatibility Detection:**
    Also identifies embeddings that don't match the active embedding configuration:
    - Model mismatch (e.g., OpenAI vs local)
    - Dimension mismatch (e.g., 1536 vs 768)

    Args:
        ontology: Limit to specific ontology (optional, applies to concepts/sources only)

    Returns:
        Dict with detailed embedding status:
            - concepts: {total, with_embeddings, without_embeddings, incompatible_embeddings, percentage}
            - sources: {total, with_embeddings, without_embeddings, stale_embeddings, incompatible_embeddings, percentage}
            - vocabulary: {total, with_embeddings, without_embeddings, incompatible_embeddings, percentage}
            - images: {total, with_embeddings, without_embeddings, percentage} (future)
            - summary: {total_entities, total_with_embeddings, total_incompatible, overall_percentage}
            - active_config: {model_name, embedding_dimensions, provider}
    """
    status = {
        "concepts": {},
        "sources": {},
        "vocabulary": {},
        "images": {},
        "summary": {},
        "active_config": {}
    }

    # Load active embedding configuration for compatibility checking
    embedding_config = load_active_embedding_config()
    if embedding_config:
        active_model = embedding_config.get("model_name")
        active_dims = embedding_config.get("embedding_dimensions")
        active_provider = embedding_config.get("provider")

        status["active_config"] = {
            "model_name": active_model,
            "embedding_dimensions": active_dims,
            "provider": active_provider
        }

        logger.debug(
            f"Active embedding config: model={active_model}, "
            f"dimensions={active_dims}, provider={active_provider}"
        )
    else:
        logger.warning("No active embedding configuration found - skipping compatibility checks")
        active_model = None
        active_dims = None
        active_provider = None

    # ====================================================================
    # 1. Concept Embeddings
    # ====================================================================
    with AGEClient() as age_client:
        # Count total concepts
        cypher = "MATCH (c:Concept)"
        params = {}

        if ontology:
            cypher += " WHERE c.ontology = $ontology"
            params["ontology"] = ontology

        cypher += " RETURN count(c) as total"

        result = age_client.facade.execute_raw(cypher, params=params if params else None, namespace="embedding_status")
        total_concepts = result[0]["total"] if result else 0

        # Count concepts WITH embeddings
        cypher = "MATCH (c:Concept) WHERE c.embedding IS NOT NULL"

        if ontology:
            cypher += " AND c.ontology = $ontology"

        cypher += " RETURN count(c) as with_embeddings"

        result = age_client.facade.execute_raw(cypher, params=params if params else None, namespace="embedding_status")
        concepts_with_embeddings = result[0]["with_embeddings"] if result else 0

        # Check for incompatible embeddings (dimension mismatch)
        # Note: AGE stores embeddings as arrays without metadata, so we check dimension by size
        incompatible_concepts = 0
        if active_dims and concepts_with_embeddings > 0:
            # Fetch all concepts with embeddings and check their dimensions
            cypher = "MATCH (c:Concept) WHERE c.embedding IS NOT NULL"

            if ontology:
                cypher += " AND c.ontology = $ontology"

            cypher += " RETURN c.concept_id, size(c.embedding) as dim"

            result = age_client.facade.execute_raw(cypher, params=params if params else None, namespace="embedding_status")

            for row in result:
                embedding_dim = row["dim"]
                if embedding_dim != active_dims:
                    incompatible_concepts += 1

            logger.debug(
                f"Concept compatibility check: {incompatible_concepts}/{concepts_with_embeddings} "
                f"incompatible (expected {active_dims} dims)"
            )

    status["concepts"] = {
        "total": total_concepts,
        "with_embeddings": concepts_with_embeddings,
        "without_embeddings": total_concepts - concepts_with_embeddings,
        "incompatible_embeddings": incompatible_concepts,
        "percentage": round((concepts_with_embeddings / total_concepts * 100) if total_concepts > 0 else 0, 1)
    }

    # ====================================================================
    # 2. Source Embeddings (with hash verification)
    # ====================================================================
    with AGEClient() as age_client:
        # Count total sources
        cypher = "MATCH (s:Source)"
        params = {}

        if ontology:
            cypher += " WHERE s.document = $ontology"
            params["ontology"] = ontology

        cypher += " RETURN count(s) as total"

        result = age_client.facade.execute_raw(cypher, params=params if params else None, namespace="embedding_status")
        total_sources = result[0]["total"] if result else 0

        # Get all sources with their content_hash
        cypher = "MATCH (s:Source)"

        if ontology:
            cypher += " WHERE s.document = $ontology"

        cypher += " RETURN s.source_id as source_id, s.content_hash as content_hash"

        result = age_client.facade.execute_raw(cypher, params=params if params else None, namespace="embedding_status")
        sources_map = {row["source_id"]: row["content_hash"] for row in result}  # {source_id: content_hash}

    # Check which sources have embeddings in PostgreSQL
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database=os.getenv("POSTGRES_DB", "knowledge_graph"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

    try:
        with conn.cursor() as cursor:
            # Get distinct source_ids with embeddings and their metadata
            cursor.execute("""
                SELECT DISTINCT
                    source_id,
                    source_hash,
                    embedding_model,
                    embedding_dimension
                FROM kg_api.source_embeddings
            """)

            embedded_sources = {}
            for row in cursor.fetchall():
                embedded_sources[row[0]] = {
                    'source_hash': row[1],
                    'embedding_model': row[2],
                    'embedding_dimension': row[3]
                }
    finally:
        conn.close()

    # Calculate stale embeddings (hash mismatch) and incompatible embeddings
    stale_count = 0
    incompatible_sources = 0

    for source_id, current_hash in sources_map.items():
        if source_id in embedded_sources:
            embedding_data = embedded_sources[source_id]
            embedding_hash = embedding_data['source_hash']
            embedding_model = embedding_data['embedding_model']
            embedding_dim = embedding_data['embedding_dimension']

            # Check if hashes match (stale detection)
            if current_hash and embedding_hash and current_hash != embedding_hash:
                stale_count += 1

            # Check compatibility with active config
            if active_model or active_dims:
                is_incompatible = False

                # Check model mismatch
                if active_model and embedding_model and embedding_model != active_model:
                    is_incompatible = True

                # Check dimension mismatch
                if active_dims and embedding_dim and embedding_dim != active_dims:
                    is_incompatible = True

                if is_incompatible:
                    incompatible_sources += 1

    sources_with_embeddings = len(embedded_sources)

    if incompatible_sources > 0:
        logger.debug(
            f"Source compatibility check: {incompatible_sources}/{sources_with_embeddings} "
            f"incompatible (expected {active_model}, {active_dims} dims)"
        )

    status["sources"] = {
        "total": total_sources,
        "with_embeddings": sources_with_embeddings,
        "without_embeddings": total_sources - sources_with_embeddings,
        "stale_embeddings": stale_count,
        "incompatible_embeddings": incompatible_sources,
        "percentage": round((sources_with_embeddings / total_sources * 100) if total_sources > 0 else 0, 1)
    }

    # ====================================================================
    # 3. Vocabulary Embeddings (relationship types)
    # ====================================================================
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database=os.getenv("POSTGRES_DB", "knowledge_graph"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

    try:
        with conn.cursor() as cursor:
            # Count total vocabulary types
            cursor.execute("""
                SELECT COUNT(*)
                FROM kg_api.relationship_vocabulary
                WHERE is_active = true
            """)
            total_vocab = cursor.fetchone()[0]

            # Count vocabulary types WITH embeddings (embedding stored as JSONB in the table)
            cursor.execute("""
                SELECT COUNT(*)
                FROM kg_api.relationship_vocabulary
                WHERE is_active = true
                  AND embedding IS NOT NULL
            """)
            vocab_with_embeddings = cursor.fetchone()[0]

            # Check for incompatible vocabulary embeddings
            # Note: Vocabulary embeddings stored as JSONB arrays, check dimension by array length
            incompatible_vocab = 0
            if active_dims and vocab_with_embeddings > 0:
                cursor.execute("""
                    SELECT relationship_type, jsonb_array_length(embedding) as dim
                    FROM kg_api.relationship_vocabulary
                    WHERE is_active = true
                      AND embedding IS NOT NULL
                """)

                for row in cursor.fetchall():
                    embedding_dim = row[1]
                    if embedding_dim != active_dims:
                        incompatible_vocab += 1

                if incompatible_vocab > 0:
                    logger.debug(
                        f"Vocabulary compatibility check: {incompatible_vocab}/{vocab_with_embeddings} "
                        f"incompatible (expected {active_dims} dims)"
                    )
    finally:
        conn.close()

    status["vocabulary"] = {
        "total": total_vocab,
        "with_embeddings": vocab_with_embeddings,
        "without_embeddings": total_vocab - vocab_with_embeddings,
        "incompatible_embeddings": incompatible_vocab,
        "percentage": round((vocab_with_embeddings / total_vocab * 100) if total_vocab > 0 else 0, 1)
    }

    # ====================================================================
    # 4. Images (future - ADR-057)
    # ====================================================================
    # TODO: Add image embedding status when ADR-057 is implemented
    status["images"] = {
        "total": 0,
        "with_embeddings": 0,
        "without_embeddings": 0,
        "percentage": 0.0,
        "note": "Image embeddings not yet implemented (ADR-057)"
    }

    # ====================================================================
    # 5. Summary
    # ====================================================================
    total_entities = (
        status["concepts"]["total"] +
        status["sources"]["total"] +
        status["vocabulary"]["total"] +
        status["images"]["total"]
    )

    total_with_embeddings = (
        status["concepts"]["with_embeddings"] +
        status["sources"]["with_embeddings"] +
        status["vocabulary"]["with_embeddings"] +
        status["images"]["with_embeddings"]
    )

    total_incompatible = (
        status["concepts"].get("incompatible_embeddings", 0) +
        status["sources"].get("incompatible_embeddings", 0) +
        status["vocabulary"].get("incompatible_embeddings", 0)
    )

    status["summary"] = {
        "total_entities": total_entities,
        "total_with_embeddings": total_with_embeddings,
        "total_without_embeddings": total_entities - total_with_embeddings,
        "total_incompatible": total_incompatible,
        "overall_percentage": round((total_with_embeddings / total_entities * 100) if total_entities > 0 else 0, 1)
    }

    return status


async def regenerate_source_embeddings(
    only_missing: bool = False,
    only_incompatible: bool = False,
    ontology: Optional[str] = None,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    Regenerate embeddings for source nodes in bulk (ADR-068 Phase 4).

    Fetches source nodes from AGE and regenerates their embeddings using
    the current active embedding configuration. Useful for:
    - Model migrations (changed embedding model)
    - Bulk regeneration after embedding config changes
    - Fixing missing/corrupted embeddings
    - Regenerating stale embeddings (hash mismatch)

    Args:
        only_missing: Only generate for sources without embeddings (no source_embeddings rows)
        ontology: Limit to specific ontology (optional)
        limit: Maximum number of sources to process (for testing/batching)

    Returns:
        Dict with processing statistics:
            - success: bool
            - job_id: str
            - target_count: int - Total sources found
            - processed_count: int - Successfully processed
            - failed_count: int - Failed to process
            - duration_ms: int - Total processing time
            - embedding_model: str
            - embedding_dimension: int
            - embedding_provider: str
            - errors: List[str] - Error messages (if any)

    Raises:
        RuntimeError: If embedding configuration not found
    """
    import time
    from uuid import uuid4

    job_id = str(uuid4())
    start_time = time.time()

    logger.info(
        f"[{job_id}] Starting source embedding regeneration "
        f"(only_missing={only_missing}, ontology={ontology}, limit={limit})"
    )

    # Load active embedding configuration
    embedding_config = load_active_embedding_config()
    if not embedding_config:
        raise RuntimeError(
            "No active embedding configuration found. "
            "Configure embeddings via: docker exec kg-operator python /workspace/operator/configure.py embedding"
        )

    embedding_model = embedding_config.get("model_name")
    embedding_dimension = embedding_config.get("embedding_dimensions")
    embedding_provider = embedding_config.get("provider")

    logger.info(
        f"[{job_id}] Using embedding config: model={embedding_model}, "
        f"dimensions={embedding_dimension}, provider={embedding_provider}"
    )

    # Fetch sources that need regeneration
    target_sources = []

    with AGEClient() as age_client:
        if only_incompatible:
            # Find sources with INCOMPATIBLE embeddings (model/dimension mismatch)
            # Use PostgreSQL to check embedding metadata
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", 5432)),
                database=os.getenv("POSTGRES_DB", "knowledge_graph"),
                user=os.getenv("POSTGRES_USER", "admin"),
                password=os.getenv("POSTGRES_PASSWORD")
            )

            try:
                with conn.cursor() as cursor:
                    # Get source_ids with incompatible embeddings
                    cursor.execute("""
                        SELECT DISTINCT source_id, embedding_model, embedding_dimension
                        FROM kg_api.source_embeddings
                        WHERE embedding_model != %s
                           OR embedding_dimension != %s
                    """, (embedding_model, embedding_dimension))

                    incompatible_source_ids = {row[0] for row in cursor.fetchall()}

                    logger.info(
                        f"[{job_id}] Found {len(incompatible_source_ids)} sources with incompatible embeddings "
                        f"(expected {embedding_model}, {embedding_dimension} dims)"
                    )
            finally:
                conn.close()

            if not incompatible_source_ids:
                logger.info(f"[{job_id}] No incompatible sources found - all embeddings match active config")
                return {
                    "success": True,
                    "job_id": job_id,
                    "target_count": 0,
                    "processed_count": 0,
                    "failed_count": 0,
                    "duration_ms": 0,
                    "embedding_model": embedding_model,
                    "embedding_dimension": embedding_dimension,
                    "embedding_provider": embedding_provider,
                    "errors": []
                }

            # Build Cypher query for sources WITH incompatible embeddings
            cypher_where = "WHERE s.source_id IN $incompatible_ids"
            params = {"incompatible_ids": list(incompatible_source_ids)}

            if ontology:
                cypher_where += " AND s.document = $ontology"
                params["ontology"] = ontology

            cypher = f"""
                MATCH (s:Source)
                {cypher_where}
                RETURN s.source_id, s.full_text, s.document, s.paragraph
                ORDER BY s.document, s.paragraph
            """

            if limit:
                cypher += f" LIMIT {limit}"

            results = age_client.facade.execute_raw(
                cypher,
                params=params,
                namespace="source_embedding_regeneration"
            )

        elif only_missing:
            # Find sources WITHOUT any source_embeddings entries
            # Use PostgreSQL to check which source_ids are missing from source_embeddings
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", 5432)),
                database=os.getenv("POSTGRES_DB", "knowledge_graph"),
                user=os.getenv("POSTGRES_USER", "admin"),
                password=os.getenv("POSTGRES_PASSWORD")
            )

            try:
                with conn.cursor() as cursor:
                    # Get all source_ids that have embeddings
                    cursor.execute("""
                        SELECT DISTINCT source_id
                        FROM kg_api.source_embeddings
                    """)
                    embedded_source_ids = {row[0] for row in cursor.fetchall()}
            finally:
                conn.close()

            # Build Cypher query for sources WITHOUT embeddings
            cypher_where = "WHERE NOT s.source_id IN $embedded_ids"
            params = {"embedded_ids": list(embedded_source_ids)}

            if ontology:
                cypher_where += " AND s.document = $ontology"
                params["ontology"] = ontology

            cypher = f"""
                MATCH (s:Source)
                {cypher_where}
                RETURN s.source_id, s.full_text, s.document, s.paragraph
                ORDER BY s.document, s.paragraph
            """

            if limit:
                cypher += f" LIMIT {limit}"

            results = age_client.facade.execute_raw(
                cypher,
                params=params,
                namespace="source_embedding_regeneration"
            )

        else:
            # Get ALL sources (or filtered by ontology)
            cypher = "MATCH (s:Source)"
            params = {}

            if ontology:
                cypher += " WHERE s.document = $ontology"
                params["ontology"] = ontology

            cypher += """
                RETURN s.source_id, s.full_text, s.document, s.paragraph
                ORDER BY s.document, s.paragraph
            """

            if limit:
                cypher += f" LIMIT {limit}"

            results = age_client.facade.execute_raw(
                cypher,
                params=params if params else None,
                namespace="source_embedding_regeneration"
            )

        # Extract source data
        for row in results:
            target_sources.append({
                "source_id": row[0],
                "full_text": row[1],
                "document": row[2],
                "paragraph": row[3]
            })

    if not target_sources:
        logger.info(f"[{job_id}] No sources need regeneration")
        return {
            "success": True,
            "job_id": job_id,
            "target_count": 0,
            "processed_count": 0,
            "failed_count": 0,
            "duration_ms": 0,
            "embedding_model": embedding_model,
            "embedding_dimension": embedding_dimension,
            "embedding_provider": embedding_provider,
            "errors": []
        }

    logger.info(f"[{job_id}] Found {len(target_sources)} sources to process")

    # Process each source
    processed_count = 0
    failed_count = 0
    errors = []

    for idx, source_data in enumerate(target_sources, 1):
        source_id = source_data["source_id"]
        source_text = source_data["full_text"]

        if not source_text:
            logger.warning(f"[{job_id}] Skipping source {source_id} - no full_text")
            failed_count += 1
            errors.append(f"{source_id}: No full_text")
            continue

        try:
            logger.debug(
                f"[{job_id}] Processing {idx}/{len(target_sources)}: {source_id} "
                f"({len(source_text)} chars)"
            )

            # Delete existing embeddings for this source (regeneration)
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", 5432)),
                database=os.getenv("POSTGRES_DB", "knowledge_graph"),
                user=os.getenv("POSTGRES_USER", "admin"),
                password=os.getenv("POSTGRES_PASSWORD")
            )

            try:
                with conn.cursor() as cursor:
                    cursor.execute("""
                        DELETE FROM kg_api.source_embeddings
                        WHERE source_id = %s
                    """, (source_id,))
                    conn.commit()
                    deleted_count = cursor.rowcount

                if deleted_count > 0:
                    logger.debug(f"[{job_id}] Deleted {deleted_count} existing embeddings for {source_id}")
            finally:
                conn.close()

            # Generate new embeddings
            result = generate_source_embeddings(
                source_id=source_id,
                source_text=source_text,
                chunk_strategy="sentence",  # Default strategy
                max_chars=500,  # Default chunk size
                embedding_config=embedding_config
            )

            processed_count += 1
            logger.debug(
                f"[{job_id}] ✓ {source_id}: {result['chunks_created']} chunks created"
            )

        except Exception as e:
            failed_count += 1
            error_msg = f"{source_id}: {str(e)}"
            errors.append(error_msg)
            logger.error(f"[{job_id}] ✗ Failed to process {source_id}: {e}", exc_info=True)

    # Calculate duration
    end_time = time.time()
    duration_ms = int((end_time - start_time) * 1000)

    logger.info(
        f"[{job_id}] Source regeneration complete: {processed_count}/{len(target_sources)} "
        f"sources processed in {duration_ms}ms ({failed_count} failed)"
    )

    return {
        "success": True,
        "job_id": job_id,
        "target_count": len(target_sources),
        "processed_count": processed_count,
        "failed_count": failed_count,
        "duration_ms": duration_ms,
        "embedding_model": embedding_model,
        "embedding_dimension": embedding_dimension,
        "embedding_provider": embedding_provider,
        "errors": errors[:10]  # Return first 10 errors
    }
