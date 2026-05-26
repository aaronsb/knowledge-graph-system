"""
Unit tests for the ADR-206 annealing tool schemas.

Verifies the schema set covers exactly the 6-verb closed vocabulary plus
ADJUST_CONTROL, that each schema's required fields match ADR-206 §Phase 1
and §Phase 3, that the discriminated `target` shape uses a flat
kind-enum (so non-oneOf-friendly providers can still use the schemas),
and that proposal_kind routing is correct for ADJUST_CONTROL.
"""

import pytest

from api.app.lib.annealing_tools import (
    ALL_ONTOLOGY_TOOLS,
    ALL_TOOLS,
    CLEAVE_TOOL,
    CONTROL_TOOLS,
    DISSOLVE_TOOL,
    ESCALATE_TOOL,
    MERGE_TOOL,
    NO_ACTION_TOOL,
    RENAME_TOOL,
    ADJUST_CONTROL_TOOL,
    TOOL_BY_NAME,
    get_tool,
    proposal_kind_for,
)
from api.app.models.ontology import ProposalType


class TestVocabularyCoverage:
    def test_ontology_tools_cover_six_verbs_exactly(self):
        names = {tool.name for tool in ALL_ONTOLOGY_TOOLS}
        assert names == {
            ProposalType.CLEAVE.value,
            ProposalType.DISSOLVE.value,
            ProposalType.MERGE.value,
            ProposalType.RENAME.value,
            ProposalType.NO_ACTION.value,
            ProposalType.ESCALATE.value,
        }

    def test_control_tools_only_contain_adjust_control(self):
        assert [t.name for t in CONTROL_TOOLS] == [ProposalType.ADJUST_CONTROL.value]

    def test_all_tools_is_union(self):
        assert len(ALL_TOOLS) == len(ALL_ONTOLOGY_TOOLS) + len(CONTROL_TOOLS)
        assert {t.name for t in ALL_TOOLS} == set(TOOL_BY_NAME.keys())


class TestRequiredFields:
    """ADR-206 §Phase 1 column 'Parameters' translated to required-field sets."""

    def test_cleave_required_fields(self):
        required = set(CLEAVE_TOOL.params_schema["required"])
        assert required == {
            "source_ontology",
            "anchor_concept_id",
            "cluster_selection",
            "cluster_params",
            "target",
            "reasoning",
        }

    def test_dissolve_required_fields_force_primordial_optional(self):
        required = set(DISSOLVE_TOOL.params_schema["required"])
        # force_primordial is intentionally NOT required — defended override
        assert required == {"source_ontology", "rationale"}
        # but force_primordial must still be declared as an allowed property
        assert "force_primordial" in DISSOLVE_TOOL.params_schema["properties"]

    def test_merge_required_fields(self):
        required = set(MERGE_TOOL.params_schema["required"])
        assert required == {"donor_ontologies", "target", "reasoning"}
        # ADR-206 §Phase 1: donor_ontologies must be ≥2
        donors = MERGE_TOOL.params_schema["properties"]["donor_ontologies"]
        assert donors["minItems"] == 2

    def test_rename_required_fields(self):
        required = set(RENAME_TOOL.params_schema["required"])
        assert required == {"ontology", "new_name", "new_description", "reasoning"}

    def test_no_action_only_requires_reasoning(self):
        required = set(NO_ACTION_TOOL.params_schema["required"])
        assert required == {"reasoning"}

    def test_escalate_required_fields(self):
        required = set(ESCALATE_TOOL.params_schema["required"])
        assert required == {
            "candidate_actions",
            "what_i_know",
            "what_i_dont_know",
            "recommended_action",
            "confidence",
        }
        # confidence is bounded [0,1]
        confidence = ESCALATE_TOOL.params_schema["properties"]["confidence"]
        assert confidence["minimum"] == 0.0
        assert confidence["maximum"] == 1.0

    def test_adjust_control_required_fields(self):
        required = set(ADJUST_CONTROL_TOOL.params_schema["required"])
        assert required == {
            "control_key",
            "current_value",
            "recommended_value",
            "defense",
        }


class TestEscalateRecursionGuard:
    """ESCALATE cannot recommend itself — would be a recursion."""

    def test_escalate_not_in_recommended_action_enum(self):
        recommended = ESCALATE_TOOL.params_schema["properties"]["recommended_action"]
        assert ProposalType.ESCALATE.value not in recommended["enum"]

    def test_escalate_not_in_candidate_actions_enum(self):
        candidates = ESCALATE_TOOL.params_schema["properties"]["candidate_actions"]
        assert ProposalType.ESCALATE.value not in candidates["items"]["enum"]


class TestDiscriminatedTargetShape:
    """
    `target` is a flat object with a kind-enum rather than a JSON-Schema
    `oneOf`, because tool-calling oneOf support varies across providers.
    Server-side validation enforces the conditional required fields.
    """

    def test_cleave_target_uses_kind_enum_not_oneof(self):
        target = CLEAVE_TOOL.params_schema["properties"]["target"]
        assert "oneOf" not in target
        kind = target["properties"]["kind"]
        assert kind["enum"] == ["new", "existing"]
        assert target["required"] == ["kind"]

    def test_merge_target_uses_kind_enum_not_oneof(self):
        target = MERGE_TOOL.params_schema["properties"]["target"]
        assert "oneOf" not in target
        assert target["properties"]["kind"]["enum"] == ["new", "existing"]


class TestProposalKindRouting:
    def test_six_verbs_route_to_ontology_kind(self):
        for tool in ALL_ONTOLOGY_TOOLS:
            assert proposal_kind_for(tool.name) == "ontology"

    def test_adjust_control_routes_to_control_kind(self):
        assert proposal_kind_for(ProposalType.ADJUST_CONTROL.value) == "control"


class TestGetTool:
    def test_get_tool_returns_matching_schema(self):
        assert get_tool(ProposalType.CLEAVE.value) is CLEAVE_TOOL
        assert get_tool(ProposalType.ADJUST_CONTROL.value) is ADJUST_CONTROL_TOOL

    def test_get_tool_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown annealing tool"):
            get_tool("MORPHING")


class TestClusterSelectionVocabulary:
    """ADR-206 §Phase 1: three cluster strategies, exactly."""

    def test_cleave_cluster_selection_enum(self):
        cluster = CLEAVE_TOOL.params_schema["properties"]["cluster_selection"]
        assert set(cluster["enum"]) == {"first_order", "embedding_radius", "named_concepts"}
