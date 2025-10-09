"""
Knowledge Graph System Constants

Centralized definitions for graph schema elements used across the codebase.
These constants define the canonical schema independent of database state.
"""

from typing import Set

# ============================================================================
# Graph Schema: Relationship Types
# ============================================================================
# Valid relationship types for the knowledge graph.
# These are used in:
# - LLM extraction prompts (src/api/lib/llm_extractor.py)
# - Backup integrity validation (src/api/lib/backup_integrity.py)
# - Query construction and validation
# ============================================================================

RELATIONSHIP_TYPES: Set[str] = {
    "IMPLIES",       # Concept A implies or leads to Concept B
    "SUPPORTS",      # Concept A provides evidence/support for Concept B
    "CONTRADICTS",   # Concept A contradicts or conflicts with Concept B
    "RELATES_TO",    # General relationship between concepts
    "PART_OF",       # Concept A is a component/part of Concept B
}

# For use in LLM prompts (comma-separated list)
RELATIONSHIP_TYPES_LIST = ", ".join(sorted(RELATIONSHIP_TYPES))

# ============================================================================
# Graph Schema: Node Labels
# ============================================================================

NODE_LABELS: Set[str] = {
    "Concept",   # Core concept node
    "Source",    # Source document/paragraph node
    "Instance",  # Evidence instance linking concept to source
}

# ============================================================================
# Backup Schema
# ============================================================================

BACKUP_TYPES: Set[str] = {
    "full_backup",      # Complete database export
    "ontology_backup",  # Single ontology export
}

BACKUP_VERSION = "1.0"  # Current backup format version

# ============================================================================
# Source Types (for Source node 'type' property)
# ============================================================================

SOURCE_TYPES: Set[str] = {
    "DOCUMENT",  # Extracted from ingested document
    "LEARNED",   # AI/human synthesized knowledge
}

# Cognitive leap levels for learned sources
COGNITIVE_LEAP_LEVELS: Set[str] = {
    "LOW",     # Incremental connection
    "MEDIUM",  # Moderate insight
    "HIGH",    # Significant conceptual leap
}
