"""Unit tests for ingestion worker helpers (#402 Defects B1 + B2).

Focused on the target-ontology validation step that decides between
"missing — recreate per operator intent", "missing but tombstoned — fail
loudly", and "frozen — fail loudly".
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

    def test_missing_without_tombstone_triggers_recreate(self):
        """A missing ontology with no tombstone is recreated — operator
        intent (the queued ingest) overrides background dissolution."""
        age_client = _make_age_client(tombstone_row=None)
        age_client.get_ontology_node.return_value = None
        age_client.ensure_ontology_exists.return_value = {
            "lifecycle_state": "active",
            "embedding": [],
        }

        node = _validate_target_ontology(
            age_client,
            "dissolved-domain",
            existed_at_submit=True,
            created_by="alice",
            job_id="job_abc",
        )

        age_client.ensure_ontology_exists.assert_called_once_with(
            "dissolved-domain", created_by="alice"
        )
        assert node["lifecycle_state"] == "active"

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

    def test_tombstone_read_failure_falls_back_to_recreate(self):
        """If the tombstone lookup itself fails (DB unreachable), the worker
        treats the result as 'no tombstone' and recreates — failing every
        ingest when the tombstone table is unreachable would be worse.
        Defect A's queue-veto remains the upstream safety layer."""
        age_client = _make_age_client(raise_on_tombstone_read=True)
        age_client.get_ontology_node.return_value = None
        age_client.ensure_ontology_exists.return_value = {
            "lifecycle_state": "active",
            "embedding": [],
        }

        node = _validate_target_ontology(
            age_client,
            "dissolved-domain",
            existed_at_submit=True,
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
