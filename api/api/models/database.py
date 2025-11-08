"""Pydantic models for database operations"""

from pydantic import BaseModel
from typing import Dict, List, Optional, Any


class RelationshipTypeCount(BaseModel):
    """Count of relationships by type"""
    rel_type: str
    count: int


class DatabaseStatsResponse(BaseModel):
    """Database statistics"""
    nodes: Dict[str, int]  # {"concepts": 100, "sources": 50, "instances": 200}
    relationships: Dict[str, Any]  # {"total": 150, "by_type": [...]}


class DatabaseInfoResponse(BaseModel):
    """Database connection information"""
    uri: str
    user: str
    connected: bool
    version: Optional[str] = None
    edition: Optional[str] = None
    error: Optional[str] = None


class IndexInfo(BaseModel):
    """Index information"""
    count: int
    status: str


class ConstraintInfo(BaseModel):
    """Constraint information"""
    count: int
    status: str


class DatabaseHealthResponse(BaseModel):
    """Database health check"""
    status: str  # "healthy", "degraded", "unhealthy"
    responsive: bool
    checks: Dict[str, Any]  # {"connectivity": "ok", "indexes": {...}}
    error: Optional[str] = None
