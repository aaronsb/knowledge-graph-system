"""
Concept CRUD API tests (ADR-089).

Tests for deterministic concept creation, update, and deletion endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import numpy as np


def make_concept_response(**overrides):
    """Create a complete mock ConceptResponse with defaults."""
    defaults = {
        "concept_id": "c_123",
        "label": "Test Concept",
        "ontology": "test-ontology",
        "description": None,
        "embedding_id": "emb_123",
        "created_at": "2024-01-01T00:00:00Z",
        "created_by": "user_1",
        "creation_method": "api",
        "matched_existing": False
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


def make_concept_list_response(concepts=None, total=0, offset=0, limit=50):
    """Create a complete mock ConceptListResponse."""
    return MagicMock(
        concepts=concepts or [],
        total=total,
        offset=offset,
        limit=limit
    )


@pytest.fixture(autouse=True)
def setup_auth_mocks(mock_oauth_validation, bypass_permission_check):
    """Auto-use mock OAuth validation and bypass RBAC for all tests in this module."""
    pass


class TestConceptCreate:
    """Tests for POST /concepts endpoint."""

    def test_create_concept_requires_auth(self, api_client: TestClient):
        """Create concept requires authentication."""
        response = api_client.post(
            "/concepts",
            json={
                "label": "Test Concept",
                "ontology": "test-ontology"
            }
        )
        assert response.status_code == 401

    def test_create_concept_success(self, api_client: TestClient, auth_headers_user):
        """Create concept with valid data succeeds."""
        with patch('api.app.routes.concepts.get_age_client') as mock_age, \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            # Mock the service
            mock_service = AsyncMock()
            mock_service.create_concept.return_value = MagicMock(
                concept_id="c_123",
                label="Test Concept",
                ontology="test-ontology",
                description=None,
                embedding_id="emb_123",
                created_at="2024-01-01T00:00:00Z",
                created_by="user_1",
                creation_method="api",
                matched_existing=False
            )
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/concepts",
                json={
                    "label": "Test Concept",
                    "ontology": "test-ontology"
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201
            data = response.json()
            assert data["concept_id"] == "c_123"
            assert data["label"] == "Test Concept"
            assert data["matched_existing"] == False

    def test_create_concept_with_matching_mode(self, api_client: TestClient, auth_headers_user):
        """Create concept respects matching_mode parameter."""
        with patch('api.app.routes.concepts.get_age_client'), \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.create_concept.return_value = make_concept_response(
                concept_id="c_existing",
                label="Existing Concept",
                matched_existing=True
            )
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/concepts",
                json={
                    "label": "Similar Concept",
                    "ontology": "test-ontology",
                    "matching_mode": "auto"
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201
            # Service was called with the matching mode
            call_args = mock_service.create_concept.call_args
            assert call_args.kwargs["request"].matching_mode.value == "auto"

    def test_create_concept_force_create_mode(self, api_client: TestClient, auth_headers_user):
        """Force create mode always creates new concept."""
        with patch('api.app.routes.concepts.get_age_client'), \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.create_concept.return_value = make_concept_response(
                concept_id="c_new",
                label="New Concept",
                matched_existing=False
            )
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/concepts",
                json={
                    "label": "New Concept",
                    "ontology": "test-ontology",
                    "matching_mode": "force_create"
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201
            call_args = mock_service.create_concept.call_args
            assert call_args.kwargs["request"].matching_mode.value == "force_create"

    def test_create_concept_validation_error(self, api_client: TestClient, auth_headers_user):
        """Create concept with invalid data returns 400."""
        with patch('api.app.routes.concepts.get_age_client'), \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.create_concept.side_effect = ValueError("Invalid concept data")
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/concepts",
                json={
                    "label": "Test",
                    "ontology": "test"
                },
                headers=auth_headers_user
            )

            assert response.status_code == 400
            assert "Invalid concept data" in response.json()["detail"]

    def test_create_concept_missing_label(self, api_client: TestClient, auth_headers_user):
        """Create concept without label returns 422."""
        response = api_client.post(
            "/concepts",
            json={
                "ontology": "test-ontology"
            },
            headers=auth_headers_user
        )
        assert response.status_code == 422


class TestConceptList:
    """Tests for GET /concepts endpoint."""

    def test_list_concepts_requires_auth(self, api_client: TestClient):
        """List concepts requires authentication."""
        response = api_client.get("/concepts")
        assert response.status_code == 401

    def test_list_concepts_success(self, api_client: TestClient, auth_headers_user):
        """List concepts returns paginated results."""
        with patch('api.app.routes.concepts.get_age_client'), \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.list_concepts.return_value = make_concept_list_response(
                concepts=[
                    make_concept_response(concept_id="c_1", label="Concept 1"),
                    make_concept_response(concept_id="c_2", label="Concept 2")
                ],
                total=2
            )
            mock_service_factory.return_value = mock_service

            response = api_client.get("/concepts", headers=auth_headers_user)

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert len(data["concepts"]) == 2

    def test_list_concepts_with_filters(self, api_client: TestClient, auth_headers_user):
        """List concepts respects filter parameters."""
        with patch('api.app.routes.concepts.get_age_client'), \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.list_concepts.return_value = make_concept_list_response(limit=10)
            mock_service_factory.return_value = mock_service

            response = api_client.get(
                "/concepts",
                params={
                    "ontology": "specific-ontology",
                    "label_contains": "test",
                    "limit": 10
                },
                headers=auth_headers_user
            )

            assert response.status_code == 200
            # Verify filters were passed to service
            call_args = mock_service.list_concepts.call_args
            assert call_args.kwargs["ontology"] == "specific-ontology"
            assert call_args.kwargs["label_contains"] == "test"
            assert call_args.kwargs["limit"] == 10


class TestConceptGet:
    """Tests for GET /concepts/{concept_id} endpoint."""

    def test_get_concept_requires_auth(self, api_client: TestClient):
        """Get concept requires authentication."""
        response = api_client.get("/concepts/c_123")
        assert response.status_code == 401

    def test_get_concept_success(self, api_client: TestClient, auth_headers_user):
        """Get concept by ID returns concept details."""
        with patch('api.app.routes.concepts.get_age_client'), \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.get_concept_response.return_value = make_concept_response()
            mock_service_factory.return_value = mock_service

            response = api_client.get("/concepts/c_123", headers=auth_headers_user)

            assert response.status_code == 200
            data = response.json()
            assert data["concept_id"] == "c_123"

    def test_get_concept_not_found(self, api_client: TestClient, auth_headers_user):
        """Get non-existent concept returns 404."""
        with patch('api.app.routes.concepts.get_age_client'), \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.get_concept_response.side_effect = ValueError("Concept not found")
            mock_service_factory.return_value = mock_service

            response = api_client.get("/concepts/c_nonexistent", headers=auth_headers_user)

            assert response.status_code == 404


class TestConceptUpdate:
    """Tests for PATCH /concepts/{concept_id} endpoint."""

    def test_update_concept_requires_auth(self, api_client: TestClient):
        """Update concept requires authentication."""
        response = api_client.patch(
            "/concepts/c_123",
            json={"label": "Updated"}
        )
        assert response.status_code == 401

    def test_update_concept_success(self, api_client: TestClient, auth_headers_user):
        """Update concept with valid data succeeds."""
        with patch('api.app.routes.concepts.get_age_client'), \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.update_concept.return_value = make_concept_response(
                label="Updated Concept"
            )
            mock_service_factory.return_value = mock_service

            response = api_client.patch(
                "/concepts/c_123",
                json={"label": "Updated Concept"},
                headers=auth_headers_user
            )

            assert response.status_code == 200
            data = response.json()
            assert data["label"] == "Updated Concept"

    def test_update_concept_not_found(self, api_client: TestClient, auth_headers_user):
        """Update non-existent concept returns 404."""
        with patch('api.app.routes.concepts.get_age_client'), \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.update_concept.side_effect = ValueError("Concept not found")
            mock_service_factory.return_value = mock_service

            response = api_client.patch(
                "/concepts/c_nonexistent",
                json={"label": "Updated"},
                headers=auth_headers_user
            )

            assert response.status_code == 404


class TestConceptDelete:
    """Tests for DELETE /concepts/{concept_id} endpoint."""

    def test_delete_concept_requires_auth(self, api_client: TestClient):
        """Delete concept requires authentication."""
        response = api_client.delete("/concepts/c_123")
        assert response.status_code == 401

    def test_delete_concept_success(self, api_client: TestClient, auth_headers_user):
        """Delete concept returns 204 No Content."""
        with patch('api.app.routes.concepts.get_age_client'), \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.delete_concept.return_value = True
            mock_service_factory.return_value = mock_service

            response = api_client.delete("/concepts/c_123", headers=auth_headers_user)

            assert response.status_code == 204

    def test_delete_concept_with_cascade(self, api_client: TestClient, auth_headers_user):
        """Delete concept with cascade deletes orphaned sources."""
        with patch('api.app.routes.concepts.get_age_client'), \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.delete_concept.return_value = True
            mock_service_factory.return_value = mock_service

            response = api_client.delete(
                "/concepts/c_123",
                params={"cascade": True},
                headers=auth_headers_user
            )

            assert response.status_code == 204
            call_args = mock_service.delete_concept.call_args
            assert call_args.kwargs["cascade"] == True

    def test_delete_concept_not_found(self, api_client: TestClient, auth_headers_user):
        """Delete non-existent concept returns 404."""
        with patch('api.app.routes.concepts.get_age_client'), \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.delete_concept.side_effect = ValueError("Concept not found")
            mock_service_factory.return_value = mock_service

            response = api_client.delete("/concepts/c_nonexistent", headers=auth_headers_user)

            assert response.status_code == 404


class TestConceptScopeEnforcement:
    """Tests for RBAC permission enforcement on concept endpoints."""

    @pytest.fixture(autouse=True)
    def _read_only_permissions(self, monkeypatch):
        """Override module-level bypass with read-only RBAC for permission tests."""
        monkeypatch.setattr(
            "api.app.dependencies.auth.check_permission",
            lambda user, resource_type, action, resource_id=None, resource_context=None: action == "read"
        )

    def test_create_concept_requires_write_scope(
        self, api_client: TestClient, auth_headers_user
    ):
        """Create concept without write permission returns 403."""
        response = api_client.post(
            "/concepts",
            json={"label": "Test", "ontology": "test"},
            headers=auth_headers_user
        )
        assert response.status_code == 403
        assert "Permission denied" in response.json()["detail"]

    def test_update_concept_requires_edit_scope(
        self, api_client: TestClient, auth_headers_user
    ):
        """Update concept without write permission returns 403."""
        response = api_client.patch(
            "/concepts/c_123",
            json={"label": "Updated"},
            headers=auth_headers_user
        )
        assert response.status_code == 403
        assert "Permission denied" in response.json()["detail"]

    def test_delete_concept_requires_edit_scope(
        self, api_client: TestClient, auth_headers_user
    ):
        """Delete concept without delete permission returns 403."""
        response = api_client.delete("/concepts/c_123", headers=auth_headers_user)
        assert response.status_code == 403
        assert "Permission denied" in response.json()["detail"]

    def test_list_concepts_allowed_with_read_scope(
        self, api_client: TestClient, auth_headers_user
    ):
        """List concepts succeeds with read permission."""
        with patch('api.app.routes.concepts.get_age_client'), \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.list_concepts.return_value = make_concept_list_response()
            mock_service_factory.return_value = mock_service

            response = api_client.get("/concepts", headers=auth_headers_user)
            assert response.status_code == 200

    def test_get_concept_allowed_with_read_scope(
        self, api_client: TestClient, auth_headers_user
    ):
        """Get concept succeeds with read permission."""
        with patch('api.app.routes.concepts.get_age_client'), \
             patch('api.app.routes.concepts.get_concept_service') as mock_service_factory:

            mock_service = AsyncMock()
            mock_service.get_concept_response.return_value = make_concept_response()
            mock_service_factory.return_value = mock_service

            response = api_client.get("/concepts/c_123", headers=auth_headers_user)
            assert response.status_code == 200
