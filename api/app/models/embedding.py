"""
Embedding Profile API Models

Request/response models for embedding profile endpoints.
Profiles unify text + image embedding model configuration (migration 055).
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, Any, List
from datetime import datetime


class ResourceAllocation(BaseModel):
    """Resource allocation settings for local embeddings"""
    max_memory_mb: Optional[int] = Field(None, description="Maximum RAM for model (MB)")
    num_threads: Optional[int] = Field(None, description="CPU threads for inference")
    device: Optional[str] = Field(None, description="Device: cpu, cuda, or mps")
    batch_size: Optional[int] = Field(None, description="Batch size for generation")


# ---------------------------------------------------------------------------
# Public response (no auth required)
# ---------------------------------------------------------------------------

class EmbeddingConfigResponse(BaseModel):
    """
    Public embedding configuration response.

    Returns summary info suitable for clients to determine if they can use
    browser-side embeddings.  Includes both text and image model info.
    """
    provider: str = Field(..., description="Text embedding provider: 'openai', 'local', or 'none'")
    model: Optional[str] = Field(None, description="Text model name")
    dimensions: Optional[int] = Field(None, description="Text embedding dimensions")
    precision: Optional[str] = Field(None, description="Text precision")
    config_id: Optional[int] = Field(None, description="Profile ID")
    supports_browser: bool = Field(..., description="Whether text model is available in transformers.js")
    vector_space: Optional[str] = Field(None, description="Vector space compatibility tag")
    multimodal: Optional[bool] = Field(None, description="True if one model handles both text and image")
    image_model: Optional[str] = Field(None, description="Image model name (None if text-only or multimodal)")
    image_dimensions: Optional[int] = Field(None, description="Image embedding dimensions")
    resource_allocation: Optional[ResourceAllocation] = Field(None, description="Resource settings (local only)")


# ---------------------------------------------------------------------------
# Admin detail
# ---------------------------------------------------------------------------

class EmbeddingProfileTextSlot(BaseModel):
    """Text model slot within a profile"""
    provider: str
    model_name: str
    loader: str
    revision: Optional[str] = None
    dimensions: int
    precision: Optional[str] = None
    trust_remote_code: bool = False
    query_prefix: Optional[str] = None
    document_prefix: Optional[str] = None


class EmbeddingProfileImageSlot(BaseModel):
    """Image model slot within a profile (None for text-only profiles)"""
    provider: str
    model_name: str
    loader: str
    revision: Optional[str] = None
    dimensions: int
    precision: Optional[str] = None
    trust_remote_code: bool = False


class EmbeddingProfileDetail(BaseModel):
    """
    Full embedding profile details (admin only).

    Includes all configuration parameters and metadata for both text and image slots.
    """
    id: int
    name: str
    vector_space: str
    multimodal: bool

    # Text slot
    text_provider: str
    text_model_name: str
    text_loader: str
    text_revision: Optional[str] = None
    text_dimensions: int
    text_precision: Optional[str] = None
    text_trust_remote_code: bool = False
    text_query_prefix: Optional[str] = None
    text_document_prefix: Optional[str] = None

    # Image slot (nullable for text-only profiles)
    image_provider: Optional[str] = None
    image_model_name: Optional[str] = None
    image_loader: Optional[str] = None
    image_revision: Optional[str] = None
    image_dimensions: Optional[int] = None
    image_precision: Optional[str] = None
    image_trust_remote_code: bool = False

    # Resources
    device: Optional[str] = None
    max_memory_mb: Optional[int] = None
    num_threads: Optional[int] = None
    batch_size: Optional[int] = None
    max_seq_length: Optional[int] = None
    normalize_embeddings: Optional[bool] = None

    # Lifecycle
    active: bool
    delete_protected: bool = False
    change_protected: bool = False
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str] = None


# ---------------------------------------------------------------------------
# Backward-compat alias (admin routes used to return EmbeddingConfigDetail)
# ---------------------------------------------------------------------------
EmbeddingConfigDetail = EmbeddingProfileDetail


# ---------------------------------------------------------------------------
# Create request
# ---------------------------------------------------------------------------

class EmbeddingProfileCreateRequest(BaseModel):
    """
    Request to create a new embedding profile.

    Supports three modes:
    1. Explicit: provide all text_* and optionally image_* fields
    2. Shorthand: provide provider/model/dimensions (mapped to text slot)
    3. JSON import: caller sends pre-built profile dict (handled at route level)
    """
    # Profile metadata
    name: Optional[str] = Field(None, description="Profile name (auto-generated if omitted)")
    vector_space: Optional[str] = Field(None, description="Vector space compatibility tag")
    multimodal: bool = Field(False, description="True = text model handles both text and image")

    # Text slot (explicit)
    text_provider: Optional[str] = Field(None, description="Text provider: 'local' or 'openai'")
    text_model_name: Optional[str] = Field(None, description="Text model (HuggingFace ID or API model)")
    text_loader: Optional[str] = Field(None, description="Loader: 'sentence-transformers', 'transformers', 'api'")
    text_revision: Optional[str] = Field(None, description="Model revision/commit hash")
    text_dimensions: Optional[int] = Field(None, description="Text embedding dimensions")
    text_precision: Optional[str] = Field('float16', description="Precision: 'float16' or 'float32'")
    text_trust_remote_code: bool = Field(False, description="Trust remote code for text model")
    text_query_prefix: Optional[str] = Field(None, description="Prefix for search queries (e.g. 'search_query: ')")
    text_document_prefix: Optional[str] = Field(None, description="Prefix for stored documents (e.g. 'search_document: ')")

    # Image slot (optional, ignored when multimodal=True)
    image_provider: Optional[str] = Field(None, description="Image provider")
    image_model_name: Optional[str] = Field(None, description="Image model")
    image_loader: Optional[str] = Field(None, description="Image loader")
    image_revision: Optional[str] = Field(None, description="Image model revision")
    image_dimensions: Optional[int] = Field(None, description="Image embedding dimensions")
    image_precision: Optional[str] = Field('float16', description="Image precision")
    image_trust_remote_code: bool = Field(False, description="Trust remote code for image model")

    # Shorthand (maps to text slot for backward compat)
    provider: Optional[str] = Field(None, description="Shorthand for text_provider")
    model_name: Optional[str] = Field(None, description="Shorthand for text_model_name")
    embedding_dimensions: Optional[int] = Field(None, description="Shorthand for text_dimensions")

    # Resources
    device: Optional[str] = Field('cpu', description="Device: 'cpu', 'cuda', or 'mps'")
    max_memory_mb: Optional[int] = Field(None, description="RAM limit (MB)")
    num_threads: Optional[int] = Field(None, description="CPU threads")
    batch_size: Optional[int] = Field(8, description="Batch size for generation")
    max_seq_length: Optional[int] = Field(None, description="Max sequence length (tokens)")
    normalize_embeddings: Optional[bool] = Field(True, description="Normalize for cosine similarity")
    updated_by: Optional[str] = Field('api', description="User/admin who made the change")


# Keep old name for backward compat in routes
UpdateEmbeddingConfigRequest = EmbeddingProfileCreateRequest


class UpdateEmbeddingConfigResponse(BaseModel):
    """Response after creating/updating embedding configuration"""
    success: bool
    message: str
    config_id: int
    reload_required: bool = Field(
        False,
        description="True if hot reload needed to apply changes"
    )


class ReloadEmbeddingModelResponse(BaseModel):
    """Response after hot reloading embedding model"""
    success: bool
    message: str
    provider: str
    model: Optional[str] = None
    dimensions: Optional[int] = None
