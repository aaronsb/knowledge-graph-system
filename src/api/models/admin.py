"""
Admin API Models

Models for backup, restore, status, and reset operations.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


# ========== Status Models ==========

class DockerStatus(BaseModel):
    """Docker container status"""
    running: bool
    container_name: Optional[str] = None
    status: Optional[str] = None
    ports: Optional[str] = None


class DatabaseConnection(BaseModel):
    """Database connection status"""
    connected: bool
    uri: str
    error: Optional[str] = None


class DatabaseStats(BaseModel):
    """Database statistics"""
    concepts: int = 0
    sources: int = 0
    instances: int = 0
    relationships: int = 0


class PythonEnvironment(BaseModel):
    """Python environment status"""
    venv_exists: bool
    python_version: Optional[str] = None


class ConfigurationStatus(BaseModel):
    """Configuration file status"""
    env_exists: bool
    anthropic_key_configured: bool
    openai_key_configured: bool


class SystemStatusResponse(BaseModel):
    """Complete system status"""
    docker: DockerStatus
    database_connection: DatabaseConnection
    database_stats: Optional[DatabaseStats] = None
    python_env: PythonEnvironment
    configuration: ConfigurationStatus
    neo4j_browser_url: Optional[str] = None
    bolt_url: Optional[str] = None


# ========== Backup Models ==========

class OntologyInfo(BaseModel):
    """Ontology information"""
    ontology: str
    file_count: int
    concept_count: int
    instance_count: int = 0


class BackupRequest(BaseModel):
    """Request to create a backup"""
    backup_type: str = Field(..., description="'full' or 'ontology'")
    ontology_name: Optional[str] = Field(None, description="Required if backup_type is 'ontology'")
    output_filename: Optional[str] = Field(None, description="Custom output filename")


class BackupIntegrityAssessment(BaseModel):
    """Backup integrity assessment results"""
    external_dependencies_count: int = 0
    warnings_count: int = 0
    issues_count: int = 0
    has_external_deps: bool = False
    details: Dict[str, Any] = {}


class BackupResponse(BaseModel):
    """Backup operation response"""
    success: bool
    backup_file: str
    file_size_mb: float
    statistics: Dict[str, int]
    integrity_assessment: Optional[BackupIntegrityAssessment] = None
    message: str


class ListBackupsResponse(BaseModel):
    """List available backups"""
    backups: List[Dict[str, Any]]
    backup_dir: str
    count: int


# ========== Restore Models ==========

class RestoreRequest(BaseModel):
    """Request to restore a backup (requires authentication)"""
    username: str = Field(..., description="Username for authentication")
    password: str = Field(..., description="Password for authentication")
    backup_file: str = Field(..., description="Path to backup file")
    overwrite: bool = Field(False, description="Overwrite existing data")
    handle_external_deps: str = Field(
        "prune",
        description="How to handle external dependencies: 'prune', 'stitch', or 'defer'"
    )


class RestoreResponse(BaseModel):
    """Restore operation response"""
    success: bool
    restored_counts: Dict[str, int]
    warnings: List[str] = []
    message: str
    external_deps_handled: Optional[str] = None


# ========== Reset Models ==========

class ResetRequest(BaseModel):
    """Request to reset database (requires authentication)"""
    username: str = Field(..., description="Username for authentication")
    password: str = Field(..., description="Password for authentication")
    confirm: bool = Field(..., description="Must be true to confirm destructive operation")
    clear_logs: bool = Field(True, description="Clear log files")
    clear_checkpoints: bool = Field(True, description="Clear checkpoint files")


class SchemaValidation(BaseModel):
    """Schema validation results"""
    constraints_count: int
    vector_index_exists: bool
    node_count: int
    schema_test_passed: bool


class ResetResponse(BaseModel):
    """Reset operation response"""
    success: bool
    schema_validation: SchemaValidation
    message: str
    warnings: List[str] = []


# ========== Admin Job Models ==========

class AdminJobStatus(BaseModel):
    """Status of a long-running admin operation"""
    job_id: str
    operation: str  # 'backup', 'restore', 'reset'
    status: str  # 'running', 'completed', 'failed'
    progress: Optional[int] = Field(None, description="Progress percentage 0-100")
    message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
