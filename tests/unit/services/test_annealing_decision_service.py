"""
Unit tests for AnnealingDecisionService (commit 5 of ADR-206 vocab migration).

Mocks the AIProvider.call_with_tools facade so the test surface is the
service's own concerns: prompt assembly, tool offering, decision parsing,
and proposal_kind routing.
"""

from unittest.mock import MagicMock

import pytest

from api.app.lib.ai_providers import (
    AIProvider,
    TokenUsage,
    ToolCallResponse,
    ToolSchema,
)
from api.app.lib.annealing_tools import ALL_ONTOLOGY_TOOLS, ADJUST_CONTROL_TOOL
from api.app.services.annealing_decision_service import (
    AffinityTarget,
    AnchorConcept,
    AnnealingCandidate,
    AnnealingContext,
    AnnealingDecisionService,
    FailedProposalSummary,
    OntologySummary,
    _build_user_prompt,
)


@pytest.fixture
def context():
    return AnnealingContext(
        ontology_inventory=[
            OntologySummary(name="primordial", concept_count=120, lifecycle_state="active"),
            OntologySummary(name="databases", concept_count=42, lifecycle_state="active"),
            OntologySummary(name="ml-ops", concept_count=8, lifecycle_state="active"),
        ]
    )


@pytest.fixture
def cleave_candidate():
    return AnnealingCandidate(
        signal_kind="high_degree_concept",
        primary_ontology="primordial",
        anchor_concept=AnchorConcept(
            concept_id="c_pg",
            label="PostgreSQL",
            description="Open-source relational DB",
            degree=23,
            top_neighbors=["MVCC", "WAL", "AGE"],
        ),
        affinity_targets=[AffinityTarget(other_ontology="databases", shared_concept_count=12, affinity_score=0.41)],
    )


@pytest.fixture
def dissolve_candidate():
    return AnnealingCandidate(
        signal_kind="low_protection_low_coherence",
        primary_ontology="ml-ops",
        mass_score=0.04,
        coherence_score=0.21,
        protection_score=-0.18,
        concept_count=8,
        affinity_targets=[
            AffinityTarget(other_ontology="devops", shared_concept_count=5, affinity_score=0.55),
            AffinityTarget(other_ontology="ml", shared_concept_count=3, affinity_score=0.30),
        ],
        recent_failures=[
            FailedProposalSummary(
                proposal_type="DISSOLVE",
                target="primordial",
                failure_reason="ingestion-in-flight",
                age_epochs=1,
            )
        ],
    )


def _mock_provider(tool_name: str, params: dict) -> MagicMock:
    provider = MagicMock(spec=AIProvider)
    provider.call_with_tools.return_value = ToolCallResponse(
        tool_name=tool_name,
        params=params,
        stop_reason="tool_use",
        tokens=TokenUsage(input_tokens=120, output_tokens=80),
    )
    return provider


class TestDecideParses6VerbResponse:
    def test_cleave_response_maps_to_ontology_kind(self, context, cleave_candidate):
        provider = _mock_provider(
            "CLEAVE",
            {
                "source_ontology": "primordial",
                "anchor_concept_id": "c_pg",
                "cluster_selection": "first_order",
                "cluster_params": {},
                "target": {"kind": "new", "new_name": "postgresql", "new_description": "PostgreSQL ecosystem"},
                "reasoning": "PostgreSQL coheres tightly around MVCC/WAL/AGE",
            },
        )
        service = AnnealingDecisionService(provider)
        decision = service.decide(context, cleave_candidate)
        assert decision.proposal_type == "CLEAVE"
        assert decision.proposal_kind == "ontology"
        assert decision.reasoning == "PostgreSQL coheres tightly around MVCC/WAL/AGE"
        assert decision.params["target"]["kind"] == "new"

    def test_dissolve_with_rationale_field_populates_reasoning(self, context, dissolve_candidate):
        provider = _mock_provider(
            "DISSOLVE",
            {
                "source_ontology": "ml-ops",
                "rationale": "Low affinity to ml; devops absorbs most sources cleanly.",
            },
        )
        service = AnnealingDecisionService(provider)
        decision = service.decide(context, dissolve_candidate)
        assert decision.proposal_type == "DISSOLVE"
        assert decision.proposal_kind == "ontology"
        # `rationale` is the DISSOLVE-specific name; service maps it to .reasoning
        assert "devops absorbs" in decision.reasoning

    def test_no_action_response_carries_reasoning(self, context, dissolve_candidate):
        provider = _mock_provider(
            "NO_ACTION",
            {"reasoning": "Refractory window still open"},
        )
        service = AnnealingDecisionService(provider)
        decision = service.decide(context, dissolve_candidate)
        assert decision.proposal_type == "NO_ACTION"
        assert decision.reasoning == "Refractory window still open"


class TestAdjustControlRouting:
    def test_adjust_control_routes_to_control_kind(self, context):
        provider = _mock_provider(
            "ADJUST_CONTROL",
            {
                "control_key": "failure_cooldown_epochs",
                "current_value": "5",
                "recommended_value": "7",
                "defense": "ecological ratio drifting; back off",
            },
        )
        # Opus-tier service offers ADJUST_CONTROL alongside the 6 verbs
        service = AnnealingDecisionService(
            provider, tools=list(ALL_ONTOLOGY_TOOLS) + [ADJUST_CONTROL_TOOL]
        )
        candidate = AnnealingCandidate(signal_kind="meta", primary_ontology="(control)")
        decision = service.decide(context, candidate)
        assert decision.proposal_type == "ADJUST_CONTROL"
        assert decision.proposal_kind == "control"
        assert decision.reasoning == "ecological ratio drifting; back off"


class TestToolOffering:
    def test_decide_forces_tool_choice(self, context, cleave_candidate):
        provider = _mock_provider("NO_ACTION", {"reasoning": "x"})
        service = AnnealingDecisionService(provider)
        service.decide(context, cleave_candidate)
        call_kwargs = provider.call_with_tools.call_args.kwargs
        assert call_kwargs["tool_choice"] == "required"

    def test_decide_offers_six_ontology_tools_by_default(self, context, cleave_candidate):
        provider = _mock_provider("NO_ACTION", {"reasoning": "x"})
        service = AnnealingDecisionService(provider)
        service.decide(context, cleave_candidate)
        offered_tools = provider.call_with_tools.call_args.kwargs["tools"]
        assert {t.name for t in offered_tools} == {t.name for t in ALL_ONTOLOGY_TOOLS}

    def test_model_override_propagates_to_provider(self, context, cleave_candidate):
        provider = _mock_provider("NO_ACTION", {"reasoning": "x"})
        service = AnnealingDecisionService(provider)
        service.decide(context, cleave_candidate, model="claude-sonnet-4-6")
        assert provider.call_with_tools.call_args.kwargs["model"] == "claude-sonnet-4-6"


class TestPromptAssembly:
    def test_prompt_includes_inventory_table(self, context, cleave_candidate):
        prompt = _build_user_prompt(context, cleave_candidate)
        assert "Ontology inventory" in prompt
        assert "primordial" in prompt and "databases" in prompt and "ml-ops" in prompt

    def test_prompt_includes_signal_kind_and_primary(self, context, dissolve_candidate):
        prompt = _build_user_prompt(context, dissolve_candidate)
        assert "low_protection_low_coherence" in prompt
        assert "ml-ops" in prompt
        # scores rendered
        assert "mass=" in prompt and "coherence=" in prompt and "protection=" in prompt

    def test_prompt_includes_anchor_concept_for_cleave_signals(self, context, cleave_candidate):
        prompt = _build_user_prompt(context, cleave_candidate)
        assert "PostgreSQL" in prompt
        assert "MVCC" in prompt
        assert "Anchor concept" in prompt

    def test_prompt_includes_recent_failures_when_present(self, context, dissolve_candidate):
        prompt = _build_user_prompt(context, dissolve_candidate)
        assert "Recent failed proposals" in prompt
        assert "ingestion-in-flight" in prompt

    def test_prompt_omits_optional_sections_when_empty(self, context):
        bare = AnnealingCandidate(signal_kind="probe", primary_ontology="primordial")
        prompt = _build_user_prompt(context, bare)
        # No anchor → no anchor section
        assert "Anchor concept" not in prompt
        # No affinity → no affinity table
        assert "Cross-ontology affinity" not in prompt
        # No failures → no failures section
        assert "Recent failed proposals" not in prompt


class TestAsyncWrapper:
    @pytest.mark.asyncio
    async def test_decide_async_returns_same_decision(self, context, cleave_candidate):
        provider = _mock_provider("NO_ACTION", {"reasoning": "z"})
        service = AnnealingDecisionService(provider)
        decision = await service.decide_async(context, cleave_candidate)
        assert decision.proposal_type == "NO_ACTION"
        assert decision.reasoning == "z"
