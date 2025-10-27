"""
Ingestion library for processing document chunks into knowledge graph.

Contains statistics tracking and chunk processing logic used by API workers.
Extracted from POC code for API-first architecture.
"""

import os
import sys
import uuid
import logging
from typing import List, Dict, Any, Union

logger = logging.getLogger(__name__)

from src.api.lib.chunker import Chunk
from src.api.lib.markdown_preprocessor import SemanticChunk
from src.api.lib.age_client import AGEClient
from src.api.lib.llm_extractor import extract_concepts
from src.api.lib.relationship_mapper import normalize_relationship_type
from src.api.lib.ai_providers import get_provider
from src.api.services.embedding_worker import get_embedding_worker


class ChunkedIngestionStats:
    """Track ingestion statistics for chunked processing."""

    def __init__(self):
        self.chunks_processed = 0
        self.sources_created = 0
        self.concepts_created = 0
        self.concepts_linked = 0
        self.instances_created = 0
        self.relationships_created = 0
        self.extraction_tokens = 0
        self.embedding_tokens = 0

    def to_dict(self) -> Dict[str, int]:
        """Convert stats to dictionary."""
        return {
            "chunks_processed": self.chunks_processed,
            "sources_created": self.sources_created,
            "concepts_created": self.concepts_created,
            "concepts_linked": self.concepts_linked,
            "instances_created": self.instances_created,
            "relationships_created": self.relationships_created,
            "extraction_tokens": self.extraction_tokens,
            "embedding_tokens": self.embedding_tokens
        }

    def from_dict(self, data: Dict[str, int]) -> None:
        """Load stats from dictionary."""
        self.chunks_processed = data.get("chunks_processed", 0)
        self.sources_created = data.get("sources_created", 0)
        self.concepts_created = data.get("concepts_created", 0)
        self.concepts_linked = data.get("concepts_linked", 0)
        self.instances_created = data.get("instances_created", 0)
        self.relationships_created = data.get("relationships_created", 0)
        self.extraction_tokens = data.get("extraction_tokens", 0)
        self.embedding_tokens = data.get("embedding_tokens", 0)

    def print_summary(self, extraction_model: str = None, embedding_model: str = None):
        """Print ingestion summary with token usage and cost estimation.

        Args:
            extraction_model: Name of the extraction model used (for cost calculation)
            embedding_model: Name of the embedding model used (for cost calculation)
        """
        print("\n" + "=" * 60)
        print("CHUNKED INGESTION SUMMARY")
        print("=" * 60)
        print(f"Chunks processed:        {self.chunks_processed}")
        print(f"Source nodes created:    {self.sources_created}")
        print(f"Concept nodes created:   {self.concepts_created}")
        print(f"Concepts linked (reuse): {self.concepts_linked}")
        print(f"Instance nodes created:  {self.instances_created}")
        print(f"Relationships created:   {self.relationships_created}")

        if self.extraction_tokens > 0 or self.embedding_tokens > 0:
            print()
            print("Token Usage:")
            if self.extraction_tokens > 0:
                print(f"  Extraction:            {self.extraction_tokens:,} tokens")
            if self.embedding_tokens > 0:
                print(f"  Embeddings:            {self.embedding_tokens:,} tokens")

            total_tokens = self.extraction_tokens + self.embedding_tokens
            print(f"  Total:                 {total_tokens:,} tokens")

            # Calculate cost based on configured pricing
            extraction_cost = self._get_extraction_cost(self.extraction_tokens, extraction_model)
            embedding_cost = self._get_embedding_cost(self.embedding_tokens, embedding_model)
            total_cost = extraction_cost + embedding_cost

            if total_cost > 0:
                print(f"  Estimated cost:        ${total_cost:.4f}")

        print("=" * 60)

    def _get_extraction_cost(self, tokens: int, model: str = None) -> float:
        """Calculate extraction cost based on model and configured pricing."""
        if tokens == 0:
            return 0.0

        # Map model names to environment variable names
        model_cost_map = {
            "gpt-4o": "TOKEN_COST_GPT4O",
            "gpt-4o-mini": "TOKEN_COST_GPT4O_MINI",
            "o1-preview": "TOKEN_COST_O1_PREVIEW",
            "o1-mini": "TOKEN_COST_O1_MINI",
            "claude-sonnet-4-20250514": "TOKEN_COST_CLAUDE_SONNET_4",
        }

        # Default cost per 1M tokens (GPT-4o average)
        default_cost = 6.25

        # Get cost from environment or use default
        if model:
            cost_var = model_cost_map.get(model, "TOKEN_COST_GPT4O")
            cost_per_million = float(os.getenv(cost_var, default_cost))
        else:
            cost_per_million = float(os.getenv("TOKEN_COST_GPT4O", default_cost))

        return (tokens / 1_000_000) * cost_per_million

    def _get_embedding_cost(self, tokens: int, model: str = None) -> float:
        """Calculate embedding cost based on model and configured pricing."""
        if tokens == 0:
            return 0.0

        # Map model names to environment variable names
        model_cost_map = {
            "text-embedding-3-small": "TOKEN_COST_EMBEDDING_SMALL",
            "text-embedding-3-large": "TOKEN_COST_EMBEDDING_LARGE",
        }

        # Default cost per 1M tokens (small embedding model)
        default_cost = 0.02

        # Get cost from environment or use default
        if model:
            cost_var = model_cost_map.get(model, "TOKEN_COST_EMBEDDING_SMALL")
            cost_per_million = float(os.getenv(cost_var, default_cost))
        else:
            cost_per_million = float(os.getenv("TOKEN_COST_EMBEDDING_SMALL", default_cost))

        return (tokens / 1_000_000) * cost_per_million

    def calculate_extraction_cost(self, model: str = None) -> float:
        """Public method to calculate extraction cost based on tracked tokens."""
        return self._get_extraction_cost(self.extraction_tokens, model)

    def calculate_embedding_cost(self, model: str = None) -> float:
        """Public method to calculate embedding cost based on tracked tokens."""
        return self._get_embedding_cost(self.embedding_tokens, model)


def process_chunk(
    chunk: Union[Chunk, SemanticChunk],
    ontology_name: str,
    filename: str,
    file_path: str,
    age_client: AGEClient,
    stats: ChunkedIngestionStats,
    existing_concepts: List[Dict[str, Any]],
    recent_concept_ids: List[str],
    verbose: bool = True
) -> List[str]:
    """
    Process a single chunk: create source, extract concepts, create graph nodes.

    Accepts both legacy Chunk (word-based) and SemanticChunk (AST-based) types.
    Both provide the same interface: text, chunk_number, word_count, boundary_type.

    Args:
        chunk: Chunk or SemanticChunk object to process
        ontology_name: Name of the ontology/collection (shared across documents)
        filename: Unique filename for source tracking
        file_path: Full path to the source file
        age_client: AGE client instance
        stats: Statistics tracker
        existing_concepts: List of existing concepts for LLM context
        recent_concept_ids: List to track recent concept IDs
        verbose: Show detailed concept summary

    Returns:
        Updated list of recent concept IDs

    Raises:
        Exception: If processing fails
    """
    # Generate unique source ID using filename (not ontology name)
    source_id = f"{filename.replace(' ', '_').lower()}_chunk{chunk.chunk_number}"

    logger.info(f"{'='*70}")
    logger.info(f"[Chunk {chunk.chunk_number}] {chunk.word_count} words, "
                f"boundary: {chunk.boundary_type}")
    logger.info(f"{'='*70}")

    # Step 1: Create Source node
    try:
        age_client.create_source_node(
            source_id=source_id,
            document=ontology_name,  # Ontology name for logical grouping
            paragraph=chunk.chunk_number,  # Using chunk number as paragraph
            full_text=chunk.text,
            file_path=file_path  # Track actual source file
        )
        stats.sources_created += 1
        logger.info(f"  ✓ Created Source node: {source_id}")
    except Exception as e:
        raise Exception(f"Failed to create Source node: {e}")

    # Step 2: Extract concepts via LLM (with context from recent concepts)
    try:
        extraction_response = extract_concepts(
            text=chunk.text,
            source_id=source_id,
            existing_concepts=existing_concepts
        )
        extraction = extraction_response["result"]
        extraction_tokens = extraction_response.get("tokens", 0)
        stats.extraction_tokens += extraction_tokens

        logger.info(f"  ✓ Extracted {len(extraction['concepts'])} concepts, "
                    f"{len(extraction['instances'])} instances, "
                    f"{len(extraction['relationships'])} relationships")
    except Exception as e:
        # Log full error for debugging
        logger.error(f"  ✗ Extraction failed: {str(e)}")
        import traceback
        traceback.print_exc()
        raise Exception(f"Failed to extract concepts: {e}")

    # Step 3: Process each concept

    # Track concept processing results for summary
    new_concepts = []
    matched_concepts = []
    failed_concepts = []

    # Map LLM concept_ids to actual concept_ids for relationship processing
    concept_id_map = {}

    # Pre-populate with existing concepts so LLM can reference them in relationships
    for existing in existing_concepts:
        # Existing concepts already have their actual IDs
        concept_id_map[existing["concept_id"]] = existing["concept_id"]

    for concept in extraction["concepts"]:
        llm_concept_id = concept["concept_id"]  # LLM-provided ID (may not be unique)
        label = concept["label"]
        search_terms = concept.get("search_terms", [])

        # Generate embedding via unified embedding worker
        # This automatically handles queueing for local providers
        try:
            embedding_worker = get_embedding_worker()
            if embedding_worker is None:
                raise RuntimeError("Embedding worker not initialized")

            embedding_response = embedding_worker.generate_concept_embedding(label)
            embedding = embedding_response["embedding"]
            embedding_tokens = embedding_response.get("tokens", 0)
            stats.embedding_tokens += embedding_tokens
        except Exception as e:
            failed_concepts.append({"label": label, "reason": f"embedding: {e}"})
            # Always log embedding failures (critical errors, not just verbose output)
            logger.error(f"  ✗ Embedding generation failed for '{label}': {e}")
            continue

        # Vector search for similar concepts
        try:
            matches = age_client.vector_search(
                embedding=embedding,
                threshold=0.85,
                top_k=5
            )

            if matches:
                # Link to existing concept
                actual_concept_id = matches[0]["concept_id"]
                similarity = matches[0]["similarity"]

                matched_concepts.append({
                    "label": label,
                    "matched_to": matches[0]["label"],
                    "similarity": similarity
                })

                age_client.link_concept_to_source(actual_concept_id, source_id)
                stats.concepts_linked += 1

                # Map LLM ID to actual ID for relationships
                concept_id_map[llm_concept_id] = actual_concept_id
            else:
                # Create new concept with unique ID
                actual_concept_id = f"{source_id}_{uuid.uuid4().hex[:8]}"

                age_client.create_concept_node(
                    concept_id=actual_concept_id,
                    label=label,
                    embedding=embedding,
                    search_terms=search_terms
                )
                age_client.link_concept_to_source(actual_concept_id, source_id)
                stats.concepts_created += 1

                new_concepts.append({"label": label, "id": actual_concept_id})

                # Track new concept
                recent_concept_ids.append(actual_concept_id)

            # Map LLM ID to actual ID for instances and relationships
            concept_id_map[llm_concept_id] = actual_concept_id

        except Exception as e:
            failed_concepts.append({"label": label, "reason": str(e)})
            if verbose:
                logger.warning(f"  ⚠ Failed: {label}")
            continue

    # Report concept processing results
    total_concepts = len(extraction["concepts"])
    successful_concepts = len(new_concepts) + len(matched_concepts)
    failed_count = len(failed_concepts)

    if failed_count > 0:
        logger.warning(f"  ⚠ {failed_count}/{total_concepts} concepts failed processing")
        if failed_count == total_concepts:
            # All concepts failed - this is a critical error
            failure_reasons = {}
            for fc in failed_concepts:
                reason = fc["reason"].split(":")[0]  # Extract category (e.g., "embedding")
                failure_reasons[reason] = failure_reasons.get(reason, 0) + 1

            error_summary = ", ".join([f"{count} {reason} failures" for reason, count in failure_reasons.items()])
            raise Exception(
                f"All {total_concepts} concepts failed processing ({error_summary}). "
                "Check embedding model availability and API connectivity."
            )

    # Step 4: Create Instance nodes
    for instance in extraction["instances"]:
        instance_id = f"{source_id}_inst_{uuid.uuid4().hex[:8]}"
        llm_concept_id = instance["concept_id"]
        quote = instance["quote"]

        # Map LLM concept ID to actual concept ID
        actual_concept_id = concept_id_map.get(llm_concept_id)
        if not actual_concept_id:
            logger.warning(f"  ⚠ Skipping instance: concept '{llm_concept_id}' not found")
            continue

        try:
            age_client.create_instance_node(instance_id=instance_id, quote=quote)
            age_client.link_instance_to_concept_and_source(
                instance_id=instance_id,
                concept_id=actual_concept_id,
                source_id=source_id
            )
            stats.instances_created += 1
        except Exception as e:
            logger.warning(f"  ⚠ Failed to create Instance: {e}")
            continue

    # Step 5: Create concept relationships
    for rel in extraction["relationships"]:
        try:
            # Validate required fields exist
            if not all(k in rel for k in ["from_concept_id", "to_concept_id", "relationship_type"]):
                logger.warning(f"  ⚠ Skipping malformed relationship (missing required fields): {rel}")
                continue

            llm_from_id = rel["from_concept_id"]
            llm_to_id = rel["to_concept_id"]
            llm_rel_type = rel["relationship_type"]
            confidence = rel.get("confidence", 1.0)  # Default to 1.0 if missing
            direction_semantics = rel.get("direction_semantics", "outward")  # ADR-049: LLM-determined direction
        except (KeyError, TypeError) as e:
            logger.warning(f"  ⚠ Skipping invalid relationship structure: {e}")
            continue

        # Validate direction_semantics (ADR-049)
        if direction_semantics not in ["outward", "inward", "bidirectional"]:
            logger.warning(f"  ⚠ Invalid direction_semantics '{direction_semantics}' for {llm_rel_type}, defaulting to 'outward'")
            direction_semantics = "outward"

        # Normalize relationship type using Porter Stemmer Enhanced Hybrid Matcher
        # Pass AGEClient so it can query existing edge types from graph
        canonical_type, category, similarity = normalize_relationship_type(
            llm_rel_type,
            age_client=age_client
        )

        if not canonical_type:
            # ADR-032: Automatically accept new edge types for vocabulary expansion
            # Instead of skipping, use the LLM's type and mark it as uncategorized
            canonical_type = llm_rel_type.strip().upper()
            category = "llm_generated"
            similarity = 1.0

            # Add to vocabulary table so it propagates to subsequent chunks
            # Generate embedding immediately for vocabulary matching on subsequent chunks
            try:
                provider = get_provider()  # Get current AI provider for embedding generation
                age_client.add_edge_type(
                    relationship_type=canonical_type,
                    category=category,
                    description=f"LLM-generated relationship type from ingestion",
                    added_by="llm_extractor",
                    is_builtin=False,
                    direction_semantics=direction_semantics,  # ADR-049: Store LLM's direction decision
                    ai_provider=provider  # Pass provider for automatic embedding generation
                )
                logger.info(f"  🆕 New edge type discovered: '{canonical_type}' (direction: {direction_semantics}, embedding generated)")
            except Exception as e:
                # If adding fails (e.g., already exists from another worker), continue anyway
                logger.debug(f"  Note: Edge type '{canonical_type}' may already exist: {e}")
        elif similarity < 1.0:
            # Log normalization if it was fuzzy matched
            logger.info(f"  🔧 Normalized '{llm_rel_type}' → '{canonical_type}' ({category}, {similarity:.2f})")

        # Map LLM concept IDs to actual concept IDs
        actual_from_id = concept_id_map.get(llm_from_id)
        actual_to_id = concept_id_map.get(llm_to_id)

        if not actual_from_id or not actual_to_id:
            logger.warning(f"  ⚠ Skipping relationship: concept not found")
            continue

        try:
            age_client.create_concept_relationship(
                from_id=actual_from_id,
                to_id=actual_to_id,
                rel_type=canonical_type,
                category=category,
                confidence=confidence
            )
            stats.relationships_created += 1
        except Exception as e:
            logger.warning(f"  ⚠ Failed to create relationship: {e}")
            continue

    # Log verbose summary
    if verbose:
        logger.info(f"\n{'-'*70}")
        logger.info("📊 CHUNK SUMMARY")
        logger.info(f"{'-'*70}")

        # Calculate hit rate
        total_concepts = len(new_concepts) + len(matched_concepts)
        if total_concepts > 0:
            hit_rate = (len(matched_concepts) / total_concepts) * 100
            logger.info(f"\n📈 VECTOR SEARCH PERFORMANCE:")
            logger.info(f"  New concepts (miss):     {len(new_concepts):>3} ({100-hit_rate:>5.1f}%)")
            logger.info(f"  Matched existing (hit):  {len(matched_concepts):>3} ({hit_rate:>5.1f}%)")

            # Show trend indicator
            if hit_rate == 0:
                logger.info(f"  Trend: 🌱 Building foundation - all concepts are new")
            elif hit_rate < 20:
                logger.info(f"  Trend: 📚 Early growth - mostly creating new concepts")
            elif hit_rate < 50:
                logger.info(f"  Trend: 🔗 Connecting ideas - balanced creation and linking")
            elif hit_rate < 80:
                logger.info(f"  Trend: 🕸️  Maturing graph - finding many connections")
            else:
                logger.info(f"  Trend: ✨ Dense graph - highly interconnected")

        if new_concepts:
            logger.info(f"\n✨ NEW CONCEPTS ({len(new_concepts)}):")
            for c in new_concepts[:5]:  # Show first 5
                logger.info(f"  • {c['label']}")
            if len(new_concepts) > 5:
                logger.info(f"  ... and {len(new_concepts) - 5} more")

        if matched_concepts:
            logger.info(f"\n🔗 LINKED TO EXISTING ({len(matched_concepts)}):")
            for c in matched_concepts[:5]:  # Show first 5
                sim_pct = int(c['similarity'] * 100)
                logger.info(f"  • '{c['label']}' → '{c['matched_to']}' ({sim_pct}%)")
            if len(matched_concepts) > 5:
                logger.info(f"  ... and {len(matched_concepts) - 5} more")

        if failed_concepts:
            logger.info(f"\n⚠️  FAILED ({len(failed_concepts)}):")
            for c in failed_concepts[:3]:  # Show max 3 failures
                logger.info(f"  • {c['label']}")

        logger.info(f"\n📝 Instances: {len([i for i in extraction['instances'] if concept_id_map.get(i['concept_id'])])}")
        logger.info(f"🔀 Relationships: {len([r for r in extraction['relationships'] if concept_id_map.get(r['from_concept_id']) and concept_id_map.get(r['to_concept_id'])])}")
        logger.info(f"{'-'*70}\n")

    return recent_concept_ids
