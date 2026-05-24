"""Unit tests for ingestion worker helpers (#402 Defects B1 + B2 + PR-404 review).

Focused on the target-ontology validation step that decides between
"first-ever ingest — create", "missing after existing — fail with
VANISHED", "tombstoned — fail with TOMBSTONED", and "frozen — fail
with FROZEN".

PR-404 review revision: tombstone is now checked *unconditionally*
(before reading the graph node) so the operator-delete route can write
the tombstone before the graph delete without a worker dequeue in the
intermediate window writing orphan content. The recreate branch
narrowed to existed_at_submit=False (first-ever ingest); existed_at_
submit=True + missing + no tombstone raises VANISHED as a real anomaly.
"""

import pytest
from unittest.mock import MagicMock

from api.app.workers.ingestion_worker import (
    _validate_target_ontology,
    _ontology_tombstone,
    ONTOLOGY_VANISHED_MID_FLIGHT_ERROR,
    ONTOLOGY_FROZEN_ERROR,
    ONTOLOGY_TOMBSTONED_ERROR,
)


def _make_age_client(tombstone_row=None, raise_on_tombstone_read=False):
    """Build an AGEClient mock with a stub pool that returns the given
    tombstone row (or None) when the worker queries kg_api.ontology_tombstones.
    """
    client = MagicMock()
    cursor = MagicMock()
    cursor.fetchone.return_value = tombstone_row
    conn = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cursor)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    if raise_on_tombstone_read:
        client.pool.getconn.side_effect = Exception("connection refused")
    else:
        client.pool.getconn.return_value = conn
    return client


@pytest.mark.unit
class TestValidateTargetOntology:
    """Defect B1+B2: missing-target handling.

    B1 established the loud-failure infrastructure (distinct error strings,
    raise propagates to status='failed' with error column populated).
    B2 narrows the loud-failure trigger to the operator-intent signal: a
    queued ingest is itself operator intent that overrides a background
    dissolution, so a missing-without-tombstone target is recreated. Only
    an explicit operator tombstone blocks recreation.
    """

    def test_existing_ontology_passes_through(self):
        """A live, active ontology is returned untouched."""
        age_client = _make_age_client()
        age_client.get_ontology_node.return_value = {
            "lifecycle_state": "active",
            "embedding": [],
        }

        node = _validate_target_ontology(
            age_client,
            "my-domain",
            existed_at_submit=True,
        )

        assert node["lifecycle_state"] == "active"
        age_client.ensure_ontology_exists.assert_not_called()

    def test_missing_after_existing_raises_vanished(self):
        """existed_at_submit=True + missing + no tombstone → VANISHED.

        With the annealing veto (A) and proposal-executor re-check in
        place, an in-flight ingest's target should not be dissolved.
        Reaching this branch indicates a real anomaly (rename without
        job migration, manual graph surgery, residual race) that an
        operator should see rather than have silently recreated."""
        age_client = _make_age_client(tombstone_row=None)
        age_client.get_ontology_node.return_value = None

        with pytest.raises(Exception) as exc_info:
            _validate_target_ontology(
                age_client,
                "vanished-domain",
                existed_at_submit=True,
                created_by="alice",
                job_id="job_abc",
            )

        msg = str(exc_info.value)
        assert "vanished-domain" in msg
        assert "existed at job submit" in msg
        # Distinct from tombstoned and frozen.
        assert msg != ONTOLOGY_TOMBSTONED_ERROR.format(name="vanished-domain")
        assert msg != ONTOLOGY_FROZEN_ERROR.format(name="vanished-domain")
        age_client.ensure_ontology_exists.assert_not_called()

    def test_missing_with_tombstone_raises_distinct_error(self):
        """An operator-tombstoned ontology must not be silently recreated —
        raise with the 'deliberately removed' string."""
        age_client = _make_age_client(
            tombstone_row=(
                "removed-domain",
                "2026-05-22 12:00:00",
                "alice",
                "operator-initiated delete via API",
            )
        )
        age_client.get_ontology_node.return_value = None

        with pytest.raises(Exception) as exc_info:
            _validate_target_ontology(
                age_client,
                "removed-domain",
                existed_at_submit=True,
            )

        msg = str(exc_info.value)
        assert "removed-domain" in msg
        assert "deliberately removed" in msg
        # Must be the tombstoned string, not the vanished one — operator
        # intent of removal is distinct from queue/execute race.
        assert msg != ONTOLOGY_VANISHED_MID_FLIGHT_ERROR.format(
            name="removed-domain"
        )
        # Must not have tried to recreate.
        age_client.ensure_ontology_exists.assert_not_called()

    def test_first_ingest_creates_ontology(self):
        """First ingest (no prior node, no tombstone) creates the namespace —
        that IS the operator's intent."""
        age_client = _make_age_client(tombstone_row=None)
        age_client.get_ontology_node.return_value = None
        age_client.ensure_ontology_exists.return_value = {
            "lifecycle_state": "active",
            "embedding": [],
        }

        node = _validate_target_ontology(
            age_client,
            "fresh-domain",
            existed_at_submit=False,
            created_by="alice",
        )

        age_client.ensure_ontology_exists.assert_called_once()
        assert node["lifecycle_state"] == "active"

    def test_frozen_ontology_raises_frozen_error(self):
        """A frozen ontology fails with the frozen string — distinct from
        the tombstoned string so both can be told apart by an operator."""
        age_client = _make_age_client()
        age_client.get_ontology_node.return_value = {
            "lifecycle_state": "frozen",
            "embedding": [],
        }

        with pytest.raises(Exception) as exc_info:
            _validate_target_ontology(
                age_client,
                "frozen-domain",
                existed_at_submit=True,
            )

        msg = str(exc_info.value)
        assert "frozen-domain" in msg
        assert "frozen (read-only)" in msg
        assert msg != ONTOLOGY_TOMBSTONED_ERROR.format(name="frozen-domain")

    def test_tombstone_present_with_live_node_still_raises(self):
        """The unconditional tombstone check covers the window where the
        operator-delete route has written the tombstone but not yet
        committed the graph delete: ontology still exists, but operator
        intent has been recorded. The worker fails TOMBSTONED rather
        than racing to write into a graph the operator is removing."""
        age_client = _make_age_client(
            tombstone_row=(
                "deleting-domain",
                "2026-05-22 12:00:00",
                "alice",
                "operator-initiated delete via API",
            )
        )
        age_client.get_ontology_node.return_value = {
            "lifecycle_state": "active",
            "embedding": [],
        }

        with pytest.raises(Exception) as exc_info:
            _validate_target_ontology(
                age_client,
                "deleting-domain",
                existed_at_submit=True,
            )

        msg = str(exc_info.value)
        assert "deliberately removed" in msg
        # Must not have even consulted the graph for lifecycle.
        age_client.ensure_ontology_exists.assert_not_called()

    def test_tombstone_read_failure_with_existed_at_submit_raises_vanished(self):
        """If the tombstone lookup itself fails (DB unreachable) AND the
        ontology was supposed to exist at submit but is missing, the
        VANISHED path fires — failing loudly is the correct fallback when
        we cannot positively rule out an operator delete. (Previously the
        worker silently recreated; that was the over-tolerant behavior
        the PR-404 review flagged.)"""
        age_client = _make_age_client(raise_on_tombstone_read=True)
        age_client.get_ontology_node.return_value = None

        with pytest.raises(Exception) as exc_info:
            _validate_target_ontology(
                age_client,
                "dissolved-domain",
                existed_at_submit=True,
                created_by="alice",
            )

        assert "existed at job submit" in str(exc_info.value)
        age_client.ensure_ontology_exists.assert_not_called()

    def test_tombstone_read_failure_on_first_ingest_still_creates(self):
        """existed_at_submit=False is a positive intent signal that the
        operator is establishing a new namespace. A tombstone-read DB
        failure on this path falls through to create (the worst case is
        creating an ontology over a stale tombstone we couldn't read; the
        operator-recreate flow already needs to handle that case)."""
        age_client = _make_age_client(raise_on_tombstone_read=True)
        age_client.get_ontology_node.return_value = None
        age_client.ensure_ontology_exists.return_value = {
            "lifecycle_state": "active",
            "embedding": [],
        }

        node = _validate_target_ontology(
            age_client,
            "fresh-domain",
            existed_at_submit=False,
            created_by="alice",
        )

        age_client.ensure_ontology_exists.assert_called_once()
        assert node["lifecycle_state"] == "active"


@pytest.mark.unit
class TestOntologyTombstone:
    """Direct tests of the tombstone lookup helper."""

    def test_returns_row_when_tombstone_exists(self):
        age_client = _make_age_client(
            tombstone_row=(
                "removed-domain",
                "2026-05-22 12:00:00",
                "alice",
                "operator-initiated delete via API",
            )
        )

        result = _ontology_tombstone(age_client, "removed-domain")

        assert result is not None
        assert result["name"] == "removed-domain"
        assert result["removed_by"] == "alice"
        assert result["reason"] == "operator-initiated delete via API"

    def test_returns_none_when_no_tombstone(self):
        age_client = _make_age_client(tombstone_row=None)
        assert _ontology_tombstone(age_client, "any-name") is None

    def test_returns_none_on_db_error(self):
        age_client = _make_age_client(raise_on_tombstone_read=True)
        assert _ontology_tombstone(age_client, "any-name") is None
