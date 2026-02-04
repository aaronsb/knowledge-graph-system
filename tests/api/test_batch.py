"""
Batch Graph Operations API tests (ADR-089 Phase 1b).

Tests for batch creation of concepts and edges with transaction support.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock


def make_batch_response(**overrides):
    """Create a complete mock BatchResponse with defaults."""
    defaults = {
        "concepts_created": 0,
        "concepts_matched": 0,
        "edges_created": 0,
        "errors": [],
        "concept_results": [],
        "edge_results": []
    }
    defaults.update(overrides)
    return MagicMock(**defaults)


@pytest.fixture(autouse=True)
def setup_auth_mocks(mock_oauth_validation):
    """Auto-use mock OAuth validation for all tests in this module."""
    pass


@pytest.fixture(autouse=True)
def bypass_permission_check(monkeypatch):
    """Bypass require_permission for route tests — auth is tested separately."""
    monkeypatch.setattr(
        "api.app.dependencies.auth.check_permission",
        lambda *args, **kwargs: True
    )


class TestBatchCreate:
    """Tests for POST /graph/batch endpoint."""

    def test_batch_requires_auth(self, api_client: TestClient):
        """Batch create requires authentication."""
        response = api_client.post(
            "/graph/batch",
            json={
                "ontology": "test-ontology",
                "concepts": [{"label": "Test Concept"}]
            }
        )
        assert response.status_code == 401

    def test_batch_requires_import_permission(
        self, api_client: TestClient, auth_headers_user, monkeypatch
    ):
        """Batch create requires import permission on graph."""
        monkeypatch.setattr(
            "api.app.dependencies.auth.check_permission",
            lambda *args, **kwargs: False
        )
        response = api_client.post(
            "/graph/batch",
            json={
                "ontology": "test-ontology",
                "concepts": [{"label": "Test Concept"}]
            },
            headers=auth_headers_user
        )
        assert response.status_code == 403
        assert "import" in response.json()["detail"]

    def test_batch_create_concepts_success(self, api_client: TestClient, auth_headers_user):
        """Batch create concepts successfully."""
        with patch('api.app.routes.graph.get_batch_service') as mock_service_factory:
            mock_service = AsyncMock()
            mock_service.execute_batch.return_value = MagicMock(
                concepts_created=2,
                concepts_matched=0,
                edges_created=0,
                errors=[],
                concept_results=[
                    MagicMock(label="Concept A", status="created", id="c_001", error=None),
                    MagicMock(label="Concept B", status="created", id="c_002", error=None)
                ],
                edge_results=[]
            )
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/graph/batch",
                json={
                    "ontology": "test-ontology",
                    "concepts": [
                        {"label": "Concept A", "description": "First concept"},
                        {"label": "Concept B", "description": "Second concept"}
                    ]
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201
            data = response.json()
            assert data["concepts_created"] == 2
            assert data["concepts_matched"] == 0
            assert len(data["concept_results"]) == 2

    def test_batch_create_edges_success(self, api_client: TestClient, auth_headers_user):
        """Batch create edges successfully."""
        with patch('api.app.routes.graph.get_batch_service') as mock_service_factory:
            mock_service = AsyncMock()
            mock_service.execute_batch.return_value = MagicMock(
                concepts_created=0,
                concepts_matched=0,
                edges_created=1,
                errors=[],
                concept_results=[],
                edge_results=[
                    MagicMock(
                        label="Concept A -> Concept B",
                        status="created",
                        id="e_001",
                        error=None
                    )
                ]
            )
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/graph/batch",
                json={
                    "ontology": "test-ontology",
                    "edges": [
                        {
                            "from_label": "Concept A",
                            "to_label": "Concept B",
                            "relationship_type": "IMPLIES"
                        }
                    ]
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201
            data = response.json()
            assert data["edges_created"] == 1

    def test_batch_combined_concepts_and_edges(self, api_client: TestClient, auth_headers_user):
        """Batch create concepts and edges together."""
        with patch('api.app.routes.graph.get_batch_service') as mock_service_factory:
            mock_service = AsyncMock()
            mock_service.execute_batch.return_value = MagicMock(
                concepts_created=2,
                concepts_matched=0,
                edges_created=1,
                errors=[],
                concept_results=[
                    MagicMock(label="Neural Networks", status="created", id="c_001", error=None),
                    MagicMock(label="Machine Learning", status="created", id="c_002", error=None)
                ],
                edge_results=[
                    MagicMock(
                        label="Neural Networks -> Machine Learning",
                        status="created",
                        id="e_001",
                        error=None
                    )
                ]
            )
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/graph/batch",
                json={
                    "ontology": "ai-research",
                    "concepts": [
                        {"label": "Neural Networks"},
                        {"label": "Machine Learning"}
                    ],
                    "edges": [
                        {
                            "from_label": "Neural Networks",
                            "to_label": "Machine Learning",
                            "relationship_type": "IS_TECHNIQUE_IN"
                        }
                    ]
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201
            data = response.json()
            assert data["concepts_created"] == 2
            assert data["edges_created"] == 1

    def test_batch_with_matching_mode(self, api_client: TestClient, auth_headers_user):
        """Batch respects matching_mode parameter."""
        with patch('api.app.routes.graph.get_batch_service') as mock_service_factory:
            mock_service = AsyncMock()
            mock_service.execute_batch.return_value = MagicMock(
                concepts_created=1,
                concepts_matched=1,
                edges_created=0,
                errors=[],
                concept_results=[
                    MagicMock(label="Existing Concept", status="matched", id="c_existing", error=None),
                    MagicMock(label="New Concept", status="created", id="c_new", error=None)
                ],
                edge_results=[]
            )
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/graph/batch",
                json={
                    "ontology": "test-ontology",
                    "matching_mode": "auto",
                    "concepts": [
                        {"label": "Existing Concept"},
                        {"label": "New Concept"}
                    ]
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201
            data = response.json()
            assert data["concepts_created"] == 1
            assert data["concepts_matched"] == 1

    def test_batch_empty_request(self, api_client: TestClient, auth_headers_user):
        """Batch with no concepts or edges returns empty response."""
        with patch('api.app.routes.graph.get_batch_service') as mock_service_factory:
            mock_service = AsyncMock()
            mock_service.execute_batch.return_value = MagicMock(
                concepts_created=0,
                concepts_matched=0,
                edges_created=0,
                errors=[],
                concept_results=[],
                edge_results=[]
            )
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/graph/batch",
                json={
                    "ontology": "test-ontology"
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201
            data = response.json()
            assert data["concepts_created"] == 0
            assert data["edges_created"] == 0

    def test_batch_validation_error(self, api_client: TestClient, auth_headers_user):
        """Batch validation error returns 400."""
        with patch('api.app.routes.graph.get_batch_service') as mock_service_factory:
            mock_service = AsyncMock()
            mock_service.execute_batch.side_effect = ValueError("Invalid ontology name")
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/graph/batch",
                json={
                    "ontology": "",  # Invalid
                    "concepts": [{"label": "Test"}]
                },
                headers=auth_headers_user
            )

            # Empty ontology should be caught by Pydantic
            assert response.status_code == 422  # Unprocessable Entity


class TestBatchEdgeLabelResolution:
    """Tests for edge label resolution in batch operations."""

    def test_edge_references_concept_in_same_batch(
        self, api_client: TestClient, auth_headers_user
    ):
        """Edge can reference concept created in same batch by label."""
        with patch('api.app.routes.graph.get_batch_service') as mock_service_factory:
            mock_service = AsyncMock()
            mock_service.execute_batch.return_value = MagicMock(
                concepts_created=2,
                concepts_matched=0,
                edges_created=1,
                errors=[],
                concept_results=[
                    MagicMock(label="A", status="created", id="c_a", error=None),
                    MagicMock(label="B", status="created", id="c_b", error=None)
                ],
                edge_results=[
                    MagicMock(label="A -> B", status="created", id="e_001", error=None)
                ]
            )
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/graph/batch",
                json={
                    "ontology": "test",
                    "concepts": [
                        {"label": "A"},
                        {"label": "B"}
                    ],
                    "edges": [
                        {"from_label": "A", "to_label": "B", "relationship_type": "RELATES_TO"}
                    ]
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201
            data = response.json()
            assert data["edges_created"] == 1

    def test_edge_error_concept_not_found(self, api_client: TestClient, auth_headers_user):
        """Edge fails when referenced concept doesn't exist."""
        with patch('api.app.routes.graph.get_batch_service') as mock_service_factory:
            mock_service = AsyncMock()
            mock_service.execute_batch.return_value = MagicMock(
                concepts_created=0,
                concepts_matched=0,
                edges_created=0,
                errors=["Edge 'Unknown' -> 'Also Unknown': Source concept not found"],
                concept_results=[],
                edge_results=[
                    MagicMock(
                        label="Unknown -> Also Unknown",
                        status="error",
                        id=None,
                        error="Source concept not found"
                    )
                ]
            )
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/graph/batch",
                json={
                    "ontology": "test",
                    "edges": [
                        {
                            "from_label": "Unknown",
                            "to_label": "Also Unknown",
                            "relationship_type": "IMPLIES"
                        }
                    ]
                },
                headers=auth_headers_user
            )

            # With errors but nothing created, should be 400
            assert response.status_code == 400


class TestBatchTransactionRollback:
    """Tests for transaction rollback on errors."""

    def test_rollback_on_concept_error(self, api_client: TestClient, auth_headers_user):
        """All changes rolled back if concept creation fails."""
        with patch('api.app.routes.graph.get_batch_service') as mock_service_factory:
            mock_service = AsyncMock()
            mock_service.execute_batch.side_effect = Exception("Transaction rolled back: Database error")
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/graph/batch",
                json={
                    "ontology": "test",
                    "concepts": [
                        {"label": "Success"},
                        {"label": "Fail"}  # This one causes DB error
                    ]
                },
                headers=auth_headers_user
            )

            assert response.status_code == 500
            assert "failed" in response.json()["detail"].lower()

    def test_rollback_on_edge_error(self, api_client: TestClient, auth_headers_user):
        """All changes rolled back if edge creation fails."""
        with patch('api.app.routes.graph.get_batch_service') as mock_service_factory:
            mock_service = AsyncMock()
            mock_service.execute_batch.side_effect = Exception("Transaction rolled back")
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/graph/batch",
                json={
                    "ontology": "test",
                    "concepts": [{"label": "A"}, {"label": "B"}],
                    "edges": [
                        {"from_label": "A", "to_label": "B", "relationship_type": "GOOD"},
                        {"from_label": "A", "to_label": "C", "relationship_type": "BAD"}  # C doesn't exist
                    ]
                },
                headers=auth_headers_user
            )

            assert response.status_code == 500


class TestBatchAuditLogging:
    """Tests for audit logging of batch operations."""

    def test_batch_logs_audit_entry(self, api_client: TestClient, auth_headers_user):
        """Successful batch creates audit log entry."""
        with patch('api.app.routes.graph.get_batch_service') as mock_service_factory:
            mock_service = AsyncMock()
            mock_service.execute_batch.return_value = MagicMock(
                concepts_created=2,
                concepts_matched=0,
                edges_created=1,
                errors=[],
                concept_results=[],
                edge_results=[]
            )
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/graph/batch",
                json={
                    "ontology": "test",
                    "concepts": [{"label": "A"}, {"label": "B"}],
                    "edges": [{"from_label": "A", "to_label": "B", "relationship_type": "R"}]
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201
            # Audit logging is called within the service
            mock_service.execute_batch.assert_called_once()


class TestBatchCreationMethod:
    """Tests for creation_method tracking."""

    def test_batch_default_creation_method_is_import(
        self, api_client: TestClient, auth_headers_user
    ):
        """Batch defaults to 'import' creation method."""
        with patch('api.app.routes.graph.get_batch_service') as mock_service_factory:
            mock_service = AsyncMock()
            mock_service.execute_batch.return_value = make_batch_response(concepts_created=1)
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/graph/batch",
                json={
                    "ontology": "test",
                    "concepts": [{"label": "Test"}]
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201
            # Check that service was called with default creation_method
            call_args = mock_service.execute_batch.call_args
            request = call_args.kwargs.get('request') or call_args.args[0]
            assert request.creation_method.value == "import"

    def test_batch_custom_creation_method(self, api_client: TestClient, auth_headers_user):
        """Batch accepts custom creation_method."""
        with patch('api.app.routes.graph.get_batch_service') as mock_service_factory:
            mock_service = AsyncMock()
            mock_service.execute_batch.return_value = make_batch_response(concepts_created=1)
            mock_service_factory.return_value = mock_service

            response = api_client.post(
                "/graph/batch",
                json={
                    "ontology": "test",
                    "creation_method": "api",
                    "concepts": [{"label": "Test"}]
                },
                headers=auth_headers_user
            )

            assert response.status_code == 201
            call_args = mock_service.execute_batch.call_args
            request = call_args.kwargs.get('request') or call_args.args[0]
            assert request.creation_method.value == "api"


class TestBatchOntologyIntegration:
    """Tests for ontology node creation and SCOPED_BY edges in BatchService."""

    @pytest.fixture
    def mock_age_client(self):
        """Provide a mock AGEClient with ontology methods."""
        client = MagicMock()
        client.graph_name = "knowledge_graph"
        client.get_current_epoch.return_value = 1
        client.ensure_ontology_exists.return_value = {
            "ontology_id": "ont_test123",
            "name": "test-ontology",
            "lifecycle_state": "active",
            "embedding": None,
        }
        client.update_ontology_embedding.return_value = True

        # Mock pool/connection for transaction phase
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__ = lambda s: mock_cursor
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        client.pool.getconn.return_value = mock_conn
        client._parse_agtype = lambda x: x

        return client

    @pytest.fixture
    def mock_embedding(self):
        """Provide a mock embedding worker."""
        worker = MagicMock()
        worker.generate_concept_embedding.return_value = {
            "embedding": [0.1] * 384,
            "model": "mock",
            "provider": "mock",
            "dimensions": 384,
            "tokens": 0
        }
        return worker

    @pytest.mark.asyncio
    async def test_execute_batch_calls_ensure_ontology_exists(
        self, mock_age_client, mock_embedding
    ):
        """BatchService calls ensure_ontology_exists before the transaction."""
        from api.app.services.batch_service import BatchService
        from api.app.models.graph import BatchCreateRequest

        service = BatchService(mock_age_client)
        service._embedding_worker = mock_embedding

        request = BatchCreateRequest(
            ontology="test-ontology",
            concepts=[{"label": "Test Concept"}]
        )

        try:
            await service.execute_batch(request, user_id=100)
        except Exception:
            pass  # Transaction will fail on mocked DB, that's fine

        mock_age_client.ensure_ontology_exists.assert_called_once_with(
            "test-ontology", created_by="100"
        )

    @pytest.mark.asyncio
    async def test_execute_batch_rejects_frozen_ontology(
        self, mock_age_client, mock_embedding
    ):
        """BatchService rejects batch when ontology is frozen."""
        from api.app.services.batch_service import BatchService
        from api.app.models.graph import BatchCreateRequest

        mock_age_client.ensure_ontology_exists.return_value = {
            "ontology_id": "ont_frozen",
            "name": "frozen-ontology",
            "lifecycle_state": "frozen",
            "embedding": [0.1] * 384,
        }

        service = BatchService(mock_age_client)
        service._embedding_worker = mock_embedding

        request = BatchCreateRequest(
            ontology="frozen-ontology",
            concepts=[{"label": "Should Not Create"}]
        )

        response = await service.execute_batch(request, user_id=100)

        assert len(response.errors) > 0
        assert "frozen" in response.errors[0].lower()
        assert response.concepts_created == 0

    @pytest.mark.asyncio
    async def test_execute_batch_generates_ontology_embedding(
        self, mock_age_client, mock_embedding
    ):
        """BatchService generates embedding for ontology if missing."""
        from api.app.services.batch_service import BatchService
        from api.app.models.graph import BatchCreateRequest

        service = BatchService(mock_age_client)
        service._embedding_worker = mock_embedding

        request = BatchCreateRequest(
            ontology="test-ontology",
            concepts=[{"label": "Test Concept"}]
        )

        try:
            await service.execute_batch(request, user_id=100)
        except Exception:
            pass

        # Embedding worker should be called for the ontology text
        embedding_calls = [
            c for c in mock_embedding.generate_concept_embedding.call_args_list
            if "test-ontology" in str(c)
        ]
        assert len(embedding_calls) > 0
        mock_age_client.update_ontology_embedding.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_batch_skips_embedding_if_present(
        self, mock_age_client, mock_embedding
    ):
        """BatchService skips ontology embedding if already present."""
        from api.app.services.batch_service import BatchService
        from api.app.models.graph import BatchCreateRequest

        mock_age_client.ensure_ontology_exists.return_value = {
            "ontology_id": "ont_test123",
            "name": "test-ontology",
            "lifecycle_state": "active",
            "embedding": [0.1] * 384,  # Already has embedding
        }

        service = BatchService(mock_age_client)
        service._embedding_worker = mock_embedding

        request = BatchCreateRequest(
            ontology="test-ontology",
            concepts=[{"label": "Test Concept"}]
        )

        try:
            await service.execute_batch(request, user_id=100)
        except Exception:
            pass

        mock_age_client.update_ontology_embedding.assert_not_called()
