"""
Knowledge Graph System Constants

Centralized definitions for graph schema elements used across the codebase.
These constants define the canonical schema independent of database state.
"""

from typing import Set

# ============================================================================
# Graph Schema: Relationship Types (30-Type Semantically Sparse System)
# ============================================================================
# Categorized relationship types for semantic richness.
# LLM receives dense list without categories to avoid overfitting.
# NLTK fuzzy matching maps LLM outputs to canonical types.
# Both category and exact type are stored in graph edges.
# ============================================================================

from typing import Dict, List

# Relationship types organized by category
RELATIONSHIP_CATEGORIES: Dict[str, List[str]] = {
    "logical_truth": [
        "IMPLIES",          # A being true makes B necessarily true
        "CONTRADICTS",      # A and B cannot both be true
        "PRESUPPOSES",      # A assumes B is true (B must be true for A to be meaningful)
        "EQUIVALENT_TO",    # A and B express the same thing differently
    ],
    "causal": [
        "CAUSES",           # A directly produces/creates B
        "ENABLES",          # A makes B possible (but doesn't guarantee it)
        "PREVENTS",         # A blocks B from occurring
        "INFLUENCES",       # A affects B without full causation
        "RESULTS_FROM",     # B is an outcome/consequence of A (reverse of CAUSES)
    ],
    "structural": [
        "PART_OF",          # A is a component of B (wheel part of car)
        "CONTAINS",         # A includes B as a member (set contains elements)
        "COMPOSED_OF",      # A is made from B as material (cake composed of flour)
        "SUBSET_OF",        # All A are B, but not all B are A
        "INSTANCE_OF",      # A is a specific example of category B
    ],
    "evidential": [
        "SUPPORTS",         # A provides evidence for B
        "REFUTES",          # A provides evidence against B
        "EXEMPLIFIES",      # A serves as a concrete example of B
        "MEASURED_BY",      # A's value/quality is quantified by B
    ],
    "similarity": [
        "SIMILAR_TO",       # A and B share properties
        "ANALOGOUS_TO",     # A maps to B metaphorically (heart:pump)
        "CONTRASTS_WITH",   # A and B differ in meaningful ways
        "OPPOSITE_OF",      # A is the inverse/negation of B
    ],
    "temporal": [
        "PRECEDES",         # A happens before B
        "CONCURRENT_WITH",  # A and B happen at the same time
        "EVOLVES_INTO",     # A transforms into B over time
    ],
    "functional": [
        "USED_FOR",         # A's purpose is to achieve B
        "REQUIRES",         # A needs B to function/exist
        "PRODUCES",         # A generates B as output
        "REGULATES",        # A controls/modifies B's behavior
    ],
    "meta": [
        "DEFINED_AS",       # A's meaning is B (definitional)
        "CATEGORIZED_AS",   # A belongs to category/type B
    ],
}

# Flat set of all valid relationship types
RELATIONSHIP_TYPES: Set[str] = {
    rel_type
    for category_types in RELATIONSHIP_CATEGORIES.values()
    for rel_type in category_types
}

# Reverse mapping: type -> category
RELATIONSHIP_TYPE_TO_CATEGORY: Dict[str, str] = {
    rel_type: category
    for category, types in RELATIONSHIP_CATEGORIES.items()
    for rel_type in types
}

# Dense comma-separated list for LLM prompts (without categories)
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
