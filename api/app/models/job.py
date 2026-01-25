"""Pydantic models for job queue API"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Union
from datetime import datetime


class JobProgress(BaseModel):
    """Job progress information"""
    stage: str = Field(..., description="Current stage of processing")
    chunks_total: Optional[int] = Field(None, description="Total chunks to process")
    chunks_processed: Optional[int] = Field(None, description="Chunks processed so far")
    percent: Optional[int] = Field(None, description="Percentage complete (0-100)")
    current_chunk: Optional[int] = Field(None, description="Current chunk being processed")
    concepts_created: Optional[int] = Field(None, description="Concepts created so far")
    sources_created: Optional[int] = Field(None, description="Sources created so far")


class JobCost(BaseModel):
    """Cost breakdown for ingestion job"""
    extraction: str = Field(..., description="Extraction cost (formatted)")
    embeddings: str = Field(..., description="Embeddings cost (formatted)")
    total: str = Field(..., description="Total cost (formatted)")
    extraction_model: Optional[str] = Field(None, description="Model used for extraction")
    embedding_model: Optional[str] = Field(None, description="Model used for embeddings")


class JobStats(BaseModel):
    """Ingestion statistics"""
    chunks_processed: int = 0
    sources_created: int = 0
    concepts_created: int = 0
    concepts_linked: int = 0
    instances_created: int = 0
    relationships_created: int = 0
    extraction_tokens: int = 0
    embedding_tokens: int = 0


class JobResult(BaseModel):
    """Job completion result"""
    status: str = Field(..., description="Completion status")
    stats: Optional[JobStats] = Field(None, description="Ingestion statistics")
    cost: Optional[JobCost] = Field(None, description="Cost breakdown")
    ontology: Optional[str] = Field(None, description="Target ontology")
    filename: Optional[str] = Field(None, description="Source filename")
    chunks_processed: Optional[int] = Field(None, description="Number of chunks processed")
    message: Optional[str] = Field(None, description="Completion message")


class JobStatus(BaseModel):
    """Complete job status response"""
    job_id: str = Field(..., description="Unique job identifier")
    job_type: str = Field(..., description="Type of job")
    status: str = Field(..., description="Job status: pending|awaiting_approval|approved|queued|processing|completed|failed|cancelled")
    user_id: Optional[int] = Field(None, description="User ID who submitted the job (from kg_auth.users)")
    username: Optional[str] = Field(None, description="Username who submitted the job")
    progress: Optional[Any] = Field(None, description="Progress information (string message or JobProgress object)")
    result: Optional[Any] = Field(None, description="Result data (if completed, format depends on job type)")
    error: Optional[str] = Field(None, description="Error message (if failed)")
    created_at: str = Field(..., description="Job creation timestamp")
    started_at: Optional[str] = Field(None, description="Job start timestamp")
    completed_at: Optional[str] = Field(None, description="Job completion timestamp")
    content_hash: Optional[str] = Field(None, description="Content hash for deduplication")
    ontology: Optional[str] = Field(None, description="Target ontology")
    processing_mode: Optional[str] = Field("serial", description="Processing mode: serial|parallel (default: serial)")
    # ADR-014: Approval workflow fields
    analysis: Optional[Dict[str, Any]] = Field(None, description="Pre-ingestion analysis (file stats, cost estimates)")
    approved_at: Optional[str] = Field(None, description="Approval timestamp")
    approved_by: Optional[str] = Field(None, description="User who approved (Phase 2)")
    expires_at: Optional[str] = Field(None, description="Expiration timestamp for unapproved jobs")
    # ADR-051: Source provenance (extracted from job_data for display)
    filename: Optional[str] = Field(None, description="Original filename or display name")
    source_type: Optional[str] = Field(None, description="Source type: file, stdin, mcp, api")
    source_path: Optional[str] = Field(None, description="Full filesystem path (file ingestion only)")
    source_hostname: Optional[str] = Field(None, description="Hostname where ingestion was initiated")


class JobSubmitResponse(BaseModel):
    """Response when submitting a new job"""
    job_id: str = Field(..., description="Unique job identifier")
    status: str = Field(..., description="Initial job status")
    content_hash: str = Field(..., description="Content hash for tracking")
    position: Optional[int] = Field(None, description="Position in queue")
    message: Optional[str] = Field(None, description="Info message")


class DuplicateJobResponse(BaseModel):
    """Response when duplicate content detected"""
    duplicate: bool = Field(True, description="Always true for this response type")
    existing_job_id: str = Field(..., description="ID of existing job")
    status: str = Field(..., description="Status of existing job")
    created_at: str = Field(..., description="When existing job was created")
    completed_at: Optional[str] = Field(None, description="When existing job completed")
    result: Optional[JobResult] = Field(None, description="Result if completed")
    message: str = Field(..., description="User-friendly message")
    use_force: Optional[str] = Field(None, description="How to override duplicate detection")
