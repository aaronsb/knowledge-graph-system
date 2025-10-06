#!/usr/bin/env python3
"""
Restore CLI - Interactive restore tool for knowledge graph data

Provides menu-driven interface to restore backups into database.
Supports full or selective restore with conflict resolution options.

Usage:
    python -m src.admin.restore
    python -m src.admin.restore --file backups/full_backup_20251006.json
    python -m src.admin.restore --file backups/ontology_watts_20251006.json --overwrite
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.lib.console import Console, Colors
from src.lib.config import Config
from src.lib.neo4j_ops import Neo4jConnection, Neo4jQueries
from src.lib.serialization import DataImporter, BackupFormat
from src.lib.integrity import BackupAssessment, DatabaseIntegrity
from src.lib.restitching import ConceptMatcher


class RestoreCLI:
    """Interactive restore CLI"""

    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.conn = Neo4jConnection()

    def run_interactive(self):
        """Run interactive restore menu"""
        Console.section("Knowledge Graph System - Restore")

        # Test connection
        if not self.conn.test_connection():
            Console.error("✗ Cannot connect to Neo4j database")
            Console.warning(f"  Check connection: {Config.neo4j_uri()}")
            Console.warning("  Start database with: docker-compose up -d")
            sys.exit(1)

        Console.success("✓ Connected to Neo4j")

        # Find backup files
        if not self.backup_dir.exists():
            Console.error(f"✗ Backup directory not found: {self.backup_dir}")
            sys.exit(1)

        backup_files = sorted(self.backup_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)

        if not backup_files:
            Console.error(f"✗ No backup files found in {self.backup_dir}")
            sys.exit(1)

        Console.info(f"Found {len(backup_files)} backup files\n")

        # Show menu
        self._show_menu(backup_files)

    def _show_menu(self, backup_files: List[Path]):
        """Display restore options menu"""
        Console.bold("Available Backups:")
        for i, backup_file in enumerate(backup_files[:10], 1):  # Show latest 10
            file_size = backup_file.stat().st_size / (1024 * 1024)
            print(f"  {i}. {backup_file.name} ({file_size:.2f} MB)")

        if len(backup_files) > 10:
            Console.warning(f"\n  ... and {len(backup_files) - 10} more")

        print("")
        choice = input("Select backup to restore [1-10] or path to file: ").strip()

        # Parse choice
        if choice.isdigit() and 1 <= int(choice) <= min(10, len(backup_files)):
            backup_file = backup_files[int(choice) - 1]
        else:
            backup_file = Path(choice)
            if not backup_file.exists():
                Console.error(f"✗ File not found: {backup_file}")
                sys.exit(1)

        self._restore_backup(backup_file)

    def _restore_backup(self, backup_file: Path, overwrite: bool = False):
        """Restore a backup file"""
        Console.section(f"Restoring: {backup_file.name}")

        # Load and validate backup
        Console.info("Loading backup file...")
        try:
            with open(backup_file, 'r') as f:
                backup_data = json.load(f)

            DataImporter.validate_backup(backup_data)
        except Exception as e:
            Console.error(f"✗ Invalid backup file: {e}")
            sys.exit(1)

        # Assess backup before restore
        Console.info("\nAnalyzing backup...")
        assessment = BackupAssessment.analyze_backup(backup_data)
        BackupAssessment.print_assessment(assessment)

        # Check for serious issues
        if assessment["issues"]:
            Console.error("\n⚠ This backup has integrity issues!")
            if not Console.confirm("Continue anyway?"):
                Console.warning("Restore cancelled")
                sys.exit(0)

        # Handle external dependencies - MUST choose stitch or prune
        restitch_action = None
        if assessment["external_dependencies"]["concepts"]:
            ext_count = len(assessment["external_dependencies"]["concepts"])

            # Check if target database is empty (nothing to stitch to)
            with self.conn.session() as session:
                existing_concepts = session.run("MATCH (c:Concept) RETURN count(c) as count").single()["count"]

            if existing_concepts == 0:
                # Clean database - stitching is impossible, auto-prune
                Console.info(f"\n✓ Target database is empty ({ext_count} external references detected)")
                Console.info("  No existing concepts to stitch to - will auto-prune to keep ontology isolated")
                restitch_action = "prune"
            else:
                # Database has concepts - offer stitching options
                Console.warning(f"\n⚠ This backup has {ext_count} external concept dependencies")
                Console.warning("  ALL external references MUST be handled to maintain graph integrity")
                Console.warning("  Choose how to handle them:")
                print("")
                print("  1) Auto-prune after restore (keep isolated)")
                print("  2) Stitch later (defer - WARNING: graph will be broken!)")
                print("  3) Cancel restore")
                print("")
                choice = input("Select option [1-3]: ").strip()

                if choice == "1":
                    restitch_action = "prune"
                    Console.info(f"\n✓ Will prune {ext_count} dangling relationships after restore")
                elif choice == "2":
                    restitch_action = "defer"
                    Console.error("\n⚠ DANGER: Graph will have dangling refs until you fix it!")
                    Console.warning("  You MUST run ONE of these immediately after restore:")
                    Console.info(f"    python -m src.admin.stitch --backup {backup_file}")
                    Console.info(f"    python -m src.admin.prune")
                    Console.warning("\n  Stitcher will handle matched refs AND auto-prune unmatched")
                    if not Console.confirm("\nI understand the graph will be broken - proceed?"):
                        Console.warning("Restore cancelled - wise choice!")
                        sys.exit(0)
                else:
                    Console.warning("Restore cancelled")
                    sys.exit(0)

        # Check for conflicts
        if backup_data.get('ontology'):
            ontology_name = backup_data['ontology']
            with self.conn.session() as session:
                existing = Neo4jQueries.get_ontology_info(session, ontology_name)

            if existing:
                Console.warning(f"\n⚠ Ontology '{ontology_name}' already exists in database")
                Console.info(f"  Current concepts: {existing['statistics']['concept_count']}")

                print("\nRestore options:")
                print("  1) Skip existing nodes (add only new data)")
                print("  2) Overwrite existing nodes (update with backup data)")
                print("  3) Cancel")
                print("")

                conflict_choice = input("Select option [1-3]: ").strip()

                if conflict_choice == "1":
                    overwrite = False
                elif conflict_choice == "2":
                    overwrite = True
                    Console.warning("⚠ This will overwrite existing data!")
                    if not Console.confirm("Are you sure?"):
                        Console.warning("Restore cancelled")
                        sys.exit(0)
                else:
                    Console.warning("Restore cancelled")
                    sys.exit(0)

        # Confirm
        print("")
        if not Console.confirm("Proceed with restore?"):
            Console.warning("Restore cancelled")
            sys.exit(0)

        # Restore
        Console.info("\nRestoring data...")
        try:
            with self.conn.session() as session:
                import_stats = DataImporter.import_backup(
                    session,
                    backup_data,
                    overwrite_existing=overwrite
                )

            # Summary
            Console.section("Restore Complete")
            Console.success("✓ Data restored successfully")
            Console.info(f"  Concepts: {import_stats['concepts_created']}")
            Console.info(f"  Sources: {import_stats['sources_created']}")
            Console.info(f"  Instances: {import_stats['instances_created']}")
            Console.info(f"  Relationships: {import_stats['relationships_created']}")

            # Handle dangling relationships based on user choice
            if restitch_action == "prune":
                Console.section("Pruning Dangling Relationships")
                Console.info("Removing relationships to external concepts...")

                with self.conn.session() as session:
                    prune_result = DatabaseIntegrity.prune_dangling_relationships(
                        session,
                        ontology=backup_data.get('ontology'),
                        dry_run=False
                    )

                if prune_result["total_pruned"] > 0:
                    Console.success(f"✓ Pruned {prune_result['total_pruned']} dangling relationships")
                    Console.info("  Graph is now clean and isolated")
                else:
                    Console.success("✓ No dangling relationships found")

            elif restitch_action == "defer":
                Console.warning("\n⚠ Graph has dangling relationships - integrity compromised")
                Console.warning("  Run stitcher or pruner immediately!")

            # Validate integrity after restore
            Console.info("\nValidating database integrity...")
            with self.conn.session() as session:
                integrity = DatabaseIntegrity.check_integrity(
                    session,
                    ontology=backup_data.get('ontology')
                )

            if integrity["issues"] or integrity["warnings"]:
                DatabaseIntegrity.print_integrity_report(integrity)

                # Offer repair
                if integrity["issues"]:
                    Console.warning("\n⚠ Integrity issues detected after restore")
                    if Console.confirm("Attempt automatic repair?"):
                        Console.info("Repairing orphaned concepts...")
                        with self.conn.session() as session:
                            repairs = DatabaseIntegrity.repair_orphaned_concepts(
                                session,
                                ontology=backup_data.get('ontology')
                            )
                        Console.success(f"✓ Repaired {repairs} orphaned concepts")

                        # Re-check
                        Console.info("Re-validating...")
                        with self.conn.session() as session:
                            integrity = DatabaseIntegrity.check_integrity(
                                session,
                                ontology=backup_data.get('ontology')
                            )
                        if not integrity["issues"]:
                            Console.success("✓ All issues resolved")
                        else:
                            Console.warning("⚠ Some issues remain - manual intervention may be needed")
            else:
                Console.success("✓ No integrity issues detected")

            # Show tips based on action taken
            if restitch_action == "defer":
                # URGENT: graph is broken
                self._show_tips(backup_file=backup_file, urgent=True)
            elif assessment["external_dependencies"]["concepts"]:
                # Pruned - graph is clean
                self._show_tips(backup_file=None, urgent=False)
            else:
                # No external deps
                self._show_tips()

        except Exception as e:
            Console.error(f"✗ Restore failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    def _show_tips(self, backup_file: Optional[Path] = None, urgent: bool = False):
        """Show helpful tips"""
        if urgent:
            Console.error("\n⚠ URGENT: Graph integrity compromised!")
            Console.error("  Dangling relationships will break traversal queries")
            Console.warning("\nRun ONE of these immediately:")
            print(f"  {Colors.FAIL}python -m src.admin.stitch --backup {backup_file}{Colors.ENDC}")
            print(f"  {Colors.FAIL}python -m src.admin.prune{Colors.ENDC}")
            Console.warning("\nUntil you do, the graph is in an inconsistent state!")
        else:
            Console.warning("\n💡 Next steps:")
            print("  • Verify data: python cli.py database stats")
            print("  • Query concepts: python cli.py search \"your query\"")
            print("  • View in browser: http://localhost:7474")

            if backup_file:
                Console.info("\nℹ Optional: Reconnect external relationships using semantic stitcher")
                print(f"  {Colors.OKCYAN}python -m src.admin.stitch --backup {backup_file}{Colors.ENDC}")
                print("  (Or leave isolated if you prefer strict ontology boundaries)")

    def restore_non_interactive(self, backup_file: str, overwrite: bool = False):
        """Non-interactive restore for automation"""
        if not self.conn.test_connection():
            Console.error("✗ Cannot connect to Neo4j database")
            sys.exit(1)

        backup_path = Path(backup_file)
        if not backup_path.exists():
            Console.error(f"✗ Backup file not found: {backup_file}")
            sys.exit(1)

        Console.info(f"Restoring from: {backup_path.name}")

        # Load backup
        with open(backup_path, 'r') as f:
            backup_data = json.load(f)

        DataImporter.validate_backup(backup_data)

        # Restore
        with self.conn.session() as session:
            import_stats = DataImporter.import_backup(
                session,
                backup_data,
                overwrite_existing=overwrite
            )

        Console.success("✓ Restore complete")
        Console.info(f"  Concepts: {import_stats['concepts_created']}")
        Console.info(f"  Sources: {import_stats['sources_created']}")
        Console.info(f"  Instances: {import_stats['instances_created']}")
        Console.info(f"  Relationships: {import_stats['relationships_created']}")

    def close(self):
        """Cleanup"""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Restore knowledge graph data from backup files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive menu
  python -m src.admin.restore

  # Restore specific file (skip existing nodes)
  python -m src.admin.restore --file backups/ontology_watts_20251006.json

  # Restore and overwrite existing nodes
  python -m src.admin.restore --file backups/full_backup_20251006.json --overwrite

  # Custom backup directory
  python -m src.admin.restore --backup-dir /path/to/backups
        """
    )

    parser.add_argument('--file', type=str,
                       help='Backup file to restore (non-interactive)')
    parser.add_argument('--overwrite', action='store_true',
                       help='Overwrite existing nodes (default: skip duplicates)')
    parser.add_argument('--backup-dir', type=str, default='backups',
                       help='Backup directory (default: backups/)')

    args = parser.parse_args()

    cli = RestoreCLI(backup_dir=args.backup_dir)

    try:
        if args.file:
            # Non-interactive mode
            cli.restore_non_interactive(
                backup_file=args.file,
                overwrite=args.overwrite
            )
        else:
            # Interactive mode
            cli.run_interactive()
    finally:
        cli.close()


if __name__ == '__main__':
    main()
