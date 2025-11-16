#!/usr/bin/env python3
"""
Calculate Semantic Roles for Vocabulary Types

Phase 1 of ADR-065 semantic role classification: Calculate semantic roles
for vocabulary relationship types based on grounding strength patterns.

Semantic Roles:
- AFFIRMATIVE: Consistently high grounding (avg > 0.8)
- CONTESTED: Mixed grounding (0.2 <= avg <= 0.8)
- CONTRADICTORY: Consistently low/negative grounding (avg < -0.5)
- HISTORICAL: Explicitly temporal vocabulary (detected by name)

This is a read-only analysis tool. Use --apply to actually store roles.

Usage:
    # Analyze without modifying database
    python -m operator.admin.calculate_vocab_semantic_roles

    # Apply roles to VocabType nodes
    python -m operator.admin.calculate_vocab_semantic_roles --apply

    # Detailed output
    python -m operator.admin.calculate_vocab_semantic_roles --verbose
"""

import argparse
import sys
from pathlib import Path
from statistics import mean, stdev
from typing import Dict, List, Tuple
import json

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
    Classify semantic role based on grounding patterns.

    Returns:
        (role, rationale)
    """
    avg_grounding = grounding_stats.get('avg_grounding', 0.0)
    edge_count = grounding_stats.get('edge_count', 0)

    # Historical detection (name-based)
    historical_markers = [
        'WAS', 'WERE', 'HAD', 'HISTORICAL', 'FORMER', 'PREVIOUS',
        'PAST', 'ANCIENT', 'ORIGINALLY'
    ]
    if any(marker in vocab_type.upper() for marker in historical_markers):
        return (
            "HISTORICAL",
            f"Temporal marker detected in name: {vocab_type}"
        )

    # Insufficient data
    if edge_count < 3:
        return (
            "INSUFFICIENT_DATA",
            f"Only {edge_count} edges - need at least 3 for classification"
        )

    # Affirmative: Consistently high grounding
    if avg_grounding > 0.8:
        return (
            "AFFIRMATIVE",
            f"High avg grounding ({avg_grounding:.3f}) across {edge_count} edges"
        )

    # Contradictory: Consistently low/negative grounding
    if avg_grounding < -0.5:
        return (
            "CONTRADICTORY",
            f"Low avg grounding ({avg_grounding:.3f}) across {edge_count} edges"
        )

    # Contested: Mixed grounding
    if 0.2 <= avg_grounding <= 0.8:
        return (
            "CONTESTED",
            f"Mixed grounding ({avg_grounding:.3f}) across {edge_count} edges"
        )

    # Default: Unclassified
    return (
        "UNCLASSIFIED",
        f"Grounding pattern ({avg_grounding:.3f}) doesn't fit known roles"
    )


def calculate_grounding_stats(
    client,
    vocab_type: str
) -> Dict:
    """
    Calculate grounding statistics for a vocabulary type.

    Returns:
        {
            'edge_count': int,
            'avg_grounding': float,
            'std_grounding': float,
            'max_grounding': float,
            'min_grounding': float,
            'grounding_distribution': [float, ...]
        }
    """
    query = f"""
        MATCH (c1:Concept)-[r:{vocab_type}]->(c2:Concept)
        RETURN
            c1.grounding_strength as from_grounding,
            c2.grounding_strength as to_grounding
    """

    try:
        results = client._execute_cypher(query)

        if not results:
            return {
                'edge_count': 0,
                'avg_grounding': 0.0,
                'std_grounding': 0.0,
                'max_grounding': 0.0,
                'min_grounding': 0.0,
                'grounding_distribution': []
            }

        # Extract grounding values (target concept grounding)
        grounding_values = [
            float(row['to_grounding'])
            for row in results
            if row['to_grounding'] is not None
        ]

        if not grounding_values:
            return {
                'edge_count': len(results),
                'avg_grounding': 0.0,
                'std_grounding': 0.0,
                'max_grounding': 0.0,
                'min_grounding': 0.0,
                'grounding_distribution': []
            }

        return {
            'edge_count': len(grounding_values),
            'avg_grounding': mean(grounding_values),
            'std_grounding': stdev(grounding_values) if len(grounding_values) > 1 else 0.0,
            'max_grounding': max(grounding_values),
            'min_grounding': min(grounding_values),
            'grounding_distribution': grounding_values
        }

    except Exception as e:
        Console.warning(f"Error calculating stats for {vocab_type}: {e}")
        return {
            'edge_count': 0,
            'avg_grounding': 0.0,
            'std_grounding': 0.0,
            'max_grounding': 0.0,
            'min_grounding': 0.0,
            'grounding_distribution': []
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


def apply_semantic_roles(
    client,
    role_assignments: Dict[str, Tuple[str, Dict]]
) -> int:
    """
    Apply semantic role classifications to VocabType nodes.

    Returns:
        Number of nodes updated
    """
    updated = 0

    for vocab_type, (role, stats) in role_assignments.items():
        try:
            # Only apply if role is classified
            if role in ['INSUFFICIENT_DATA', 'UNCLASSIFIED']:
                continue

            # Convert stats dict to JSON string for storage
            stats_json = json.dumps(stats).replace("'", "\\'")

            query = f"""
                MATCH (v:VocabType {{name: '{vocab_type}'}})
                SET v.semantic_role = '{role}',
                    v.grounding_stats = '{stats_json}'
                RETURN v.name as name
            """

            client._execute_cypher(query)
            updated += 1

        except Exception as e:
            Console.warning(f"Error updating {vocab_type}: {e}")

    return updated


def print_role_report(
    role_assignments: Dict[str, Tuple[str, Dict, str]],
    verbose: bool = False
):
    """
    Print semantic role classification report.

    role_assignments: {vocab_type: (role, stats, rationale)}
    """
    Console.section("Semantic Role Classification Report")

    # Count by role
    role_counts = {}
    for vocab_type, (role, stats, rationale) in role_assignments.items():
        role_counts[role] = role_counts.get(role, 0) + 1

    # Summary
    Console.info("Summary:")
    for role, count in sorted(role_counts.items(), key=lambda x: -x[1]):
        Console.info(f"  {role}: {count}")

    print()

    # Detailed breakdown
    for role in sorted(role_counts.keys()):
        Console.header(f"\n{role} ({role_counts[role]})")

        for vocab_type, (r, stats, rationale) in role_assignments.items():
            if r != role:
                continue

            edge_count = stats.get('edge_count', 0)
            avg_grounding = stats.get('avg_grounding', 0.0)

            print(f"  • {vocab_type}")
            print(f"    {edge_count} edges | avg grounding: {avg_grounding:+.3f}")

            if verbose:
                print(f"    Rationale: {rationale}")
                std_grounding = stats.get('std_grounding', 0.0)
                min_grounding = stats.get('min_grounding', 0.0)
                max_grounding = stats.get('max_grounding', 0.0)
                print(f"    Range: [{min_grounding:+.3f}, {max_grounding:+.3f}] | std: {std_grounding:.3f}")

            print()


def main():
    parser = argparse.ArgumentParser(
        description="Calculate semantic roles for vocabulary types",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Semantic Roles:
  AFFIRMATIVE    - Consistently high grounding (avg > 0.8)
  CONTESTED      - Mixed grounding (0.2 <= avg <= 0.8)
  CONTRADICTORY  - Consistently low/negative grounding (avg < -0.5)
  HISTORICAL     - Temporal vocabulary (detected by name)

Examples:
  # Analyze current vocabulary
  python -m operator.admin.calculate_vocab_semantic_roles

  # Apply roles to database
  python -m operator.admin.calculate_vocab_semantic_roles --apply

  # Detailed analysis
  python -m operator.admin.calculate_vocab_semantic_roles --verbose
        """
    )

    parser.add_argument('--apply', action='store_true',
                       help='Apply role classifications to VocabType nodes')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed statistics')

    args = parser.parse_args()

    Console.section("Vocabulary Semantic Role Analysis")

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

    Console.info(f"Found {len(vocab_types)} vocabulary types\n")

    # Calculate roles for each type
    Console.info("Analyzing grounding patterns...")
    role_assignments = {}

    for vocab_type in vocab_types:
        stats = calculate_grounding_stats(client, vocab_type)
        role, rationale = classify_semantic_role(vocab_type, stats)
        role_assignments[vocab_type] = (role, stats, rationale)

    # Print report
    print()
    print_role_report(role_assignments, verbose=args.verbose)

    # Apply if requested
    if args.apply:
        Console.warning("\n🔧 Applying semantic roles to VocabType nodes...")

        # Convert to format expected by apply function
        apply_data = {
            vocab_type: (role, stats)
            for vocab_type, (role, stats, _) in role_assignments.items()
        }

        updated = apply_semantic_roles(client, apply_data)

        if updated > 0:
            Console.success(f"✓ Updated {updated} VocabType nodes with semantic roles")
        else:
            Console.info("No nodes updated (all were unclassified or insufficient data)")
    else:
        Console.info("\n💡 Run with --apply to store these roles in the database")


if __name__ == '__main__':
    main()
