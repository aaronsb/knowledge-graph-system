"""Unit tests for ingestion worker helpers (#402 Defect B1).

Focused on the target-ontology validation step that decides between
"first-ingest, create it" and "vanished mid-flight, fail loudly".
"""

import pytest
from unittest.mock import MagicMock

from api.app.workers.ingestion_worker import (
    _validate_target_ontology,
    ONTOLOGY_VANISHED_MID_FLIGHT_ERROR,
    ONTOLOGY_FROZEN_ERROR,
)


@pytest.mark.unit
class TestValidateTargetOntology:
    """Defect B1: when the target ontology disappears between job submit and
    job execute (annealing dissolved it, an operator deleted it, etc.) the
    ingestion worker must fail loudly with a structured error rather than
    silently recreate the ontology and accept the data."""

    def test_existing_ontology_passes_through(self):
        """A live, active ontology is returned untouched."""
        age_client = MagicMock()
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

    def test_vanished_after_submit_raises_distinct_error(self):
        """If the operator targeted an existing ontology and it is gone
        now, the worker must raise with the 'vanished mid-flight' string."""
        age_client = MagicMock()
        age_client.get_ontology_node.return_value = None

        with pytest.raises(Exception) as exc_info:
            _validate_target_ontology(
                age_client,
                "vanished-domain",
                existed_at_submit=True,
            )

        msg = str(exc_info.value)
        assert "vanished-domain" in msg
        assert "removed between queue and execution" in msg
        # Must be the distinct string, not the frozen one — Defect B2 will
        # add a third distinct string for 'deliberately removed'.
        assert msg != ONTOLOGY_FROZEN_ERROR.format(name="vanished-domain")
        age_client.ensure_ontology_exists.assert_not_called()

    def test_first_ingest_creates_ontology(self):
        """If the operator targeted a fresh namespace (existed_at_submit
        is False) and no node exists, creating it IS the intent — do so."""
        age_client = MagicMock()
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

        age_client.ensure_ontology_exists.assert_called_once_with(
            "fresh-domain", created_by="alice"
        )
        assert node["lifecycle_state"] == "active"

    def test_frozen_ontology_raises_frozen_error(self):
        """A frozen ontology fails with the frozen string — distinct from
        the vanished-mid-flight string so both can be told apart."""
        age_client = MagicMock()
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
        assert msg != ONTOLOGY_VANISHED_MID_FLIGHT_ERROR.format(
            name="frozen-domain"
        )

    def test_legacy_job_defaults_existed_at_submit_true(self):
        """A pre-B1 job without the ontology_existed_at_submit key on its
        job_data must default to the safe behavior (fail on missing) when
        the worker's job_data.get(..., True) is supplied as the argument."""
        age_client = MagicMock()
        age_client.get_ontology_node.return_value = None

        # The worker calls job_data.get('ontology_existed_at_submit', True);
        # this test exercises the post-get value directly.
        with pytest.raises(Exception) as exc_info:
            _validate_target_ontology(
                age_client,
                "legacy-domain",
                existed_at_submit=True,
            )

        assert "removed between queue and execution" in str(exc_info.value)
