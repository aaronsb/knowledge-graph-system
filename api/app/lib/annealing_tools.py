"""
Tool schemas for the ADR-206 closed annealing-action vocabulary.

Each schema corresponds to one entry in `ProposalType` (api.app.models.ontology)
and matches the parameter shape declared in ADR-206 §Phase 1. The
`AnnealingDecisionService` (commit 5) offers all seven schemas to the LLM
through `AIProvider.call_with_tools` and converts the returned tool call
into a (`proposal_type`, `params`, `proposal_kind`) tuple ready for
`kg_api.annealing_proposals`.

The schemas are intentionally flat — discriminated unions ('one of') are
expressed via a `kind` enum plus conditional fields rather than `oneOf`,
because tool-calling support for `oneOf` varies across providers (OpenAI
handles it; some Ollama models do not). Server-side validation in the
executor enforces the conditional requirements (kind='new' → new_name +
new_description required, etc.).
"""

from typing import Any, Dict, List

from .ai_providers import ToolSchema
from ..models.ontology import ProposalType

CLUSTER_SELECTION_VALUES = ["first_order", "embedding_radius", "named_concepts"]

TARGET_KIND_VALUES = ["new", "existing"]

CLEAVE_TOOL = ToolSchema(
    name=ProposalType.CLEAVE.value,
    description=(
        "Donate a sub-cluster of concepts from one ontology to another. "
        "The anchor concept plus a strategy-determined neighborhood are "
        "moved either into a new ontology you name, or into an existing "
        "named ontology. Use CLEAVE to promote primordial concepts into a "
        "named domain (source_ontology='primordial') or to refine an "
        "established ontology by carving out a coherent sub-region."
    ),
    params_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "source_ontology": {
                "type": "string",
                "description": "Ontology the cluster is donated FROM. May be 'primordial'.",
            },
            "anchor_concept_id": {
                "type": "string",
                "description": "Concept ID at the center of the cluster being moved.",
            },
            "cluster_selection": {
                "type": "string",
                "enum": CLUSTER_SELECTION_VALUES,
                "description": (
                    "Strategy used to materialize the cluster from the anchor: "
                    "first_order (anchor + direct neighbors), "
                    "embedding_radius (anchor + concepts within cosine distance r), "
                    "named_concepts (an explicit list)."
                ),
            },
            "cluster_params": {
                "type": "object",
                "additionalProperties": True,
                "description": (
                    "Strategy-specific parameters. embedding_radius requires "
                    "{radius: float in (0,1]}; named_concepts requires "
                    "{concept_ids: [string]}; first_order accepts {}."
                ),
            },
            "target": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": TARGET_KIND_VALUES,
                        "description": (
                            "'new' creates a fresh ontology with new_name + "
                            "new_description. 'existing' donates into an "
                            "ontology that already exists and differs from "
                            "source_ontology."
                        ),
                    },
                    "new_name": {
                        "type": "string",
                        "description": "Required when kind='new'. Must not already exist.",
                    },
                    "new_description": {
                        "type": "string",
                        "description": "Required when kind='new'. Short human-readable purpose.",
                    },
                    "existing_ontology": {
                        "type": "string",
                        "description": "Required when kind='existing'. Must exist and differ from source_ontology.",
                    },
                },
                "required": ["kind"],
            },
            "reasoning": {
                "type": "string",
                "description": "Short justification — what signal led to this CLEAVE and why this strategy.",
            },
        },
        "required": [
            "source_ontology",
            "anchor_concept_id",
            "cluster_selection",
            "cluster_params",
            "target",
            "reasoning",
        ],
    },
)


DISSOLVE_TOOL = ToolSchema(
    name=ProposalType.DISSOLVE.value,
    description=(
        "Dissolve a named ontology by routing each of its sources to the "
        "ontology with the highest cross-ontology affinity (read from "
        "graph data at execution time). Orphans fall to the primordial "
        "pool. Use force_primordial=true ONLY when the donor is "
        "wholesale-dead and its sources should not migrate to neighbors; "
        "this is a defended override and requires explicit justification "
        "in the reasoning chain. The primordial pool itself cannot be "
        "dissolved."
    ),
    params_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "source_ontology": {
                "type": "string",
                "description": "Named ontology to dissolve. Cannot be 'primordial'.",
            },
            "force_primordial": {
                "type": "boolean",
                "description": (
                    "If true, all sources route to primordial regardless "
                    "of affinity. Defended override — only when the donor "
                    "is wholesale-dead."
                ),
                "default": False,
            },
            "rationale": {
                "type": "string",
                "description": (
                    "Why this ontology should be dissolved. If "
                    "force_primordial=true, must defend that choice too."
                ),
            },
        },
        "required": ["source_ontology", "rationale"],
    },
)


MERGE_TOOL = ToolSchema(
    name=ProposalType.MERGE.value,
    description=(
        "Merge two or more named ontologies into a single target. Each "
        "donor is dissolved into the target. Donors must all exist, must "
        "all be named (not primordial), and the target must differ from "
        "every donor. Target may be an existing named ontology or a new "
        "one created on the fly."
    ),
    params_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "donor_ontologies": {
                "type": "array",
                "minItems": 2,
                "items": {"type": "string"},
                "description": "≥2 named ontologies to merge. None may be 'primordial'.",
            },
            "target": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "kind": {
                        "type": "string",
                        "enum": TARGET_KIND_VALUES,
                    },
                    "new_name": {"type": "string"},
                    "new_description": {"type": "string"},
                    "existing_ontology": {"type": "string"},
                },
                "required": ["kind"],
            },
            "reasoning": {
                "type": "string",
                "description": "What signal indicates these ontologies should fuse.",
            },
        },
        "required": ["donor_ontologies", "target", "reasoning"],
    },
)


RENAME_TOOL = ToolSchema(
    name=ProposalType.RENAME.value,
    description=(
        "Rename a named ontology and/or replace its description. The "
        "ontology must already exist and must not be 'primordial' (whose "
        "name is a system invariant). new_name must not collide with any "
        "existing ontology."
    ),
    params_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "ontology": {
                "type": "string",
                "description": "Current name of the ontology. Cannot be 'primordial'.",
            },
            "new_name": {
                "type": "string",
                "description": "New name. Must not already exist.",
            },
            "new_description": {
                "type": "string",
                "description": "New description.",
            },
            "reasoning": {
                "type": "string",
                "description": "Why the rename clarifies the ontology's purpose.",
            },
        },
        "required": ["ontology", "new_name", "new_description", "reasoning"],
    },
)


NO_ACTION_TOOL = ToolSchema(
    name=ProposalType.NO_ACTION.value,
    description=(
        "Decline to act on this signal. Use when the signal is real but "
        "the system is better served by leaving the graph alone — the "
        "ontology is healthy enough, the candidate cluster is too "
        "ambiguous, or the refractory period suggests waiting. The "
        "reasoning is recorded as an epistemic-ledger entry so future "
        "cycles can learn from the deferral."
    ),
    params_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "reasoning": {
                "type": "string",
                "description": "Why no action is the right response to this signal.",
            },
        },
        "required": ["reasoning"],
    },
)


ESCALATE_TOOL = ToolSchema(
    name=ProposalType.ESCALATE.value,
    description=(
        "Hand the decision to the next tier in the escalation chain "
        "(typically Opus, then human). Use when the signal is real but "
        "you cannot confidently pick one of the other actions. Surface "
        "what you know, what you do not know, and the action you would "
        "tentatively recommend if forced. confidence is your own "
        "self-assessment in [0,1] for the recommended_action."
    ),
    params_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "candidate_actions": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "string",
                    "enum": [
                        ProposalType.CLEAVE.value,
                        ProposalType.DISSOLVE.value,
                        ProposalType.MERGE.value,
                        ProposalType.RENAME.value,
                        ProposalType.NO_ACTION.value,
                    ],
                },
                "description": "Actions you considered — anything other than ESCALATE itself.",
            },
            "what_i_know": {
                "type": "string",
                "description": "The evidence that argues for some action.",
            },
            "what_i_dont_know": {
                "type": "string",
                "description": "The missing context that prevents you from picking one.",
            },
            "recommended_action": {
                "type": "string",
                "enum": [
                    ProposalType.CLEAVE.value,
                    ProposalType.DISSOLVE.value,
                    ProposalType.MERGE.value,
                    ProposalType.RENAME.value,
                    ProposalType.NO_ACTION.value,
                ],
                "description": "If forced to pick today, this one. The escalator may override.",
            },
            "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Your confidence in recommended_action, in [0,1].",
            },
        },
        "required": [
            "candidate_actions",
            "what_i_know",
            "what_i_dont_know",
            "recommended_action",
            "confidence",
        ],
    },
)


ADJUST_CONTROL_TOOL = ToolSchema(
    name=ProposalType.ADJUST_CONTROL.value,
    description=(
        "Tune one Phase-3 operational control knob (cadence, cooldown, "
        "eligibility threshold). Opus-tier action only. The set of "
        "tuneable keys is enforced server-side — safety rails "
        "(automation_level, escalation_chain, opus_confidence, "
        "phone_a_friend_cost_budget) are NOT tuneable by Opus and will "
        "reject. Each adjustment is itself a proposal in the queue "
        "carrying a defense."
    ),
    params_schema={
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "control_key": {
                "type": "string",
                "description": (
                    "Name of the kg_api.annealing_options key to tune. "
                    "Safety rails are rejected at validation time."
                ),
            },
            "current_value": {
                "type": "string",
                "description": "Current value as observed at cycle start (for audit).",
            },
            "recommended_value": {
                "type": "string",
                "description": "Proposed new value. Bezier-derived or operator-justified.",
            },
            "defense": {
                "type": "string",
                "description": (
                    "Written justification — typically references the "
                    "ecological snapshot inputs that produced the "
                    "recommendation."
                ),
            },
        },
        "required": [
            "control_key",
            "current_value",
            "recommended_value",
            "defense",
        ],
    },
)


ALL_ONTOLOGY_TOOLS: List[ToolSchema] = [
    CLEAVE_TOOL,
    DISSOLVE_TOOL,
    MERGE_TOOL,
    RENAME_TOOL,
    NO_ACTION_TOOL,
    ESCALATE_TOOL,
]
"""The 6-verb closed vocabulary — what Sonnet picks from per cycle."""


CONTROL_TOOLS: List[ToolSchema] = [ADJUST_CONTROL_TOOL]
"""Opus-tier meta-action. Offered only when the agent has Phase-3 tuning authority."""


ALL_TOOLS: List[ToolSchema] = ALL_ONTOLOGY_TOOLS + CONTROL_TOOLS


TOOL_BY_NAME: Dict[str, ToolSchema] = {tool.name: tool for tool in ALL_TOOLS}


def get_tool(name: str) -> ToolSchema:
    """Look up a schema by its canonical verb name."""
    try:
        return TOOL_BY_NAME[name]
    except KeyError as exc:
        raise ValueError(
            f"Unknown annealing tool {name!r}; expected one of {sorted(TOOL_BY_NAME)}"
        ) from exc


def proposal_kind_for(name: str) -> str:
    """Return the proposal_kind discriminator for a verb (ADR-206)."""
    if name == ProposalType.ADJUST_CONTROL.value:
        return "control"
    return "ontology"
