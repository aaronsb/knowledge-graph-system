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
        age_client = AGEClient()

        try:
            result_set = age_client._execute_cypher("""
                MATCH (s:Source {source_id: $source_id})
                RETURN s.source_id, s.full_text, s.document, s.paragraph
            """, params={"source_id": source_id})

            if not result_set:
                raise ValueError(f"Source not found: {source_id}")

            source_data = result_set[0]
            source_text = source_data[1]  # full_text

            if not source_text:
                raise ValueError(f"Source {source_id} has no full_text")

            logger.info(f"Fetched Source: {len(source_text)} chars")

        finally:
            age_client.close()

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
        age_client = AGEClient()
        try:
            # Use Cypher to update content_hash property
            age_client._execute_cypher("""
                MATCH (s:Source {source_id: $source_id})
                SET s.content_hash = $content_hash
                RETURN s.source_id
            """, params={
                "source_id": source_id,
                "content_hash": source_hash
            })
            logger.debug(f"Updated Source.content_hash in AGE: {source_hash[:16]}...")
        finally:
            age_client.close()

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
