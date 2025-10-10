"""
Relationship Type Mapper

Maps LLM-generated relationship types to canonical types using fuzzy string matching.
Handles variations like "CONTRASTS" → "CONTRASTS_WITH", "supports" → "SUPPORTS", etc.
"""

from difflib import SequenceMatcher
from typing import Tuple, Optional
from ..constants import RELATIONSHIP_TYPES, RELATIONSHIP_TYPE_TO_CATEGORY


def normalize_relationship_type(
    llm_type: str,
    similarity_threshold: float = 0.7
) -> Tuple[Optional[str], Optional[str], float]:
    """
    Map LLM-generated relationship type to canonical type using fuzzy matching.

    Args:
        llm_type: Relationship type from LLM (may be variation/typo)
        similarity_threshold: Minimum similarity score to accept match (default: 0.7)

    Returns:
        Tuple of (canonical_type, category, similarity_score)
        Returns (None, None, 0.0) if no good match found

    Examples:
        normalize_relationship_type("CONTRASTS") → ("CONTRASTS_WITH", "similarity", 0.89)
        normalize_relationship_type("causes") → ("CAUSES", "causal", 1.0)
        normalize_relationship_type("SUPPORTS") → ("SUPPORTS", "evidential", 1.0)
    """
    # Normalize input
    llm_type_upper = llm_type.strip().upper()

    # Exact match (fast path)
    if llm_type_upper in RELATIONSHIP_TYPES:
        category = RELATIONSHIP_TYPE_TO_CATEGORY[llm_type_upper]
        return (llm_type_upper, category, 1.0)

    # Fuzzy match using sequence similarity
    best_match = None
    best_score = 0.0
    best_category = None

    for canonical_type in RELATIONSHIP_TYPES:
        score = SequenceMatcher(None, llm_type_upper, canonical_type).ratio()

        if score > best_score:
            best_score = score
            best_match = canonical_type
            best_category = RELATIONSHIP_TYPE_TO_CATEGORY[canonical_type]

    # Only return match if above threshold
    if best_score >= similarity_threshold:
        return (best_match, best_category, best_score)

    return (None, None, 0.0)


def get_relationship_category(rel_type: str) -> Optional[str]:
    """
    Get category for a canonical relationship type.

    Args:
        rel_type: Canonical relationship type

    Returns:
        Category name or None if type not found

    Example:
        get_relationship_category("CAUSES") → "causal"
        get_relationship_category("SUPPORTS") → "evidential"
    """
    return RELATIONSHIP_TYPE_TO_CATEGORY.get(rel_type.upper())
