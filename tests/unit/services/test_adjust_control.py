"""
Unit tests for ADJUST_CONTROL (#249 Part 2, ADR-206 §Phase 3).

Covers two surfaces:
  - ProposalExecutor.execute_adjust_control: safety-rail rejection,
    unknown-key rejection, happy-path UPDATE.
  - AnnealingManager._emit_control_proposals: deadband behaviour,
    open-proposal dedup, parameter shape.
"""

from unittest.mock import MagicMock

import pytest

from api.app.services.proposal_executor import ProposalExecutor


def _mock_client_with_cursor(fetchone_value=(1,), update_returning="7"):
    """Build a MagicMock client whose cursor walks: SELECT 1 → UPDATE RETURNING."""
    client = MagicMock()
    cur = MagicMock()
    cur.fetchone.side_effect = [fetchone_value, (update_returning,)]
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    client.pool = MagicMock()
    client.pool.getconn.return_value = conn
    return client, cur


class TestExecuteAdjustControlHappyPath:
    def test_updates_annealing_options_value(self):
        client, cur = _mock_client_with_cursor(update_returning="7")
        executor = ProposalExecutor(client)
        result = executor.execute_adjust_control({
            "id": 99,
            "params": {
                "control_key": "failure_cooldown_epochs",
                "current_value": "5",
                "recommended_value": "7",
                "defense": "Pressure score 0.50 (tight); cool off harder.",
            },
        })
        assert result["success"] is True
        assert result["control_key"] == "failure_cooldown_epochs"
        assert result["new_value"] == "7"
        # The UPDATE SQL was executed
        update_call = cur.execute.call_args_list[1]
        assert "UPDATE kg_api.annealing_options" in update_call.args[0]
        assert update_call.args[1] == ("7", "failure_cooldown_epochs")


class TestExecuteAdjustControlSafetyRails:
    @pytest.mark.parametrize(
        "rail_key",
        [
            "automation_level",
            "escalation_chain",
            "opus_confidence",
            "phone_a_friend_cost_budget",
        ],
    )
    def test_safety_rail_keys_rejected_without_db_touch(self, rail_key):
        client = MagicMock()
        executor = ProposalExecutor(client)
        result = executor.execute_adjust_control({
            "params": {
                "control_key": rail_key,
                "current_value": "x",
                "recommended_value": "y",
                "defense": "should be rejected",
            },
        })
        assert result["success"] is False
        assert result["rejected_reason"] == "safety_rail"
        # Never touched the pool — rejected before opening a connection
        client.pool.getconn.assert_not_called()


class TestExecuteAdjustControlMissingParams:
    def test_missing_control_key_rejected(self):
        executor = ProposalExecutor(MagicMock())
        result = executor.execute_adjust_control({"params": {"recommended_value": "5"}})
        assert result["success"] is False
        assert "control_key" in result["error"]

    def test_missing_recommended_value_rejected(self):
        executor = ProposalExecutor(MagicMock())
        result = executor.execute_adjust_control({
            "params": {"control_key": "failure_cooldown_epochs"}
        })
        assert result["success"] is False
        assert "recommended_value" in result["error"]


class TestExecuteAdjustControlUnknownKey:
    def test_unknown_control_key_rejected(self):
        client = MagicMock()
        cur = MagicMock()
        # The SELECT returns no row — key doesn't exist
        cur.fetchone.return_value = None
        conn = MagicMock()
        conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
        conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        client.pool = MagicMock()
        client.pool.getconn.return_value = conn

        executor = ProposalExecutor(client)
        result = executor.execute_adjust_control({
            "params": {
                "control_key": "not_a_real_key",
                "current_value": "1",
                "recommended_value": "2",
                "defense": "bogus",
            },
        })
        assert result["success"] is False
        assert "not found" in result["error"]


# ---------- Manager-side emission (deadband + dedup) ----------

def _emit(manager, recommendation, pressure_score=0.7, pressure_zone="tight"):
    return manager._emit_control_proposals(
        recommendation=recommendation,
        pressure_score=pressure_score,
        pressure_zone=pressure_zone,
        epoch=42,
    )


class TestEmitControlProposalsDeadband:
    """Inline helper to avoid pulling the heavy AnnealingManager fixture."""

    def _make_manager_stub(self, open_keys=None, store_returns=None):
        from api.app.services.annealing_manager import AnnealingManager

        stub = AnnealingManager.__new__(AnnealingManager)
        stub.client = MagicMock()
        stub._get_open_control_keys = lambda: set(open_keys or [])
        # Patch _store_proposal to return a deterministic id sequence
        ids = list(store_returns or [101])
        stub._store_proposal = MagicMock(side_effect=ids)
        return stub

    def test_small_delta_below_deadband_emits_nothing(self):
        m = self._make_manager_stub()
        result = _emit(m, {
            "failure_cooldown_epochs": {"current": 5, "recommended": 6, "delta": 1},
        })
        assert result == []
        m._store_proposal.assert_not_called()

    def test_delta_exactly_at_deadband_emits(self):
        m = self._make_manager_stub(store_returns=[42])
        result = _emit(m, {
            "failure_cooldown_epochs": {"current": 5, "recommended": 7, "delta": 2},
        })
        assert result == [42]
        m._store_proposal.assert_called_once()
        call_kwargs = m._store_proposal.call_args.kwargs
        assert call_kwargs["proposal_type"] == "ADJUST_CONTROL"
        assert call_kwargs["proposal_kind"] == "control"
        assert call_kwargs["params"]["control_key"] == "failure_cooldown_epochs"
        assert call_kwargs["params"]["recommended_value"] == "7"

    def test_negative_delta_emits_when_magnitude_exceeds_deadband(self):
        m = self._make_manager_stub(store_returns=[55])
        result = _emit(m, {
            "max_proposals_per_cycle": {"current": 10, "recommended": 4, "delta": -6},
        })
        assert result == [55]

    def test_open_proposal_skips_emission(self):
        m = self._make_manager_stub(open_keys={"failure_cooldown_epochs"})
        result = _emit(m, {
            "failure_cooldown_epochs": {"current": 5, "recommended": 9, "delta": 4},
        })
        assert result == []
        m._store_proposal.assert_not_called()

    def test_multiple_keys_some_above_some_below(self):
        m = self._make_manager_stub(store_returns=[201, 202])
        result = _emit(m, {
            "failure_cooldown_epochs": {"current": 5, "recommended": 9, "delta": 4},
            "max_proposals_per_cycle": {"current": 10, "recommended": 10, "delta": 0},
            "min_activity_for_cycle": {"current": 1, "recommended": 4, "delta": 3},
        })
        assert result == [201, 202]
        assert m._store_proposal.call_count == 2

    def test_defense_text_includes_pressure_zone_and_delta(self):
        m = self._make_manager_stub(store_returns=[300])
        _emit(
            m,
            {"failure_cooldown_epochs": {"current": 5, "recommended": 8, "delta": 3}},
            pressure_score=0.83,
            pressure_zone="over",
        )
        params = m._store_proposal.call_args.kwargs["params"]
        assert "0.83" in params["defense"]
        assert "over" in params["defense"]
        assert "+3" in params["defense"]
