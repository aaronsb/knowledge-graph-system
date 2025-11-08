#!/usr/bin/env python3
"""
Backup CLI - Interactive backup tool for knowledge graph data

Provides menu-driven interface to backup entire database or specific ontologies.
Exports data to portable JSON format with full embeddings preserved.

Usage:
    python -m src.admin.backup
    python -m src.admin.backup --auto-full
    python -m src.admin.backup --ontology "My Ontology" --output custom_backup.json
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from api.lib.console import Console, Colors
from api.lib.config import Config
from api.lib.age_ops import AGEConnection, AGEQueries
from api.lib.serialization import DataExporter
from api.lib.integrity import BackupAssessment


class BackupCLI:
    """Interactive backup CLI"""

    def __init__(self, backup_dir: str = "backups"):
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(exist_ok=True)
        self.conn = AGEConnection()

    def run_interactive(self):
        """Run interactive backup menu"""
        Console.section("Knowledge Graph System - Backup")

        # Test connection
        if not self.conn.test_connection():
            Console.error("✗ Cannot connect to Apache AGE database")
            Console.warning(f"  Check connection: {Config.postgres_host()}:{Config.postgres_port()}")
            Console.warning("  Start database with: docker-compose up -d")
            sys.exit(1)

        Console.success("✓ Connected to Apache AGE")

        # Get ontology list
        client = self.conn.get_client()
        ontologies = AGEQueries.get_ontology_list(client)

        if not ontologies:
            Console.error("✗ No ontologies found in database")
            sys.exit(1)

        Console.info(f"Found {len(ontologies)} ontologies\n")

        # Show menu
        self._show_menu(ontologies)

    def _show_menu(self, ontologies: List[dict]):
        """Display backup options menu"""
        Console.bold("Backup Options:")
        print("  1) Full database backup (all ontologies)")
        print("  2) Specific ontology backup")
        print("")

        choice = input("Select option [1-2]: ").strip()

        if choice == "1":
            self._backup_full(ontologies)
        elif choice == "2":
            self._backup_ontology(ontologies)
        else:
            Console.error("Invalid option")
            sys.exit(1)

    def _backup_full(self, ontologies: List[dict]):
        """Full database backup"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"full_backup_{timestamp}.json"

        Console.section("Full Database Backup")

        # Show what will be backed up
        Console.warning("The following will be backed up:")
        for ont in ontologies:
            print(f"  • {ont['ontology']} ({ont['file_count']} files, {ont['concept_count']} concepts)")

        # Show statistics
        client = self.conn.get_client()
        stats = AGEQueries.get_database_stats(client)

        Console.warning("\nDatabase totals:")
        Console.key_value("  Concepts", str(stats['nodes'].get('concepts', 0)), Colors.BOLD, Colors.OKGREEN)
        Console.key_value("  Sources", str(stats['nodes'].get('sources', 0)), Colors.BOLD, Colors.OKGREEN)
        Console.key_value("  Instances", str(stats['nodes'].get('instances', 0)), Colors.BOLD, Colors.OKGREEN)
        Console.key_value("  Relationships", str(stats['relationships'].get('total', 0)), Colors.BOLD, Colors.OKGREEN)

        Console.warning(f"\nBackup destination: {backup_file}")
        print("")

        if not Console.confirm("Press Enter to start backup (Ctrl+C to cancel)"):
            Console.warning("Backup cancelled")
            sys.exit(0)

        # Export
        Console.info("\nExporting database...")
        client = self.conn.get_client()
        backup_data = DataExporter.export_full_backup(client)

        # Write to file
        Console.info(f"Writing to {backup_file}...")
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)

        # Show summary
        file_size = backup_file.stat().st_size
        size_mb = file_size / (1024 * 1024)

        Console.section("Backup Complete")
        Console.success(f"✓ Full backup created: {backup_file}")
        Console.info(f"  Size: {size_mb:.2f} MB")
        Console.info(f"  Concepts: {backup_data['statistics']['concepts']}")
        Console.info(f"  Sources: {backup_data['statistics']['sources']}")
        Console.info(f"  Instances: {backup_data['statistics']['instances']}")
        Console.info(f"  Relationships: {backup_data['statistics']['relationships']}")

        self._show_tips()

    def _backup_ontology(self, ontologies: List[dict]):
        """Ontology-specific backup"""
        Console.section("Select Ontologies to Backup")

        # Show ontologies
        for ont in ontologies:
            print(f"  • {ont['ontology']} ({ont['file_count']} files, {ont['concept_count']} concepts)")

        Console.warning("\nEnter ontology names to backup (comma-separated):")
        Console.warning("Or type 'all' to backup all ontologies separately")
        ontology_input = input("> ").strip()

        if ontology_input.lower() == "all":
            self._backup_all_ontologies_separately(ontologies)
        else:
            self._backup_specific_ontologies(ontology_input, ontologies)

    def _backup_all_ontologies_separately(self, ontologies: List[dict]):
        """Backup each ontology to separate files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        Console.warning(f"\nWill create separate backups for {len(ontologies)} ontologies")
        if not Console.confirm("Press Enter to continue (Ctrl+C to cancel)"):
            Console.warning("Backup cancelled")
            sys.exit(0)

        backup_files = []
        for i, ont_info in enumerate(ontologies, 1):
            ontology = ont_info['ontology']
            safe_name = ontology.replace(' ', '_').replace('/', '_').lower()
            backup_file = self.backup_dir / f"ontology_{safe_name}_{timestamp}.json"

            Console.info(f"\n[{i}/{len(ontologies)}] Backing up: {ontology}")

            client = self.conn.get_client()
            backup_data = DataExporter.export_ontology_backup(client, ontology)

            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2)

            file_size = backup_file.stat().st_size
            size_mb = file_size / (1024 * 1024)
            Console.success(f"✓ Backed up to: {backup_file} ({size_mb:.2f} MB)")
            backup_files.append(backup_file)

        # Summary
        Console.section("Backup Complete")
        Console.success(f"✓ Created {len(backup_files)} ontology backups")
        for f in backup_files:
            print(f"  • {f.name}")

        self._show_tips()

    def _backup_specific_ontologies(self, ontology_input: str, ontologies: List[dict]):
        """Backup specific ontologies"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        ontology_names = [name.strip() for name in ontology_input.split(',')]

        # Validate
        available_names = {ont['ontology'] for ont in ontologies}
        invalid = [name for name in ontology_names if name not in available_names]
        if invalid:
            Console.error(f"✗ Ontologies not found: {', '.join(invalid)}")
            sys.exit(1)

        backup_files = []
        for i, ontology in enumerate(ontology_names, 1):
            safe_name = ontology.replace(' ', '_').replace('/', '_').lower()
            backup_file = self.backup_dir / f"ontology_{safe_name}_{timestamp}.json"

            # Show info
            ont_info = next(ont for ont in ontologies if ont['ontology'] == ontology)
            Console.info(f"\n[{i}/{len(ontology_names)}] Backing up: {ontology}")
            Console.info(f"  Files: {ont_info['file_count']}")
            Console.info(f"  Concepts: {ont_info['concept_count']}")
            Console.info(f"  Instances: {ont_info['instance_count']}")
            Console.info(f"  Destination: {backup_file}")

            # Export
            client = self.conn.get_client()
            backup_data = DataExporter.export_ontology_backup(client, ontology)

            # Assess backup integrity
            assessment = BackupAssessment.analyze_backup(backup_data)

            # Write
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2)

            file_size = backup_file.stat().st_size
            size_mb = file_size / (1024 * 1024)
            Console.success(f"✓ Backed up ({size_mb:.2f} MB)")

            # Show warnings if external dependencies exist
            if assessment["warnings"] or assessment["issues"]:
                Console.warning(f"  ⚠ {len(assessment['warnings'])} warnings, {len(assessment['issues'])} issues")
                if assessment["external_dependencies"]["concepts"]:
                    ext_count = len(assessment["external_dependencies"]["concepts"])
                    Console.warning(f"  ⚠ {ext_count} relationships to external concepts")

            backup_files.append(backup_file)

        # Summary
        Console.section("Backup Complete")
        Console.success(f"✓ Created {len(backup_files)} backups")

        # Check if any backup has external deps
        has_external_deps = False
        for f in backup_files:
            with open(f, 'r') as bf:
                backup_data = json.load(bf)
            assessment = BackupAssessment.analyze_backup(backup_data)
            if assessment["external_dependencies"]["concepts"]:
                has_external_deps = True
                print(f"  • {f.name} {Colors.WARNING}(has external dependencies){Colors.ENDC}")
            else:
                print(f"  • {f.name}")

        self._show_tips(show_stitch_warning=has_external_deps)

    def _show_tips(self, show_stitch_warning: bool = False):
        """Show helpful tips"""
        Console.warning("\n💡 Tips:")
        print("  • Backup files are portable - share or move them as needed")
        print("  • Use restore.py to restore ontologies into this or another database")
        print("  • Ontology backups can be selectively restored without affecting other data")
        print("  • Backups include full embeddings (1536-dim vectors) and all text")

        if show_stitch_warning:
            Console.info("\nℹ External Dependencies Detected:")
            print("  This backup has cross-ontology relationships (external concept references)")
            print("  After restoring, you can optionally reconnect them using the semantic stitcher:")
            print(f"    {Colors.OKCYAN}python -m src.admin.stitch --backup <backup-file>{Colors.ENDC}")
            print("  Or leave them isolated if you prefer strict ontology boundaries")

    def backup_non_interactive(self, ontology: Optional[str] = None, output: Optional[str] = None):
        """Non-interactive backup for automation"""
        if not self.conn.test_connection():
            Console.error("✗ Cannot connect to Apache AGE database")
            sys.exit(1)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        client = self.conn.get_client()

        if ontology:
            # Ontology backup
            if output:
                backup_file = Path(output)
            else:
                safe_name = ontology.replace(' ', '_').replace('/', '_').lower()
                backup_file = self.backup_dir / f"ontology_{safe_name}_{timestamp}.json"

            Console.info(f"Backing up ontology: {ontology}")
            backup_data = DataExporter.export_ontology_backup(client, ontology)

        else:
            # Full backup
            if output:
                backup_file = Path(output)
            else:
                backup_file = self.backup_dir / f"full_backup_{timestamp}.json"

            Console.info("Backing up full database")
            backup_data = DataExporter.export_full_backup(client)

        # Write
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)

        file_size = backup_file.stat().st_size
        size_mb = file_size / (1024 * 1024)
        Console.success(f"✓ Backup complete: {backup_file} ({size_mb:.2f} MB)")

    def close(self):
        """Cleanup"""
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Backup knowledge graph data to portable JSON format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive menu
  python -m src.admin.backup

  # Non-interactive full backup
  python -m src.admin.backup --auto-full

  # Backup specific ontology
  python -m src.admin.backup --ontology "My Ontology"

  # Custom output file
  python -m src.admin.backup --ontology "My Ontology" --output my_backup.json
        """
    )

    parser.add_argument('--auto-full', action='store_true',
                       help='Automatically backup full database (non-interactive)')
    parser.add_argument('--ontology', type=str,
                       help='Backup specific ontology (non-interactive)')
    parser.add_argument('--output', type=str,
                       help='Custom output file path')
    parser.add_argument('--backup-dir', type=str, default='backups',
                       help='Backup directory (default: backups/)')

    args = parser.parse_args()

    cli = BackupCLI(backup_dir=args.backup_dir)

    try:
        if args.auto_full or args.ontology:
            # Non-interactive mode
            cli.backup_non_interactive(
                ontology=args.ontology,
                output=args.output
            )
        else:
            # Interactive mode
            cli.run_interactive()
    finally:
        cli.close()


if __name__ == '__main__':
    main()
