"""
AI Extraction Configuration API Models

Request/response models for AI extraction configuration endpoints (ADR-041).
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ExtractionConfigResponse(BaseModel):
    """
    Public AI extraction configuration response.

    Returns summary info suitable for clients to understand which AI provider
    is active and its capabilities.
    """
    provider: str = Field(..., description="AI provider: 'openai', 'anthropic', 'ollama', or 'none'")
    model: Optional[str] = Field(None, description="Model name (e.g., 'gpt-4o', 'claude-sonnet-4-20250514', 'mistral:7b-instruct')")
    supports_vision: bool = Field(..., description="Whether the model supports vision/image inputs")
    supports_json_mode: bool = Field(..., description="Whether the model supports JSON mode")
    max_tokens: Optional[int] = Field(None, description="Maximum token limit")
    config_id: Optional[int] = Field(None, description="Database config ID")

    # Local provider configuration (Ollama, vLLM) - ADR-042
    base_url: Optional[str] = Field(None, description="Base URL for local providers (e.g., http://localhost:11434)")
    temperature: Optional[float] = Field(None, description="Sampling temperature (0.0-1.0)")
    top_p: Optional[float] = Field(None, description="Nucleus sampling threshold (0.0-1.0)")
    gpu_layers: Optional[int] = Field(None, description="GPU layers: -1=auto, 0=CPU only, >0=specific count")
    num_threads: Optional[int] = Field(None, description="CPU threads for inference")
    thinking_mode: Optional[str] = Field(None, description="Thinking mode: 'off', 'low', 'medium', 'high' (Ollama 0.12.x+)")

    # Rate limiting configuration (Migration 018)
    max_concurrent_requests: Optional[int] = Field(None, description="Maximum concurrent API requests for this provider")
    max_retries: Optional[int] = Field(None, description="Maximum retry attempts for rate-limited requests (429 errors)")


class ExtractionConfigDetail(BaseModel):
    """
    Full AI extraction configuration details (admin only).

    Includes all configuration parameters and metadata.
    """
    id: int
    provider: str
    model_name: str
    supports_vision: bool
    supports_json_mode: bool
    max_tokens: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    updated_by: Optional[str] = None
    active: bool

    # Local provider configuration (Ollama, vLLM) - ADR-042
    base_url: Optional[str] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    gpu_layers: Optional[int] = None
    num_threads: Optional[int] = None
    thinking_mode: Optional[str] = None

    # Rate limiting configuration (Migration 018)
    max_concurrent_requests: Optional[int] = None
    max_retries: Optional[int] = None


class UpdateExtractionConfigRequest(BaseModel):
    """
    Request to update AI extraction configuration.

    All fields except provider and model_name are optional.
    """
    provider: str = Field(..., description="Provider: 'openai', 'anthropic', or 'ollama'")
    model_name: str = Field(..., description="Model identifier (e.g., 'gpt-4o', 'mistral:7b-instruct')")
    supports_vision: Optional[bool] = Field(False, description="Model supports vision inputs")
    supports_json_mode: Optional[bool] = Field(True, description="Model supports JSON mode")
    max_tokens: Optional[int] = Field(None, description="Maximum token limit")
    updated_by: Optional[str] = Field('api', description="User/admin who made the change")

    # Local provider configuration (Ollama, vLLM) - ADR-042
    base_url: Optional[str] = Field(None, description="Base URL for local providers")
    temperature: Optional[float] = Field(None, description="Sampling temperature (0.0-1.0)")
    top_p: Optional[float] = Field(None, description="Nucleus sampling (0.0-1.0)")
    gpu_layers: Optional[int] = Field(None, description="GPU layers: -1=auto, 0=CPU, >0=specific")
    num_threads: Optional[int] = Field(None, description="CPU threads for inference")
    thinking_mode: Optional[str] = Field('off', description="Thinking mode: 'off', 'low', 'medium', 'high' (Ollama 0.12.x+)")

    # Rate limiting configuration (Migration 018)
    max_concurrent_requests: Optional[int] = Field(None, description="Maximum concurrent API requests (OpenAI=8, Anthropic=4, Ollama=1)")
    max_retries: Optional[int] = Field(None, description="Maximum retry attempts for rate limits (cloud=8, local=3)")


class UpdateExtractionConfigResponse(BaseModel):
    """Response after updating AI extraction configuration"""
    success: bool
    message: str
    config_id: int
    reload_required: bool = Field(
        ...,
        description="True if API restart required to apply changes. "
                    "In DEVELOPMENT_MODE=false, configuration is loaded from database on startup."
    )
