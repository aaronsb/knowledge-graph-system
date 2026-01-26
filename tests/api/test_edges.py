"""
Edge CRUD API tests (ADR-089).

Tests for deterministic edge creation, update, and deletion endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock


def make_edge_response(**overrides):
    """Create a complete mock EdgeResponse with defaults."""
    defaults = {
        "edge_id": "e_c_1_IMPLIES_c_2",
        "from_concept_id": "c_1",
        "to_concept_id": "c_2",
        "relationship_type": "IMPLIES",
        "category": "logical_truth",
        "confidence": 1.0,
        "source": "api_creation",
        "created_at": "2024-01-01T00:00:00Z",
        "created_by": "user_1"
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


def make_edge_list_response(edges=None, total=0, offset=0, limit=50):
    """Create a complete mock EdgeListResponse."""
    return MagicMock(
        edges=edges or [],
        total=total,
        offset=offset,
        limit=limit
    )


@pytest.fixture(autouse=True)
def setup_auth_mocks(mock_oauth_validation):
    """Auto-use mock OAuth validation for all tests in this module."""
    pass


class TestEdgeCreate:
    """Tests for POST /edges endpoint."""

    def test_create_edge_requires_auth(self, api_client: TestClient):
        """Create edge requires authentication."""
        response = api_client.post(
            "/edges",
            json={
                "from_concept_id": "c_1",
                "to_concept_id": "c_2",
                "relationship_type": "IMPLIES",
                "category": "logical_truth"
            }
        )
        assert response.status_code == 401

    def test_create_edge_success(self, api_client: TestClient, auth_headers_user):
        """Create edge with valid data succeeds."""
        with patch('api.app.routes.edges.get_age_client'), \
             patch('api.app.routes.edges.get_edge_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.create_edge.return_value = MagicMock(
                edge_id="e_c_1_IMPLIES_c_2",
                from_concept_id="c_1",
                to_concept_id="c_2",
                relationship_type="IMPLIES",
                category="logical_truth",
                confidence=1.0,
                source="api_creation",
                created_at="2024-01-01T00:00:00Z",
                created_by="user_1"
            )
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/edges",
                json={
                    "from_concept_id": "c_1",
                    "to_concept_id": "c_2",
                    "relationship_type": "IMPLIES",
                    "category": "logical_truth"
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201
            data = response.json()
            assert data["from_concept_id"] == "c_1"
            assert data["to_concept_id"] == "c_2"
            assert data["relationship_type"] == "IMPLIES"

    def test_create_edge_normalizes_type(self, api_client: TestClient, auth_headers_user):
        """Edge type is normalized to uppercase."""
        with patch('api.app.routes.edges.get_age_client'), \
             patch('api.app.routes.edges.get_edge_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.create_edge.return_value = make_edge_response(
                edge_id="e_c_1_SUPPORTS_c_2",
                relationship_type="SUPPORTS"
            )
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/edges",
                json={
                    "from_concept_id": "c_1",
                    "to_concept_id": "c_2",
                    "relationship_type": "supports",  # lowercase
                    "category": "logical_truth"
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201

    def test_create_edge_source_not_found(self, api_client: TestClient, auth_headers_user):
        """Create edge with non-existent source concept returns 400."""
        with patch('api.app.routes.edges.get_age_client'), \
             patch('api.app.routes.edges.get_edge_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.create_edge.side_effect = ValueError("Source concept not found: c_invalid")
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/edges",
                json={
                    "from_concept_id": "c_invalid",
                    "to_concept_id": "c_2",
                    "relationship_type": "IMPLIES",
                    "category": "logical_truth"
                },
                headers=auth_headers_user
            )

            assert response.status_code == 400
            assert "Source concept not found" in response.json()["detail"]

    def test_create_edge_with_confidence(self, api_client: TestClient, auth_headers_user):
        """Create edge with custom confidence score."""
        with patch('api.app.routes.edges.get_age_client'), \
             patch('api.app.routes.edges.get_edge_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.create_edge.return_value = make_edge_response(confidence=0.85)
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/edges",
                json={
                    "from_concept_id": "c_1",
                    "to_concept_id": "c_2",
                    "relationship_type": "IMPLIES",
                    "category": "logical_truth",
                    "confidence": 0.85
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201
            call_args = mock_service.create_edge.call_args
            assert call_args.kwargs["request"].confidence == 0.85


class TestEdgeList:
    """Tests for GET /edges endpoint."""

    def test_list_edges_requires_auth(self, api_client: TestClient):
        """List edges requires authentication."""
        response = api_client.get("/edges")
        assert response.status_code == 401

    def test_list_edges_success(self, api_client: TestClient, auth_headers_user):
        """List edges returns paginated results."""
        with patch('api.app.routes.edges.get_age_client'), \
             patch('api.app.routes.edges.get_edge_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.list_edges.return_value = make_edge_list_response(
                edges=[
                    make_edge_response(edge_id="e_1", relationship_type="IMPLIES"),
                    make_edge_response(edge_id="e_2", relationship_type="SUPPORTS")
                ],
                total=2
            )
            mock_service_factory.return_value = mock_service

            response = api_client.get("/edges", headers=auth_headers_user)

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["edges"]) == 2

    def test_list_edges_filter_by_concept(self, api_client: TestClient, auth_headers_user):
        """List edges filtered by source or target concept."""
        with patch('api.app.routes.edges.get_age_client'), \
             patch('api.app.routes.edges.get_edge_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.list_edges.return_value = make_edge_list_response()
            mock_service_factory.return_value = mock_service

            response = api_client.get(
                "/edges",
                params={"from_concept_id": "c_1"},
                headers=auth_headers_user
            )

            assert response.status_code == 200
            call_args = mock_service.list_edges.call_args
            assert call_args.kwargs["from_concept_id"] == "c_1"

    def test_list_edges_filter_by_type(self, api_client: TestClient, auth_headers_user):
        """List edges filtered by relationship type."""
        with patch('api.app.routes.edges.get_age_client'), \
             patch('api.app.routes.edges.get_edge_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.list_edges.return_value = make_edge_list_response()
            mock_service_factory.return_value = mock_service

            response = api_client.get(
                "/edges",
                params={"relationship_type": "CONTRADICTS"},
                headers=auth_headers_user
            )

            assert response.status_code == 200
            call_args = mock_service.list_edges.call_args
            assert call_args.kwargs["relationship_type"] == "CONTRADICTS"


class TestEdgeUpdate:
    """Tests for PATCH /edges/{from}/{type}/{to} endpoint."""

    def test_update_edge_requires_auth(self, api_client: TestClient):
        """Update edge requires authentication."""
        response = api_client.patch(
            "/edges/c_1/IMPLIES/c_2",
            json={"confidence": 0.9}
        )
        assert response.status_code == 401

    def test_update_edge_success(self, api_client: TestClient, auth_headers_user):
        """Update edge with valid data succeeds."""
        with patch('api.app.routes.edges.get_age_client'), \
             patch('api.app.routes.edges.get_edge_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.update_edge.return_value = make_edge_response(confidence=0.9)
            mock_service_factory.return_value = mock_service

            response = api_client.patch(
                "/edges/c_1/IMPLIES/c_2",
                json={"confidence": 0.9},
                headers=auth_headers_user
            )

            assert response.status_code == 200

    def test_update_edge_change_category(self, api_client: TestClient, auth_headers_user):
        """Update edge category."""
        with patch('api.app.routes.edges.get_age_client'), \
             patch('api.app.routes.edges.get_edge_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.update_edge.return_value = make_edge_response(
                relationship_type="CAUSES",
                category="causal"
            )
            mock_service_factory.return_value = mock_service

            response = api_client.patch(
                "/edges/c_1/CAUSES/c_2",
                json={"category": "causal"},
                headers=auth_headers_user
            )

            assert response.status_code == 200

    def test_update_edge_not_found(self, api_client: TestClient, auth_headers_user):
        """Update non-existent edge returns 404."""
        with patch('api.app.routes.edges.get_age_client'), \
             patch('api.app.routes.edges.get_edge_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.update_edge.side_effect = ValueError("Edge not found")
            mock_service_factory.return_value = mock_service

            response = api_client.patch(
                "/edges/c_1/NONEXISTENT/c_2",
                json={"confidence": 0.5},
                headers=auth_headers_user
            )

            assert response.status_code == 404


class TestEdgeDelete:
    """Tests for DELETE /edges/{from}/{type}/{to} endpoint."""

    def test_delete_edge_requires_auth(self, api_client: TestClient):
        """Delete edge requires authentication."""
        response = api_client.delete("/edges/c_1/IMPLIES/c_2")
        assert response.status_code == 401

    def test_delete_edge_success(self, api_client: TestClient, auth_headers_user):
        """Delete edge returns 204 No Content."""
        with patch('api.app.routes.edges.get_age_client'), \
             patch('api.app.routes.edges.get_edge_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.delete_edge.return_value = True
            mock_service_factory.return_value = mock_service

            response = api_client.delete("/edges/c_1/IMPLIES/c_2", headers=auth_headers_user)

            assert response.status_code == 204

    def test_delete_edge_not_found(self, api_client: TestClient, auth_headers_user):
        """Delete non-existent edge returns 404."""
        with patch('api.app.routes.edges.get_age_client'), \
             patch('api.app.routes.edges.get_edge_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.delete_edge.side_effect = ValueError("Edge not found")
            mock_service_factory.return_value = mock_service

            response = api_client.delete("/edges/c_1/NONEXISTENT/c_2", headers=auth_headers_user)

            assert response.status_code == 404


class TestEdgeCategories:
    """Tests for edge category validation."""

    @pytest.mark.parametrize("category", [
        "logical_truth",
        "causal",
        "structural",
        "temporal",
        "comparative",
        "functional",
        "definitional"
    ])
    def test_valid_categories_accepted(self, api_client: TestClient, auth_headers_user, category):
        """All valid edge categories are accepted."""
        with patch('api.app.routes.edges.get_age_client'), \
             patch('api.app.routes.edges.get_edge_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.create_edge.return_value = MagicMock(
                edge_id=f"e_c_1_RELATES_TO_c_2",
                from_concept_id="c_1",
                to_concept_id="c_2",
                relationship_type="RELATES_TO",
                category=category,
                confidence=1.0,
                source="api_creation",
                created_at="2024-01-01T00:00:00Z",
                created_by="user_1"
            )
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/edges",
                json={
                    "from_concept_id": "c_1",
                    "to_concept_id": "c_2",
                    "relationship_type": "RELATES_TO",
                    "category": category
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201

    def test_invalid_category_rejected(self, api_client: TestClient, auth_headers_user):
        """Invalid edge category returns 422."""
        response = api_client.post(
            "/edges",
            json={
                "from_concept_id": "c_1",
                "to_concept_id": "c_2",
                "relationship_type": "IMPLIES",
                "category": "invalid_category"
            },
            headers=auth_headers_user
        )

        assert response.status_code == 422
