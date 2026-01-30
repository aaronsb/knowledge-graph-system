"""
Ontology route tests for ADR-200 client exposure.

Tests the new and modified ontology endpoints:
- POST /ontology/ — create ontology (directed growth)
- GET /ontology/{name}/node — graph node properties
- GET /ontology/ — list with graph node properties
- GET /ontology/{name} — info with graph node properties

Mocks AGEClient since these are unit-level route tests.
"""

import pytest
from unittest.mock import patch, MagicMock


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


def mock_age_client(**method_overrides):
    """Create a mock AGEClient with configurable method return values."""
    client = MagicMock()
    client.close = MagicMock()

    # Defaults: empty graph
    client.get_ontology_node = MagicMock(return_value=None)
    client.list_ontology_nodes = MagicMock(return_value=[])
    client.create_ontology_node = MagicMock(return_value={})
    client.update_ontology_embedding = MagicMock(return_value=True)
    client._execute_cypher = MagicMock(return_value=None)

    # Connection pool mock for create endpoint's epoch lookup
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (42,)
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    client.pool = MagicMock()
    client.pool.getconn.return_value = mock_conn

    for method, return_value in method_overrides.items():
        getattr(client, method).return_value = return_value

    return client


# ==========================================================================
# POST /ontology/ — Create ontology
# ==========================================================================

@pytest.mark.unit
class TestCreateOntologyRoute:
    """Tests for POST /ontology/ endpoint."""

    def test_create_returns_201(self, api_client, auth_headers_admin):
        """Creating an ontology returns 201 with node properties."""
        client = mock_age_client(
            create_ontology_node={
                'ontology_id': 'ont_new',
                'name': 'Test Domain',
                'lifecycle_state': 'active',
                'creation_epoch': 42,
            }
        )

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            with patch('api.app.lib.ai_providers.get_provider', return_value=None):
                response = api_client.post(
                    "/ontology/",
                    json={"name": "Test Domain", "description": "A test"},
                    headers=auth_headers_admin,
                )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Domain"
        assert data["description"] == "A test"
        assert data["lifecycle_state"] == "active"

    def test_create_duplicate_returns_409(self, api_client, auth_headers_admin):
        """Creating an ontology that already exists returns 409."""
        client = mock_age_client(
            get_ontology_node={
                'ontology_id': 'ont_existing',
                'name': 'Already Here',
            }
        )

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/",
                json={"name": "Already Here"},
                headers=auth_headers_admin,
            )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_create_requires_auth(self, api_client):
        """Creating an ontology requires authentication."""
        response = api_client.post(
            "/ontology/",
            json={"name": "No Auth"},
        )
        assert response.status_code == 401

    def test_create_requires_name(self, api_client, auth_headers_admin):
        """Creating an ontology requires a name."""
        with patch('api.app.routes.ontology.get_age_client', return_value=mock_age_client()):
            response = api_client.post(
                "/ontology/",
                json={},
                headers=auth_headers_admin,
            )
        assert response.status_code == 422


# ==========================================================================
# GET /ontology/{name}/node — Graph node properties
# ==========================================================================

@pytest.mark.unit
class TestGetOntologyNodeRoute:
    """Tests for GET /ontology/{name}/node endpoint."""

    def test_get_node_returns_properties(self, api_client, auth_headers_user):
        """Getting an ontology node returns its graph properties."""
        client = mock_age_client(
            get_ontology_node={
                'ontology_id': 'ont_abc',
                'name': 'my-domain',
                'description': 'Test',
                'lifecycle_state': 'active',
                'creation_epoch': 5,
                'embedding': [0.1] * 10,
                'search_terms': ['alt'],
            }
        )

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/my-domain/node",
                headers=auth_headers_user,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["ontology_id"] == "ont_abc"
        assert data["lifecycle_state"] == "active"
        assert data["has_embedding"] is True
        assert data["search_terms"] == ["alt"]

    def test_get_node_not_found(self, api_client, auth_headers_user):
        """Getting a nonexistent ontology node returns 404."""
        client = mock_age_client()

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/ghost/node",
                headers=auth_headers_user,
            )

        assert response.status_code == 404

    def test_has_embedding_false_when_none(self, api_client, auth_headers_user):
        """has_embedding is False when embedding is None."""
        client = mock_age_client(
            get_ontology_node={
                'ontology_id': 'ont_no_emb',
                'name': 'no-embedding',
                'lifecycle_state': 'active',
                'creation_epoch': 0,
                'embedding': None,
                'search_terms': [],
            }
        )

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/no-embedding/node",
                headers=auth_headers_user,
            )

        assert response.status_code == 200
        assert response.json()["has_embedding"] is False


# ==========================================================================
# GET /ontology/ — List with graph node properties
# ==========================================================================

@pytest.mark.unit
class TestListOntologiesRoute:
    """Tests for GET /ontology/ with ADR-200 enrichment."""

    def test_list_includes_graph_node_fields(self, api_client, auth_headers_user):
        """List response includes graph node properties."""
        client = mock_age_client(
            list_ontology_nodes=[
                {
                    'name': 'domain-a',
                    'ontology_id': 'ont_a',
                    'lifecycle_state': 'active',
                    'creation_epoch': 0,
                    'embedding': [0.1],
                },
            ]
        )
        # Source stats query
        client._execute_cypher = MagicMock(return_value=[
            {
                'ontology': 'domain-a',
                'source_count': 5,
                'file_count': 2,
                'concept_count': 10,
            }
        ])

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get("/ontology/", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        item = data["ontologies"][0]
        assert item["ontology_id"] == "ont_a"
        assert item["lifecycle_state"] == "active"
        assert item["has_embedding"] is True
        assert item["source_count"] == 5

    def test_list_includes_empty_ontologies(self, api_client, auth_headers_user):
        """Empty ontologies (directed growth) appear in list with zero counts."""
        client = mock_age_client(
            list_ontology_nodes=[
                {
                    'name': 'empty-domain',
                    'ontology_id': 'ont_empty',
                    'lifecycle_state': 'active',
                    'creation_epoch': 0,
                    'embedding': None,
                },
            ]
        )
        # No sources exist
        client._execute_cypher = MagicMock(return_value=[])

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get("/ontology/", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        item = data["ontologies"][0]
        assert item["ontology"] == "empty-domain"
        assert item["source_count"] == 0
        assert item["concept_count"] == 0
        assert item["has_embedding"] is False

    def test_list_empty_graph(self, api_client, auth_headers_user):
        """Empty graph returns count 0."""
        client = mock_age_client()
        client._execute_cypher = MagicMock(return_value=[])

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get("/ontology/", headers=auth_headers_user)

        assert response.status_code == 200
        assert response.json()["count"] == 0


# ==========================================================================
# GET /ontology/{name} — Info with graph node
# ==========================================================================

@pytest.mark.unit
class TestGetOntologyInfoRoute:
    """Tests for GET /ontology/{name} with ADR-200 node enrichment."""

    def test_info_includes_node(self, api_client, auth_headers_user):
        """Info response includes node object when graph node exists."""
        client = mock_age_client(
            get_ontology_node={
                'ontology_id': 'ont_info',
                'name': 'test-info',
                'description': 'Desc',
                'lifecycle_state': 'active',
                'creation_epoch': 3,
                'embedding': [0.5],
                'search_terms': [],
            }
        )
        # Existence check returns True, stats query returns data
        client._execute_cypher = MagicMock(side_effect=[
            {'ontology_exists': True},  # existence check
            {  # stats query
                'source_count': 2,
                'file_count': 1,
                'concept_count': 4,
                'instance_count': 3,
                'relationship_count': 1,
                'files': ['doc.txt'],
            },
        ])

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/test-info",
                headers=auth_headers_user,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["node"] is not None
        assert data["node"]["ontology_id"] == "ont_info"
        assert data["node"]["has_embedding"] is True
        assert data["statistics"]["concept_count"] == 4

    def test_info_empty_ontology_returns_200(self, api_client, auth_headers_user):
        """Empty ontology (directed growth) returns 200 with zero stats."""
        client = mock_age_client(
            get_ontology_node={
                'ontology_id': 'ont_empty',
                'name': 'empty-one',
                'description': '',
                'lifecycle_state': 'active',
                'creation_epoch': 0,
                'embedding': None,
                'search_terms': [],
            }
        )
        # No sources exist
        client._execute_cypher = MagicMock(return_value={'ontology_exists': False})

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/empty-one",
                headers=auth_headers_user,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["statistics"]["source_count"] == 0
        assert data["node"]["ontology_id"] == "ont_empty"

    def test_info_nonexistent_returns_404(self, api_client, auth_headers_user):
        """Nonexistent ontology (no sources, no graph node) returns 404."""
        client = mock_age_client()
        client._execute_cypher = MagicMock(return_value={'ontology_exists': False})

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/ghost",
                headers=auth_headers_user,
            )

        assert response.status_code == 404


# ==========================================================================
# PUT /ontology/{name}/lifecycle — Lifecycle state changes (ADR-200 Phase 2)
# ==========================================================================

@pytest.mark.unit
class TestUpdateOntologyLifecycleRoute:
    """Tests for PUT /ontology/{name}/lifecycle endpoint."""

    def test_freeze_returns_200(self, api_client, auth_headers_admin):
        """Freezing an ontology returns 200 with state transition."""
        client = mock_age_client(
            get_ontology_node={
                'ontology_id': 'ont_lc',
                'name': 'my-domain',
                'lifecycle_state': 'active',
            },
            update_ontology_lifecycle={
                'ontology_id': 'ont_lc',
                'name': 'my-domain',
                'lifecycle_state': 'frozen',
            }
        )

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.put(
                "/ontology/my-domain/lifecycle",
                json={"state": "frozen"},
                headers=auth_headers_admin,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["previous_state"] == "active"
        assert data["new_state"] == "frozen"
        assert data["success"] is True

    def test_not_found_returns_404(self, api_client, auth_headers_admin):
        """Lifecycle change on nonexistent ontology returns 404."""
        client = mock_age_client()

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.put(
                "/ontology/ghost/lifecycle",
                json={"state": "frozen"},
                headers=auth_headers_admin,
            )

        assert response.status_code == 404

    def test_invalid_state_returns_422(self, api_client, auth_headers_admin):
        """Invalid lifecycle state returns 422 validation error."""
        client = mock_age_client(
            get_ontology_node={'ontology_id': 'ont_x', 'lifecycle_state': 'active'}
        )

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.put(
                "/ontology/test/lifecycle",
                json={"state": "invalid"},
                headers=auth_headers_admin,
            )

        assert response.status_code == 422

    def test_noop_same_state(self, api_client, auth_headers_admin):
        """Setting the same state is a no-op (idempotent)."""
        client = mock_age_client(
            get_ontology_node={
                'ontology_id': 'ont_same',
                'name': 'already-frozen',
                'lifecycle_state': 'frozen',
            }
        )

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.put(
                "/ontology/already-frozen/lifecycle",
                json={"state": "frozen"},
                headers=auth_headers_admin,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["previous_state"] == "frozen"
        assert data["new_state"] == "frozen"
        # update_ontology_lifecycle should not have been called
        client.update_ontology_lifecycle.assert_not_called()

    def test_requires_auth(self, api_client):
        """Lifecycle change requires authentication."""
        response = api_client.put(
            "/ontology/test/lifecycle",
            json={"state": "frozen"},
        )
        assert response.status_code == 401


# ==========================================================================
# Frozen enforcement (ADR-200 Phase 2)
# ==========================================================================

@pytest.mark.unit
class TestFrozenEnforcement:
    """Tests for frozen ontology enforcement."""

    def test_frozen_rename_rejected(self, api_client, auth_headers_admin):
        """Renaming a frozen ontology returns 403."""
        client = mock_age_client()
        client.is_ontology_frozen = MagicMock(return_value=True)

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/frozen-domain/rename",
                json={"new_name": "new-name"},
                headers=auth_headers_admin,
            )

        assert response.status_code == 403
        assert "frozen" in response.json()["detail"].lower()

    def test_active_rename_allowed(self, api_client, auth_headers_admin):
        """Renaming an active ontology is allowed."""
        client = mock_age_client()
        client.is_ontology_frozen = MagicMock(return_value=False)
        client.rename_ontology = MagicMock(return_value={"sources_updated": 3})
        client.rename_ontology_node = MagicMock(return_value=True)

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/active-domain/rename",
                json={"new_name": "new-name"},
                headers=auth_headers_admin,
            )

        assert response.status_code == 200

    def test_frozen_ingest_text_rejected(self, api_client, auth_headers_admin):
        """Ingesting text into a frozen ontology returns 403."""
        client = MagicMock()
        client.is_ontology_frozen = MagicMock(return_value=True)
        client.close = MagicMock()

        with patch('api.app.lib.age_client.AGEClient', return_value=client):
            with patch('api.app.routes.ingest.get_job_queue', return_value=MagicMock()):
                response = api_client.post(
                    "/ingest/text",
                    data={"text": "test content", "ontology": "frozen-domain"},
                    headers=auth_headers_admin,
                )

        assert response.status_code == 403
        assert "frozen" in response.json()["detail"].lower()
        client.close.assert_called_once()

    def test_frozen_ingest_file_rejected(self, api_client, auth_headers_admin):
        """Uploading a file to a frozen ontology returns 403."""
        client = MagicMock()
        client.is_ontology_frozen = MagicMock(return_value=True)
        client.close = MagicMock()

        with patch('api.app.lib.age_client.AGEClient', return_value=client):
            with patch('api.app.routes.ingest.get_job_queue', return_value=MagicMock()):
                response = api_client.post(
                    "/ingest",
                    data={"ontology": "frozen-domain"},
                    files={"file": ("test.txt", b"test content", "text/plain")},
                    headers=auth_headers_admin,
                )

        assert response.status_code == 403
        assert "frozen" in response.json()["detail"].lower()
        client.close.assert_called_once()

    def test_created_by_in_node_response(self, api_client, auth_headers_user):
        """Node response includes created_by field."""
        client = mock_age_client(
            get_ontology_node={
                'ontology_id': 'ont_prov',
                'name': 'provenance-test',
                'lifecycle_state': 'active',
                'creation_epoch': 0,
                'embedding': None,
                'search_terms': [],
                'created_by': 'admin',
            }
        )

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/provenance-test/node",
                headers=auth_headers_user,
            )

        assert response.status_code == 200
        assert response.json()["created_by"] == "admin"
