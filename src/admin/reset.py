#!/usr/bin/env python3
"""
Reset CLI - Database reset tool for knowledge graph system

Provides nuclear reset option to completely wipe and reinitialize the database.
Includes schema verification and optional cleanup of logs and checkpoints.

Usage:
    python -m src.admin.reset
    python -m src.admin.reset --auto-confirm
    python -m src.admin.reset --no-logs --no-checkpoints
"""

import argparse
import subprocess
import sys
import time
import os
import glob
from pathlib import Path
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.lib.console import Console, Colors
from src.lib.config import Config
from src.lib.age_ops import AGEConnection


class ResetManager:
    """Database reset manager"""

    def __init__(self, project_root: Path = None):
        self.project_root = project_root or Path(__file__).parent.parent.parent
        self.postgres_user = Config.postgres_user()
        self.postgres_db = Config.postgres_db()
        self.container_name = "knowledge-graph-postgres"

    def run_interactive(self):
        """Run interactive reset with confirmation"""
        Console.section("Knowledge Graph System - Database Reset")

        Console.error("⚠️  WARNING: This will delete ALL graph data!")
        Console.warning("\nThis operation will:")
        print("  • Stop the PostgreSQL container")
        print("  • Delete all database volumes (complete data loss)")
        print("  • Reinitialize with fresh schema")
        print("  • Optionally clear logs and checkpoints")
        print("")

        if not Console.confirm("Are you sure you want to continue? Type 'yes' to confirm: ", exact="yes"):
            Console.warning("Reset cancelled")
            sys.exit(0)

        # Ask about clearing logs/checkpoints
        clear_logs = Console.confirm("\nClear ingestion log files? [Y/n]: ")
        clear_checkpoints = Console.confirm("Clear checkpoint files? [Y/n]: ")

        # Execute reset
        result = self.reset(
            clear_logs=clear_logs,
            clear_checkpoints=clear_checkpoints,
            verbose=True
        )

        # Show results
        Console.section("Reset Complete")

        if result["success"]:
            Console.success("✅ Database reset successfully")

            validation = result["validation"]
            Console.info("\nSchema Validation:")
            Console.key_value("  Graph exists", "✓" if validation["graph_exists"] else "✗",
                            Colors.BOLD, Colors.OKGREEN if validation["graph_exists"] else Colors.FAIL)
            Console.key_value("  Tables created", str(validation["table_count"]),
                            Colors.BOLD, Colors.OKGREEN if validation["table_count"] >= 4 else Colors.WARNING)
            Console.key_value("  Node count", str(validation["node_count"]),
                            Colors.BOLD, Colors.OKGREEN if validation["node_count"] == 0 else Colors.WARNING)
            Console.key_value("  Schema test", "✓" if validation["schema_test_passed"] else "✗",
                            Colors.BOLD, Colors.OKGREEN if validation["schema_test_passed"] else Colors.FAIL)

            Console.warning("\n💡 Database is now empty and ready for fresh data")
            Console.info("   Use 'kg ingest' to add documents")

        else:
            Console.error("✗ Reset failed")
            Console.error(f"  {result['error']}")
            sys.exit(1)

    def reset(
        self,
        clear_logs: bool = True,
        clear_checkpoints: bool = True,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Execute database reset

        Args:
            clear_logs: Clear ingestion log files
            clear_checkpoints: Clear checkpoint files
            verbose: Show detailed progress messages

        Returns:
            Dict with success status, validation results, and any errors
        """

        try:
            # Step 1: Stop and remove PostgreSQL container with volumes
            if verbose:
                Console.info("\n🛑 Stopping PostgreSQL container...")

            result = subprocess.run(
                ["docker-compose", "down", "-v"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {"success": False, "error": "Failed to stop PostgreSQL container"}

            # Step 2: Remove data volumes explicitly
            if verbose:
                Console.info("🗑️  Removing database volumes...")

            volumes = [
                "knowledge-graph-system_postgres_data",
                "knowledge-graph-system_postgres_import",
            ]

            for volume in volumes:
                subprocess.run(
                    ["docker", "volume", "rm", volume],
                    capture_output=True,
                    text=True
                )
                # Ignore errors if volume doesn't exist

            # Step 3: Start fresh PostgreSQL container
            if verbose:
                Console.info("🚀 Starting fresh PostgreSQL container...")

            result = subprocess.run(
                ["docker-compose", "up", "-d"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Failed to start PostgreSQL container: {result.stderr}"
                }

            # Step 4: Wait for PostgreSQL to be ready
            if verbose:
                Console.info("⏳ Waiting for PostgreSQL to be ready...")

            max_attempts = 30
            for attempt in range(max_attempts):
                time.sleep(2)

                result = subprocess.run(
                    [
                        "docker", "exec", self.container_name,
                        "psql", "-U", self.postgres_user, "-d", self.postgres_db,
                        "-c", "SELECT 1"
                    ],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0:
                    if verbose:
                        Console.success(f"✓ PostgreSQL ready (took {(attempt + 1) * 2}s)")
                    break

                if verbose and attempt % 5 == 0:
                    print(".", end="", flush=True)

                if attempt == max_attempts - 1:
                    return {
                        "success": False,
                        "error": "PostgreSQL failed to start within timeout"
                    }

            # Step 5: Initialize schema from init_age.sql
            if verbose:
                Console.info("📋 Initializing schema from init_age.sql...")

            schema_file = self.project_root / "schema" / "init_age.sql"

            if not schema_file.exists():
                return {
                    "success": False,
                    "error": f"Schema file not found: {schema_file}"
                }

            with open(schema_file, 'r') as f:
                schema_sql = f.read()

            result = subprocess.run(
                [
                    "docker", "exec", "-i", self.container_name,
                    "psql", "-U", self.postgres_user, "-d", self.postgres_db
                ],
                input=schema_sql,
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": f"Schema initialization failed: {result.stderr}"
                }

            if verbose:
                Console.success("✓ Schema initialized")

            # Step 6: Clear log files
            if clear_logs:
                if verbose:
                    Console.info("🧹 Clearing log files...")

                log_dir = self.project_root / "logs"
                if log_dir.exists():
                    log_count = 0
                    for log_file in glob.glob(str(log_dir / "ingest_*.log")):
                        try:
                            Path(log_file).unlink()
                            log_count += 1
                        except Exception:
                            pass  # Ignore errors

                    if verbose and log_count > 0:
                        Console.success(f"✓ Cleared {log_count} log file(s)")

            # Step 7: Clear checkpoint files
            if clear_checkpoints:
                if verbose:
                    Console.info("🧹 Clearing checkpoint files...")

                checkpoint_dir = self.project_root / ".checkpoints"
                if checkpoint_dir.exists():
                    checkpoint_count = 0
                    for checkpoint_file in glob.glob(str(checkpoint_dir / "*.json")):
                        try:
                            Path(checkpoint_file).unlink()
                            checkpoint_count += 1
                        except Exception:
                            pass  # Ignore errors

                    if verbose and checkpoint_count > 0:
                        Console.success(f"✓ Cleared {checkpoint_count} checkpoint file(s)")

            # Step 8: Verify schema
            if verbose:
                Console.info("✅ Verifying schema...")

            validation = self._verify_schema()

            return {
                "success": True,
                "validation": validation,
                "error": None
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "validation": None
            }

    def _verify_schema(self) -> Dict[str, Any]:
        """Verify schema was created correctly after reset"""

        # Check that knowledge_graph exists
        result = subprocess.run(
            [
                "docker", "exec", self.container_name,
                "psql", "-U", self.postgres_user, "-d", self.postgres_db,
                "-t", "-c", "SELECT name FROM ag_catalog.ag_graph WHERE name = 'knowledge_graph'"
            ],
            capture_output=True,
            text=True
        )
        graph_exists = "knowledge_graph" in result.stdout.strip()

        # Check that application tables exist
        result = subprocess.run(
            [
                "docker", "exec", self.container_name,
                "psql", "-U", self.postgres_user, "-d", self.postgres_db,
                "-t", "-c",
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name IN ('users', 'api_keys', 'sessions', 'ingestion_jobs')"
            ],
            capture_output=True,
            text=True
        )
        table_count = int(result.stdout.strip() or "0")

        # Check graph node count (should be 0)
        node_count = 0
        try:
            conn = AGEConnection()
            client = conn.get_client()
            results = client._execute_cypher("MATCH (n) RETURN count(n) as node_count", fetch_one=True)
            node_count = int(list(results.values())[0]) if results else 0
            conn.close()
        except Exception:
            node_count = 0

        # Schema test: Try creating and deleting a test concept
        schema_test_passed = False
        try:
            conn = AGEConnection()
            client = conn.get_client()
            client._execute_cypher("""
                CREATE (c:Concept {concept_id: 'test_schema', label: 'Test', embedding: [0.1], search_terms: []})
            """)
            client._execute_cypher("""
                MATCH (c:Concept {concept_id: 'test_schema'}) DELETE c
            """)
            schema_test_passed = True
            conn.close()
        except Exception:
            schema_test_passed = False

        return {
            "graph_exists": graph_exists,
            "table_count": table_count,
            "node_count": node_count,
            "schema_test_passed": schema_test_passed,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Reset knowledge graph database (DESTRUCTIVE)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (with confirmation)
  python -m src.admin.reset

  # Auto-confirm (for scripts)
  python -m src.admin.reset --auto-confirm

  # Skip clearing logs and checkpoints
  python -m src.admin.reset --auto-confirm --no-logs --no-checkpoints
        """
    )

    parser.add_argument('--auto-confirm', action='store_true',
                       help='Skip confirmation prompt (DANGEROUS)')
    parser.add_argument('--no-logs', action='store_true',
                       help='Do not clear log files')
    parser.add_argument('--no-checkpoints', action='store_true',
                       help='Do not clear checkpoint files')

    args = parser.parse_args()

    manager = ResetManager()

    if args.auto_confirm:
        # Non-interactive mode
        Console.section("Knowledge Graph System - Database Reset")
        Console.warning("⚠️  Auto-confirm mode - proceeding without confirmation")

        result = manager.reset(
            clear_logs=not args.no_logs,
            clear_checkpoints=not args.no_checkpoints,
            verbose=True
        )

        if result["success"]:
            Console.success("\n✅ Reset complete")
            sys.exit(0)
        else:
            Console.error(f"\n✗ Reset failed: {result['error']}")
            sys.exit(1)
    else:
        # Interactive mode with confirmation
        manager.run_interactive()


if __name__ == '__main__':
    main()
