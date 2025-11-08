#!/usr/bin/env python3
"""
Semantic Stitcher - Reconnect dangling relationships after partial restore

When you restore a partial ontology backup, external concept references become
dangling (point to non-existent concepts). This tool finds similar concepts in
the target database and reconnects the relationships using vector similarity.

Workflow:
1. Restore ontology normally (dangling refs created)
2. Run stitcher to analyze and reconnect
3. Review proposed stitches before applying
4. Optionally adjust similarity threshold and re-run

Usage:
    python -m src.admin.stitch --backup backups/ontology_a.json
    python -m src.admin.stitch --backup backups/ontology_a.json --threshold 0.90
    python -m src.admin.stitch --backup backups/ontology_a.json --auto-apply
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.lib.console import Console, Colors
from api.lib.config import Config
from api.lib.age_ops import AGEConnection
from api.lib.restitching import ConceptMatcher
from api.lib.serialization import DataImporter
from api.lib.integrity import DatabaseIntegrity


def main():
    parser = argparse.ArgumentParser(
        description="Semantic stitcher - Reconnect dangling relationships using vector similarity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflow:
  1. Restore partial ontology backup (creates dangling references)
  2. Run stitcher to analyze external dependencies
  3. Review proposed re-stitching (concept matches)
  4. Apply stitches to reconnect relationships

Examples:
  # Analyze external dependencies and propose stitches
  python -m src.admin.stitch --backup backups/ontology_a.json

  # Higher threshold for stricter matching (>95% similarity)
  python -m src.admin.stitch --backup backups/ontology_a.json --threshold 0.95

  # Lower threshold for more permissive matching (>80% similarity)
  python -m src.admin.stitch --backup backups/ontology_a.json --threshold 0.80

  # Auto-apply without confirmation
  python -m src.admin.stitch --backup backups/ontology_a.json --auto-apply

  # Dry-run: show proposed stitches but don't apply
  python -m src.admin.stitch --backup backups/ontology_a.json --dry-run

  # Create placeholders for unmatched concepts
  python -m src.admin.stitch --backup backups/ontology_a.json --create-placeholders

Note:
  This tool analyzes the BACKUP FILE to identify external dependencies, then
  searches the CURRENT DATABASE for similar concepts. It does NOT modify the
  backup file - only the live database.
        """
    )

    parser.add_argument('--backup', '-b', type=str, required=True,
                       help='Backup file to analyze for external dependencies')
    parser.add_argument('--threshold', '-t', type=float, default=0.85,
                       help='Similarity threshold for matching (0.0-1.0, default: 0.85)')
    parser.add_argument('--auto-apply', action='store_true',
                       help='Auto-apply stitches without confirmation')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show proposed stitches but do not apply')
    parser.add_argument('--create-placeholders', action='store_true',
                       help='Create placeholder concepts for unmatched references')

    args = parser.parse_args()

    # Validate threshold
    if not 0.0 <= args.threshold <= 1.0:
        Console.error("Threshold must be between 0.0 and 1.0")
        sys.exit(1)

    Console.section("Semantic Stitcher")

    # Load backup file
    backup_path = Path(args.backup)
    if not backup_path.exists():
        Console.error(f"✗ Backup file not found: {backup_path}")
        sys.exit(1)

    Console.info(f"Loading backup: {backup_path.name}")
    with open(backup_path, 'r') as f:
        backup_data = json.load(f)

    # Validate backup
    try:
        DataImporter.validate_backup(backup_data)
    except Exception as e:
        Console.error(f"✗ Invalid backup file: {e}")
        sys.exit(1)

    # Connect to database
    conn = AGEConnection()
    if not conn.test_connection():
        Console.error("✗ Cannot connect to Apache AGE database")
        Console.warning(f"  Check connection: {Config.postgres_host()}:{Config.postgres_port()}")
        sys.exit(1)

    Console.success("✓ Connected to target database")
    Console.key_value("  Backup type", backup_data['type'])
    if backup_data.get('ontology'):
        Console.key_value("  Ontology", backup_data['ontology'])
    Console.key_value("  Similarity threshold", f"{args.threshold:.0%}")

    # Create matcher
    matcher = ConceptMatcher(conn, similarity_threshold=args.threshold)

    # Find external concepts
    Console.info("\nAnalyzing backup for external concept references...")
    external_concepts = matcher.find_external_concepts(backup_data)

    if not external_concepts:
        Console.success("\n✓ No external concept references found")
        Console.info("  This backup has no cross-ontology dependencies")
        conn.close()
        sys.exit(0)

    Console.warning(f"\nFound {len(external_concepts)} external concept references")

    # Create re-stitching plan
    Console.info("Searching target database for similar concepts...")
    client = conn.get_client()
    restitch_plan = matcher.create_restitch_plan(external_concepts, client)

    # Print plan
    matcher.print_restitch_plan(restitch_plan)

    # Check if any matches found
    if not restitch_plan["matched"] and not restitch_plan["unmatched"]:
        Console.info("\nNo stitching needed")
        conn.close()
        sys.exit(0)

    # Dry-run mode
    if args.dry_run:
        Console.warning("\n[DRY-RUN MODE] No changes will be applied")
        conn.close()
        sys.exit(0)

    # Offer choices
    if restitch_plan["matched"]:
        if args.auto_apply:
            Console.warning("\n[AUTO-APPLY MODE] Applying stitches automatically...")
            apply = True
            prune = False
        else:
            Console.warning("\n⚠ What would you like to do with external references?")
            print("  1) Re-stitch to similar concepts (semantic merging)")
            print("  2) Prune dangling relationships (keep isolated)")
            print("  3) Leave as-is (accept dangling references)")
            print("")
            choice = input("Select option [1-3]: ").strip()

            if choice == "1":
                apply = True
                prune = False
            elif choice == "2":
                apply = False
                prune = True
            else:
                apply = False
                prune = False

        if apply:
            Console.section("Applying Re-stitching")
            client = conn.get_client()
            stats = matcher.execute_restitch(
                restitch_plan,
                client,
                create_placeholders=args.create_placeholders
            )

            Console.success(f"\n✓ Re-stitched {stats['restitched']} relationships")

            if stats["placeholders"] > 0:
                Console.info(f"  Created {stats['placeholders']} placeholder concepts")

            # MUST prune unmatched references - 100% edge handling
            if restitch_plan["unmatched"]:
                Console.warning(f"\n⚠ {len(restitch_plan['unmatched'])} external concepts could not be matched")
                Console.info("  Pruning relationships to unmatched concepts...")

                ontology = backup_data.get('ontology')
                client = conn.get_client()
                prune_result = DatabaseIntegrity.prune_dangling_relationships(
                    client,
                    ontology=ontology,
                    dry_run=False
                )

                if prune_result["total_pruned"] > 0:
                    Console.success(f"✓ Pruned {prune_result['total_pruned']} unmatched relationships")
                    Console.info("  All external references handled - graph is clean")

            # Show next steps
            Console.warning("\n💡 Next steps:")
            print("  • Verify stitches: python cli.py ontology info \"Ontology Name\"")
            print("  • Check integrity: python -m src.admin.check_integrity")
            print("  • Query concepts: python cli.py search \"your query\"")
        elif prune:
            # Prune dangling relationships
            Console.section("Pruning Dangling Relationships")
            Console.info("Removing relationships to external concepts...")

            ontology = backup_data.get('ontology')
            client = conn.get_client()
            prune_result = DatabaseIntegrity.prune_dangling_relationships(
                client,
                ontology=ontology,
                dry_run=False
            )

            DatabaseIntegrity.print_pruning_report(prune_result, dry_run=False)

            Console.success("\n✓ All external references handled - graph is clean")
            Console.info("  Ontology is now isolated - no cross-ontology relationships")
        else:
            Console.warning("\nNo action taken - dangling relationships remain")
            Console.info("  You can:")
            print("    • Re-run with different --threshold to adjust matches")
            print("    • Use: python -m src.admin.prune to remove danglers")
            print("    • Leave as-is if queries don't traverse these relationships")
    else:
        Console.warning("\nNo matches found - all external references would remain dangling")

        if args.create_placeholders:
            Console.warning(f"Creating {len(restitch_plan['unmatched'])} placeholder concepts...")
            client = conn.get_client()
            stats = matcher.execute_restitch(
                restitch_plan,
                client,
                create_placeholders=True
            )
            Console.success(f"✓ Created {stats['placeholders']} placeholder concepts")
            Console.warning("  ⚠ Placeholders need manual review and connection")
        else:
            Console.info("\n  Options:")
            print("    1. Lower --threshold to find more permissive matches")
            print("    2. Use --create-placeholders to create stub concepts")
            print("    3. Accept dangling references (queries will skip them)")

    conn.close()


if __name__ == '__main__':
    main()
