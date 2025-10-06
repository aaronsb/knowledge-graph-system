#!/usr/bin/env python3
"""
Integrity Check CLI - Validate database integrity

Checks for:
- Orphaned concepts (no APPEARS_IN relationships)
- Dangling relationships (pointing to non-existent concepts)
- Missing embeddings
- Cross-ontology relationships
- Torn ontological fabric

Usage:
    python -m src.admin.check_integrity
    python -m src.admin.check_integrity --ontology "My Ontology"
    python -m src.admin.check_integrity --repair
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.lib.console import Console
from src.lib.config import Config
from src.lib.neo4j_ops import Neo4jConnection
from src.lib.integrity import DatabaseIntegrity


def main():
    parser = argparse.ArgumentParser(
        description="Check database integrity and detect ontological fabric issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check entire database
  python -m src.admin.check_integrity

  # Check specific ontology
  python -m src.admin.check_integrity --ontology "My Ontology"

  # Check and auto-repair
  python -m src.admin.check_integrity --repair

  # Detailed report with samples
  python -m src.admin.check_integrity --verbose
        """
    )

    parser.add_argument('--ontology', type=str,
                       help='Check specific ontology (default: entire database)')
    parser.add_argument('--repair', action='store_true',
                       help='Automatically repair orphaned concepts')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Show detailed report with samples')

    args = parser.parse_args()

    Console.section("Database Integrity Check")

    # Connect
    conn = Neo4jConnection()
    if not conn.test_connection():
        Console.error("✗ Cannot connect to Neo4j database")
        Console.warning(f"  Check connection: {Config.neo4j_uri()}")
        Console.warning("  Start database with: docker-compose up -d")
        sys.exit(1)

    Console.success("✓ Connected to Neo4j")

    if args.ontology:
        Console.info(f"Checking ontology: {args.ontology}\n")
    else:
        Console.info("Checking entire database\n")

    # Check integrity
    with conn.session() as session:
        integrity = DatabaseIntegrity.check_integrity(session, args.ontology)

    # Print report
    DatabaseIntegrity.print_integrity_report(integrity)

    # Repair if requested
    if args.repair and integrity["issues"]:
        Console.warning("\n🔧 Attempting automatic repair...")

        with conn.session() as session:
            repairs = DatabaseIntegrity.repair_orphaned_concepts(session, args.ontology)

        if repairs > 0:
            Console.success(f"✓ Repaired {repairs} orphaned concepts")

            # Re-check
            Console.info("\nRe-validating integrity...")
            with conn.session() as session:
                integrity = DatabaseIntegrity.check_integrity(session, args.ontology)

            if not integrity["issues"]:
                Console.success("✓ All issues resolved!")
            else:
                Console.warning("⚠ Some issues remain - manual intervention may be needed")
                DatabaseIntegrity.print_integrity_report(integrity)
        else:
            Console.info("No repairs needed")

    conn.close()

    # Exit code based on integrity
    if integrity["issues"]:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
