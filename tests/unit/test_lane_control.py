"""Unit tests for worker-lane freeze / quiesce (ADR-102 A14 / P5).

freeze_lanes / thaw_lanes are tested against a fake connection that records the
SQL it executes and answers SELECTs from an in-memory ``worker_lanes`` model, so
the prior-state capture + restore logic is exercised without a database. The
wait_for_quiesce loop logic (drain vs fail-open timeout) is tested by patching
the DB-touching helpers, isolating the control flow.
"""
from unittest.mock import patch

import pytest

from api.app.lib import lane_control


# --------------------------------------------------------------------------
# A tiny fake job_queue whose connection answers the exact SQL lane_control uses.
# --------------------------------------------------------------------------
class _FakeCursor:
    def __init__(self, lanes):
        self._lanes = lanes          # {name: {"enabled": bool, "job_types": [...]}}
        self._result = None

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.startswith("SELECT enabled FROM kg_api.worker_lanes WHERE name ="):
            name = params[0]
            row = self._lanes.get(name)
            self._result = [(row["enabled"],)] if row else []
        elif s.startswith("UPDATE kg_api.worker_lanes SET enabled ="):
            # Two shapes: freeze (literal FALSE, 1 param=name) and thaw (param enabled, name).
            if len(params) == 1:
                name = params[0]
                if name in self._lanes:
                    self._lanes[name]["enabled"] = False
            else:
                enabled, name = params
                if name in self._lanes:
                    self._lanes[name]["enabled"] = enabled
            self._result = []
        else:
            self._result = []

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return list(self._result)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __init__(self, lanes):
        self._lanes = lanes
        self.committed = False
        self.rolled_back = False

    def cursor(self, **kw):
        return _FakeCursor(self._lanes)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


class _FakeQueue:
    def __init__(self, lanes):
        self.lanes = lanes
        self.returned = False

    def _get_connection(self):
        return _FakeConn(self.lanes)

    def _return_connection(self, conn):
        self.returned = True


def _lanes():
    return {
        "interactive": {"enabled": True, "job_types": ["ingestion", "polarity"]},
        "maintenance": {"enabled": True, "job_types": ["projection"]},
        "system": {"enabled": True, "job_types": ["restore", "source_embedding"]},
    }


# ---- freeze / thaw ----

def test_freeze_captures_prior_and_disables():
    q = _FakeQueue(_lanes())
    prior = lane_control.freeze_lanes(q, ["interactive", "maintenance"])
    assert prior == {"interactive": True, "maintenance": True}
    assert q.lanes["interactive"]["enabled"] is False
    assert q.lanes["maintenance"]["enabled"] is False
    # system never touched
    assert q.lanes["system"]["enabled"] is True


def test_thaw_restores_prior_state_not_blanket_enable():
    # maintenance was ALREADY disabled by an operator before the restore.
    lanes = _lanes()
    lanes["maintenance"]["enabled"] = False
    q = _FakeQueue(lanes)

    prior = lane_control.freeze_lanes(q, ["interactive", "maintenance"])
    assert prior == {"interactive": True, "maintenance": False}
    assert q.lanes["interactive"]["enabled"] is False

    lane_control.thaw_lanes(q, prior)
    # interactive restored to enabled; maintenance stays disabled (its prior state).
    assert q.lanes["interactive"]["enabled"] is True
    assert q.lanes["maintenance"]["enabled"] is False


def test_thaw_empty_is_noop():
    q = _FakeQueue(_lanes())
    lane_control.thaw_lanes(q, {})  # must not raise
    lane_control.thaw_lanes(q, None)


def test_thaw_never_raises_on_db_error():
    class _BoomQueue:
        def _get_connection(self):
            raise RuntimeError("db down")
    # Must swallow + log, not propagate (called from a finally).
    lane_control.thaw_lanes(_BoomQueue(), {"interactive": True})


# ---- wait_for_quiesce ----

def test_quiesce_returns_true_when_drained():
    q = _FakeQueue(_lanes())
    with patch.object(lane_control, "_lane_job_types", return_value=["ingestion"]), \
         patch.object(lane_control, "_count_inflight", return_value=0):
        assert lane_control.wait_for_quiesce(q, ["interactive"], timeout_s=5) is True


def test_quiesce_fail_open_on_timeout():
    q = _FakeQueue(_lanes())
    # Never drains → returns False (fail-open), does NOT raise.
    with patch.object(lane_control, "_lane_job_types", return_value=["ingestion"]), \
         patch.object(lane_control, "_count_inflight", return_value=3):
        assert lane_control.wait_for_quiesce(
            q, ["interactive"], timeout_s=0, poll_interval_s=0.01) is False


def test_quiesce_drains_after_a_few_polls():
    q = _FakeQueue(_lanes())
    counts = iter([2, 1, 0])
    with patch.object(lane_control, "_lane_job_types", return_value=["ingestion"]), \
         patch.object(lane_control, "_count_inflight", side_effect=lambda *a: next(counts)):
        assert lane_control.wait_for_quiesce(
            q, ["interactive"], timeout_s=5, poll_interval_s=0.01) is True
