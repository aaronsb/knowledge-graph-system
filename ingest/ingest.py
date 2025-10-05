#!/usr/bin/env python3
"""
Main ingestion script for knowledge graph system.

Usage:
    python ingest.py <filepath> --document-name "Document Name"

Ingests text files into Neo4j knowledge graph by:
1. Parsing documents into paragraphs
2. Extracting concepts using Claude LLM
3. Creating graph nodes and relationships
4. Performing vector similarity search to link concepts
"""

import os
import sys
import argparse
import uuid
from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

from ingest.parser import parse_text_file
from ingest.neo4j_client import Neo4jClient
from ingest.llm_extractor import extract_concepts, generate_embedding


class IngestionStats:
    """Track ingestion statistics."""

    def __init__(self):
        self.paragraphs_processed = 0
        self.sources_created = 0
        self.concepts_created = 0
        self.concepts_linked = 0
        self.instances_created = 0
        self.relationships_created = 0

    def print_summary(self):
        """Print ingestion summary."""
        print("\n" + "=" * 50)
        print("INGESTION SUMMARY")
        print("=" * 50)
        print(f"Paragraphs processed:    {self.paragraphs_processed}")
        print(f"Source nodes created:    {self.sources_created}")
        print(f"Concept nodes created:   {self.concepts_created}")
        print(f"Concepts linked (reuse): {self.concepts_linked}")
        print(f"Instance nodes created:  {self.instances_created}")
        print(f"Relationships created:   {self.relationships_created}")
        print("=" * 50)


def process_paragraph(
    paragraph_text: str,
    paragraph_num: int,
    document_name: str,
    neo4j_client: Neo4jClient,
    stats: IngestionStats,
    existing_concepts: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Process a single paragraph: create source, extract concepts, create graph nodes.

    Args:
        paragraph_text: Text content of the paragraph
        paragraph_num: Paragraph number in document
        document_name: Name of the source document
        neo4j_client: Neo4j client instance
        stats: Statistics tracker
        existing_concepts: List of existing concepts from previous paragraphs

    Returns:
        List of newly created concepts (to add to existing_concepts)

    Raises:
        Exception: If processing fails
    """
    # Generate source ID
    source_id = f"{document_name.replace(' ', '_').lower()}_p{paragraph_num}"

    print(f"\n[Paragraph {paragraph_num}] Processing...")

    # Step 1: Create Source node
    try:
        neo4j_client.create_source_node(
            source_id=source_id,
            document=document_name,
            paragraph=paragraph_num,
            full_text=paragraph_text
        )
        stats.sources_created += 1
        print(f"  ✓ Created Source node: {source_id}")
    except Exception as e:
        raise Exception(f"Failed to create Source node: {e}")

    # Step 2: Extract concepts via LLM
    try:
        extraction = extract_concepts(
            text=paragraph_text,
            source_id=source_id,
            existing_concepts=existing_concepts
        )
        print(f"  ✓ Extracted {len(extraction['concepts'])} concepts, "
              f"{len(extraction['instances'])} instances, "
              f"{len(extraction['relationships'])} relationships")
    except Exception as e:
        raise Exception(f"Failed to extract concepts: {e}")

    new_concepts = []

    # Step 3: Process each concept
    for concept in extraction["concepts"]:
        concept_id = concept["concept_id"]
        label = concept["label"]
        search_terms = concept.get("search_terms", [])

        # Generate embedding for the concept label
        try:
            embedding = generate_embedding(label)
        except Exception as e:
            print(f"  ⚠ Failed to generate embedding for '{label}': {e}")
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
                existing_concept_id = matches[0]["concept_id"]
                similarity = matches[0]["similarity"]
                print(f"  → Matched '{label}' to existing concept "
                      f"'{matches[0]['label']}' (similarity: {similarity:.2f})")

                neo4j_client.link_concept_to_source(existing_concept_id, source_id)
                stats.concepts_linked += 1

                # Use existing concept_id for instances
                concept_id = existing_concept_id
            else:
                # Create new concept
                neo4j_client.create_concept_node(
                    concept_id=concept_id,
                    label=label,
                    embedding=embedding,
                    search_terms=search_terms
                )
                neo4j_client.link_concept_to_source(concept_id, source_id)
                stats.concepts_created += 1
                print(f"  ✓ Created Concept: {label} ({concept_id})")

                # Track new concept
                new_concepts.append({
                    "concept_id": concept_id,
                    "label": label
                })

        except Exception as e:
            print(f"  ⚠ Failed to process concept '{label}': {e}")
            continue

    # Step 4: Create Instance nodes and link them
    for instance in extraction["instances"]:
        # Generate globally unique instance ID (ignore LLM-provided ID)
        instance_id = f"{source_id}_inst_{uuid.uuid4().hex[:8]}"
        concept_id = instance["concept_id"]
        quote = instance["quote"]

        try:
            neo4j_client.create_instance_node(
                instance_id=instance_id,
                quote=quote
            )

            neo4j_client.link_instance_to_concept_and_source(
                instance_id=instance_id,
                concept_id=concept_id,
                source_id=source_id
            )
            stats.instances_created += 1

        except Exception as e:
            print(f"  ⚠ Failed to create Instance: {e}")
            continue

    # Step 5: Create concept relationships
    for rel in extraction["relationships"]:
        from_id = rel["from_concept_id"]
        to_id = rel["to_concept_id"]
        rel_type = rel["relationship_type"]
        confidence = rel["confidence"]

        try:
            neo4j_client.create_concept_relationship(
                from_id=from_id,
                to_id=to_id,
                rel_type=rel_type,
                confidence=confidence
            )
            stats.relationships_created += 1

        except Exception as e:
            print(f"  ⚠ Failed to create relationship {from_id} -{rel_type}-> {to_id}: {e}")
            continue

    return new_concepts


def main():
    """Main ingestion entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest text documents into Neo4j knowledge graph"
    )
    parser.add_argument(
        "filepath",
        help="Path to the text file to ingest"
    )
    parser.add_argument(
        "--document-name",
        required=True,
        help="Name/title of the document"
    )

    args = parser.parse_args()

    # Load environment variables
    load_dotenv()

    # Validate file exists
    if not Path(args.filepath).exists():
        print(f"Error: File not found: {args.filepath}")
        sys.exit(1)

    print("=" * 50)
    print("KNOWLEDGE GRAPH INGESTION")
    print("=" * 50)
    print(f"Document: {args.document_name}")
    print(f"File: {args.filepath}")

    # Parse document into paragraphs
    try:
        paragraphs = parse_text_file(args.filepath)
        print(f"\n✓ Parsed {len(paragraphs)} paragraphs")
    except Exception as e:
        print(f"Error parsing file: {e}")
        sys.exit(1)

    # Initialize Neo4j client
    try:
        neo4j_client = Neo4jClient()
        print("✓ Connected to Neo4j")
    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
        sys.exit(1)

    # Initialize statistics tracker
    stats = IngestionStats()

    # Track existing concepts across paragraphs
    existing_concepts: List[Dict[str, Any]] = []

    # Process each paragraph
    try:
        with neo4j_client:
            for idx, paragraph in enumerate(paragraphs, start=1):
                stats.paragraphs_processed += 1

                new_concepts = process_paragraph(
                    paragraph_text=paragraph,
                    paragraph_num=idx,
                    document_name=args.document_name,
                    neo4j_client=neo4j_client,
                    stats=stats,
                    existing_concepts=existing_concepts
                )

                # Add new concepts to tracking list
                existing_concepts.extend(new_concepts)

    except KeyboardInterrupt:
        print("\n\n⚠ Ingestion interrupted by user")
        stats.print_summary()
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Ingestion failed: {e}")
        stats.print_summary()
        sys.exit(1)

    # Print summary
    stats.print_summary()
    print("\n✓ Ingestion completed successfully")


if __name__ == "__main__":
    main()
