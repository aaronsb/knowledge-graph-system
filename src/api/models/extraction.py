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
    provider: str = Field(..., description="AI provider: 'openai', 'anthropic', or 'none'")
    model: Optional[str] = Field(None, description="Model name (e.g., 'gpt-4o', 'claude-sonnet-4-20250514')")
    supports_vision: bool = Field(..., description="Whether the model supports vision/image inputs")
    supports_json_mode: bool = Field(..., description="Whether the model supports JSON mode")
    max_tokens: Optional[int] = Field(None, description="Maximum token limit")
    config_id: Optional[int] = Field(None, description="Database config ID")


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


class UpdateExtractionConfigRequest(BaseModel):
    """
    Request to update AI extraction configuration.

    All fields except provider and model_name are optional.
    """
    provider: str = Field(..., description="Provider: 'openai' or 'anthropic'")
    model_name: str = Field(..., description="Model identifier (e.g., 'gpt-4o', 'claude-sonnet-4-20250514')")
    supports_vision: Optional[bool] = Field(False, description="Model supports vision inputs")
    supports_json_mode: Optional[bool] = Field(True, description="Model supports JSON mode")
    max_tokens: Optional[int] = Field(None, description="Maximum token limit")
    updated_by: Optional[str] = Field('api', description="User/admin who made the change")


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
