#!/usr/bin/env python3
"""
Calculate and Store Grounding Strength for All Concepts

Batch process to calculate grounding strength for all concepts in the graph
and persist the values to enable faster queries and epistemic status measurement.

Grounding calculation uses polarity axis projection (ADR-044) to determine
how well-supported each concept is based on incoming relationship semantics.

Usage:
    python -m operator.admin.calculate_concept_grounding [--batch-size N] [--dry-run]
"""

import sys
from pathlib import Path
import argparse
from typing import List, Dict, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.api.lib.age_client import AGEClient
from api.lib.console import Console


def get_all_concepts(client: AGEClient, batch_size: int = 100, offset: int = 0) -> List[Dict]:
    """Fetch concepts in batches for memory efficiency."""
    query = f"""
        MATCH (c:Concept)
        RETURN c.concept_id as concept_id, c.label as label
        ORDER BY c.concept_id
        SKIP {offset}
        LIMIT {batch_size}
    """
    return client._execute_cypher(query)


def calculate_and_store_grounding(
    client: AGEClient,
    concept_id: str,
    dry_run: bool = False
) -> Tuple[bool, float]:
    """
    Calculate grounding and store to concept node.

    Returns:
        (success: bool, grounding: float)
    """
    try:
        # Calculate grounding using polarity axis projection
        grounding = client.calculate_grounding_strength_semantic(concept_id)

        if not dry_run:
            # Store grounding in concept node
            update_query = """
                MATCH (c:Concept {concept_id: $concept_id})
                SET c.grounding_strength = $grounding
                RETURN c.concept_id
            """
            result = client._execute_cypher(
                update_query,
                params={
                    "concept_id": concept_id,
                    "grounding": grounding
                }
            )

            if not result:
                Console.error(f"Failed to store grounding for {concept_id}")
                return (False, grounding)

        return (True, grounding)

    except Exception as e:
        Console.error(f"Error calculating grounding for {concept_id}: {e}")
        return (False, 0.0)


def main():
    parser = argparse.ArgumentParser(
        description="Calculate and store grounding strength for all concepts"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of concepts to process per batch (default: 100)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Calculate grounding but don't store to database"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit total concepts processed (for testing)"
    )

    args = parser.parse_args()

    Console.section("Concept Grounding Calculation")

    if args.dry_run:
        Console.warning("DRY RUN MODE - No database updates will be made")

    # Connect to database
    try:
        client = AGEClient()
        Console.success("✓ Connected to Apache AGE")
    except Exception as e:
        Console.error(f"✗ Cannot connect to database: {e}")
        sys.exit(1)

    # Get total concept count
    total_query = "MATCH (c:Concept) RETURN count(c) as total"
    total_result = client._execute_cypher(total_query)
    total_concepts = total_result[0]['total'] if total_result else 0

    Console.info(f"Total concepts in graph: {total_concepts}")

    if args.limit:
        total_concepts = min(total_concepts, args.limit)
        Console.info(f"Limiting processing to {total_concepts} concepts")

    # Process in batches
    offset = 0
    processed = 0
    successful = 0
    failed = 0

    grounding_distribution = {
        "strong_positive": 0,    # > 0.7
        "moderate_positive": 0,  # 0.3 to 0.7
        "weak_positive": 0,      # 0 to 0.3
        "weak_negative": 0,      # -0.3 to 0
        "moderate_negative": 0,  # -0.7 to -0.3
        "strong_negative": 0,    # < -0.7
    }

    while offset < total_concepts:
        batch = get_all_concepts(client, args.batch_size, offset)

        if not batch:
            break

        Console.info(f"\nProcessing batch: {offset + 1} to {offset + len(batch)}")

        for concept in batch:
            concept_id = concept['concept_id']
            label = concept.get('label', 'Unknown')

            success, grounding = calculate_and_store_grounding(
                client,
                concept_id,
                dry_run=args.dry_run
            )

            if success:
                successful += 1

                # Track distribution
                if grounding > 0.7:
                    grounding_distribution["strong_positive"] += 1
                elif grounding > 0.3:
                    grounding_distribution["moderate_positive"] += 1
                elif grounding >= 0:
                    grounding_distribution["weak_positive"] += 1
                elif grounding >= -0.3:
                    grounding_distribution["weak_negative"] += 1
                elif grounding >= -0.7:
                    grounding_distribution["moderate_negative"] += 1
                else:
                    grounding_distribution["strong_negative"] += 1

                status = "✓ Calculated" if args.dry_run else "✓ Stored"
                Console.success(f"  {status}: {label[:60]} (g: {grounding:.3f})")
            else:
                failed += 1
                Console.error(f"  ✗ Failed: {label[:60]}")

            processed += 1

            # Progress indicator
            if processed % 50 == 0:
                progress = (processed / total_concepts) * 100
                Console.info(f"Progress: {processed}/{total_concepts} ({progress:.1f}%)")

        offset += len(batch)

        # Check if we've hit the limit
        if args.limit and processed >= args.limit:
            break

    # Summary
    Console.section("Summary")
    Console.info(f"Total processed: {processed}")
    Console.success(f"Successful: {successful}")
    if failed > 0:
        Console.error(f"Failed: {failed}")

    Console.section("Grounding Distribution")
    Console.info(f"  Strong positive (>0.7):     {grounding_distribution['strong_positive']}")
    Console.info(f"  Moderate positive (0.3-0.7): {grounding_distribution['moderate_positive']}")
    Console.info(f"  Weak positive (0-0.3):       {grounding_distribution['weak_positive']}")
    Console.info(f"  Weak negative (-0.3-0):      {grounding_distribution['weak_negative']}")
    Console.info(f"  Moderate negative (-0.7--0.3): {grounding_distribution['moderate_negative']}")
    Console.info(f"  Strong negative (<-0.7):     {grounding_distribution['strong_negative']}")

    if not args.dry_run:
        Console.success(f"\n✓ Grounding values stored to {successful} concept nodes")
        Console.info("Epistemic status measurement will now work correctly!")
    else:
        Console.info("\nDry run complete. Use without --dry-run to store values.")

    client.close()


if __name__ == '__main__':
    main()
