"""
Grounding hydration on /query/related (ADR-044, #280 follow-up).

The original ADR-201 Phase 5f acceleration shipped grounding hydration on
/search/concepts and /query/connect but skipped /query/related — the route
returned bare (concept_id, label, distance, path_types) tuples even when
clients asked for grounding. The CLI/MCP `related` callers never bothered to
ask, since the field didn't exist.

These tests lock in the fix: include_grounding=true populates the four
grounding fields per related concept, and include_grounding=false (or absent
in the legacy contract) leaves them null.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture(autouse=True)
def setup_auth_mocks(mock_oauth_validation, bypass_permission_check):
    """Auto-use mock OAuth validation and bypass RBAC for all tests in this module."""
    pass


def _neighborhood_rows():
    """Three concepts at varying distances from the seed."""
    return [
        {"concept_id": "c_alpha", "label": "Alpha", "distance": 1, "path_types": ["IMPLIES"]},
        {"concept_id": "c_beta", "label": "Beta", "distance": 1, "path_types": ["SUPPORTS"]},
        {"concept_id": "c_gamma", "label": "Gamma", "distance": 2, "path_types": ["IMPLIES", "ENABLES"]},
    ]


def _grounding_batch_response():
    """What _hydrate_grounding_batch would return for the three concepts above."""
    return {
        "c_alpha": {
            "grounding_strength": 0.82,
            "confidence_level": "high",
            "confidence_score": 0.91,
            "grounding_display": "Strong",
        },
        "c_beta": {
            "grounding_strength": 0.31,
            "confidence_level": "medium",
            "confidence_score": 0.55,
            "grounding_display": "Moderate",
        },
        "c_gamma": {
            "grounding_strength": -0.12,
            "confidence_level": "low",
            "confidence_score": 0.22,
            "grounding_display": "Negative",
        },
    }


@pytest.mark.unit
class TestRelatedConceptsGroundingHydration:
    """Behavior under different include_grounding settings."""

    def test_include_grounding_true_populates_all_four_fields(
        self, api_client: TestClient, auth_headers_user
    ):
        """
        With include_grounding=True (the default), each related concept carries
        the full ADR-044 quartet: grounding_strength, confidence_level,
        confidence_score, grounding_display.
        """
        with patch("api.app.routes.queries.get_age_client") as mock_age_factory, \
             patch("api.app.routes.queries._hydrate_grounding_batch") as mock_hydrate, \
             patch("api.app.routes.queries.resolve_epistemic_filters_to_rel_types") as mock_epist:
            mock_client = MagicMock()
            mock_client.graph.neighborhood.return_value = _neighborhood_rows()
            mock_age_factory.return_value = mock_client
            mock_epist.return_value = None
            mock_hydrate.return_value = _grounding_batch_response()

            response = api_client.post(
                "/query/related",
                json={"concept_id": "c_seed", "max_depth": 2, "include_grounding": True},
                headers=auth_headers_user,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 3

            alpha = next(r for r in data["results"] if r["concept_id"] == "c_alpha")
            assert alpha["grounding_strength"] == pytest.approx(0.82)
            assert alpha["confidence_level"] == "high"
            assert alpha["confidence_score"] == pytest.approx(0.91)
            assert alpha["grounding_display"] == "Strong"

            # And the batch hydrator was called once with the three concept IDs
            mock_hydrate.assert_called_once()
            hydrated_ids = mock_hydrate.call_args.args[1]
            assert set(hydrated_ids) == {"c_alpha", "c_beta", "c_gamma"}

    def test_include_grounding_false_skips_hydration(
        self, api_client: TestClient, auth_headers_user
    ):
        """
        With include_grounding=False, grounding fields are null and the
        batch hydrator is never called — caller opted out for speed (ADR-044).
        """
        with patch("api.app.routes.queries.get_age_client") as mock_age_factory, \
             patch("api.app.routes.queries._hydrate_grounding_batch") as mock_hydrate, \
             patch("api.app.routes.queries.resolve_epistemic_filters_to_rel_types") as mock_epist:
            mock_client = MagicMock()
            mock_client.graph.neighborhood.return_value = _neighborhood_rows()
            mock_age_factory.return_value = mock_client
            mock_epist.return_value = None

            response = api_client.post(
                "/query/related",
                json={"concept_id": "c_seed", "max_depth": 2, "include_grounding": False},
                headers=auth_headers_user,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 3
            for r in data["results"]:
                assert r["grounding_strength"] is None
                assert r["confidence_level"] is None
                assert r["confidence_score"] is None
                assert r["grounding_display"] is None

            mock_hydrate.assert_not_called()

    def test_empty_neighborhood_skips_hydration(
        self, api_client: TestClient, auth_headers_user
    ):
        """
        Empty neighborhood: no point calling the batch hydrator with an empty
        ID list. The short-circuit lives in the route, not the hydrator.
        """
        with patch("api.app.routes.queries.get_age_client") as mock_age_factory, \
             patch("api.app.routes.queries._hydrate_grounding_batch") as mock_hydrate, \
             patch("api.app.routes.queries.resolve_epistemic_filters_to_rel_types") as mock_epist:
            mock_client = MagicMock()
            mock_client.graph.neighborhood.return_value = []
            mock_age_factory.return_value = mock_client
            mock_epist.return_value = None

            response = api_client.post(
                "/query/related",
                json={"concept_id": "c_isolated", "max_depth": 2, "include_grounding": True},
                headers=auth_headers_user,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 0
            assert data["results"] == []
            mock_hydrate.assert_not_called()

    def test_default_request_hydrates_grounding(
        self, api_client: TestClient, auth_headers_user
    ):
        """
        Backwards-compatible default: omitting include_grounding still hydrates,
        because the Pydantic default is True. This is the path the CLI/MCP take
        before #280's client-side flag-handling lands — they don't send the
        field, but the server fills grounding anyway.
        """
        with patch("api.app.routes.queries.get_age_client") as mock_age_factory, \
             patch("api.app.routes.queries._hydrate_grounding_batch") as mock_hydrate, \
             patch("api.app.routes.queries.resolve_epistemic_filters_to_rel_types") as mock_epist:
            mock_client = MagicMock()
            mock_client.graph.neighborhood.return_value = _neighborhood_rows()
            mock_age_factory.return_value = mock_client
            mock_epist.return_value = None
            mock_hydrate.return_value = _grounding_batch_response()

            response = api_client.post(
                "/query/related",
                json={"concept_id": "c_seed", "max_depth": 2},
                headers=auth_headers_user,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 3
            alpha = next(r for r in data["results"] if r["concept_id"] == "c_alpha")
            assert alpha["grounding_strength"] == pytest.approx(0.82)
