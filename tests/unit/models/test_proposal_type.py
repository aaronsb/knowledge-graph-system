"""
Unit tests for ADR-206 proposal-type vocabulary normalization.

Covers the deprecated-name aliases (promotion → CLEAVE, demotion → DISSOLVE)
and the AnnealingProposal.from_row builder that applies them on load.
"""

from datetime import datetime, timezone

import pytest

from api.app.models.ontology import (
    AnnealingProposal,
    ProposalKind,
    ProposalType,
    normalize_proposal_type,
)


class TestNormalizeProposalType:
    def test_canonical_passthrough(self):
        for verb in (
            "CLEAVE",
            "DISSOLVE",
            "MERGE",
            "RENAME",
            "NO_ACTION",
            "ESCALATE",
            "ADJUST_CONTROL",
        ):
            canonical, params = normalize_proposal_type(verb, {})
            assert canonical.value == verb
            assert params == {}

    def test_promotion_alias_maps_to_cleave_with_parent_as_source(self):
        # v1 promotion's parent ontology lived in the row's ontology_name
        # column — could be any ontology, not only primordial.
        canonical, params = normalize_proposal_type(
            "promotion", None, ontology_name="philosophy"
        )
        assert canonical is ProposalType.CLEAVE
        assert params == {"source_ontology": "philosophy"}

    def test_promotion_alias_without_ontology_name_leaves_source_unset(self):
        canonical, params = normalize_proposal_type("promotion", None)
        assert canonical is ProposalType.CLEAVE
        assert params == {}

    def test_demotion_alias_threads_ontology_name_to_source(self):
        canonical, params = normalize_proposal_type(
            "demotion", {"rationale": "x"}, ontology_name="philosophy"
        )
        assert canonical is ProposalType.DISSOLVE
        assert params == {"rationale": "x", "source_ontology": "philosophy"}

    def test_caller_params_win_over_alias_delta(self):
        # Stored row claims source_ontology='alpha' — alias should NOT
        # overwrite that with the row's ontology_name.
        canonical, params = normalize_proposal_type(
            "promotion", {"source_ontology": "alpha"}, ontology_name="philosophy"
        )
        assert canonical is ProposalType.CLEAVE
        assert params == {"source_ontology": "alpha"}

    def test_unknown_proposal_type_raises(self):
        with pytest.raises(ValueError, match="Unknown proposal_type"):
            normalize_proposal_type("MORPHING", None)


def _row(**overrides):
    base = {
        "id": 1,
        "proposal_type": "CLEAVE",
        "ontology_name": "alpha",
        "reasoning": "test",
        "status": "pending",
        "created_at": datetime.now(timezone.utc),
        "created_at_epoch": 0,
        "proposal_kind": "ontology",
    }
    base.update(overrides)
    return base


class TestAnnealingProposalFromRow:
    def test_canonical_row_round_trips(self):
        row = _row(proposal_type="DISSOLVE", params={"force_primordial": True})
        proposal = AnnealingProposal.from_row(row)
        assert proposal.proposal_type == ProposalType.DISSOLVE.value
        assert proposal.params == {"force_primordial": True}
        assert proposal.proposal_kind == ProposalKind.ONTOLOGY.value

    def test_legacy_promotion_row_threads_ontology_name_as_source(self):
        # Historical row with no params JSONB — alias should populate
        # source_ontology from the row's parent ontology, not a hardcoded
        # primordial. The reviewer's failure case: a non-primordial
        # promotion executes as a zero-source no-op under the hardcoded
        # default.
        row = _row(proposal_type="promotion", ontology_name="philosophy", params=None)
        proposal = AnnealingProposal.from_row(row)
        assert proposal.proposal_type == ProposalType.CLEAVE.value
        assert proposal.params == {"source_ontology": "philosophy"}

    def test_legacy_demotion_row_threads_ontology_name_as_source(self):
        row = _row(
            proposal_type="demotion",
            ontology_name="ml-ops",
            params={"force_primordial": True, "rationale": "low affinity"},
        )
        proposal = AnnealingProposal.from_row(row)
        assert proposal.proposal_type == ProposalType.DISSOLVE.value
        assert proposal.params == {
            "force_primordial": True,
            "rationale": "low affinity",
            "source_ontology": "ml-ops",
        }

    def test_adjust_control_kind_preserved(self):
        row = _row(
            proposal_type="ADJUST_CONTROL",
            proposal_kind="control",
            params={"control_key": "failure_cooldown_epochs", "recommended_value": 7},
        )
        proposal = AnnealingProposal.from_row(row)
        assert proposal.proposal_type == ProposalType.ADJUST_CONTROL.value
        assert proposal.proposal_kind == ProposalKind.CONTROL.value

    def test_empty_params_jsonb_becomes_none(self):
        # Row with proposal_type that does not need params and no caller params.
        row = _row(proposal_type="NO_ACTION", params=None)
        proposal = AnnealingProposal.from_row(row)
        assert proposal.params is None
