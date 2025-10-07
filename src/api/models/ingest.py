"""Pydantic models for ingestion API"""

from pydantic import BaseModel, Field
from typing import Optional


class IngestionOptions(BaseModel):
    """Options for document ingestion"""
    target_words: int = Field(1000, description="Target words per chunk", ge=100, le=5000)
    min_words: Optional[int] = Field(None, description="Minimum words per chunk (defaults to 80% of target)")
    max_words: Optional[int] = Field(None, description="Maximum words per chunk (defaults to 150% of target)")
    overlap_words: int = Field(200, description="Overlap between chunks", ge=0, le=1000)

    def get_min_words(self) -> int:
        """Get min_words with default calculation"""
        return self.min_words or int(self.target_words * 0.8)

    def get_max_words(self) -> int:
        """Get max_words with default calculation"""
        return self.max_words or int(self.target_words * 1.5)


class IngestionRequest(BaseModel):
    """Request to ingest a document"""
    ontology: str = Field(..., description="Ontology/collection name", min_length=1)
    filename: Optional[str] = Field(None, description="Original filename (auto-generated if not provided)")
    force: bool = Field(False, description="Force re-ingestion even if duplicate detected")
    options: Optional[IngestionOptions] = Field(
        default_factory=IngestionOptions,
        description="Chunking and processing options"
    )
