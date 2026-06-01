"""
Admin Service

Service layer for admin operations (backup, restore, status, reset).
Wraps the Python admin tools and provides async execution.
"""

import asyncio
import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..lib.age_client import AGEClient

logger = logging.getLogger(__name__)

from ..models.admin import (
    SystemStatusResponse,
    DockerStatus,
    DatabaseConnection,
    DatabaseStats,
    PythonEnvironment,
    ConfigurationStatus,
    ListBackupsResponse,
)


class AdminService:
    """Service for admin operations"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent.parent
        self.backup_dir = self.project_root / "backups"
        self.backup_dir.mkdir(exist_ok=True)

    async def get_system_status(self) -> SystemStatusResponse:
        """Get complete system status"""
        # Docker status
        docker_running = await self._check_docker_running()
        docker_info = await self._get_docker_info() if docker_running else None

        # Database connection
        db_connected, db_error = await self._check_database_connection()
        db_stats = await self._get_database_stats() if db_connected else None

        # Python environment (always available in container)
        python_version = await self._get_python_version()

        # Configuration (API keys from encrypted database)
        anthropic_configured, openai_configured = await self._check_api_keys()

        return SystemStatusResponse(
            docker=DockerStatus(
                running=docker_running,
                container_name=docker_info.get("name") if docker_info else None,
                status=docker_info.get("status") if docker_info else None,
                ports=docker_info.get("ports") if docker_info else None,
            ),
            database_connection=DatabaseConnection(
                connected=db_connected,
                uri=f"postgresql://{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'knowledge_graph')}",
                error=db_error,
            ),
            database_stats=db_stats,
            python_env=PythonEnvironment(
                venv_exists=True,  # Always true in container
                python_version=python_version,
            ),
            configuration=ConfigurationStatus(
                env_exists=True,  # Config is in database, not .env
                anthropic_key_configured=anthropic_configured,
                openai_key_configured=openai_configured,
            ),
            neo4j_browser_url=f"postgresql://{os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}/{os.getenv('POSTGRES_DB', 'knowledge_graph')}" if docker_running else None,
            bolt_url=None,  # PostgreSQL doesn't use Bolt protocol
        )

    async def list_backups(self) -> ListBackupsResponse:
        """List available backup files"""
        backup_files = sorted(
            self.backup_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )

        backups = []
        for backup_file in backup_files:
            stat = backup_file.stat()
            backups.append({
                "filename": backup_file.name,
                "path": str(backup_file),
                "size_mb": stat.st_size / (1024 * 1024),
                "created": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

        return ListBackupsResponse(
            backups=backups,
            backup_dir=str(self.backup_dir),
            count=len(backups),
        )

    # ========== Helper Methods ==========

    async def _check_docker_running(self) -> bool:
        """Check if running in container (always true when API is containerized)"""
        # When running in a container, we can't run docker commands
        # Check if we're in a container by looking for /.dockerenv
        return Path("/.dockerenv").exists()

    async def _get_docker_info(self) -> Dict[str, str]:
        """Get container info"""
        # When running in a container, return info about current environment
        if Path("/.dockerenv").exists():
            return {
                "name": "kg-api-dev",
                "status": "running (containerized)",
                "ports": "8000"
            }
        return {}

    async def _check_database_connection(self) -> tuple[bool, Optional[str]]:
        """Check if database is connectable using direct connection"""
        import psycopg2

        try:
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                database=os.getenv("POSTGRES_DB", "knowledge_graph"),
                user=os.getenv("POSTGRES_USER", "admin"),
                password=os.environ["POSTGRES_PASSWORD"],
                connect_timeout=5
            )
            conn.close()
            return True, None
        except Exception as e:
            return False, str(e)

    async def _get_database_stats(self) -> DatabaseStats:
        """Get database statistics using Apache AGE via AGEClient"""
        try:
            # Use AGEClient which handles all AGE connection logic
            client = AGEClient()

            # Execute count queries using AGEClient
            def query_count(cypher_query: str) -> int:
                try:
                    results = client._execute_cypher(cypher_query, fetch_one=True)
                    if results:
                        # Get the count value (column name depends on the RETURN clause)
                        count_value = list(results.values())[0] if results else 0
                        return int(count_value)
                    return 0
                except Exception:
                    return 0

            # Run queries in thread pool to avoid blocking async
            loop = asyncio.get_event_loop()
            concepts = await loop.run_in_executor(
                None, query_count, "MATCH (c:Concept) RETURN count(c)"
            )
            sources = await loop.run_in_executor(
                None, query_count, "MATCH (s:Source) RETURN count(s)"
            )
            instances = await loop.run_in_executor(
                None, query_count, "MATCH (i:Instance) RETURN count(i)"
            )
            relationships = await loop.run_in_executor(
                None, query_count, "MATCH ()-[r]->() RETURN count(r)"
            )

            client.close()

            return DatabaseStats(
                concepts=concepts,
                sources=sources,
                instances=instances,
                relationships=relationships,
            )
        except Exception as e:
            # If AGEClient fails, return zeros
            return DatabaseStats(
                concepts=0,
                sources=0,
                instances=0,
                relationships=0,
            )

    async def _get_python_version(self) -> Optional[str]:
        """Get Python version from current interpreter"""
        import sys
        return f"Python {sys.version.split()[0]}"

    async def _check_api_keys(self) -> tuple[bool, bool]:
        """Check if API keys are configured (from encrypted database storage)"""
        from ..lib.encrypted_keys import EncryptedKeyStore
        import psycopg2

        anthropic = False
        openai = False

        try:
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=int(os.getenv("POSTGRES_PORT", "5432")),
                database=os.getenv("POSTGRES_DB", "knowledge_graph"),
                user=os.getenv("POSTGRES_USER", "admin"),
                password=os.environ["POSTGRES_PASSWORD"]
            )
            key_store = EncryptedKeyStore(conn)

            try:
                key_store.get_key("anthropic")
                anthropic = True
            except ValueError:
                pass

            try:
                key_store.get_key("openai")
                openai = True
            except ValueError:
                pass

            conn.close()
        except Exception:
            pass

        return anthropic, openai

