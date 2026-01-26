"""
Probabilistic Vocabulary Categorization (ADR-047).

Automatically assigns semantic categories to LLM-generated relationship types
using embedding similarity to 30 builtin seed types.

Core Principle:
    Categories emerge from semantic similarity to seed types, not fixed assignments.

Architecture:
    1. Seed Types (30 Builtin): Ground truth for each of 8 categories
    2. Category Assignment: max(similarity to seeds in category)
    3. Confidence Thresholds: ≥70% (high), 50-69% (medium), <50% (low)
    4. Ambiguity Detection: Runner-up score > 0.70 flags multi-category types

Usage:
    from api.app.lib.vocabulary_categorizer import VocabularyCategorizer

    categorizer = VocabularyCategorizer(db_client, ai_provider)

    # Compute category scores for a type
    scores = await categorizer.compute_category_scores("ENHANCES")
    # => {'causation': 0.85, 'composition': 0.45, ...}

    # Assign category to a type
    result = await categorizer.assign_category("ENHANCES")
    # => {'category': 'causation', 'confidence': 0.85, 'scores': {...}, 'ambiguous': False}

    # Refresh all computed categories
    results = await categorizer.refresh_all_categories()

References:
    - ADR-047: Probabilistic Vocabulary Categorization
    - ADR-044: Probabilistic Truth Convergence (grounding strength pattern)
    - ADR-045: Unified Embedding Generation (provides embeddings)
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import logging
import numpy as np

logger = logging.getLogger(__name__)


# Category seed types (30 builtin types mapped to 11 categories)
CATEGORY_SEEDS = {
    'causation': ['CAUSES', 'ENABLES', 'PREVENTS', 'INFLUENCES', 'RESULTS_FROM'],
    'composition': ['PART_OF', 'CONTAINS', 'COMPOSED_OF', 'SUBSET_OF', 'INSTANCE_OF', 'COMPLEMENTS'],
    'logical': ['IMPLIES', 'CONTRADICTS', 'PRESUPPOSES', 'EQUIVALENT_TO'],
    'evidential': ['SUPPORTS', 'REFUTES', 'EXEMPLIFIES', 'MEASURED_BY'],
    'semantic': ['SIMILAR_TO', 'ANALOGOUS_TO', 'CONTRASTS_WITH', 'OPPOSITE_OF'],
    'temporal': ['PRECEDES', 'CONCURRENT_WITH', 'EVOLVES_INTO'],
    'dependency': ['DEPENDS_ON', 'REQUIRES', 'CONSUMES', 'PRODUCES'],
    'derivation': ['DERIVED_FROM', 'GENERATED_BY', 'BASED_ON'],
    'operation': ['ANALYZES', 'CALCULATES', 'PROCESSES', 'TRANSFORMS', 'EVALUATES'],
    'interaction': ['INTEGRATES_WITH', 'COMMUNICATES_WITH', 'CONNECTS_TO', 'INTERACTS_WITH'],
    'modification': ['CONFIGURES', 'UPDATES', 'ENHANCES', 'OPTIMIZES', 'IMPROVES']
}

# Confidence thresholds (ADR-047)
CONFIDENCE_HIGH = 0.70  # ≥70%: Auto-categorize confidently
CONFIDENCE_MEDIUM = 0.50  # 50-69%: Auto-categorize with warning
CONFIDENCE_LOW = 0.50  # <50%: Flag for curator review

# Ambiguity threshold
AMBIGUITY_THRESHOLD = 0.70  # Runner-up > 70% = ambiguous


@dataclass
class CategoryAssignment:
    """Result of category assignment for a relationship type."""
    relationship_type: str
    category: str
    confidence: float
    scores: Dict[str, float]
    ambiguous: bool
    runner_up_category: Optional[str] = None
    runner_up_score: Optional[float] = None


class VocabularyCategorizer:
    """
    Assigns semantic categories to vocabulary types using embedding similarity.

    Implements ADR-047 probabilistic categorization:
    - Uses cosine similarity to seed types
    - Max similarity (satisficing, not mean)
    - Confidence-based thresholds
    - Ambiguity detection
    """

    def __init__(self, db_client, ai_provider=None):
        """
        Initialize categorizer.

        Args:
            db_client: AGEClient instance for database operations
            ai_provider: Optional AI provider for embedding generation (uses db_client if None)
        """
        self.db = db_client
        self.provider = ai_provider

    async def compute_category_scores(
        self,
        relationship_type: str,
        embedding: Optional[List[float]] = None
    ) -> Dict[str, float]:
        """
        Compute similarity scores to all categories for a relationship type.

        Uses embedding similarity to seed types:
        - Category score = max(similarity to any seed in category)
        - Satisficing approach (max, not mean) handles opposing polarities

        Args:
            relationship_type: Edge type to categorize (e.g., "ENHANCES")
            embedding: Optional pre-computed embedding (avoids re-query, useful during creation)

        Returns:
            Dict mapping category names to similarity scores (0.0-1.0)
            Example: {'causation': 0.85, 'composition': 0.45, ...}

        Raises:
            ValueError: If relationship_type has no embedding and none provided
        """
        # Get embedding for target type (use provided or query)
        if embedding is not None:
            type_embedding = np.array(embedding, dtype=np.float32)
        else:
            type_embedding = await self._get_embedding(relationship_type)
            if type_embedding is None:
                raise ValueError(f"No embedding found for relationship type: {relationship_type}")

        category_scores = {}

        # Compute similarity to seeds in each category
        for category, seed_types in CATEGORY_SEEDS.items():
            similarities = []

            for seed in seed_types:
                seed_embedding = await self._get_embedding(seed)
                if seed_embedding is not None:
                    similarity = self._cosine_similarity(type_embedding, seed_embedding)
                    similarities.append(similarity)

            # Category score = max similarity (satisficing)
            if similarities:
                category_scores[category] = max(similarities)
            else:
                category_scores[category] = 0.0

        return category_scores

    async def assign_category(
        self,
        relationship_type: str,
        store: bool = True,
        embedding: Optional[List[float]] = None
    ) -> CategoryAssignment:
        """
        Assign category to a relationship type based on embedding similarity.

        Args:
            relationship_type: Edge type to categorize
            store: If True, store result in database
            embedding: Optional pre-computed embedding (avoids re-query, useful during creation)

        Returns:
            CategoryAssignment with category, confidence, scores, ambiguity

        Raises:
            ValueError: If relationship_type has no embedding and none provided
        """
        # Compute similarity scores
        scores = await self.compute_category_scores(relationship_type, embedding=embedding)

        # Sort by score to find primary and runner-up
        sorted_categories = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        primary_category, primary_score = sorted_categories[0]
        runner_up_category, runner_up_score = sorted_categories[1] if len(sorted_categories) > 1 else (None, 0.0)

        # Check for ambiguity
        ambiguous = runner_up_score > AMBIGUITY_THRESHOLD if runner_up_score else False

        assignment = CategoryAssignment(
            relationship_type=relationship_type,
            category=primary_category,
            confidence=primary_score,
            scores=scores,
            ambiguous=ambiguous,
            runner_up_category=runner_up_category,
            runner_up_score=runner_up_score
        )

        # Store in database if requested
        if store:
            await self._store_category_assignment(assignment)

        return assignment

    async def refresh_all_categories(
        self,
        only_computed: bool = True
    ) -> List[CategoryAssignment]:
        """
        Refresh category assignments for all vocabulary types.

        Args:
            only_computed: If True, only refresh types with category_source='computed'
                         If False, refresh all types (including builtins)

        Returns:
            List of CategoryAssignment results
        """
        # Get types to refresh
        if only_computed:
            query = """
                SELECT relationship_type
                FROM kg_api.relationship_vocabulary
                WHERE category_source = 'computed' AND is_active = TRUE
                ORDER BY relationship_type
            """
        else:
            query = """
                SELECT relationship_type
                FROM kg_api.relationship_vocabulary
                WHERE is_active = TRUE
                ORDER BY relationship_type
            """

        results = await self.db.execute_query(query)
        types_to_refresh = [row['relationship_type'] for row in results]

        assignments = []
        for relationship_type in types_to_refresh:
            try:
                assignment = await self.assign_category(relationship_type, store=True)
                assignments.append(assignment)
                logger.info(f"Refreshed category for {relationship_type}: {assignment.category} ({assignment.confidence:.2f})")
            except ValueError as e:
                logger.warning(f"Skipping {relationship_type}: {e}")

        return assignments

    async def _get_embedding(self, relationship_type: str) -> Optional[np.ndarray]:
        """
        Get embedding vector for a relationship type.

        Args:
            relationship_type: Edge type label

        Returns:
            Numpy array of embedding vector, or None if not found
        """
        query = """
            SELECT embedding
            FROM kg_api.relationship_vocabulary
            WHERE relationship_type = %s
        """
        result = await self.db.execute_query(query, (relationship_type,))

        if result and result[0].get('embedding'):
            # Convert JSONB array to numpy array
            embedding_list = result[0]['embedding']
            return np.array(embedding_list, dtype=np.float32)

        return None

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        Compute cosine similarity between two vectors.

        Args:
            vec1, vec2: Numpy arrays of same dimension

        Returns:
            Similarity score between 0.0 and 1.0
        """
        # Normalize vectors
        vec1_norm = vec1 / (np.linalg.norm(vec1) + 1e-10)
        vec2_norm = vec2 / (np.linalg.norm(vec2) + 1e-10)

        # Compute cosine similarity
        similarity = np.dot(vec1_norm, vec2_norm)

        # Clamp to [0, 1] range
        return float(max(0.0, min(1.0, similarity)))

    async def _store_category_assignment(self, assignment: CategoryAssignment) -> None:
        """
        Store category assignment in database and graph.

        Updates:
        1. relationship_vocabulary table (PostgreSQL)
        2. :VocabType node (graph) - ADR-048

        Args:
            assignment: CategoryAssignment to store
        """
        import json
        import asyncio

        # Update PostgreSQL table
        query = """
            UPDATE kg_api.relationship_vocabulary
            SET category = %s,
                category_confidence = %s,
                category_scores = %s::jsonb,
                category_ambiguous = %s,
                category_source = 'computed'
            WHERE relationship_type = %s
        """

        await self.db.execute_query(
            query,
            (
                assignment.category,
                assignment.confidence,
                json.dumps(assignment.scores),
                assignment.ambiguous,
                assignment.relationship_type
            )
        )

        # Update :VocabType graph node (ADR-048 Phase 3.3)
        # Update :IN_CATEGORY relationship to reflect new category
        try:
            cypher_query = """
                MATCH (v:VocabType {name: $name})
                OPTIONAL MATCH (v)-[old_rel:IN_CATEGORY]->()
                DELETE old_rel
                WITH v
                MERGE (c:VocabCategory {name: $category})
                MERGE (v)-[:IN_CATEGORY]->(c)
                RETURN v.name as name
            """
            params = {
                "name": assignment.relationship_type,
                "category": assignment.category
            }

            # Run Cypher in executor since it's sync
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                self.db._execute_cypher,
                cypher_query,
                params
            )

            logger.debug(
                f"Updated :IN_CATEGORY relationship: {assignment.relationship_type} → {assignment.category} "
                f"({assignment.confidence:.2f})"
            )
        except Exception as e:
            logger.warning(
                f"Failed to update :IN_CATEGORY relationship for '{assignment.relationship_type}': {e}"
            )
            # Don't fail the entire operation - table was updated successfully
