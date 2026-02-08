"""
Annealing Evaluator — LLM judgment for ontology promotion/demotion (ADR-200 Phase 3b).

Follows the same pattern as pruning_strategies.llm_evaluate_merge():
structured prompt → JSON response → parsed decision dataclass.

Two evaluation types:
- Promotion: Is a high-degree concept a natural nucleus or a crossroads?
- Demotion: Should a low-protection ontology be absorbed or revived?
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PromotionDecision:
    """Result of LLM evaluation for concept → ontology promotion."""
    should_promote: bool
    reasoning: str
    suggested_name: Optional[str] = None
    suggested_description: Optional[str] = None


@dataclass
class DemotionDecision:
    """Result of LLM evaluation for ontology demotion/absorption."""
    should_demote: bool
    reasoning: str
    absorption_target: Optional[str] = None


async def llm_evaluate_promotion(
    concept_label: str,
    concept_description: str,
    degree: int,
    ontology_name: str,
    ontology_concept_count: int,
    top_neighbors: List[str],
    affinity_targets: List[Dict[str, Any]],
    ai_provider,
) -> PromotionDecision:
    """
    Ask LLM whether a high-degree concept should be promoted to an ontology.

    Args:
        concept_label: The candidate concept's label
        concept_description: The candidate concept's description
        degree: Total degree (in + out edges)
        ontology_name: Current ontology containing this concept
        ontology_concept_count: Total concepts in the current ontology
        top_neighbors: Labels of the concept's most-connected neighbors
        affinity_targets: Cross-ontology affinity data
        ai_provider: AI provider instance

    Returns:
        PromotionDecision with structured judgment
    """
    neighbors_text = ", ".join(top_neighbors[:10]) if top_neighbors else "none available"
    affinity_text = "\n".join(
        f"  - {a.get('other_ontology', '?')}: {a.get('shared_concept_count', 0)} shared concepts"
        for a in affinity_targets[:5]
    ) if affinity_targets else "  none"

    prompt = f"""You are evaluating whether a concept in a knowledge graph should be promoted to become its own ontology (knowledge domain).

**Candidate Concept:** {concept_label}
- Description: {concept_description or 'No description available'}
- Total edges (degree): {degree}
- Current ontology: {ontology_name} ({ontology_concept_count} concepts)
- Connected neighbors: {neighbors_text}

**Cross-ontology affinity from current ontology:**
{affinity_text}

**Task:**
Determine if this concept is a **nucleus** (should become its own ontology) or a **crossroads** (bridges domains but shouldn't be elevated).

A **nucleus** concept:
- Has neighbors that are semantically coherent (related to each other)
- Represents a distinct sub-domain within its current ontology
- Would benefit from being a separate organizing frame
- Has enough depth to sustain an independent knowledge domain

A **crossroads** concept:
- Connects diverse, unrelated topics
- Is a generic/abstract term (e.g., "Management", "Process", "System")
- Would create a grab-bag ontology if promoted
- Serves better as a bridge than as a domain anchor

**Response format (JSON):**
```json
{{
  "should_promote": true or false,
  "reasoning": "Brief explanation of the decision",
  "suggested_name": "Name for the new ontology (only if promoting)",
  "suggested_description": "What this knowledge domain covers (only if promoting)"
}}
```

Respond with ONLY the JSON, no other text."""

    return await _call_llm(
        prompt=prompt,
        ai_provider=ai_provider,
        parse_fn=lambda result: PromotionDecision(
            should_promote=bool(result.get("should_promote", False)),
            reasoning=result.get("reasoning", "No reasoning provided"),
            suggested_name=result.get("suggested_name"),
            suggested_description=result.get("suggested_description"),
        ),
        fallback=PromotionDecision(
            should_promote=False,
            reasoning="LLM evaluation failed; defaulting to no promotion",
        ),
    )


async def llm_evaluate_demotion(
    ontology_name: str,
    mass_score: float,
    coherence_score: float,
    protection_score: float,
    concept_count: int,
    affinity_targets: List[Dict[str, Any]],
    ai_provider,
) -> DemotionDecision:
    """
    Ask LLM whether a low-protection ontology should be demoted (absorbed).

    Args:
        ontology_name: The struggling ontology
        mass_score: Current mass score
        coherence_score: Current coherence score
        protection_score: Current protection score (below demotion threshold)
        concept_count: Number of concepts in this ontology
        affinity_targets: Cross-ontology affinity data (potential absorption targets)
        ai_provider: AI provider instance

    Returns:
        DemotionDecision with structured judgment
    """
    affinity_text = "\n".join(
        f"  - {a.get('other_ontology', '?')}: {a.get('shared_concept_count', 0)} shared, "
        f"{a.get('affinity_score', 0):.1%} affinity"
        for a in affinity_targets[:5]
    ) if affinity_targets else "  none"

    best_target = affinity_targets[0].get("other_ontology", "unknown") if affinity_targets else "none"

    prompt = f"""You are evaluating whether a knowledge domain (ontology) in a knowledge graph should be demoted — its sources absorbed into another ontology.

**Ontology:** {ontology_name}
- Concepts: {concept_count}
- Mass score: {mass_score:.3f} (0-1, higher = more substantial)
- Coherence score: {coherence_score:.3f} (0-1, higher = tighter semantic focus)
- Protection score: {protection_score:.3f} (below demotion threshold)

**Affinity with other ontologies (potential absorption targets):**
{affinity_text}

**Best absorption target by affinity:** {best_target}

**Task:**
Determine if this ontology should be **demoted** (absorbed into another) or **revived** (kept alive with the expectation of future growth).

Reasons to **demote:**
- Very low mass (not enough content to justify a separate domain)
- High affinity with another ontology (its content belongs there)
- Low coherence (it's a grab-bag, not a focused domain)
- The content would be better organized within the absorption target

Reasons to **revive/keep:**
- The domain is legitimate but young (needs more content)
- It covers a distinct topic not well-served by any affinity target
- Coherence is reasonable — the domain is focused, just small
- Absorption would create a less coherent target ontology

**Response format (JSON):**
```json
{{
  "should_demote": true or false,
  "reasoning": "Brief explanation of the decision",
  "absorption_target": "name of the best target ontology (only if demoting)"
}}
```

Respond with ONLY the JSON, no other text."""

    return await _call_llm(
        prompt=prompt,
        ai_provider=ai_provider,
        parse_fn=lambda result: DemotionDecision(
            should_demote=bool(result.get("should_demote", False)),
            reasoning=result.get("reasoning", "No reasoning provided"),
            absorption_target=result.get("absorption_target"),
        ),
        fallback=DemotionDecision(
            should_demote=False,
            reasoning="LLM evaluation failed; defaulting to no demotion",
        ),
    )


def _call_llm_sync(prompt: str, ai_provider) -> str:
    """Synchronous LLM call. Runs in a thread pool via _call_llm."""
    from api.app.lib.llm_utils import call_llm_sync

    return call_llm_sync(
        ai_provider,
        prompt=prompt,
        system_msg="You are a knowledge graph architect. Respond with valid JSON only.",
        max_tokens=400,
        json_mode=True,
    )


async def _call_llm(prompt: str, ai_provider, parse_fn, fallback):
    """
    Call LLM with structured prompt and parse JSON response.

    Offloads synchronous provider I/O to a thread pool so the event
    loop is not blocked during LLM inference.
    """
    try:
        content = await asyncio.to_thread(_call_llm_sync, prompt, ai_provider)

        # Extract JSON from markdown if needed
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        result = json.loads(content)
        return parse_fn(result)

    except Exception as e:
        logger.error(f"LLM evaluation failed: {e}")
        return fallback
