#!/usr/bin/env python3
"""
Measure Semantic Roles for Vocabulary Types (Dynamic Analysis)

Phase 1 of ADR-065 semantic role classification: Measure current semantic
role patterns for vocabulary types by sampling edges and calculating grounding
dynamically.

Philosophy (Bounded Locality + Satisficing):
- Grounding is calculated at query time with limited recursion depth
- Perfect knowledge requires infinite computation (Gödel incompleteness)
- We satisfice: sample edges, calculate bounded grounding, estimate patterns
- Each run is a "measurement" - results are temporal, observer-dependent
- Larger graphs → sampling becomes more important (avoid computational churn)

Semantic Roles (Estimated from Sampled Edges):
- AFFIRMATIVE: Consistently high grounding (avg > 0.8)
- CONTESTED: Mixed grounding (0.2 <= avg <= 0.8)
- CONTRADICTORY: Consistently low/negative grounding (avg < -0.5)
- HISTORICAL: Explicitly temporal vocabulary (detected by name)

This is a MEASUREMENT tool, not a storage tool. Results reflect the graph
state at the moment of observation. Re-running will give different results
as the graph evolves.

Usage:
    # Measure current state (default: 100 edge sample per type)
    python -m operator.admin.calculate_vocab_semantic_roles

    # Larger sample for more precision
    python -m operator.admin.calculate_vocab_semantic_roles --sample-size 500

    # Detailed output with uncertainty metrics
    python -m operator.admin.calculate_vocab_semantic_roles --verbose
"""

import argparse
import sys
from pathlib import Path
from statistics import mean, stdev
from typing import Dict, List, Tuple
import json
from datetime import datetime
import random

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.lib.console import Console
from api.lib.config import Config
from api.api.lib.age_client import AGEClient


def classify_semantic_role(
    vocab_type: str,
    grounding_stats: Dict
) -> Tuple[str, str]:
    """
    Estimate semantic role based on measured grounding patterns.

    Note: This is a MEASUREMENT, not a classification. Results are temporal
    and observer-dependent (sample-based, bounded calculation).

    Returns:
        (role, rationale)
    """
    avg_grounding = grounding_stats.get('avg_grounding', 0.0)
    measured = grounding_stats.get('measured_concepts', 0)
    sampled = grounding_stats.get('sampled_edges', 0)
    total = grounding_stats.get('total_edges', 0)

    # Historical detection (name-based heuristic)
    historical_markers = [
        'WAS', 'WERE', 'HAD', 'HISTORICAL', 'FORMER', 'PREVIOUS',
        'PAST', 'ANCIENT', 'ORIGINALLY'
    ]
    if any(marker in vocab_type.upper() for marker in historical_markers):
        return (
            "HISTORICAL",
            f"Temporal marker detected in name: {vocab_type}"
        )

    # Insufficient measurement
    if measured < 3:
        return (
            "INSUFFICIENT_DATA",
            f"Only {measured} successful measurements from {sampled} sampled edges (total: {total})"
        )

    # Affirmative: Consistently high grounding
    if avg_grounding > 0.8:
        return (
            "AFFIRMATIVE",
            f"High avg grounding ({avg_grounding:.3f}) from {measured} measurements ({sampled}/{total} edges sampled)"
        )

    # Contradictory: Consistently low/negative grounding
    if avg_grounding < -0.5:
        return (
            "CONTRADICTORY",
            f"Low avg grounding ({avg_grounding:.3f}) from {measured} measurements ({sampled}/{total} edges sampled)"
        )

    # Contested: Mixed grounding
    if 0.2 <= avg_grounding <= 0.8:
        return (
            "CONTESTED",
            f"Mixed grounding ({avg_grounding:.3f}) from {measured} measurements ({sampled}/{total} edges sampled)"
        )

    # Default: Unclassified
    return (
        "UNCLASSIFIED",
        f"Grounding pattern ({avg_grounding:.3f}) doesn't fit known roles ({measured} measurements)"
    )


def calculate_grounding_stats(
    client,
    vocab_type: str,
    sample_size: int = 100
) -> Dict:
    """
    Measure grounding statistics for a vocabulary type by sampling edges.

    Philosophy: We don't analyze ALL edges (computationally expensive, mostly churn).
    Instead, we sample N edges and calculate grounding dynamically for target concepts.
    This gives us an estimate with bounded computational cost.

    Args:
        client: AGEClient instance
        vocab_type: Vocabulary relationship type to analyze
        sample_size: Maximum number of edges to sample

    Returns:
        {
            'total_edges': int,          # Total edges of this type in graph
            'sampled_edges': int,        # Number of edges sampled
            'measured_concepts': int,    # Concepts with successful grounding calculation
            'avg_grounding': float,      # Mean grounding of sampled targets
            'std_grounding': float,      # Standard deviation
            'max_grounding': float,      # Maximum observed
            'min_grounding': float,      # Minimum observed
            'grounding_distribution': [float, ...],  # All measured values
            'measurement_timestamp': str  # When this measurement was taken
        }
    """
    try:
        # First, get total edge count and sample concept IDs
        query = f"""
            MATCH (c1:Concept)-[r:{vocab_type}]->(c2:Concept)
            RETURN c2.concept_id as target_id
        """

        results = client._execute_cypher(query)
        total_edges = len(results)

        if total_edges == 0:
            return {
                'total_edges': 0,
                'sampled_edges': 0,
                'measured_concepts': 0,
                'avg_grounding': 0.0,
                'std_grounding': 0.0,
                'max_grounding': 0.0,
                'min_grounding': 0.0,
                'grounding_distribution': [],
                'measurement_timestamp': datetime.now().isoformat()
            }

        # Sample edges (or take all if fewer than sample_size)
        sample = results if total_edges <= sample_size else random.sample(results, sample_size)
        sampled_count = len(sample)

        # Calculate grounding dynamically for each sampled target concept
        grounding_values = []
        for row in sample:
            target_id = row.get('target_id')
            if not target_id:
                continue

            try:
                # Dynamic grounding calculation (bounded recursion)
                grounding = client.calculate_grounding_strength_semantic(target_id)
                if grounding is not None:
                    grounding_values.append(float(grounding))
            except Exception as e:
                # Skip concepts where grounding calculation fails
                continue

        if not grounding_values:
            return {
                'total_edges': total_edges,
                'sampled_edges': sampled_count,
                'measured_concepts': 0,
                'avg_grounding': 0.0,
                'std_grounding': 0.0,
                'max_grounding': 0.0,
                'min_grounding': 0.0,
                'grounding_distribution': [],
                'measurement_timestamp': datetime.now().isoformat()
            }

        return {
            'total_edges': total_edges,
            'sampled_edges': sampled_count,
            'measured_concepts': len(grounding_values),
            'avg_grounding': mean(grounding_values),
            'std_grounding': stdev(grounding_values) if len(grounding_values) > 1 else 0.0,
            'max_grounding': max(grounding_values),
            'min_grounding': min(grounding_values),
            'grounding_distribution': grounding_values,
            'measurement_timestamp': datetime.now().isoformat()
        }

    except Exception as e:
        Console.warning(f"Error measuring stats for {vocab_type}: {e}")
        return {
            'total_edges': 0,
            'sampled_edges': 0,
            'measured_concepts': 0,
            'avg_grounding': 0.0,
            'std_grounding': 0.0,
            'max_grounding': 0.0,
            'min_grounding': 0.0,
            'grounding_distribution': [],
            'measurement_timestamp': datetime.now().isoformat()
        }


def get_all_vocab_types(client) -> List[str]:
    """
    Get all unique vocabulary relationship types from the graph.
    """
    query = """
        MATCH (v:VocabType)
        RETURN v.name as name
        ORDER BY v.name
    """

    try:
        results = client._execute_cypher(query)
        return [row['name'] for row in results if row['name']]
    except Exception as e:
        Console.error(f"Error fetching vocabulary types: {e}")
        return []




def print_role_report(
    role_assignments: Dict[str, Tuple[str, Dict, str]],
    verbose: bool = False,
    measurement_time: str = None
):
    """
    Print semantic role measurement report.

    role_assignments: {vocab_type: (role, stats, rationale)}
    """
    Console.section("Semantic Role Measurement Report")

    # Measurement metadata
    if measurement_time:
        Console.info(f"Measurement timestamp: {measurement_time}")
        Console.info("Note: Results are temporal - rerunning will give different values as graph evolves")
        print()

    # Count by role
    role_counts = {}
    total_measured = 0
    total_sampled = 0
    total_edges = 0

    for vocab_type, (role, stats, rationale) in role_assignments.items():
        role_counts[role] = role_counts.get(role, 0) + 1
        total_measured += stats.get('measured_concepts', 0)
        total_sampled += stats.get('sampled_edges', 0)
        total_edges += stats.get('total_edges', 0)

    # Summary
    Console.info("Summary:")
    for role, count in sorted(role_counts.items(), key=lambda x: -x[1]):
        Console.info(f"  {role}: {count}")

    Console.info(f"\nMeasurement scope:")
    Console.info(f"  Total edges in graph: {total_edges:,}")
    Console.info(f"  Sampled edges: {total_sampled:,} ({100*total_sampled/total_edges if total_edges > 0 else 0:.1f}%)")
    Console.info(f"  Successful grounding calculations: {total_measured:,}")

    print()

    # Detailed breakdown
    for role in sorted(role_counts.keys()):
        Console.header(f"\n{role} ({role_counts[role]})")

        for vocab_type, (r, stats, rationale) in role_assignments.items():
            if r != role:
                continue

            total = stats.get('total_edges', 0)
            sampled = stats.get('sampled_edges', 0)
            measured = stats.get('measured_concepts', 0)
            avg_grounding = stats.get('avg_grounding', 0.0)

            print(f"  • {vocab_type}")
            print(f"    {measured} measurements from {sampled}/{total} edges | avg grounding: {avg_grounding:+.3f}")

            if verbose:
                print(f"    Rationale: {rationale}")
                std_grounding = stats.get('std_grounding', 0.0)
                min_grounding = stats.get('min_grounding', 0.0)
                max_grounding = stats.get('max_grounding', 0.0)
                timestamp = stats.get('measurement_timestamp', 'unknown')
                print(f"    Range: [{min_grounding:+.3f}, {max_grounding:+.3f}] | std: {std_grounding:.3f}")
                print(f"    Measured at: {timestamp}")

            print()


def main():
    parser = argparse.ArgumentParser(
        description="Measure semantic roles for vocabulary types (dynamic analysis)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Semantic Roles (Estimated from Measurements):
  AFFIRMATIVE    - Consistently high grounding (avg > 0.8)
  CONTESTED      - Mixed grounding (0.2 <= avg <= 0.8)
  CONTRADICTORY  - Consistently low/negative grounding (avg < -0.5)
  HISTORICAL     - Temporal vocabulary (detected by name)

Philosophy:
  This is a MEASUREMENT tool, not a storage tool. Grounding is calculated
  dynamically at query time using bounded recursion. We sample edges and
  calculate grounding for target concepts to estimate patterns. Results
  are temporal and will change as the graph evolves.

Examples:
  # Measure current state (100 edge sample per type)
  python -m operator.admin.calculate_vocab_semantic_roles

  # Larger sample for more precision (slower)
  python -m operator.admin.calculate_vocab_semantic_roles --sample-size 500

  # Detailed analysis with uncertainty metrics
  python -m operator.admin.calculate_vocab_semantic_roles --verbose
        """
    )

    parser.add_argument('--sample-size', type=int, default=100,
                       help='Maximum edges to sample per vocabulary type (default: 100)')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed statistics and uncertainty metrics')
    parser.add_argument('--store', action='store_true',
                       help='Store semantic role and grounding stats as VocabType properties (ADR-065 Phase 2)')

    args = parser.parse_args()

    Console.section("Vocabulary Semantic Role Measurement")

    # Measurement start time
    measurement_start = datetime.now().isoformat()

    # Connect to database
    try:
        client = AGEClient()
        Console.success("✓ Connected to Apache AGE")
    except Exception as e:
        Console.error(f"✗ Cannot connect to Apache AGE database: {e}")
        sys.exit(1)

    # Get all vocabulary types
    Console.info("Fetching vocabulary types...")
    vocab_types = get_all_vocab_types(client)

    if not vocab_types:
        Console.warning("No vocabulary types found in database")
        sys.exit(0)

    Console.info(f"Found {len(vocab_types)} vocabulary types")
    Console.info(f"Sample size: {args.sample_size} edges per type")
    Console.info(f"Starting measurement at {measurement_start}\n")

    # Measure roles for each type
    Console.info("Measuring grounding patterns (this may take a while)...")
    role_assignments = {}

    for i, vocab_type in enumerate(vocab_types, 1):
        if i % 50 == 0:
            Console.info(f"  Progress: {i}/{len(vocab_types)} vocabulary types measured...")

        stats = calculate_grounding_stats(client, vocab_type, sample_size=args.sample_size)
        role, rationale = classify_semantic_role(vocab_type, stats)
        role_assignments[vocab_type] = (role, stats, rationale)

    # Store results if requested (ADR-065 Phase 2)
    if args.store:
        Console.info("\n📝 Storing semantic roles to VocabType nodes...")
        stored_count = 0

        for vocab_type, (role, stats, rationale) in role_assignments.items():
            try:
                # Store semantic_role and grounding_stats as VocabType properties
                query = """
                    MATCH (v:VocabType {name: $vocab_type})
                    SET v.semantic_role = $role,
                        v.grounding_stats = $stats,
                        v.role_measured_at = $timestamp
                """
                client._execute_cypher(query, {
                    "vocab_type": vocab_type,
                    "role": role,
                    "stats": {
                        "avg_grounding": stats.get('avg_grounding', 0.0),
                        "std_grounding": stats.get('std_grounding', 0.0),
                        "min_grounding": stats.get('min_grounding', 0.0),
                        "max_grounding": stats.get('max_grounding', 0.0),
                        "measured_concepts": stats.get('measured_concepts', 0),
                        "sampled_edges": stats.get('sampled_edges', 0),
                        "total_edges": stats.get('total_edges', 0)
                    },
                    "timestamp": measurement_start
                })
                stored_count += 1

                if stored_count % 50 == 0:
                    Console.info(f"  Progress: {stored_count}/{len(role_assignments)} roles stored...")

            except Exception as e:
                Console.warning(f"  Failed to store role for {vocab_type}: {e}")

        Console.success(f"✓ Stored {stored_count}/{len(role_assignments)} semantic roles to VocabType nodes")
        Console.info("  Phase 2 query filtering now available via GraphQueryFacade.match_concept_relationships()")

    # Print report
    print()
    print_role_report(role_assignments, verbose=args.verbose, measurement_time=measurement_start)

    # Measurement complete
    if args.store:
        Console.info("\n💡 Measurement complete and stored. Results are temporal - rerun with --store to remeasure.")
    else:
        Console.info("\n💡 Measurement complete. Results are temporal - rerun to remeasure as graph evolves.")
        Console.info("   Use --store flag to persist semantic roles for Phase 2 query filtering.")


if __name__ == '__main__':
    main()
