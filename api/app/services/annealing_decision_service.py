"""
AnnealingDecisionService — drives the 6-verb closed annealing-action
vocabulary (ADR-206) through the provider-neutral call_with_tools facade.

Replaces the boolean promotion/demotion judgment in
api.app.lib.annealing_evaluator with a single multi-way decision: given
a signal, the LLM picks exactly one of ALL_ONTOLOGY_TOOLS (CLEAVE,
DISSOLVE, MERGE, RENAME, NO_ACTION, ESCALATE) and supplies the
parameters that primitive needs. The returned tool call maps directly
to a (proposal_type, params, proposal_kind) tuple ready for
kg_api.annealing_proposals.

The service performs no execution and no graph mutation — it only
produces a proposal. Execution still goes through proposal_executor
under the existing Phase 4 review/approve/execute flow.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..lib.ai_providers import AIProvider, ToolSchema, TokenUsage
from ..lib.annealing_tools import (
    ALL_ONTOLOGY_TOOLS,
    proposal_kind_for,
)

logger = logging.getLogger(__name__)


@dataclass
class OntologySummary:
    """Inventory row for the Sonnet prompt."""
    name: str
    concept_count: int
    lifecycle_state: str = "active"


@dataclass
class AnchorConcept:
    """Concept-centric context for CLEAVE-shaped signals."""
    concept_id: str
    label: str
    description: str = ""
    degree: int = 0
    top_neighbors: List[str] = field(default_factory=list)


@dataclass
class AffinityTarget:
    """A cross-ontology affinity row to surface to the LLM."""
    other_ontology: str
    shared_concept_count: int = 0
    affinity_score: float = 0.0


@dataclass
class FailedProposalSummary:
    """Past failure on the same signal class — prevents indefinite retry."""
    proposal_type: str
    target: Optional[str]
    failure_reason: str
    age_epochs: int = 0


@dataclass
class AnnealingContext:
    """Per-cycle context shared across every candidate this cycle."""
    ontology_inventory: List[OntologySummary]
    primordial_pool_name: str = "primordial"


@dataclass
class AnnealingCandidate:
    """One signal that needs a verb decision."""
    signal_kind: str
    primary_ontology: str
    mass_score: Optional[float] = None
    coherence_score: Optional[float] = None
    protection_score: Optional[float] = None
    concept_count: Optional[int] = None
    anchor_concept: Optional[AnchorConcept] = None
    affinity_targets: List[AffinityTarget] = field(default_factory=list)
    recent_failures: List[FailedProposalSummary] = field(default_factory=list)


@dataclass
class AnnealingDecision:
    """Result of one LLM action-selection call."""
    proposal_type: str
    proposal_kind: str
    params: Dict[str, Any]
    reasoning: str
    tokens: TokenUsage
    raw_response: Any = None


_SYSTEM_PROMPT = """\
You are an ontology-annealing reasoner choosing one action per signal in a
self-organizing knowledge graph. You will be offered the closed action
vocabulary as tools — pick exactly one tool call per turn.

The vocabulary is symmetric and conservation-bound: every concept and every
source remains in the graph regardless of which action you take. The primordial
pool is the floor (orphans land there) and is itself just another ontology that
can be CLEAVEd. You cannot DISSOLVE, MERGE-into, or RENAME primordial.

Choose NO_ACTION when the signal is real but acting would not improve the graph
(refractory period, ambiguous cluster, healthy ontology). Choose ESCALATE only
when you cannot confidently pick one of the other five actions; surface what
you know and what you do not know.

Every action must carry a reasoning / rationale / defense field — the queue is
a permanent epistemic ledger; future cycles read your justifications.
"""


class AnnealingDecisionService:
    """
    Drives the 6-verb vocabulary through AIProvider.call_with_tools.

    Construction:
        service = AnnealingDecisionService(provider)
    Per candidate:
        decision = service.decide(context, candidate)
        await service.decide_async(context, candidate)
    """

    def __init__(
        self,
        ai_provider: AIProvider,
        tools: Optional[List[ToolSchema]] = None,
        max_tokens: int = 2048,
        temperature: Optional[float] = 0.2,
    ):
        self.provider = ai_provider
        self.tools = tools if tools is not None else list(ALL_ONTOLOGY_TOOLS)
        self.max_tokens = max_tokens
        self.temperature = temperature

    def decide(
        self,
        context: AnnealingContext,
        candidate: AnnealingCandidate,
        model: Optional[str] = None,
    ) -> AnnealingDecision:
        """Run one action-selection turn; return the parsed decision."""
        user_prompt = _build_user_prompt(context, candidate)
        response = self.provider.call_with_tools(
            system_prompt=_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            tools=self.tools,
            tool_choice="required",
            max_tokens=self.max_tokens,
            model=model,
            temperature=self.temperature,
        )
        params = response.params or {}
        reasoning = (
            params.get("reasoning")
            or params.get("rationale")
            or params.get("defense")
            or ""
        )
        proposal_type = response.tool_name
        return AnnealingDecision(
            proposal_type=proposal_type,
            proposal_kind=proposal_kind_for(proposal_type),
            params=params,
            reasoning=reasoning,
            tokens=response.tokens,
            raw_response=response.raw_response,
        )

    async def decide_async(
        self,
        context: AnnealingContext,
        candidate: AnnealingCandidate,
        model: Optional[str] = None,
    ) -> AnnealingDecision:
        """Async wrapper — runs `decide` in a worker thread."""
        return await asyncio.to_thread(self.decide, context, candidate, model)


def _build_user_prompt(
    context: AnnealingContext,
    candidate: AnnealingCandidate,
) -> str:
    """Assemble the user-turn prompt for one candidate."""
    parts: List[str] = []

    parts.append("## Ontology inventory")
    if context.ontology_inventory:
        parts.append(
            "| name | concepts | lifecycle |\n|---|---|---|\n"
            + "\n".join(
                f"| {o.name} | {o.concept_count} | {o.lifecycle_state} |"
                for o in context.ontology_inventory
            )
        )
    else:
        parts.append("_(empty)_")

    parts.append(f"\n## Signal\n- kind: `{candidate.signal_kind}`")
    parts.append(f"- primary ontology: `{candidate.primary_ontology}`")
    if candidate.concept_count is not None:
        parts.append(f"- concepts in primary: {candidate.concept_count}")
    score_bits: List[str] = []
    if candidate.mass_score is not None:
        score_bits.append(f"mass={candidate.mass_score:.3f}")
    if candidate.coherence_score is not None:
        score_bits.append(f"coherence={candidate.coherence_score:.3f}")
    if candidate.protection_score is not None:
        score_bits.append(f"protection={candidate.protection_score:.3f}")
    if score_bits:
        parts.append("- scores: " + ", ".join(score_bits))

    if candidate.anchor_concept is not None:
        anchor = candidate.anchor_concept
        parts.append("\n## Anchor concept")
        parts.append(f"- id: `{anchor.concept_id}`")
        parts.append(f"- label: {anchor.label}")
        if anchor.description:
            parts.append(f"- description: {anchor.description}")
        if anchor.degree:
            parts.append(f"- degree: {anchor.degree}")
        if anchor.top_neighbors:
            neighbors = ", ".join(anchor.top_neighbors[:10])
            parts.append(f"- top neighbors: {neighbors}")

    if candidate.affinity_targets:
        parts.append("\n## Cross-ontology affinity (from primary)")
        parts.append("| other ontology | shared concepts | affinity |\n|---|---|---|")
        for a in candidate.affinity_targets[:8]:
            parts.append(
                f"| {a.other_ontology} | {a.shared_concept_count} | {a.affinity_score:.1%} |"
            )

    if candidate.recent_failures:
        parts.append("\n## Recent failed proposals on this signal class")
        parts.append("| action | target | reason | age (epochs) |\n|---|---|---|---|")
        for f in candidate.recent_failures[:5]:
            target = f.target or "—"
            parts.append(
                f"| {f.proposal_type} | {target} | {f.failure_reason} | {f.age_epochs} |"
            )

    parts.append(
        "\nPick exactly one action. Include a reasoning / rationale / defense "
        "field justifying the choice against the signal and the inventory above."
    )
    return "\n".join(parts)
