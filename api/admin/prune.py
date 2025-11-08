#!/usr/bin/env python3
"""
Pruning Tool - Remove dangling relationships to keep graph clean

When restoring partial ontologies without stitching, dangling relationships
(pointing to non-existent concepts) remain in the graph. These break traversal
queries and should be removed.

This tool "trims the torn fabric" by cleanly removing dangling relationships.

Usage:
    python -m src.admin.prune
    python -m src.admin.prune --ontology "My Ontology"
    python -m src.admin.prune --dry-run
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.lib.console import Console
from api.lib.config import Config
from api.lib.age_ops import AGEConnection
from api.lib.integrity import DatabaseIntegrity


def main():
    parser = argparse.ArgumentParser(
        description="Prune dangling relationships to keep graph clean",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
What gets pruned:
  - Relationships pointing to concepts that don't exist (no APPEARS_IN)
  - Relationships from orphaned concepts

Why prune:
  - Prevents broken graph traversal queries
  - Keeps semantic structure clean
  - Eliminates "phantom" relationships

When to use:
  - After restoring partial ontology WITHOUT stitching
  - When choosing to keep ontologies strictly isolated
  - To clean up after ontology deletion

Examples:
  # Preview what would be pruned (dry-run)
  python -m src.admin.prune --dry-run

  # Prune entire database
  python -m src.admin.prune

  # Prune specific ontology
  python -m src.admin.prune --ontology "My Ontology"

  # Check integrity first, then prune
  python -m src.admin.check_integrity
  python -m src.admin.prune

Note:
  This is irreversible! Pruned relationships cannot be recovered.
  Use --dry-run first to preview changes.
        """
    )

    parser.add_argument('--ontology', type=str,
                       help='Prune only relationships from specific ontology')
    parser.add_argument('--dry-run', action='store_true',
                       help='Preview what would be pruned without making changes')

    args = parser.parse_args()

    Console.section("Relationship Pruning")

    # Connect to database
    conn = AGEConnection()
    if not conn.test_connection():
        Console.error("✗ Cannot connect to Apache AGE database")
        Console.warning(f"  Check connection: {Config.postgres_host()}:{Config.postgres_port()}")
        sys.exit(1)

    Console.success("✓ Connected to Apache AGE")

    if args.ontology:
        Console.info(f"Scope: Ontology '{args.ontology}'")
    else:
        Console.info("Scope: Entire database")

    if args.dry_run:
        Console.warning("\n[DRY-RUN MODE] No changes will be made\n")

    # Find and prune dangling relationships
    Console.info("Searching for dangling relationships...")
    client = conn.get_client()
    result = DatabaseIntegrity.prune_dangling_relationships(
        client,
        ontology=args.ontology,
        dry_run=args.dry_run
    )

    # Print results
    DatabaseIntegrity.print_pruning_report(result, dry_run=args.dry_run)

    # Confirmation for actual pruning
    if not args.dry_run and result["total_pruned"] > 0:
        Console.warning("\n💡 Next steps:")
        print("  • Verify graph health: python -m src.admin.check_integrity")
        print("  • Query concepts: python cli.py search \"your query\"")
        print("  • Test traversal: python cli.py related <concept-id>")

    conn.close()

    # Exit code based on results
    if result["total_pruned"] > 0:
        sys.exit(0 if not args.dry_run else 1)  # dry-run exits with 1 to signal found issues
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
