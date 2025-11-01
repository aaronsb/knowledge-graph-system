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
            Console.key_value("  AGE Graph", "✓" if validation["graph_exists"] else "✗",
                            Colors.BOLD, Colors.OKGREEN if validation["graph_exists"] else Colors.FAIL)
            Console.key_value("  PG Schemas", f"{validation['schema_count']}/3 (kg_api, kg_auth, kg_logs)",
                            Colors.BOLD, Colors.OKGREEN if validation["schema_count"] == 3 else Colors.WARNING)
            Console.key_value("  Core Tables", f"{validation['table_count']}/5 (users, api_keys, roles, jobs, sessions)",
                            Colors.BOLD, Colors.OKGREEN if validation["table_count"] == 5 else Colors.WARNING)
            Console.key_value("  Node count", str(validation["node_count"]),
                            Colors.BOLD, Colors.OKGREEN if validation["node_count"] == 0 else Colors.WARNING)
            Console.key_value("  Graph test", "✓" if validation["schema_test_passed"] else "✗",
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

            # Step 4: Wait for PostgreSQL initialization to complete
            # Note: docker-entrypoint-initdb.d automatically runs schema files
            # (01_init_age.sql and 02_multi_schema.sql) on fresh volumes
            if verbose:
                Console.info("⏳ Waiting for PostgreSQL initialization to complete...")

            max_attempts = 45  # Increased from 30 to allow time for schema initialization
            for attempt in range(max_attempts):
                time.sleep(2)

                # Check if PostgreSQL is accepting connections
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
                    # PostgreSQL is up, now check if AGE graph is initialized
                    graph_check = subprocess.run(
                        [
                            "docker", "exec", self.container_name,
                            "psql", "-U", self.postgres_user, "-d", self.postgres_db,
                            "-t", "-c", "SELECT name FROM ag_catalog.ag_graph WHERE name = 'knowledge_graph'"
                        ],
                        capture_output=True,
                        text=True
                    )

                    if "knowledge_graph" in graph_check.stdout:
                        if verbose:
                            Console.success(f"✓ PostgreSQL initialization complete (took {(attempt + 1) * 2}s)")
                        break

                if verbose and attempt % 5 == 0:
                    print(".", end="", flush=True)

                if attempt == max_attempts - 1:
                    return {
                        "success": False,
                        "error": "PostgreSQL initialization failed to complete within timeout"
                    }

            # Step 5: Wait for schema initialization to fully complete
            # Check that schema_migrations table exists (created by baseline migration)
            if verbose:
                Console.info("⏳ Waiting for schema initialization to complete...")

            max_schema_wait = 30  # 30 attempts = 60 seconds max
            schema_ready = False
            for attempt in range(max_schema_wait):
                time.sleep(2)

                # Check if schema_migrations table exists
                result = subprocess.run(
                    [
                        "docker", "exec", self.container_name,
                        "psql", "-U", self.postgres_user, "-d", self.postgres_db,
                        "-t", "-A", "-c",
                        "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'schema_migrations')"
                    ],
                    capture_output=True,
                    text=True
                )

                if result.returncode == 0 and "t" in result.stdout.lower():
                    schema_ready = True
                    if verbose:
                        Console.success(f"✓ Schema initialized (took {(attempt + 1) * 2}s)")
                    break

                if verbose and attempt % 3 == 0:
                    print(".", end="", flush=True)

            if not schema_ready:
                return {
                    "success": False,
                    "error": "Schema initialization timeout: schema_migrations table not created"
                }

            # Step 6: Apply database migrations (ADR-040)
            if verbose:
                Console.info("📦 Applying database migrations...")

            migration_result = self._apply_migrations(verbose=verbose)
            if not migration_result["success"]:
                return {
                    "success": False,
                    "error": f"Failed to apply migrations: {migration_result['error']}"
                }

            if verbose:
                Console.success(f"✓ Applied {migration_result['applied_count']} migration(s)")

            # Step 7: Explicitly clear ALL graph nodes (safety check)
            # Even though docker-compose down -v should clear volumes,
            # this ensures absolute clean state
            if verbose:
                Console.info("🧹 Clearing all graph nodes...")

            try:
                conn = AGEConnection()
                client = conn.get_client()

                # Delete all nodes (and their relationships cascade)
                client._execute_cypher("MATCH (n) DETACH DELETE n")

                conn.close()
                if verbose:
                    Console.success("✓ Graph cleared")
            except Exception as e:
                if verbose:
                    Console.warning(f"⚠ Graph clear failed (might already be empty): {e}")

            # Step 8: Clear log files
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

            # Step 9: Clear checkpoint files
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

            # Step 10: Verify schema
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

    def _apply_migrations(self, verbose: bool = False) -> Dict[str, Any]:
        """
        Apply database migrations from schema/migrations/ directory (ADR-040).

        This is a Python-based migrator that works identically to migrate-db.sh:
        - Idempotent: checks schema_migrations table
        - Ordered: applies migrations in numeric order (001, 002, 003...)
        - Atomic: stops on first failure

        Returns:
            Dict with success status, applied_count, and any errors
        """
        migrations_dir = self.project_root / "schema" / "migrations"

        if not migrations_dir.exists():
            return {"success": False, "error": "Migrations directory not found", "applied_count": 0}

        # Get currently applied migrations from database
        result = subprocess.run(
            [
                "docker", "exec", self.container_name,
                "psql", "-U", self.postgres_user, "-d", self.postgres_db,
                "-t", "-A", "-c",
                "SELECT version FROM public.schema_migrations ORDER BY version"
            ],
            capture_output=True,
            text=True
        )

        applied_versions = set()
        if result.returncode == 0 and result.stdout.strip():
            applied_versions = set(result.stdout.strip().split('\n'))

        # Find pending migrations
        pending_migrations = []
        for migration_file in sorted(migrations_dir.glob("*.sql")):
            # Extract version from filename (001_baseline.sql → 001)
            filename = migration_file.name
            if filename == "README.md":
                continue

            version = filename.split('_')[0]

            # Skip if already applied
            if version in applied_versions:
                continue

            pending_migrations.append((version, migration_file))

        if not pending_migrations:
            return {"success": True, "applied_count": 0}

        # Apply each pending migration
        applied_count = 0
        for version, migration_file in pending_migrations:
            if verbose:
                print(f"  → Applying migration {version}...", end=" ", flush=True)

            # Apply migration
            with open(migration_file, 'r') as f:
                result = subprocess.run(
                    [
                        "docker", "exec", "-i", self.container_name,
                        "psql", "-U", self.postgres_user, "-d", self.postgres_db
                    ],
                    stdin=f,
                    capture_output=True,
                    text=True
                )

            if result.returncode != 0 or "ERROR" in result.stderr:
                error_msg = result.stderr if result.stderr else result.stdout
                return {
                    "success": False,
                    "error": f"Migration {version} failed: {error_msg}",
                    "applied_count": applied_count
                }

            applied_count += 1
            if verbose:
                print("✓")

        return {"success": True, "applied_count": applied_count}

    def _verify_schema(self) -> Dict[str, Any]:
        """Verify schema was created correctly after reset (PostgreSQL + AGE)"""

        # Check that knowledge_graph exists in AGE
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

        # Check that schemas exist (PostgreSQL multi-schema architecture per ADR-024)
        result = subprocess.run(
            [
                "docker", "exec", self.container_name,
                "psql", "-U", self.postgres_user, "-d", self.postgres_db,
                "-t", "-c",
                "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name IN ('kg_api', 'kg_auth', 'kg_logs')"
            ],
            capture_output=True,
            text=True
        )
        schema_count = int(result.stdout.strip() or "0")

        # Check that critical tables exist in their schemas
        result = subprocess.run(
            [
                "docker", "exec", self.container_name,
                "psql", "-U", self.postgres_user, "-d", self.postgres_db,
                "-t", "-c",
                """SELECT COUNT(*) FROM information_schema.tables
                   WHERE (table_schema = 'kg_auth' AND table_name IN ('users', 'api_keys', 'roles'))
                   OR (table_schema = 'kg_api' AND table_name IN ('ingestion_jobs', 'sessions'))"""
            ],
            capture_output=True,
            text=True
        )
        table_count = int(result.stdout.strip() or "0")

        # Check graph node count (should be 0 after reset)
        node_count = 0
        try:
            conn = AGEConnection()
            client = conn.get_client()
            results = client._execute_cypher("MATCH (n) RETURN count(n) as node_count", fetch_one=True)
            node_count = int(list(results.values())[0]) if results else 0
            conn.close()
        except Exception:
            node_count = 0

        # Schema test: Try creating and deleting a test concept (verifies AGE graph works)
        schema_test_passed = False
        try:
            conn = AGEConnection()
            client = conn.get_client()
            # Use params to properly convert lists to JSON
            client._execute_cypher(
                "CREATE (c:Concept {concept_id: $cid, label: $label, embedding: $emb, search_terms: $terms})",
                params={
                    "cid": "test_schema",
                    "label": "Test",
                    "emb": [0.1],
                    "terms": []
                }
            )
            client._execute_cypher(
                "MATCH (c:Concept {concept_id: $cid}) DELETE c",
                params={"cid": "test_schema"}
            )
            schema_test_passed = True
            conn.close()
        except Exception:
            schema_test_passed = False

        return {
            "graph_exists": graph_exists,
            "schema_count": schema_count,  # PostgreSQL schemas (kg_api, kg_auth, kg_logs)
            "table_count": table_count,     # Critical tables in those schemas
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
