"""
Unified Embedding Generation Worker (ADR-045).

Centralized service for all embedding generation tasks:
- Concept embeddings (during ingestion)
- Vocabulary type embeddings (on creation or bulk regeneration)
- Cold start initialization (builtin types)
- Model migration (regenerate all embeddings)

Usage:
    from src.api.services.embedding_worker import get_embedding_worker

    worker = get_embedding_worker(age_client, ai_provider)
    result = await worker.initialize_builtin_embeddings()

References:
    - ADR-045: Unified Embedding Generation System
    - ADR-046: Grounding-Aware Vocabulary Management
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4
import logging
import json

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingJobResult:
    """
    Result of an embedding generation job.

    Attributes:
        job_id: Unique job identifier
        job_type: Type of job (cold_start, vocabulary_update, etc.)
        target_count: Number of types to process
        processed_count: Number successfully processed
        failed_count: Number that failed
        duration_ms: Job duration in milliseconds
        embedding_model: Model used for generation
        embedding_provider: Provider used (openai, local, etc.)
        errors: List of error messages for failed types
    """
    job_id: str
    job_type: str
    target_count: int
    processed_count: int
    failed_count: int
    duration_ms: int
    embedding_model: str
    embedding_provider: str
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage"""
        if self.target_count == 0:
            return 0.0
        return (self.processed_count / self.target_count) * 100.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "target_count": self.target_count,
            "processed_count": self.processed_count,
            "failed_count": self.failed_count,
            "success_rate": self.success_rate,
            "duration_ms": self.duration_ms,
            "embedding_model": self.embedding_model,
            "embedding_provider": self.embedding_provider,
            "errors": self.errors
        }


class EmbeddingWorker:
    """
    Unified embedding generation service.

    Handles embedding generation for:
    - Concept nodes (during ingestion)
    - Vocabulary relationship types (on creation or bulk regeneration)
    - Cold start initialization (builtin types)
    - Model migration (regenerate all embeddings)
    """

    def __init__(self, db_client, ai_provider):
        """
        Initialize worker with database client and AI provider.

        Args:
            db_client: AGEClient instance
            ai_provider: AIProvider instance (OpenAI, Anthropic, Ollama, etc.)
        """
        self.db = db_client
        self.provider = ai_provider
        self.provider_name = ai_provider.__class__.__name__.replace("Provider", "").lower()

    async def initialize_builtin_embeddings(self) -> EmbeddingJobResult:
        """
        Generate embeddings for all builtin vocabulary types without embeddings.

        Called during system initialization or after schema migrations.
        Idempotent - safe to call multiple times.

        Returns:
            EmbeddingJobResult with processing statistics

        Example:
            >>> worker = EmbeddingWorker(age_client, ai_provider)
            >>> result = await worker.initialize_builtin_embeddings()
            >>> print(f"Initialized {result.processed_count}/{result.target_count} types")
        """
        job_id = str(uuid4())
        start_time = datetime.now()

        logger.info(f"[{job_id}] Starting cold start: Initializing builtin vocabulary embeddings")

        # Check if already initialized
        is_initialized = await self._check_initialization_status()
        if is_initialized:
            logger.info(f"[{job_id}] Cold start already completed, skipping")
            return EmbeddingJobResult(
                job_id=job_id,
                job_type="cold_start",
                target_count=0,
                processed_count=0,
                failed_count=0,
                duration_ms=0,
                embedding_model=self.provider.model_name if hasattr(self.provider, 'model_name') else "unknown",
                embedding_provider=self.provider_name
            )

        # Get builtin types missing embeddings
        target_types = await self._get_builtin_types_missing_embeddings()

        if not target_types:
            logger.info(f"[{job_id}] No builtin types need embeddings")
            await self._mark_initialization_complete(job_id, 0)
            return EmbeddingJobResult(
                job_id=job_id,
                job_type="cold_start",
                target_count=0,
                processed_count=0,
                failed_count=0,
                duration_ms=0,
                embedding_model=self.provider.model_name if hasattr(self.provider, 'model_name') else "unknown",
                embedding_provider=self.provider_name
            )

        # Create job record
        await self._create_job_record(
            job_id=job_id,
            job_type="cold_start",
            target_types=target_types
        )

        # Update job status to running
        await self._update_job_status(job_id, "running", started_at=start_time)

        # Generate embeddings
        result = await self._batch_generate_embeddings(
            job_id=job_id,
            relationship_types=target_types,
            job_type="cold_start"
        )

        # Mark initialization as complete
        await self._mark_initialization_complete(job_id, result.processed_count)

        # Update job record with final status
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        await self._complete_job(
            job_id=job_id,
            processed_count=result.processed_count,
            failed_count=result.failed_count,
            duration_ms=duration_ms,
            result_summary=result.to_dict()
        )

        logger.info(
            f"[{job_id}] Cold start complete: {result.processed_count}/{result.target_count} "
            f"builtin types initialized in {duration_ms}ms"
        )

        return result

    async def generate_vocabulary_embedding(
        self,
        relationship_type: str,
        description: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate embedding for a single vocabulary type.

        Called when adding new vocabulary types or regenerating individual embeddings.

        Args:
            relationship_type: The relationship type to generate embedding for
            description: Optional description (fetched from DB if not provided)

        Returns:
            Dictionary with embedding data: {embedding, model, provider, dimensions}

        Example:
            >>> result = await worker.generate_vocabulary_embedding("IMPLIES")
            >>> print(f"Generated {len(result['embedding'])}D embedding")
        """
        logger.info(f"Generating embedding for vocabulary type: {relationship_type}")

        # Get description if not provided
        if description is None:
            description = await self._get_vocabulary_description(relationship_type)

        # Generate descriptive text for embedding
        descriptive_text = self._create_descriptive_text(relationship_type, description)

        # Generate embedding via AI provider
        try:
            embedding_response = self.provider.generate_embedding(descriptive_text)
            embedding = embedding_response["embedding"]
            model = embedding_response.get("model", "unknown")

            # Store embedding in database
            await self._store_vocabulary_embedding(
                relationship_type=relationship_type,
                embedding=embedding,
                model=model,
                provider=self.provider_name
            )

            logger.info(
                f"Successfully generated {len(embedding)}D embedding for {relationship_type} "
                f"using {self.provider_name}/{model}"
            )

            return {
                "embedding": embedding,
                "model": model,
                "provider": self.provider_name,
                "dimensions": len(embedding)
            }

        except Exception as e:
            logger.error(f"Failed to generate embedding for {relationship_type}: {e}")
            raise

    async def regenerate_all_embeddings(
        self,
        only_missing: bool = False,
        only_stale: bool = False
    ) -> EmbeddingJobResult:
        """
        Regenerate embeddings for all vocabulary types.

        Useful for:
        - Model migrations (changed embedding model)
        - Bulk regeneration after data cleanup
        - Fixing invalid embeddings

        Args:
            only_missing: Only generate for types without embeddings
            only_stale: Only generate for types marked as stale

        Returns:
            EmbeddingJobResult with processing statistics
        """
        job_id = str(uuid4())
        start_time = datetime.now()

        logger.info(
            f"[{job_id}] Starting bulk regeneration "
            f"(only_missing={only_missing}, only_stale={only_stale})"
        )

        # Get target types
        if only_missing:
            target_types = await self._get_types_without_embeddings()
        elif only_stale:
            target_types = await self._get_stale_embeddings()
        else:
            target_types = await self._get_all_active_types()

        if not target_types:
            logger.info(f"[{job_id}] No types need regeneration")
            return EmbeddingJobResult(
                job_id=job_id,
                job_type="batch_regeneration",
                target_count=0,
                processed_count=0,
                failed_count=0,
                duration_ms=0,
                embedding_model=self.provider.model_name if hasattr(self.provider, 'model_name') else "unknown",
                embedding_provider=self.provider_name
            )

        # Create job record
        await self._create_job_record(
            job_id=job_id,
            job_type="batch_regeneration",
            target_types=target_types
        )

        await self._update_job_status(job_id, "running", started_at=start_time)

        # Generate embeddings
        result = await self._batch_generate_embeddings(
            job_id=job_id,
            relationship_types=target_types,
            job_type="batch_regeneration"
        )

        # Update job record
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        await self._complete_job(
            job_id=job_id,
            processed_count=result.processed_count,
            failed_count=result.failed_count,
            duration_ms=duration_ms,
            result_summary=result.to_dict()
        )

        logger.info(
            f"[{job_id}] Bulk regeneration complete: {result.processed_count}/{result.target_count} "
            f"types processed in {duration_ms}ms"
        )

        return result

    # ========================================================================
    # Private Helper Methods
    # ========================================================================

    async def _batch_generate_embeddings(
        self,
        job_id: str,
        relationship_types: List[str],
        job_type: str
    ) -> EmbeddingJobResult:
        """Generate embeddings for multiple types in batch"""
        start_time = datetime.now()
        processed = 0
        failed = 0
        errors = []

        total = len(relationship_types)
        logger.info(f"[{job_id}] Generating embeddings for {total} types")

        for i, rel_type in enumerate(relationship_types, 1):
            try:
                await self.generate_vocabulary_embedding(rel_type)
                processed += 1

                if i % 10 == 0 or i == total:
                    logger.info(f"[{job_id}] Progress: {i}/{total} ({(i/total)*100:.1f}%)")

            except Exception as e:
                failed += 1
                error_msg = f"{rel_type}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"[{job_id}] Failed to generate embedding for {rel_type}: {e}")

        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return EmbeddingJobResult(
            job_id=job_id,
            job_type=job_type,
            target_count=total,
            processed_count=processed,
            failed_count=failed,
            duration_ms=duration_ms,
            embedding_model=self.provider.model_name if hasattr(self.provider, 'model_name') else "unknown",
            embedding_provider=self.provider_name,
            errors=errors
        )

    async def _get_builtin_types_missing_embeddings(self) -> List[str]:
        """Get builtin vocabulary types without embeddings"""
        query = """
            SELECT relationship_type
            FROM kg_api.v_builtin_types_missing_embeddings
            ORDER BY usage_count DESC, relationship_type
        """
        results = await self.db.execute_query(query)
        return [row["relationship_type"] for row in results]

    async def _get_types_without_embeddings(self) -> List[str]:
        """Get all active types without embeddings"""
        query = """
            SELECT relationship_type
            FROM kg_api.relationship_vocabulary
            WHERE embedding IS NULL
              AND is_active = TRUE
            ORDER BY is_builtin DESC, usage_count DESC, relationship_type
        """
        results = await self.db.execute_query(query)
        return [row["relationship_type"] for row in results]

    async def _get_stale_embeddings(self) -> List[str]:
        """Get types with stale embeddings"""
        query = """
            SELECT relationship_type
            FROM kg_api.relationship_vocabulary
            WHERE embedding_validation_status = 'stale'
              AND is_active = TRUE
            ORDER BY usage_count DESC, relationship_type
        """
        results = await self.db.execute_query(query)
        return [row["relationship_type"] for row in results]

    async def _get_all_active_types(self) -> List[str]:
        """Get all active vocabulary types"""
        query = """
            SELECT relationship_type
            FROM kg_api.relationship_vocabulary
            WHERE is_active = TRUE
            ORDER BY is_builtin DESC, usage_count DESC, relationship_type
        """
        results = await self.db.execute_query(query)
        return [row["relationship_type"] for row in results]

    async def _get_vocabulary_description(self, relationship_type: str) -> Optional[str]:
        """Get description for a vocabulary type"""
        query = """
            SELECT description
            FROM kg_api.relationship_vocabulary
            WHERE relationship_type = %s
        """
        results = await self.db.execute_query(query, (relationship_type,))
        if results:
            return results[0].get("description")
        return None

    def _create_descriptive_text(self, relationship_type: str, description: Optional[str]) -> str:
        """
        Create descriptive text for embedding generation.

        Combines relationship type and description to create semantically rich text.
        """
        if description:
            return f"{relationship_type}: {description}"
        else:
            # Use relationship type only (convert underscores to spaces)
            readable = relationship_type.replace("_", " ").lower()
            return f"relationship type: {readable}"

    async def _store_vocabulary_embedding(
        self,
        relationship_type: str,
        embedding: List[float],
        model: str,
        provider: str
    ) -> None:
        """Store embedding in relationship_vocabulary table"""
        query = """
            UPDATE kg_api.relationship_vocabulary
            SET embedding = %s::jsonb,
                embedding_model = %s,
                embedding_generated_at = CURRENT_TIMESTAMP
            WHERE relationship_type = %s
        """
        embedding_json = json.dumps(embedding)
        await self.db.execute_query(query, (embedding_json, model, relationship_type))

    async def _check_initialization_status(self) -> bool:
        """Check if cold start initialization is complete"""
        query = """
            SELECT initialized
            FROM kg_api.system_initialization_status
            WHERE component = 'builtin_vocabulary_embeddings'
        """
        try:
            results = await self.db.execute_query(query)
            if results and len(results) > 0:
                return results[0]["initialized"]
            return False
        except Exception as e:
            logger.debug(f"Error checking initialization status: {e}")
            return False

    async def _mark_initialization_complete(self, job_id: str, count: int) -> None:
        """Mark cold start initialization as complete"""
        query = """
            UPDATE kg_api.system_initialization_status
            SET initialized = TRUE,
                initialized_at = CURRENT_TIMESTAMP,
                initialization_job_id = %s,
                metadata = jsonb_build_object(
                    'types_initialized', %s,
                    'provider', %s,
                    'model', %s
                )
            WHERE component = 'builtin_vocabulary_embeddings'
        """
        await self.db.execute_query(
            query,
            (
                job_id,
                count,
                self.provider_name,
                self.provider.model_name if hasattr(self.provider, 'model_name') else "unknown"
            )
        )

    async def _create_job_record(
        self,
        job_id: str,
        job_type: str,
        target_types: List[str]
    ) -> None:
        """Create embedding generation job record"""
        query = """
            INSERT INTO kg_api.embedding_generation_jobs (
                job_id, job_type, target_types, target_count,
                embedding_model, embedding_provider
            ) VALUES (%s, %s, %s, %s, %s, %s)
        """
        await self.db.execute_query(
            query,
            (
                job_id,
                job_type,
                target_types,
                len(target_types),
                self.provider.model_name if hasattr(self.provider, 'model_name') else "unknown",
                self.provider_name
            )
        )

    async def _update_job_status(
        self,
        job_id: str,
        status: str,
        started_at: Optional[datetime] = None
    ) -> None:
        """Update job status"""
        if started_at:
            query = """
                UPDATE kg_api.embedding_generation_jobs
                SET status = %s, started_at = %s
                WHERE job_id = %s
            """
            await self.db.execute_query(query, (status, started_at, job_id))
        else:
            query = """
                UPDATE kg_api.embedding_generation_jobs
                SET status = %s
                WHERE job_id = %s
            """
            await self.db.execute_query(query, (status, job_id))

    async def _complete_job(
        self,
        job_id: str,
        processed_count: int,
        failed_count: int,
        duration_ms: int,
        result_summary: Dict[str, Any]
    ) -> None:
        """Mark job as complete with results"""
        query = """
            UPDATE kg_api.embedding_generation_jobs
            SET status = %s,
                completed_at = CURRENT_TIMESTAMP,
                processed_count = %s,
                failed_count = %s,
                duration_ms = %s,
                result_summary = %s::jsonb
            WHERE job_id = %s
        """
        status = "completed" if failed_count == 0 else "completed"  # Mark as completed even with failures
        await self.db.execute_query(
            query,
            (status, processed_count, failed_count, duration_ms, json.dumps(result_summary), job_id)
        )


# ============================================================================
# Singleton Pattern for EmbeddingWorker
# ============================================================================

_embedding_worker: Optional[EmbeddingWorker] = None


def get_embedding_worker(db_client=None, ai_provider=None) -> Optional[EmbeddingWorker]:
    """
    Get or create the singleton EmbeddingWorker instance.

    Args:
        db_client: AGEClient instance (required on first call)
        ai_provider: AIProvider instance (required on first call)

    Returns:
        EmbeddingWorker instance or None if not initialized

    Example:
        >>> # Initialize (typically in main.py startup)
        >>> worker = get_embedding_worker(age_client, ai_provider)
        >>>
        >>> # Use later without arguments
        >>> worker = get_embedding_worker()
        >>> result = await worker.initialize_builtin_embeddings()
    """
    global _embedding_worker

    if _embedding_worker is None:
        if db_client is None or ai_provider is None:
            logger.warning("EmbeddingWorker not initialized - provide db_client and ai_provider")
            return None
        _embedding_worker = EmbeddingWorker(db_client, ai_provider)
        logger.info(f"EmbeddingWorker initialized with {ai_provider.__class__.__name__}")

    return _embedding_worker


def reset_embedding_worker():
    """Reset singleton (useful for testing)"""
    global _embedding_worker
    _embedding_worker = None
