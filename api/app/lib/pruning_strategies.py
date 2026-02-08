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
    from api.app.lib.pruning_strategies import PruningStrategy, ActionRecommendation

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
import asyncio
import json
import logging

# Type imports for other ADR-032 modules
from api.app.lib.synonym_detector import SynonymCandidate, SynonymStrength
from api.app.lib.vocabulary_scoring import EdgeTypeScore
from api.app.lib.llm_utils import call_llm_sync

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
    ai_provider,
    type1_epistemic_status: Optional[str] = None,
    type2_epistemic_status: Optional[str] = None
) -> MergeDecision:
    """
    Use LLM to evaluate whether two edge types should be merged.

    This is the core AITL worker function. It asks the LLM:
    1. Are these truly synonyms or do they have semantic distinctions?
    2. If synonyms, what's a better unified name?
    3. ADR-065: Are their epistemic states compatible for merging?

    Args:
        type1: First edge type name
        type2: Second edge type name
        type1_edge_count: Number of edges using type1
        type2_edge_count: Number of edges using type2
        similarity: Embedding similarity score (0.0-1.0)
        ai_provider: AI provider instance (OpenAI/Anthropic)
        type1_epistemic_status: Epistemic status of type1 (ADR-065)
        type2_epistemic_status: Epistemic status of type2 (ADR-065)

    Returns:
        MergeDecision with structured decision

    Example:
        >>> from api.app.lib.ai_providers import get_provider
        >>> provider = get_provider()
        >>> decision = await llm_evaluate_merge(
        ...     "STATUS", "HAS_STATUS", 5, 12, 0.934, provider,
        ...     "AFFIRMATIVE", "AFFIRMATIVE"
        ... )
        >>> if decision.should_merge:
        ...     print(f"Merge into: {decision.blended_term}")
    """

    # Construct prompt for LLM
    # ADR-065: Include epistemic status context if available
    epistemic_context = ""
    if type1_epistemic_status or type2_epistemic_status:
        epistemic_context = f"""
**Epistemic Status Information:**
- Type 1 Epistemic Status: {type1_epistemic_status or 'Not measured'}
- Type 2 Epistemic Status: {type2_epistemic_status or 'Not measured'}

**Epistemic Status Meanings:**
- **AFFIRMATIVE**: Well-established, high grounding (>0.8) - strongly supported by evidence
- **CONTESTED**: Mixed evidence, debated (0.2-0.8) - partially supported
- **CONTRADICTORY**: Contradicted by evidence (<-0.5) - actively contradicted
- **HISTORICAL**: Temporal/historical vocabulary - time-sensitive semantics
- **INSUFFICIENT_DATA**: <3 measurements - not enough data to classify
- **UNCLASSIFIED**: Doesn't fit known patterns

**IMPORTANT:** Epistemic status reflects how well-grounded the relationships using each type are in the knowledge graph. Merging types with divergent epistemic states can pollute provenance quality.
"""

    prompt = f"""You are evaluating whether two relationship types in a knowledge graph should be merged.

**Type 1:** {type1}
- Current usage: {type1_edge_count} edges
- Embedding similarity to Type 2: {similarity:.1%}

**Type 2:** {type2}
- Current usage: {type2_edge_count} edges
{epistemic_context}
**Task:**
Determine if these are truly synonymous and should be merged into a single type.

Consider:
1. **Semantic equivalence**: Do they mean the same thing in practice?
2. **Directional inverses**: Are they opposite directions (e.g., PART_OF vs HAS_PART)?
3. **Useful distinctions**: Would merging lose important nuance?
4. **Graph consistency**: Would a unified term improve clarity?
5. **Simplicity**: Always prefer the simpler, single-word term when possible
6. **Epistemic compatibility** (if status provided): Are their validation states compatible? Don't merge AFFIRMATIVE with CONTESTED/CONTRADICTORY types.

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
        content = call_llm_sync(
            ai_provider,
            prompt=prompt,
            system_msg="You are a knowledge graph vocabulary expert. Respond with valid JSON only.",
            max_tokens=300,
            json_mode=True,
        )

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
    AI = "ai"               # AI review (LLM grounded in math)
    HEURISTIC = "heuristic" # Threshold fallback (no LLM available)
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
        mode: Literal["naive", "hitl", "aitl"] = "aitl",  # Default to AITL (HITL deprecated)
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

    def _call_llm(self, prompt: str, system_msg: str = "You are a knowledge graph vocabulary expert.") -> str:
        """
        Call the configured reasoning LLM and return the response text.

        Delegates to the shared call_llm_sync() utility for provider dispatch.

        Args:
            prompt: User prompt to send
            system_msg: System message for context

        Returns:
            Raw response text from the LLM

        Raises:
            ValueError: If provider type is unsupported
            Exception: If the LLM call fails
        """
        return call_llm_sync(
            self.ai_provider,
            prompt=prompt,
            system_msg=system_msg,
            max_tokens=300,
        )

    async def _ai_review_synonym(
        self,
        candidate: SynonymCandidate,
        type1_score: EdgeTypeScore,
        type2_score: EdgeTypeScore
    ) -> ActionRecommendation:
        """
        AI review for moderate synonym matches in AITL mode.

        Presents mathematical scores to the reasoning LLM and asks it to decide
        whether the types should be merged. The grounding data (edge counts,
        value scores, bridge counts, similarity) prevents LLM drift — the
        decision is anchored in objective graph measurements.

        Falls back to heuristic threshold if the LLM call fails.

        Args:
            candidate: Synonym candidate with similarity score
            type1_score: Value score for type1
            type2_score: Value score for type2

        Returns:
            ActionRecommendation with LLM-grounded or heuristic decision
        """
        preserve_type = candidate.type1 if type1_score.value_score >= type2_score.value_score else candidate.type2
        deprecate_type = candidate.type2 if preserve_type == candidate.type1 else candidate.type1

        prompt = f"""Evaluate whether to merge these potentially synonym edge types:

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

Respond with MERGE or SKIP and a one-sentence reasoning."""

        try:
            response = await asyncio.to_thread(self._call_llm, prompt)
            first_line = response.strip().upper().split(".")[0]

            # Validate the LLM gave a parsable decision.
            # Use first keyword position to resolve ambiguity (e.g. "SKIP. MERGE would lose...")
            merge_pos = first_line.find("MERGE")
            skip_pos = first_line.find("SKIP")
            if merge_pos == -1 and skip_pos == -1:
                raise ValueError(f"Unparsable LLM response (no MERGE/SKIP keyword): {response[:100]}")

            # First keyword wins when both appear
            is_merge = merge_pos != -1 and (skip_pos == -1 or merge_pos < skip_pos)

            if is_merge:
                reasoning = response.strip()
                logger.info(f"LLM synonym review: MERGE {deprecate_type} → {preserve_type} ({reasoning})")
                return ActionRecommendation(
                    action_type=ActionType.MERGE,
                    edge_type=deprecate_type,
                    target_type=preserve_type,
                    review_level=ReviewLevel.AI,
                    should_execute=True,
                    needs_review=False,
                    reasoning=f"LLM approved merge: {reasoning}",
                    metadata={
                        "similarity": candidate.similarity,
                        "decision_source": "llm",
                        "preserve_value": type1_score.value_score if preserve_type == candidate.type1 else type2_score.value_score
                    }
                )
            else:
                reasoning = response.strip()
                logger.info(f"LLM synonym review: SKIP {candidate.type1} vs {candidate.type2} ({reasoning})")
                return ActionRecommendation(
                    action_type=ActionType.SKIP,
                    edge_type=candidate.type1,
                    review_level=ReviewLevel.AI,
                    should_execute=False,
                    needs_review=False,
                    reasoning=f"LLM rejected merge: {reasoning}",
                    metadata={
                        "similarity": candidate.similarity,
                        "decision_source": "llm"
                    }
                )

        except Exception as e:
            logger.warning(f"LLM synonym review failed, falling back to heuristic: {e}")

            # Heuristic fallback: threshold on similarity score
            if candidate.similarity >= 0.80:
                return ActionRecommendation(
                    action_type=ActionType.MERGE,
                    edge_type=deprecate_type,
                    target_type=preserve_type,
                    review_level=ReviewLevel.HEURISTIC,
                    should_execute=True,
                    needs_review=False,
                    reasoning=f"Heuristic merge (similarity {candidate.similarity:.3f} >= 0.80, LLM unavailable: {e})",
                    metadata={
                        "similarity": candidate.similarity,
                        "decision_source": "heuristic_fallback",
                        "preserve_value": type1_score.value_score if preserve_type == candidate.type1 else type2_score.value_score
                    }
                )
            else:
                return ActionRecommendation(
                    action_type=ActionType.SKIP,
                    edge_type=candidate.type1,
                    review_level=ReviewLevel.HEURISTIC,
                    should_execute=False,
                    needs_review=False,
                    reasoning=f"Heuristic skip (similarity {candidate.similarity:.3f} < 0.80, LLM unavailable: {e})",
                    metadata={
                        "similarity": candidate.similarity,
                        "decision_source": "heuristic_fallback"
                    }
                )

    async def _ai_review_low_value(
        self,
        score: EdgeTypeScore
    ) -> ActionRecommendation:
        """
        AI review for low-value types with edges in AITL mode.

        Presents mathematical scores to the reasoning LLM and asks whether
        the type should be deprecated. The grounding data (value score,
        edge count, traversal frequency, bridge count) anchors the LLM's
        reasoning in objective measurements.

        Falls back to heuristic threshold if the LLM call fails.

        Args:
            score: EdgeTypeScore for low-value type

        Returns:
            ActionRecommendation with LLM-grounded or heuristic decision
        """
        prompt = f"""Evaluate whether to deprecate this low-value edge type:

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

Respond with DEPRECATE or SKIP and a one-sentence reasoning."""

        try:
            response = await asyncio.to_thread(self._call_llm, prompt)
            first_line = response.strip().upper().split(".")[0]

            # Validate the LLM gave a parsable decision.
            # Use first keyword position to resolve ambiguity.
            deprecate_pos = first_line.find("DEPRECATE")
            skip_pos = first_line.find("SKIP")
            if deprecate_pos == -1 and skip_pos == -1:
                raise ValueError(f"Unparsable LLM response (no DEPRECATE/SKIP keyword): {response[:100]}")

            # First keyword wins when both appear
            is_deprecate = deprecate_pos != -1 and (skip_pos == -1 or deprecate_pos < skip_pos)

            if is_deprecate:
                reasoning = response.strip()
                logger.info(f"LLM low-value review: DEPRECATE {score.relationship_type} ({reasoning})")
                return ActionRecommendation(
                    action_type=ActionType.DEPRECATE,
                    edge_type=score.relationship_type,
                    review_level=ReviewLevel.AI,
                    should_execute=True,
                    needs_review=False,
                    reasoning=f"LLM approved deprecation: {reasoning}",
                    metadata={
                        "value_score": score.value_score,
                        "edge_count": score.edge_count,
                        "bridge_count": score.bridge_count,
                        "decision_source": "llm"
                    }
                )
            else:
                reasoning = response.strip()
                logger.info(f"LLM low-value review: SKIP {score.relationship_type} ({reasoning})")
                return ActionRecommendation(
                    action_type=ActionType.SKIP,
                    edge_type=score.relationship_type,
                    review_level=ReviewLevel.AI,
                    should_execute=False,
                    needs_review=False,
                    reasoning=f"LLM rejected deprecation: {reasoning}",
                    metadata={
                        "value_score": score.value_score,
                        "edge_count": score.edge_count,
                        "bridge_count": score.bridge_count,
                        "decision_source": "llm"
                    }
                )

        except Exception as e:
            logger.warning(f"LLM low-value review failed, falling back to heuristic: {e}")

            # Heuristic fallback: low value + no bridges → deprecate
            if score.value_score < 0.5 and score.bridge_count == 0:
                return ActionRecommendation(
                    action_type=ActionType.DEPRECATE,
                    edge_type=score.relationship_type,
                    review_level=ReviewLevel.HEURISTIC,
                    should_execute=True,
                    needs_review=False,
                    reasoning=f"Heuristic deprecation (value {score.value_score:.2f} < 0.5, no bridges, LLM unavailable: {e})",
                    metadata={
                        "value_score": score.value_score,
                        "edge_count": score.edge_count,
                        "bridge_count": score.bridge_count,
                        "decision_source": "heuristic_fallback"
                    }
                )
            else:
                return ActionRecommendation(
                    action_type=ActionType.SKIP,
                    edge_type=score.relationship_type,
                    review_level=ReviewLevel.HEURISTIC,
                    should_execute=False,
                    needs_review=False,
                    reasoning=f"Heuristic skip (value {score.value_score:.2f}, bridges: {score.bridge_count}, LLM unavailable: {e})",
                    metadata={
                        "value_score": score.value_score,
                        "edge_count": score.edge_count,
                        "bridge_count": score.bridge_count,
                        "decision_source": "heuristic_fallback"
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
    print("  from api.app.lib.pruning_strategies import PruningStrategy")
    print("  strategy = PruningStrategy(mode='aitl', ai_provider=provider)")
    print("  action = await strategy.evaluate_synonym(candidate, score1, score2)")
    print()
    print("For testing, run: pytest tests/test_pruning_strategies.py")
