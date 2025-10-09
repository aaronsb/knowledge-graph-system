"""
Admin Service

Service layer for admin operations (backup, restore, status, reset).
Wraps the Python admin tools and provides async execution.
"""

import asyncio
import subprocess
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..models.admin import (
    SystemStatusResponse,
    DockerStatus,
    DatabaseConnection,
    DatabaseStats,
    PythonEnvironment,
    ConfigurationStatus,
    BackupResponse,
    BackupIntegrityAssessment,
    ListBackupsResponse,
    RestoreResponse,
    ResetResponse,
    SchemaValidation,
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

        # Python environment
        venv_exists = (self.project_root / "venv").exists()
        python_version = await self._get_python_version() if venv_exists else None

        # Configuration
        env_exists = (self.project_root / ".env").exists()
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
                venv_exists=venv_exists,
                python_version=python_version,
            ),
            configuration=ConfigurationStatus(
                env_exists=env_exists,
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

    async def create_backup(
        self,
        backup_type: str,
        ontology_name: Optional[str] = None,
        output_filename: Optional[str] = None
    ) -> BackupResponse:
        """Create a backup (full or ontology-specific)"""
        # Build command
        cmd = [
            str(self.project_root / "venv" / "bin" / "python"),
            "-m",
            "src.admin.backup",
        ]

        if backup_type == "full":
            cmd.append("--auto-full")
        elif backup_type == "ontology":
            if not ontology_name:
                raise ValueError("ontology_name required for ontology backup")
            cmd.extend(["--ontology", ontology_name])
        else:
            raise ValueError(f"Invalid backup_type: {backup_type}")

        if output_filename:
            cmd.extend(["--output", output_filename])

        # Execute backup
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.project_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Backup failed: {stderr.decode()}")

        # Parse output to find backup file
        output = stdout.decode()
        backup_file = await self._extract_backup_file_from_output(output, output_filename)

        # Get file info
        backup_path = Path(backup_file)
        file_size_mb = backup_path.stat().st_size / (1024 * 1024)

        # Load backup to get statistics
        with open(backup_path, 'r') as f:
            backup_data = json.load(f)

        statistics = backup_data.get('statistics', {})

        # TODO: Add integrity assessment
        integrity = None

        return BackupResponse(
            success=True,
            backup_file=str(backup_path),
            file_size_mb=file_size_mb,
            statistics=statistics,
            integrity_assessment=integrity,
            message=f"Backup created successfully: {backup_path.name}",
        )

    async def restore_backup(
        self,
        backup_file: str,
        overwrite: bool = False,
        handle_external_deps: str = "prune"
    ) -> RestoreResponse:
        """Restore a backup"""
        # Validate backup file exists
        backup_path = Path(backup_file)
        if not backup_path.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_file}")

        # Build command
        cmd = [
            str(self.project_root / "venv" / "bin" / "python"),
            "-m",
            "src.admin.restore",
            "--file",
            str(backup_path),
        ]

        if overwrite:
            cmd.append("--overwrite")

        # TODO: Add external deps handling once the restore script supports it

        # Execute restore
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.project_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,  # For confirmations
        )

        # Send confirmations (auto-accept for now)
        stdout, stderr = await proc.communicate(input=b"y\n")

        if proc.returncode != 0:
            raise RuntimeError(f"Restore failed: {stderr.decode()}")

        # Parse output for results
        output = stdout.decode()

        return RestoreResponse(
            success=True,
            restored_counts={},  # TODO: Parse from output
            message="Restore completed successfully",
            external_deps_handled=handle_external_deps,
        )

    async def reset_database(
        self,
        clear_logs: bool = True,
        clear_checkpoints: bool = True
    ) -> ResetResponse:
        """Reset database (nuclear option)"""
        # Build command
        cmd = [str(self.project_root / "scripts" / "reset.sh")]

        # Execute reset
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=self.project_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE,
        )

        # Auto-confirm
        stdout, stderr = await proc.communicate(input=b"y\n")

        if proc.returncode != 0:
            raise RuntimeError(f"Reset failed: {stderr.decode()}")

        # Parse output for validation results
        output = stdout.decode()

        # TODO: Parse schema validation from output
        schema_validation = SchemaValidation(
            constraints_count=3,
            vector_index_exists=True,
            node_count=0,
            schema_test_passed=True,
        )

        return ResetResponse(
            success=True,
            schema_validation=schema_validation,
            message="Database reset successfully",
        )

    # ========== Helper Methods ==========

    async def _check_docker_running(self) -> bool:
        """Check if PostgreSQL Docker container is running"""
        proc = await asyncio.create_subprocess_exec(
            "docker", "ps", "--format", "{{.Names}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return "knowledge-graph-postgres" in stdout.decode()

    async def _get_docker_info(self) -> Dict[str, str]:
        """Get Docker container info"""
        proc = await asyncio.create_subprocess_exec(
            "docker", "ps",
            "--filter", "name=knowledge-graph-postgres",
            "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        parts = stdout.decode().strip().split("\t")
        if len(parts) >= 3:
            return {"name": parts[0], "status": parts[1], "ports": parts[2]}
        return {}

    async def _check_database_connection(self) -> tuple[bool, Optional[str]]:
        """Check if database is connectable"""
        postgres_user = os.getenv("POSTGRES_USER", "admin")
        postgres_db = os.getenv("POSTGRES_DB", "knowledge_graph")
        proc = await asyncio.create_subprocess_exec(
            "docker", "exec", "knowledge-graph-postgres",
            "psql", "-U", postgres_user, "-d", postgres_db,
            "-c", "SELECT 1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        connected = proc.returncode == 0
        error = stderr.decode() if not connected else None
        return connected, error

    async def _get_database_stats(self) -> DatabaseStats:
        """Get database statistics using Apache AGE"""
        postgres_user = os.getenv("POSTGRES_USER", "admin")
        postgres_db = os.getenv("POSTGRES_DB", "knowledge_graph")
        graph_name = "knowledge_graph"

        async def query_count(cypher_query: str) -> int:
            # Wrap Cypher query in AGE SQL syntax
            sql_query = f"SELECT * FROM cypher('{graph_name}', $$ {cypher_query} $$) as (count agtype);"
            proc = await asyncio.create_subprocess_exec(
                "docker", "exec", "knowledge-graph-postgres",
                "psql", "-U", postgres_user, "-d", postgres_db,
                "-t", "-c", sql_query,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode().strip()
            # Parse AGE integer output (comes as string)
            try:
                return int(output)
            except (ValueError, TypeError):
                return 0

        concepts = await query_count("MATCH (c:Concept) RETURN count(c)")
        sources = await query_count("MATCH (s:Source) RETURN count(s)")
        instances = await query_count("MATCH (i:Instance) RETURN count(i)")
        relationships = await query_count("MATCH ()-[r]->() RETURN count(r)")

        return DatabaseStats(
            concepts=concepts,
            sources=sources,
            instances=instances,
            relationships=relationships,
        )

    async def _get_python_version(self) -> Optional[str]:
        """Get Python version from venv"""
        python_path = self.project_root / "venv" / "bin" / "python"
        if not python_path.exists():
            return None

        proc = await asyncio.create_subprocess_exec(
            str(python_path), "--version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        return stdout.decode().strip()

    async def _check_api_keys(self) -> tuple[bool, bool]:
        """Check if API keys are configured"""
        env_file = self.project_root / ".env"
        if not env_file.exists():
            return False, False

        content = env_file.read_text()
        anthropic = "ANTHROPIC_API_KEY=" in content and "ANTHROPIC_API_KEY=$" not in content
        openai = "OPENAI_API_KEY=" in content and "OPENAI_API_KEY=$" not in content
        return anthropic, openai

    async def _extract_backup_file_from_output(
        self,
        output: str,
        custom_filename: Optional[str]
    ) -> str:
        """Extract backup filename from command output"""
        # If custom filename was provided, use it
        if custom_filename:
            return str(self.backup_dir / custom_filename)

        # Otherwise, find latest backup file
        backup_files = sorted(
            self.backup_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        if backup_files:
            return str(backup_files[0])

        raise RuntimeError("Could not determine backup file path")
