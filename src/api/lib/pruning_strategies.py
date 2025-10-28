"""
Pruning Strategies for Automatic Edge Vocabulary Expansion.

Implements three-tier decision model for vocabulary management (ADR-032):
- Naive: Algorithmic decisions only (auto-merge/prune)
- HITL: Human-in-the-loop (all decisions need approval)
- AITL: AI-in-the-loop (AI makes tactical decisions, humans set strategy)

Decision Matrix:

                    | Naive         | HITL          | AITL
--------------------+---------------+---------------+----------------
Strong Synonym      | Auto-merge    | Needs approval| Auto-merge
(>= 0.90)          |               |               |
--------------------+---------------+---------------+----------------
Moderate Synonym    | Skip          | Needs approval| Needs AI review
(0.70-0.89)        |               |               |
--------------------+---------------+---------------+----------------
Zero-edge Type      | Auto-prune    | Needs approval| Auto-prune
(value = 0)        |               |               |
--------------------+---------------+---------------+----------------
Low-value Type      | Skip          | Needs approval| Needs AI review
(0 < value < 1.0)  |               |               |

Usage:
    from src.api.lib.pruning_strategies import PruningStrategy, ActionRecommendation

    strategy = PruningStrategy(mode="aitl", ai_provider=provider)

    # Evaluate merge candidate
    action = await strategy.evaluate_synonym(synonym_candidate, edge_counts)

    if action.should_execute:
        print(f"Auto-execute: {action.action_type}")
    elif action.needs_review:
        print(f"Human review: {action.reasoning}")

References:
    - ADR-032: Automatic Edge Vocabulary Expansion
    - ADR-025: Dynamic Relationship Vocabulary
"""

from typing import Dict, List, Optional, Literal
from dataclasses import dataclass
from enum import Enum
import json
import logging

# Type imports for other ADR-032 modules
from src.api.lib.synonym_detector import SynonymCandidate, SynonymStrength
from src.api.lib.vocabulary_scoring import EdgeTypeScore

logger = logging.getLogger(__name__)


@dataclass
class MergeDecision:
    """
    LLM decision about merging two edge types.

    Attributes:
        should_merge: True if types should be merged
        blended_term: New unified term name (if should_merge)
        blended_description: Description of blended term (if should_merge)
        reasoning: Explanation for decision
        confidence: LLM confidence in decision (0.0-1.0)
    """
    should_merge: bool
    reasoning: str
    confidence: float = 0.8
    blended_term: Optional[str] = None
    blended_description: Optional[str] = None


async def llm_evaluate_merge(
    type1: str,
    type2: str,
    type1_edge_count: int,
    type2_edge_count: int,
    similarity: float,
    ai_provider
) -> MergeDecision:
    """
    Use LLM to evaluate whether two edge types should be merged.

    This is the core AITL worker function. It asks the LLM:
    1. Are these truly synonyms or do they have semantic distinctions?
    2. If synonyms, what's a better unified name?

    Args:
        type1: First edge type name
        type2: Second edge type name
        type1_edge_count: Number of edges using type1
        type2_edge_count: Number of edges using type2
        similarity: Embedding similarity score (0.0-1.0)
        ai_provider: AI provider instance (OpenAI/Anthropic)

    Returns:
        MergeDecision with structured decision

    Example:
        >>> from src.api.lib.ai_providers import get_provider
        >>> provider = get_provider()
        >>> decision = await llm_evaluate_merge(
        ...     "STATUS", "HAS_STATUS", 5, 12, 0.934, provider
        ... )
        >>> if decision.should_merge:
        ...     print(f"Merge into: {decision.blended_term}")
    """

    # Construct prompt for LLM
    prompt = f"""You are evaluating whether two relationship types in a knowledge graph should be merged.

**Type 1:** {type1}
- Current usage: {type1_edge_count} edges
- Embedding similarity to Type 2: {similarity:.1%}

**Type 2:** {type2}
- Current usage: {type2_edge_count} edges

**Task:**
Determine if these are truly synonymous and should be merged into a single type.

Consider:
1. **Semantic equivalence**: Do they mean the same thing in practice?
2. **Directional inverses**: Are they opposite directions (e.g., PART_OF vs HAS_PART)?
3. **Useful distinctions**: Would merging lose important nuance?
4. **Graph consistency**: Would a unified term improve clarity?
5. **Simplicity**: Always prefer the simpler, single-word term when possible

**Response format (JSON):**
```json
{{
  "should_merge": true or false,
  "reasoning": "Brief explanation of decision",
  "blended_term": "UNIFIED_TERM_NAME" (only if merging, use SCREAMING_SNAKE_CASE),
  "blended_description": "What this unified relationship represents"
}}
```

**Important:**
- If they're directional inverses (opposite directions), return should_merge=false
- **STRONGLY prefer single-word relationship types** (e.g., PROVIDES, DESCRIBES, ENABLES, FACILITATES)
- Only use compound terms for directional relationships with prepositions (BY, TO, FROM, IN, FOR, WITH)
- **NEVER** create verb+noun compounds (e.g., FACILITATES_ESTABLISHMENT → use FACILITATES)
- **NEVER** create verb+verb compounds (e.g., DESCRIBES_PROVIDES → use DESCRIBES or PROVIDES)
- **NEVER** use OR clauses in names (e.g., DESCRIBES_OR_IDENTIFIES → choose DESCRIBES or IDENTIFIES)
- Prefer the simpler, more general term from the pair when choosing
- If compound is absolutely necessary: use VERB_PREPOSITION format only (e.g., SPECIFIED_IN, DERIVED_FROM, MEASURED_BY)

Respond with ONLY the JSON, no other text."""

    try:
        # Call LLM (handle both OpenAI and Anthropic providers)
        provider_name = ai_provider.get_provider_name().lower()

        if provider_name == "openai":
            response = ai_provider.client.chat.completions.create(
                model=ai_provider.extraction_model,
                messages=[
                    {"role": "system", "content": "You are a knowledge graph vocabulary expert. Respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content.strip()

        elif provider_name == "anthropic":
            message = ai_provider.client.messages.create(
                model=ai_provider.extraction_model,
                max_tokens=300,
                temperature=0.3,
                system="You are a knowledge graph vocabulary expert. Respond with valid JSON only.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            content = message.content[0].text.strip()

        elif "ollama" in provider_name:
            # Ollama provider - use direct HTTP API
            response = ai_provider.session.post(
                f"{ai_provider.base_url}/api/chat",
                json={
                    "model": ai_provider.extraction_model,
                    "messages": [
                        {"role": "system", "content": "You are a knowledge graph vocabulary expert. Respond with valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    "format": "json",  # Ollama JSON mode
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "top_p": ai_provider.top_p,
                        "num_predict": 300
                    }
                },
                timeout=60
            )
            response.raise_for_status()
            response_data = response.json()
            content = response_data["message"]["content"].strip()

        else:
            raise ValueError(f"Unsupported AI provider: {provider_name}")

        # Extract JSON if wrapped in markdown
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        result = json.loads(content)

        # Validate response structure
        if "should_merge" not in result or "reasoning" not in result:
            raise ValueError("LLM response missing required fields")

        # Build MergeDecision
        decision = MergeDecision(
            should_merge=bool(result["should_merge"]),
            reasoning=result["reasoning"],
            blended_term=result.get("blended_term"),
            blended_description=result.get("blended_description"),
            confidence=0.8  # Could be extracted from LLM if it provides it
        )

        logger.info(
            f"LLM merge decision: {type1} + {type2} → "
            f"{'MERGE' if decision.should_merge else 'SKIP'} "
            f"({decision.blended_term if decision.should_merge else 'N/A'})"
        )

        return decision

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response as JSON: {e}")
        logger.error(f"Raw response: {content}")

        # Fallback decision
        return MergeDecision(
            should_merge=False,
            reasoning=f"LLM response parsing failed: {str(e)}",
            confidence=0.0
        )

    except Exception as e:
        logger.error(f"LLM evaluation failed: {e}", exc_info=True)

        # Fallback decision
        return MergeDecision(
            should_merge=False,
            reasoning=f"LLM call failed: {str(e)}",
            confidence=0.0
        )


class PruningMode(Enum):
    """Pruning decision mode."""
    NAIVE = "naive"  # Algorithmic only
    HITL = "hitl"    # Human-in-the-loop
    AITL = "aitl"    # AI-in-the-loop


class ActionType(Enum):
    """Type of vocabulary action."""
    MERGE = "merge"          # Merge synonyms
    PRUNE = "prune"          # Remove type entirely
    DEPRECATE = "deprecate"  # Mark inactive but keep
    SKIP = "skip"            # No action needed


class ReviewLevel(Enum):
    """Required review level for action."""
    NONE = "none"           # Auto-execute
    AI = "ai"               # AI review
    HUMAN = "human"         # Human approval required


@dataclass
class ActionRecommendation:
    """
    Recommendation for vocabulary action.

    Attributes:
        action_type: Type of action (merge, prune, deprecate, skip)
        edge_type: Primary edge type affected
        review_level: Required review level
        should_execute: True if can auto-execute
        needs_review: True if needs human/AI approval
        target_type: Secondary type (for merges)
        reasoning: Explanation of recommendation
        metadata: Additional context for decision
    """
    action_type: ActionType
    edge_type: str
    review_level: ReviewLevel
    should_execute: bool
    needs_review: bool
    target_type: Optional[str] = None
    reasoning: str = ""
    metadata: Optional[Dict] = None

    def __repr__(self) -> str:
        if self.action_type == ActionType.MERGE:
            return (
                f"ActionRecommendation(MERGE {self.edge_type} → {self.target_type}, "
                f"review={self.review_level.value})"
            )
        else:
            return (
                f"ActionRecommendation({self.action_type.value.upper()} {self.edge_type}, "
                f"review={self.review_level.value})"
            )


class PruningStrategy:
    """
    Vocabulary pruning strategy implementing naive/HITL/AITL decision models.

    Determines which actions to auto-execute vs require approval based on mode.
    """

    def __init__(
        self,
        mode: Literal["naive", "hitl", "aitl"] = "hitl",
        ai_provider = None
    ):
        """
        Initialize pruning strategy.

        Args:
            mode: Decision mode (naive, hitl, aitl)
            ai_provider: AI provider for AITL mode (optional)
        """
        try:
            self.mode = PruningMode(mode)
        except ValueError:
            raise ValueError(f"Invalid mode: {mode}. Must be 'naive', 'hitl', or 'aitl'")

        self.ai_provider = ai_provider

        # Validate AI provider for AITL mode
        if self.mode == PruningMode.AITL and ai_provider is None:
            raise ValueError("AITL mode requires ai_provider")

    async def evaluate_synonym(
        self,
        candidate: SynonymCandidate,
        type1_score: EdgeTypeScore,
        type2_score: EdgeTypeScore
    ) -> ActionRecommendation:
        """
        Evaluate synonym merge candidate and recommend action.

        Args:
            candidate: Synonym candidate from SynonymDetector
            type1_score: Value score for type1
            type2_score: Value score for type2

        Returns:
            ActionRecommendation with merge decision

        Example:
            >>> strategy = PruningStrategy(mode="aitl", ai_provider=provider)
            >>> action = await strategy.evaluate_synonym(candidate, score1, score2)
            >>> if action.should_execute:
            ...     # Auto-merge
        """
        # Determine which type to preserve (higher value)
        preserve_type = candidate.type1 if type1_score.value_score >= type2_score.value_score else candidate.type2
        deprecate_type = candidate.type2 if preserve_type == candidate.type1 else candidate.type1

        # Decision logic based on mode and similarity strength
        if candidate.strength == SynonymStrength.STRONG:
            # Strong match (>= 0.90)
            if self.mode == PruningMode.NAIVE:
                # Auto-merge in naive mode
                return ActionRecommendation(
                    action_type=ActionType.MERGE,
                    edge_type=deprecate_type,
                    target_type=preserve_type,
                    review_level=ReviewLevel.NONE,
                    should_execute=True,
                    needs_review=False,
                    reasoning=f"Strong synonym ({candidate.similarity:.3f}) - auto-merge in naive mode",
                    metadata={
                        "similarity": candidate.similarity,
                        "preserve_value": type1_score.value_score if preserve_type == candidate.type1 else type2_score.value_score,
                        "deprecate_value": type2_score.value_score if deprecate_type == candidate.type2 else type1_score.value_score
                    }
                )
            elif self.mode == PruningMode.HITL:
                # Need human approval in HITL mode
                return ActionRecommendation(
                    action_type=ActionType.MERGE,
                    edge_type=deprecate_type,
                    target_type=preserve_type,
                    review_level=ReviewLevel.HUMAN,
                    should_execute=False,
                    needs_review=True,
                    reasoning=f"Strong synonym ({candidate.similarity:.3f}) - human approval required in HITL mode",
                    metadata={
                        "similarity": candidate.similarity,
                        "preserve_value": type1_score.value_score if preserve_type == candidate.type1 else type2_score.value_score,
                        "deprecate_value": type2_score.value_score if deprecate_type == candidate.type2 else type1_score.value_score
                    }
                )
            else:  # AITL
                # Auto-merge in AITL mode (high confidence)
                return ActionRecommendation(
                    action_type=ActionType.MERGE,
                    edge_type=deprecate_type,
                    target_type=preserve_type,
                    review_level=ReviewLevel.NONE,
                    should_execute=True,
                    needs_review=False,
                    reasoning=f"Strong synonym ({candidate.similarity:.3f}) - auto-merge in AITL mode",
                    metadata={
                        "similarity": candidate.similarity,
                        "preserve_value": type1_score.value_score if preserve_type == candidate.type1 else type2_score.value_score,
                        "deprecate_value": type2_score.value_score if deprecate_type == candidate.type2 else type1_score.value_score
                    }
                )

        elif candidate.strength == SynonymStrength.MODERATE:
            # Moderate match (0.70-0.89)
            if self.mode == PruningMode.NAIVE:
                # Skip in naive mode (not confident enough)
                return ActionRecommendation(
                    action_type=ActionType.SKIP,
                    edge_type=deprecate_type,
                    target_type=preserve_type,
                    review_level=ReviewLevel.NONE,
                    should_execute=False,
                    needs_review=False,
                    reasoning=f"Moderate synonym ({candidate.similarity:.3f}) - skip in naive mode (threshold too low)",
                    metadata={"similarity": candidate.similarity}
                )
            elif self.mode == PruningMode.HITL:
                # Need human approval in HITL mode
                return ActionRecommendation(
                    action_type=ActionType.MERGE,
                    edge_type=deprecate_type,
                    target_type=preserve_type,
                    review_level=ReviewLevel.HUMAN,
                    should_execute=False,
                    needs_review=True,
                    reasoning=f"Moderate synonym ({candidate.similarity:.3f}) - human approval required in HITL mode",
                    metadata={
                        "similarity": candidate.similarity,
                        "preserve_value": type1_score.value_score if preserve_type == candidate.type1 else type2_score.value_score,
                        "deprecate_value": type2_score.value_score if deprecate_type == candidate.type2 else type1_score.value_score
                    }
                )
            else:  # AITL
                # AI review for moderate matches
                ai_decision = await self._ai_review_synonym(candidate, type1_score, type2_score)
                return ai_decision

        else:
            # Weak match (< 0.70) - always skip
            return ActionRecommendation(
                action_type=ActionType.SKIP,
                edge_type=candidate.type1,
                review_level=ReviewLevel.NONE,
                should_execute=False,
                needs_review=False,
                reasoning=f"Weak similarity ({candidate.similarity:.3f}) - not synonyms",
                metadata={"similarity": candidate.similarity}
            )

    async def evaluate_low_value_type(
        self,
        score: EdgeTypeScore
    ) -> ActionRecommendation:
        """
        Evaluate low-value edge type and recommend prune/deprecate.

        Args:
            score: Value score from VocabularyScorer

        Returns:
            ActionRecommendation with prune/deprecate decision

        Example:
            >>> strategy = PruningStrategy(mode="naive")
            >>> action = await strategy.evaluate_low_value_type(score)
            >>> if action.action_type == ActionType.PRUNE:
            ...     # Remove type
        """
        # Never prune builtin types
        if score.is_builtin:
            return ActionRecommendation(
                action_type=ActionType.SKIP,
                edge_type=score.relationship_type,
                review_level=ReviewLevel.NONE,
                should_execute=False,
                needs_review=False,
                reasoning="Builtin type - cannot prune",
                metadata={"value_score": score.value_score, "is_builtin": True}
            )

        # Zero edges - safe to prune
        if score.edge_count == 0:
            if self.mode == PruningMode.NAIVE:
                # Auto-prune in naive mode
                return ActionRecommendation(
                    action_type=ActionType.PRUNE,
                    edge_type=score.relationship_type,
                    review_level=ReviewLevel.NONE,
                    should_execute=True,
                    needs_review=False,
                    reasoning="Zero edges - auto-prune in naive mode",
                    metadata={"value_score": score.value_score, "edge_count": 0}
                )
            elif self.mode == PruningMode.HITL:
                # Need human approval in HITL mode
                return ActionRecommendation(
                    action_type=ActionType.PRUNE,
                    edge_type=score.relationship_type,
                    review_level=ReviewLevel.HUMAN,
                    should_execute=False,
                    needs_review=True,
                    reasoning="Zero edges - human approval required in HITL mode",
                    metadata={"value_score": score.value_score, "edge_count": 0}
                )
            else:  # AITL
                # Auto-prune in AITL mode (safe - no data loss)
                return ActionRecommendation(
                    action_type=ActionType.PRUNE,
                    edge_type=score.relationship_type,
                    review_level=ReviewLevel.NONE,
                    should_execute=True,
                    needs_review=False,
                    reasoning="Zero edges - auto-prune in AITL mode (no data loss)",
                    metadata={"value_score": score.value_score, "edge_count": 0}
                )

        # Has edges but low value
        if self.mode == PruningMode.NAIVE:
            # Skip in naive mode (too risky)
            return ActionRecommendation(
                action_type=ActionType.SKIP,
                edge_type=score.relationship_type,
                review_level=ReviewLevel.NONE,
                should_execute=False,
                needs_review=False,
                reasoning=f"Low value ({score.value_score:.2f}) but has {score.edge_count} edges - skip in naive mode (too risky)",
                metadata={"value_score": score.value_score, "edge_count": score.edge_count}
            )
        elif self.mode == PruningMode.HITL:
            # Need human approval in HITL mode
            return ActionRecommendation(
                action_type=ActionType.DEPRECATE,
                edge_type=score.relationship_type,
                review_level=ReviewLevel.HUMAN,
                should_execute=False,
                needs_review=True,
                reasoning=f"Low value ({score.value_score:.2f}) with {score.edge_count} edges - human approval required in HITL mode",
                metadata={"value_score": score.value_score, "edge_count": score.edge_count}
            )
        else:  # AITL
            # AI review for low-value types with edges
            ai_decision = await self._ai_review_low_value(score)
            return ai_decision

    async def batch_evaluate(
        self,
        synonyms: List[tuple[SynonymCandidate, EdgeTypeScore, EdgeTypeScore]],
        low_value_types: List[EdgeTypeScore]
    ) -> Dict[str, List[ActionRecommendation]]:
        """
        Evaluate multiple candidates in batch.

        Args:
            synonyms: List of (candidate, type1_score, type2_score) tuples
            low_value_types: List of low-value EdgeTypeScore objects

        Returns:
            Dict with 'auto_execute' and 'needs_review' lists

        Example:
            >>> results = await strategy.batch_evaluate(synonyms, low_value)
            >>> for action in results['auto_execute']:
            ...     # Execute immediately
            >>> for action in results['needs_review']:
            ...     # Queue for approval
        """
        auto_execute = []
        needs_review = []

        # Evaluate synonyms
        for candidate, score1, score2 in synonyms:
            action = await self.evaluate_synonym(candidate, score1, score2)
            if action.should_execute:
                auto_execute.append(action)
            elif action.needs_review:
                needs_review.append(action)

        # Evaluate low-value types
        for score in low_value_types:
            action = await self.evaluate_low_value_type(score)
            if action.should_execute:
                auto_execute.append(action)
            elif action.needs_review:
                needs_review.append(action)

        return {
            "auto_execute": auto_execute,
            "needs_review": needs_review
        }

    async def _ai_review_synonym(
        self,
        candidate: SynonymCandidate,
        type1_score: EdgeTypeScore,
        type2_score: EdgeTypeScore
    ) -> ActionRecommendation:
        """
        AI review for moderate synonym matches in AITL mode.

        Uses LLM to make tactical decision about merge.

        Args:
            candidate: Synonym candidate
            type1_score: Score for type1
            type2_score: Score for type2

        Returns:
            ActionRecommendation with AI decision
        """
        # Prepare context for AI
        context = f"""
Evaluate whether to merge these potentially synonym edge types:

Type 1: {candidate.type1}
  - Edges: {type1_score.edge_count}
  - Value Score: {type1_score.value_score:.2f}
  - Bridges: {type1_score.bridge_count}

Type 2: {candidate.type2}
  - Edges: {type2_score.edge_count}
  - Value Score: {type2_score.value_score:.2f}
  - Bridges: {type2_score.bridge_count}

Similarity: {candidate.similarity:.3f} (moderate match)

Should these be merged? Consider:
- Are they truly synonyms in practice?
- Would merging lose important semantic distinctions?
- Is the similarity score reliable?

Respond with MERGE or SKIP and brief reasoning.
"""

        # TODO: Implement actual AI call when LLM integration is ready
        # For now, use heuristic: if similarity >= 0.80, recommend merge
        if candidate.similarity >= 0.80:
            preserve_type = candidate.type1 if type1_score.value_score >= type2_score.value_score else candidate.type2
            deprecate_type = candidate.type2 if preserve_type == candidate.type1 else candidate.type1

            return ActionRecommendation(
                action_type=ActionType.MERGE,
                edge_type=deprecate_type,
                target_type=preserve_type,
                review_level=ReviewLevel.AI,
                should_execute=True,
                needs_review=False,
                reasoning=f"AI approved merge (similarity: {candidate.similarity:.3f})",
                metadata={
                    "similarity": candidate.similarity,
                    "ai_decision": "MERGE",
                    "preserve_value": type1_score.value_score if preserve_type == candidate.type1 else type2_score.value_score
                }
            )
        else:
            return ActionRecommendation(
                action_type=ActionType.SKIP,
                edge_type=candidate.type1,
                review_level=ReviewLevel.AI,
                should_execute=False,
                needs_review=False,
                reasoning=f"AI rejected merge (similarity: {candidate.similarity:.3f} - semantic distinction likely important)",
                metadata={
                    "similarity": candidate.similarity,
                    "ai_decision": "SKIP"
                }
            )

    async def _ai_review_low_value(
        self,
        score: EdgeTypeScore
    ) -> ActionRecommendation:
        """
        AI review for low-value types with edges in AITL mode.

        Uses LLM to make tactical decision about deprecation.

        Args:
            score: EdgeTypeScore for low-value type

        Returns:
            ActionRecommendation with AI decision
        """
        # Prepare context for AI
        context = f"""
Evaluate whether to deprecate this low-value edge type:

Type: {score.relationship_type}
  - Edges: {score.edge_count}
  - Value Score: {score.value_score:.2f}
  - Avg Traversal: {score.avg_traversal:.2f}
  - Bridges: {score.bridge_count}

This type has low usage but some existing edges.

Should it be deprecated? Consider:
- Is it structurally important (bridges)?
- Is usage just temporarily low?
- Would deprecation harm the graph?

Respond with DEPRECATE or SKIP and brief reasoning.
"""

        # TODO: Implement actual AI call when LLM integration is ready
        # For now, use heuristic: if value < 0.5 and no bridges, deprecate
        if score.value_score < 0.5 and score.bridge_count == 0:
            return ActionRecommendation(
                action_type=ActionType.DEPRECATE,
                edge_type=score.relationship_type,
                review_level=ReviewLevel.AI,
                should_execute=True,
                needs_review=False,
                reasoning=f"AI approved deprecation (value: {score.value_score:.2f}, no bridges)",
                metadata={
                    "value_score": score.value_score,
                    "edge_count": score.edge_count,
                    "bridge_count": score.bridge_count,
                    "ai_decision": "DEPRECATE"
                }
            )
        else:
            return ActionRecommendation(
                action_type=ActionType.SKIP,
                edge_type=score.relationship_type,
                review_level=ReviewLevel.AI,
                should_execute=False,
                needs_review=False,
                reasoning=f"AI rejected deprecation (value: {score.value_score:.2f}, bridges: {score.bridge_count} - structurally important)",
                metadata={
                    "value_score": score.value_score,
                    "edge_count": score.edge_count,
                    "bridge_count": score.bridge_count,
                    "ai_decision": "SKIP"
                }
            )


# ============================================================================
# Utility Functions
# ============================================================================


def filter_by_review_level(
    recommendations: List[ActionRecommendation],
    review_level: ReviewLevel
) -> List[ActionRecommendation]:
    """
    Filter recommendations by review level.

    Args:
        recommendations: List of action recommendations
        review_level: Target review level

    Returns:
        Filtered list

    Example:
        >>> auto = filter_by_review_level(actions, ReviewLevel.NONE)
        >>> for action in auto:
        ...     # Execute immediately
    """
    return [r for r in recommendations if r.review_level == review_level]


def group_by_action_type(
    recommendations: List[ActionRecommendation]
) -> Dict[ActionType, List[ActionRecommendation]]:
    """
    Group recommendations by action type.

    Args:
        recommendations: List of action recommendations

    Returns:
        Dict mapping ActionType -> list of recommendations

    Example:
        >>> groups = group_by_action_type(actions)
        >>> merges = groups[ActionType.MERGE]
        >>> prunes = groups[ActionType.PRUNE]
    """
    groups = {}
    for action in recommendations:
        if action.action_type not in groups:
            groups[action.action_type] = []
        groups[action.action_type].append(action)
    return groups


if __name__ == "__main__":
    # Quick demonstration
    import asyncio
    import sys

    print("Pruning Strategies - ADR-032 Implementation")
    print("=" * 60)
    print()
    print("This module implements three-tier decision model:")
    print("  - Naive: Algorithmic decisions (auto-merge/prune)")
    print("  - HITL: Human-in-the-loop (all need approval)")
    print("  - AITL: AI-in-the-loop (AI tactical, human strategic)")
    print()
    print("Usage:")
    print("  from src.api.lib.pruning_strategies import PruningStrategy")
    print("  strategy = PruningStrategy(mode='aitl', ai_provider=provider)")
    print("  action = await strategy.evaluate_synonym(candidate, score1, score2)")
    print()
    print("For testing, run: pytest tests/test_pruning_strategies.py")
