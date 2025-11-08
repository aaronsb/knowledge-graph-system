"""
Embedding Configuration API Models

Request/response models for embedding configuration endpoints (ADR-039).
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime


class ResourceAllocation(BaseModel):
    """Resource allocation settings for local embeddings"""
    max_memory_mb: Optional[int] = Field(None, description="Maximum RAM for model (MB)")
    num_threads: Optional[int] = Field(None, description="CPU threads for inference")
    device: Optional[str] = Field(None, description="Device: cpu, cuda, or mps")
    batch_size: Optional[int] = Field(None, description="Batch size for generation")


class EmbeddingConfigResponse(BaseModel):
    """
    Public embedding configuration response.

    Returns summary info suitable for clients to determine if they can use
    browser-side embeddings.
    """
    provider: str = Field(..., description="Embedding provider: 'openai', 'local', or 'none'")
    model: Optional[str] = Field(None, description="Model name (e.g., 'nomic-ai/nomic-embed-text-v1.5')")
    dimensions: Optional[int] = Field(None, description="Embedding vector dimensions")
    precision: Optional[str] = Field(None, description="Precision: 'float16' or 'float32'")
    config_id: Optional[int] = Field(None, description="Database config ID")
    supports_browser: bool = Field(..., description="Whether this model is available in transformers.js")
    resource_allocation: Optional[ResourceAllocation] = Field(None, description="Resource settings (local only)")


class EmbeddingConfigDetail(BaseModel):
    """
    Full embedding configuration details (admin only).

    Includes all configuration parameters and metadata.
    """
    id: int
    provider: str
    model_name: Optional[str] = None
    embedding_dimensions: Optional[int] = None
    precision: Optional[str] = None
    max_memory_mb: Optional[int] = None
    num_threads: Optional[int] = None
    device: Optional[str] = None
    batch_size: Optional[int] = None
    max_seq_length: Optional[int] = None
    normalize_embeddings: Optional[bool] = None
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str] = None
    active: bool


class UpdateEmbeddingConfigRequest(BaseModel):
    """
    Request to update embedding configuration.

    All fields are optional. Omitted fields keep existing values.
    """
    provider: str = Field(..., description="Provider: 'openai' or 'local'")
    model_name: Optional[str] = Field(None, description="HuggingFace model ID (for local)")
    embedding_dimensions: Optional[int] = Field(None, description="Vector dimensions")
    precision: Optional[str] = Field('float16', description="Precision: 'float16' or 'float32'")
    max_memory_mb: Optional[int] = Field(None, description="RAM limit (MB)")
    num_threads: Optional[int] = Field(None, description="CPU threads")
    device: Optional[str] = Field('cpu', description="Device: 'cpu', 'cuda', or 'mps'")
    batch_size: Optional[int] = Field(8, description="Batch size for generation")
    max_seq_length: Optional[int] = Field(None, description="Max sequence length (tokens)")
    normalize_embeddings: Optional[bool] = Field(True, description="Normalize embeddings for cosine similarity")
    updated_by: Optional[str] = Field('api', description="User/admin who made the change")


class UpdateEmbeddingConfigResponse(BaseModel):
    """Response after updating embedding configuration"""
    success: bool
    message: str
    config_id: int
    reload_required: bool = Field(
        ...,
        description="True if API restart required to apply changes (Phase 1). "
                    "In Phase 2, this triggers automatic hot reload."
    )


class ReloadEmbeddingModelResponse(BaseModel):
    """Response after hot reloading embedding model"""
    success: bool
    message: str
    provider: str
    model: Optional[str] = None
    dimensions: Optional[int] = None
