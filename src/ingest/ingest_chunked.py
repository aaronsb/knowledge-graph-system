#!/usr/bin/env python3
"""
Chunked ingestion script for large documents.

Supports:
- Smart chunking with natural boundaries
- Position tracking and checkpointing
- Resume from interruption
- Graph context awareness (recent concepts)

Usage:
    python ingest/ingest_chunked.py <filepath> --document-name "Document Name"
    python ingest/ingest_chunked.py <filepath> --document-name "Name" --resume
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Force unbuffered output for real-time display
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from src.ingest.chunker import SmartChunker, ChunkingConfig, Chunk
from src.ingest.checkpoint import IngestionCheckpoint
from src.ingest.neo4j_client import Neo4jClient
from src.ingest.llm_extractor import extract_concepts, generate_embedding

# Suppress Neo4j notification warnings (they're informational, not errors)
import logging
logging.getLogger("neo4j.notifications").setLevel(logging.ERROR)


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
    chunk: Chunk,
    ontology_name: str,
    filename: str,
    file_path: str,
    neo4j_client: Neo4jClient,
    stats: ChunkedIngestionStats,
    existing_concepts: List[Dict[str, Any]],
    recent_concept_ids: List[str],
    verbose: bool = True
) -> List[str]:
    """
    Process a single chunk: create source, extract concepts, create graph nodes.

    Args:
        chunk: Chunk object to process
        ontology_name: Name of the ontology/collection (shared across documents)
        filename: Unique filename for source tracking
        file_path: Full path to the source file
        neo4j_client: Neo4j client instance
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

    print(f"\n{'='*70}")
    print(f"[Chunk {chunk.chunk_number}] {chunk.word_count} words, "
          f"boundary: {chunk.boundary_type}")
    print(f"{'='*70}")
    sys.stdout.flush()  # Ensure immediate display

    # Step 1: Create Source node
    try:
        neo4j_client.create_source_node(
            source_id=source_id,
            document=ontology_name,  # Ontology name for logical grouping
            paragraph=chunk.chunk_number,  # Using chunk number as paragraph
            full_text=chunk.text,
            file_path=file_path  # Track actual source file
        )
        stats.sources_created += 1
        print(f"  ✓ Created Source node: {source_id}")
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

        print(f"  ✓ Extracted {len(extraction['concepts'])} concepts, "
              f"{len(extraction['instances'])} instances, "
              f"{len(extraction['relationships'])} relationships")
        sys.stdout.flush()  # Show extraction results immediately
    except Exception as e:
        raise Exception(f"Failed to extract concepts: {e}")

    # Step 3: Process each concept
    import uuid

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

        # Generate embedding
        try:
            embedding_response = generate_embedding(label)
            embedding = embedding_response["embedding"]
            embedding_tokens = embedding_response.get("tokens", 0)
            stats.embedding_tokens += embedding_tokens
        except Exception as e:
            failed_concepts.append({"label": label, "reason": f"embedding: {e}"})
            if verbose:
                print(f"  ⚠ Embedding failed: {label}")
            continue

        # Vector search for similar concepts
        try:
            matches = neo4j_client.vector_search(
                embedding=embedding,
                threshold=0.85,
                limit=5
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

                neo4j_client.link_concept_to_source(actual_concept_id, source_id)
                stats.concepts_linked += 1

                # Map LLM ID to actual ID for relationships
                concept_id_map[llm_concept_id] = actual_concept_id
            else:
                # Create new concept with unique ID
                actual_concept_id = f"{source_id}_{uuid.uuid4().hex[:8]}"

                neo4j_client.create_concept_node(
                    concept_id=actual_concept_id,
                    label=label,
                    embedding=embedding,
                    search_terms=search_terms
                )
                neo4j_client.link_concept_to_source(actual_concept_id, source_id)
                stats.concepts_created += 1

                new_concepts.append({"label": label, "id": actual_concept_id})

                # Track new concept
                recent_concept_ids.append(actual_concept_id)

            # Map LLM ID to actual ID for instances and relationships
            concept_id_map[llm_concept_id] = actual_concept_id

        except Exception as e:
            failed_concepts.append({"label": label, "reason": str(e)})
            if verbose:
                print(f"  ⚠ Failed: {label}")
            continue

    # Step 4: Create Instance nodes
    for instance in extraction["instances"]:
        instance_id = f"{source_id}_inst_{uuid.uuid4().hex[:8]}"
        llm_concept_id = instance["concept_id"]
        quote = instance["quote"]

        # Map LLM concept ID to actual concept ID
        actual_concept_id = concept_id_map.get(llm_concept_id)
        if not actual_concept_id:
            print(f"  ⚠ Skipping instance: concept '{llm_concept_id}' not found")
            continue

        try:
            neo4j_client.create_instance_node(instance_id=instance_id, quote=quote)
            neo4j_client.link_instance_to_concept_and_source(
                instance_id=instance_id,
                concept_id=actual_concept_id,
                source_id=source_id
            )
            stats.instances_created += 1
        except Exception as e:
            print(f"  ⚠ Failed to create Instance: {e}")
            continue

    # Step 5: Create concept relationships
    for rel in extraction["relationships"]:
        llm_from_id = rel["from_concept_id"]
        llm_to_id = rel["to_concept_id"]
        rel_type = rel["relationship_type"]
        confidence = rel["confidence"]

        # Map LLM concept IDs to actual concept IDs
        actual_from_id = concept_id_map.get(llm_from_id)
        actual_to_id = concept_id_map.get(llm_to_id)

        if not actual_from_id or not actual_to_id:
            print(f"  ⚠ Skipping relationship: concept not found")
            continue

        try:
            neo4j_client.create_concept_relationship(
                from_id=actual_from_id,
                to_id=actual_to_id,
                rel_type=rel_type,
                confidence=confidence
            )
            stats.relationships_created += 1
        except Exception as e:
            print(f"  ⚠ Failed to create relationship: {e}")
            continue

    # Print verbose summary
    if verbose:
        print(f"\n{'-'*70}")
        print("📊 CHUNK SUMMARY")
        print(f"{'-'*70}")

        # Calculate hit rate
        total_concepts = len(new_concepts) + len(matched_concepts)
        if total_concepts > 0:
            hit_rate = (len(matched_concepts) / total_concepts) * 100
            print(f"\n📈 VECTOR SEARCH PERFORMANCE:")
            print(f"  New concepts (miss):     {len(new_concepts):>3} ({100-hit_rate:>5.1f}%)")
            print(f"  Matched existing (hit):  {len(matched_concepts):>3} ({hit_rate:>5.1f}%)")

            # Show trend indicator
            if hit_rate == 0:
                print(f"  Trend: 🌱 Building foundation - all concepts are new")
            elif hit_rate < 20:
                print(f"  Trend: 📚 Early growth - mostly creating new concepts")
            elif hit_rate < 50:
                print(f"  Trend: 🔗 Connecting ideas - balanced creation and linking")
            elif hit_rate < 80:
                print(f"  Trend: 🕸️  Maturing graph - finding many connections")
            else:
                print(f"  Trend: ✨ Dense graph - highly interconnected")

        if new_concepts:
            print(f"\n✨ NEW CONCEPTS ({len(new_concepts)}):")
            for c in new_concepts[:5]:  # Show first 5
                print(f"  • {c['label']}")
            if len(new_concepts) > 5:
                print(f"  ... and {len(new_concepts) - 5} more")

        if matched_concepts:
            print(f"\n🔗 LINKED TO EXISTING ({len(matched_concepts)}):")
            for c in matched_concepts[:5]:  # Show first 5
                sim_pct = int(c['similarity'] * 100)
                print(f"  • '{c['label']}' → '{c['matched_to']}' ({sim_pct}%)")
            if len(matched_concepts) > 5:
                print(f"  ... and {len(matched_concepts) - 5} more")

        if failed_concepts:
            print(f"\n⚠️  FAILED ({len(failed_concepts)}):")
            for c in failed_concepts[:3]:  # Show max 3 failures
                print(f"  • {c['label']}")

        print(f"\n📝 Instances: {len([i for i in extraction['instances'] if concept_id_map.get(i['concept_id'])])}")
        print(f"🔀 Relationships: {len([r for r in extraction['relationships'] if concept_id_map.get(r['from_concept_id']) and concept_id_map.get(r['to_concept_id'])])}")
        print(f"{'-'*70}\n")
        sys.stdout.flush()  # Ensure summary appears immediately

    return recent_concept_ids


def main():
    """Main chunked ingestion entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest large documents using smart chunking"
    )
    parser.add_argument("filepath", help="Path to the text file to ingest")
    parser.add_argument("--ontology", required=True, help="Ontology/collection name for grouping documents")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--target-words", type=int, default=1000, help="Target words per chunk")
    parser.add_argument("--min-words", type=int, default=800, help="Minimum words per chunk")
    parser.add_argument("--max-words", type=int, default=1500, help="Maximum words per chunk")
    parser.add_argument("--overlap-words", type=int, default=200, help="Overlap between chunks")
    parser.add_argument("--checkpoint-interval", type=int, default=5,
                       help="Save checkpoint every N chunks")

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Get AI provider info for cost calculation
    from src.ingest.ai_providers import get_provider
    try:
        provider = get_provider()
        extraction_model = provider.get_extraction_model()
        embedding_model = provider.get_embedding_model()
    except Exception:
        # If provider fails to initialize, cost calculation will use defaults
        extraction_model = None
        embedding_model = None

    # Validate file exists
    filepath = Path(args.filepath)
    if not filepath.exists():
        print(f"Error: File not found: {args.filepath}")
        sys.exit(1)

    # Extract filename for source tracking (unique per file)
    filename = filepath.stem  # filename without extension

    print("=" * 60)
    print("CHUNKED KNOWLEDGE GRAPH INGESTION")
    print("=" * 60)
    print(f"Ontology: {args.ontology}")
    print(f"File: {args.filepath}")

    # Initialize checkpoint manager
    checkpoint_mgr = IngestionCheckpoint()

    # Check for existing checkpoint (keyed by filename, not ontology)
    start_position = 0
    stats = ChunkedIngestionStats()
    recent_concept_ids = []

    if args.resume:
        checkpoint = checkpoint_mgr.load(filename)
        if checkpoint:
            if checkpoint_mgr.validate(checkpoint):
                start_position = checkpoint["char_position"]
                stats.from_dict(checkpoint["stats"])
                recent_concept_ids = checkpoint["recent_concept_ids"]
                print(f"\n✓ Resuming from checkpoint:")
                print(f"  Position: {start_position:,} characters")
                print(f"  Chunks processed: {stats.chunks_processed}")
            else:
                print("\n⚠ Checkpoint invalid, starting from beginning")
        else:
            print(f"\n⚠ No checkpoint found for '{filename}'")

    # Load full text
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            full_text = f.read()
        print(f"\n✓ Loaded document: {len(full_text):,} characters")
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

    # Configure chunker
    config = ChunkingConfig(
        target_words=args.target_words,
        min_words=args.min_words,
        max_words=args.max_words,
        overlap_words=args.overlap_words
    )

    # Create chunks
    print("\n📊 Chunking document...")
    chunker = SmartChunker(config)
    chunks = chunker.chunk_text(full_text, start_position=start_position)
    print(chunker.get_chunk_summary(chunks))

    if not chunks:
        print("No chunks to process")
        sys.exit(0)

    # Initialize Neo4j client
    try:
        neo4j_client = Neo4jClient()
        print("\n✓ Connected to Neo4j")
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
        sys.exit(1)

    # Process chunks
    print(f"\n🚀 Processing {len(chunks)} chunks...\n")

    try:
        with neo4j_client:
            # Get existing concepts from document for context awareness
            try:
                import sys
                import os

                # Temporarily suppress stderr to hide Neo4j's informational warnings
                old_stderr = sys.stderr
                sys.stderr = open(os.devnull, 'w')

                existing_concepts, has_empty_warnings = neo4j_client.get_document_concepts(
                    document_name=args.ontology,
                    recent_chunks_only=3,  # Last 3 chunks for context
                    warn_on_empty=True
                )

                # Restore stderr
                sys.stderr.close()
                sys.stderr = old_stderr

                # Show friendly message if database was empty
                if len(existing_concepts) == 0:
                    print(f"ℹ️  Database is empty (first ingestion) - all concepts will be new\n")

                print(f"✓ Loaded {len(existing_concepts)} existing concepts for context\n")
            except Exception as e:
                if 'old_stderr' in locals():
                    sys.stderr = old_stderr  # Ensure stderr restored on error
                print(f"⚠ Could not load existing concepts: {e}\n")
                existing_concepts = []
            for idx, chunk in enumerate(chunks):
                stats.chunks_processed += 1

                # Process the chunk
                recent_concept_ids = process_chunk(
                    chunk=chunk,
                    ontology_name=args.ontology,
                    filename=filename,
                    file_path=str(filepath.absolute()),
                    neo4j_client=neo4j_client,
                    stats=stats,
                    existing_concepts=existing_concepts,
                    recent_concept_ids=recent_concept_ids
                )

                # Periodically save checkpoint (keyed by filename, not ontology)
                if (idx + 1) % args.checkpoint_interval == 0:
                    checkpoint_mgr.save(
                        document_name=filename,
                        file_path=str(filepath.absolute()),
                        char_position=chunk.end_char,
                        chunks_processed=stats.chunks_processed,
                        recent_concept_ids=recent_concept_ids,
                        stats=stats.to_dict()
                    )

                # Refresh context from graph every few chunks (by ontology)
                if (idx + 1) % 3 == 0:
                    existing_concepts, _ = neo4j_client.get_document_concepts(
                        document_name=args.ontology,
                        recent_chunks_only=3,
                        warn_on_empty=False  # Don't warn after first check
                    )

    except KeyboardInterrupt:
        print("\n\n⚠ Ingestion interrupted by user")
        # Save checkpoint on interrupt (keyed by filename)
        if chunks and stats.chunks_processed > 0:
            last_chunk = chunks[stats.chunks_processed - 1]
            checkpoint_mgr.save(
                document_name=filename,
                file_path=str(filepath.absolute()),
                char_position=last_chunk.end_char,
                chunks_processed=stats.chunks_processed,
                recent_concept_ids=recent_concept_ids,
                stats=stats.to_dict()
            )
        stats.print_summary(extraction_model=extraction_model, embedding_model=embedding_model)
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Ingestion failed: {e}")
        stats.print_summary(extraction_model=extraction_model, embedding_model=embedding_model)
        sys.exit(1)

    # Clean up checkpoint on successful completion (keyed by filename)
    checkpoint_mgr.delete(filename)

    # Print summary
    stats.print_summary(extraction_model=extraction_model, embedding_model=embedding_model)
    print("\n✓ Ingestion completed successfully")


if __name__ == "__main__":
    main()
