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


# =========================================================================
# ADR-200 Phase 3a: Scoring & Breathing Control Surface Route Tests
# =========================================================================


class TestScoresRoute:
    """Tests for GET/POST /ontology/{name}/scores."""

    def test_get_cached_scores(self, api_client, auth_headers_user):
        """GET scores returns cached values from Ontology node."""
        client = mock_age_client(
            get_ontology_node={
                'name': 'scored-onto',
                'lifecycle_state': 'active',
                'mass_score': 0.75,
                'coherence_score': 0.6,
                'raw_exposure': 0.3,
                'weighted_exposure': 0.35,
                'protection_score': 0.42,
                'last_evaluated_epoch': 10,
            }
        )

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/scored-onto/scores",
                headers=auth_headers_user,
            )

        assert response.status_code == 200
        data = response.json()
        assert data['ontology'] == 'scored-onto'
        assert data['mass_score'] == 0.75
        assert data['protection_score'] == 0.42

    def test_get_scores_not_found(self, api_client, auth_headers_user):
        """GET scores for nonexistent ontology returns 404."""
        client = mock_age_client()

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/ghost/scores",
                headers=auth_headers_user,
            )

        assert response.status_code == 404

    def test_compute_scores(self, api_client, auth_headers_admin):
        """POST scores recomputes and returns new values."""
        client = mock_age_client()

        mock_scorer = MagicMock()
        mock_scorer.score_ontology.return_value = {
            'ontology': 'test-onto',
            'mass_score': 0.5,
            'coherence_score': 0.4,
            'raw_exposure': 0.1,
            'weighted_exposure': 0.15,
            'protection_score': 0.3,
            'last_evaluated_epoch': 5,
        }

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            with patch('api.app.lib.ontology_scorer.OntologyScorer', return_value=mock_scorer):
                response = api_client.post(
                    "/ontology/test-onto/scores",
                    headers=auth_headers_admin,
                )

        assert response.status_code == 200
        assert response.json()['mass_score'] == 0.5

    def test_compute_scores_not_found(self, api_client, auth_headers_admin):
        """POST scores for nonexistent ontology returns 404."""
        client = mock_age_client()

        mock_scorer = MagicMock()
        mock_scorer.score_ontology.return_value = None

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            with patch('api.app.lib.ontology_scorer.OntologyScorer', return_value=mock_scorer):
                response = api_client.post(
                    "/ontology/ghost/scores",
                    headers=auth_headers_admin,
                )

        assert response.status_code == 404


class TestScoreAllRoute:
    """Tests for POST /ontology/scores."""

    def test_compute_all_scores(self, api_client, auth_headers_admin):
        """POST /ontology/scores recomputes all ontologies."""
        client = mock_age_client()
        client.get_current_epoch = MagicMock(return_value=42)

        mock_scorer = MagicMock()
        mock_scorer.score_all_ontologies.return_value = [
            {'ontology': 'a', 'mass_score': 0.5, 'coherence_score': 0.4,
             'raw_exposure': 0.1, 'weighted_exposure': 0.15,
             'protection_score': 0.3, 'last_evaluated_epoch': 42},
        ]

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            with patch('api.app.lib.ontology_scorer.OntologyScorer', return_value=mock_scorer):
                response = api_client.post(
                    "/ontology/scores",
                    headers=auth_headers_admin,
                )

        assert response.status_code == 200
        data = response.json()
        assert data['count'] == 1
        assert data['global_epoch'] == 42


class TestCandidatesRoute:
    """Tests for GET /ontology/{name}/candidates."""

    def test_get_candidates(self, api_client, auth_headers_user):
        """GET candidates returns ranked concepts."""
        client = mock_age_client(
            get_ontology_node={
                'name': 'test-onto', 'lifecycle_state': 'active',
            }
        )
        client.get_concept_degree_ranking = MagicMock(return_value=[
            {'concept_id': 'c1', 'label': 'Top', 'degree': 10, 'in_degree': 6, 'out_degree': 4},
        ])

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/test-onto/candidates",
                headers=auth_headers_user,
            )

        assert response.status_code == 200
        data = response.json()
        assert data['count'] == 1
        assert data['concepts'][0]['label'] == 'Top'

    def test_candidates_not_found(self, api_client, auth_headers_user):
        """GET candidates for nonexistent ontology returns 404."""
        client = mock_age_client()

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/ghost/candidates",
                headers=auth_headers_user,
            )

        assert response.status_code == 404


class TestAffinityRoute:
    """Tests for GET /ontology/{name}/affinity."""

    def test_get_affinity(self, api_client, auth_headers_user):
        """GET affinity returns cross-ontology overlap."""
        client = mock_age_client(
            get_ontology_node={
                'name': 'test-onto', 'lifecycle_state': 'active',
            }
        )
        client.get_cross_ontology_affinity = MagicMock(return_value=[
            {'other_ontology': 'related', 'shared_concept_count': 5, 'total_concepts': 50, 'affinity_score': 0.1},
        ])

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/test-onto/affinity",
                headers=auth_headers_user,
            )

        assert response.status_code == 200
        data = response.json()
        assert data['count'] == 1
        assert data['affinities'][0]['affinity_score'] == 0.1


class TestReassignRoute:
    """Tests for POST /ontology/{name}/reassign."""

    def test_reassign_success(self, api_client, auth_headers_admin):
        """POST reassign moves sources."""
        client = mock_age_client()
        client.reassign_sources = MagicMock(return_value={
            'sources_reassigned': 3,
            'success': True,
            'error': None,
        })

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/from-onto/reassign",
                json={"target_ontology": "to-onto", "source_ids": ["s1", "s2", "s3"]},
                headers=auth_headers_admin,
            )

        assert response.status_code == 200
        assert response.json()['sources_reassigned'] == 3

    def test_reassign_frozen_rejected(self, api_client, auth_headers_admin):
        """POST reassign from frozen ontology returns 403."""
        client = mock_age_client()
        client.reassign_sources = MagicMock(return_value={
            'sources_reassigned': 0,
            'success': False,
            'error': "Source ontology 'frozen-onto' is frozen",
        })

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/frozen-onto/reassign",
                json={"target_ontology": "to-onto", "source_ids": ["s1"]},
                headers=auth_headers_admin,
            )

        assert response.status_code == 403

    def test_reassign_not_found(self, api_client, auth_headers_admin):
        """POST reassign with nonexistent ontology returns 404."""
        client = mock_age_client()
        client.reassign_sources = MagicMock(return_value={
            'sources_reassigned': 0,
            'success': False,
            'error': "Source ontology 'ghost' not found",
        })

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/ghost/reassign",
                json={"target_ontology": "to-onto", "source_ids": ["s1"]},
                headers=auth_headers_admin,
            )

        assert response.status_code == 404


class TestDissolveRoute:
    """Tests for POST /ontology/{name}/dissolve."""

    def test_dissolve_success(self, api_client, auth_headers_admin):
        """POST dissolve moves sources and removes node."""
        client = mock_age_client()
        client.dissolve_ontology = MagicMock(return_value={
            'dissolved_ontology': 'old-onto',
            'sources_reassigned': 5,
            'ontology_node_deleted': True,
            'reassignment_targets': ['target-onto'],
            'success': True,
            'error': None,
        })

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/old-onto/dissolve",
                json={"target_ontology": "target-onto"},
                headers=auth_headers_admin,
            )

        assert response.status_code == 200
        data = response.json()
        assert data['sources_reassigned'] == 5
        assert data['ontology_node_deleted'] is True

    def test_dissolve_pinned_rejected(self, api_client, auth_headers_admin):
        """POST dissolve pinned ontology returns 403."""
        client = mock_age_client()
        client.dissolve_ontology = MagicMock(return_value={
            'dissolved_ontology': 'pinned-onto',
            'sources_reassigned': 0,
            'ontology_node_deleted': False,
            'reassignment_targets': [],
            'success': False,
            'error': "Ontology 'pinned-onto' is pinned — cannot dissolve",
        })

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/pinned-onto/dissolve",
                json={"target_ontology": "target"},
                headers=auth_headers_admin,
            )

        assert response.status_code == 403

    def test_dissolve_not_found(self, api_client, auth_headers_admin):
        """POST dissolve nonexistent ontology returns 404."""
        client = mock_age_client()
        client.dissolve_ontology = MagicMock(return_value={
            'dissolved_ontology': 'ghost',
            'sources_reassigned': 0,
            'ontology_node_deleted': False,
            'reassignment_targets': [],
            'success': False,
            'error': "Ontology 'ghost' not found",
        })

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/ghost/dissolve",
                json={"target_ontology": "target"},
                headers=auth_headers_admin,
            )

        assert response.status_code == 404


# ==========================================================================
# GET /ontology/proposals — List breathing proposals (ADR-200 Phase 3b)
# ==========================================================================

def mock_proposals_cursor(proposals):
    """Create a mock cursor that returns proposal rows."""
    client = mock_age_client()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = proposals
    mock_cursor.fetchone.return_value = proposals[0] if proposals else None
    mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    client.pool = MagicMock()
    client.pool.getconn.return_value = mock_conn
    return client


SAMPLE_PROPOSAL_ROW = (
    1,                                      # id
    "demotion",                             # proposal_type
    "test-ontology",                        # ontology_name
    None,                                   # anchor_concept_id
    "parent-ontology",                      # target_ontology
    "Low mass, should be absorbed",         # reasoning
    0.05,                                   # mass_score (Decimal)
    0.30,                                   # coherence_score
    -0.10,                                  # protection_score
    "pending",                              # status
    "2026-01-30T18:00:00+00:00",           # created_at
    13,                                     # created_at_epoch
    None,                                   # reviewed_at
    None,                                   # reviewed_by
    None,                                   # reviewer_notes
)

SAMPLE_PROMOTION_ROW = (
    2,                                      # id
    "promotion",                            # proposal_type
    "big-domain",                           # ontology_name
    "c_abc123",                             # anchor_concept_id
    None,                                   # target_ontology
    "PostgreSQL is a natural nucleus",      # reasoning
    None,                                   # mass_score
    None,                                   # coherence_score
    None,                                   # protection_score
    "pending",                              # status
    "2026-01-30T18:01:00+00:00",           # created_at
    13,                                     # created_at_epoch
    None,                                   # reviewed_at
    None,                                   # reviewed_by
    None,                                   # reviewer_notes
)


@pytest.mark.unit
class TestListProposalsRoute:
    """Tests for GET /ontology/proposals endpoint."""

    def test_list_empty(self, api_client, auth_headers_user):
        """Empty proposal list returns count=0."""
        client = mock_proposals_cursor([])
        client.pool.getconn.return_value.cursor.return_value.__enter__.return_value.fetchall.return_value = []

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get("/ontology/proposals", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["proposals"] == []

    def test_list_with_proposals(self, api_client, auth_headers_user):
        """List returns proposal data."""
        client = mock_proposals_cursor([SAMPLE_PROPOSAL_ROW, SAMPLE_PROMOTION_ROW])

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get("/ontology/proposals", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert data["proposals"][0]["proposal_type"] == "demotion"
        assert data["proposals"][1]["proposal_type"] == "promotion"

    def test_list_filter_by_status(self, api_client, auth_headers_user):
        """Status filter is passed to query."""
        client = mock_proposals_cursor([])
        client.pool.getconn.return_value.cursor.return_value.__enter__.return_value.fetchall.return_value = []

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/proposals?status=pending",
                headers=auth_headers_user,
            )

        assert response.status_code == 200


@pytest.mark.unit
class TestGetProposalRoute:
    """Tests for GET /ontology/proposals/{id} endpoint."""

    def test_get_existing_proposal(self, api_client, auth_headers_user):
        """Get proposal by ID returns full details."""
        client = mock_proposals_cursor([SAMPLE_PROPOSAL_ROW])

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get("/ontology/proposals/1", headers=auth_headers_user)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1
        assert data["proposal_type"] == "demotion"
        assert data["ontology_name"] == "test-ontology"
        assert data["target_ontology"] == "parent-ontology"
        assert data["status"] == "pending"

    def test_get_nonexistent_proposal(self, api_client, auth_headers_user):
        """Get nonexistent proposal returns 404."""
        client = mock_age_client()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        client.pool = MagicMock()
        client.pool.getconn.return_value = mock_conn

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get("/ontology/proposals/999", headers=auth_headers_user)

        assert response.status_code == 404


@pytest.mark.unit
class TestReviewProposalRoute:
    """Tests for POST /ontology/proposals/{id}/review endpoint."""

    def test_approve_proposal(self, api_client, auth_headers_admin):
        """Approving a pending proposal returns updated proposal."""
        # First fetchone returns pending status, second returns updated row
        reviewed_row = list(SAMPLE_PROPOSAL_ROW)
        reviewed_row[9] = "approved"  # status
        reviewed_row[12] = "2026-01-30T19:00:00+00:00"  # reviewed_at
        reviewed_row[13] = "admin"  # reviewed_by
        reviewed_row[14] = "Looks good"  # reviewer_notes

        client = mock_age_client()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        # First call: check status; second call: update and return
        mock_cursor.fetchone.side_effect = [("pending",), tuple(reviewed_row)]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        client.pool = MagicMock()
        client.pool.getconn.return_value = mock_conn

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/proposals/1/review",
                json={"status": "approved", "notes": "Looks good"},
                headers=auth_headers_admin,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"

    def test_reject_proposal(self, api_client, auth_headers_admin):
        """Rejecting a pending proposal returns updated proposal."""
        reviewed_row = list(SAMPLE_PROPOSAL_ROW)
        reviewed_row[9] = "rejected"

        client = mock_age_client()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.side_effect = [("pending",), tuple(reviewed_row)]
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        client.pool = MagicMock()
        client.pool.getconn.return_value = mock_conn

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/proposals/1/review",
                json={"status": "rejected"},
                headers=auth_headers_admin,
            )

        assert response.status_code == 200

    def test_review_already_reviewed_returns_409(self, api_client, auth_headers_admin):
        """Reviewing an already-reviewed proposal returns 409 Conflict."""
        client = mock_age_client()
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = ("approved",)  # Already approved
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        client.pool = MagicMock()
        client.pool.getconn.return_value = mock_conn

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/proposals/1/review",
                json={"status": "rejected"},
                headers=auth_headers_admin,
            )

        assert response.status_code == 409

    def test_review_invalid_status_returns_422(self, api_client, auth_headers_admin):
        """Invalid review status returns 422."""
        with patch('api.app.routes.ontology.get_age_client', return_value=mock_age_client()):
            response = api_client.post(
                "/ontology/proposals/1/review",
                json={"status": "invalid_status"},
                headers=auth_headers_admin,
            )

        assert response.status_code == 422


# ==========================================================================
# GET /ontology/{name}/edges — Ontology-to-Ontology Edges (ADR-200 Phase 5)
# ==========================================================================


@pytest.mark.unit
class TestGetOntologyEdgesRoute:
    """Tests for GET /ontology/{name}/edges endpoint."""

    def test_get_edges_returns_list(self, api_client, auth_headers_user):
        """GET edges returns list of edges for an ontology."""
        client = mock_age_client(
            get_ontology_node={"name": "my-domain", "ontology_id": "ont_1"},
            get_ontology_edges=[
                {
                    "from_ontology": "my-domain",
                    "to_ontology": "other-domain",
                    "edge_type": "OVERLAPS",
                    "score": 0.5,
                    "shared_concept_count": 10,
                    "computed_at_epoch": 5,
                    "source": "breathing_worker",
                    "direction": "outgoing",
                },
            ],
        )

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/my-domain/edges",
                headers=auth_headers_user,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["ontology"] == "my-domain"
        assert data["count"] == 1
        assert data["edges"][0]["edge_type"] == "OVERLAPS"
        assert data["edges"][0]["score"] == 0.5

    def test_get_edges_empty(self, api_client, auth_headers_user):
        """GET edges for ontology with no edges returns empty list."""
        client = mock_age_client(
            get_ontology_node={"name": "lonely", "ontology_id": "ont_2"},
            get_ontology_edges=[],
        )

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/lonely/edges",
                headers=auth_headers_user,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["edges"] == []

    def test_get_edges_not_found(self, api_client, auth_headers_user):
        """GET edges for nonexistent ontology returns 404."""
        client = mock_age_client()  # Default: get_ontology_node returns None

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.get(
                "/ontology/ghost/edges",
                headers=auth_headers_user,
            )

        assert response.status_code == 404


@pytest.mark.unit
class TestCreateOntologyEdgeRoute:
    """Tests for POST /ontology/{name}/edges endpoint."""

    def test_create_manual_edge(self, api_client, auth_headers_admin):
        """Creating a manual edge returns the edge details."""
        client = mock_age_client(
            get_ontology_node={"name": "from-domain", "ontology_id": "ont_1"},
            get_current_epoch=10,
        )
        client.upsert_ontology_edge = MagicMock(return_value=True)

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/from-domain/edges",
                json={
                    "to_ontology": "to-domain",
                    "edge_type": "SPECIALIZES",
                    "score": 0.75,
                    "shared_concept_count": 15,
                },
                headers=auth_headers_admin,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["from_ontology"] == "from-domain"
        assert data["to_ontology"] == "to-domain"
        assert data["edge_type"] == "SPECIALIZES"
        assert data["source"] == "manual"

    def test_create_edge_target_not_found(self, api_client, auth_headers_admin):
        """Creating edge to nonexistent target returns 404."""
        client = mock_age_client()
        # from exists, to doesn't
        client.get_ontology_node = MagicMock(
            side_effect=lambda name: (
                {"name": "from-domain", "ontology_id": "ont_1"}
                if name == "from-domain" else None
            )
        )

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/from-domain/edges",
                json={
                    "to_ontology": "ghost",
                    "edge_type": "OVERLAPS",
                },
                headers=auth_headers_admin,
            )

        assert response.status_code == 404
        assert "ghost" in response.json()["detail"]

    def test_create_self_edge_returns_400(self, api_client, auth_headers_admin):
        """Creating an edge from an ontology to itself returns 400."""
        client = mock_age_client(
            get_ontology_node={"name": "self-ref", "ontology_id": "ont_1"},
        )

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/self-ref/edges",
                json={
                    "to_ontology": "self-ref",
                    "edge_type": "OVERLAPS",
                },
                headers=auth_headers_admin,
            )

        assert response.status_code == 400

    def test_create_invalid_edge_type_returns_422(self, api_client, auth_headers_admin):
        """Invalid edge type returns 422 (Pydantic validation)."""
        client = mock_age_client(
            get_ontology_node={"name": "a", "ontology_id": "ont_1"},
        )

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.post(
                "/ontology/a/edges",
                json={
                    "to_ontology": "b",
                    "edge_type": "INVALID",
                },
                headers=auth_headers_admin,
            )

        assert response.status_code == 422


@pytest.mark.unit
class TestDeleteOntologyEdgeRoute:
    """Tests for DELETE /ontology/{name}/edges/{type}/{to} endpoint."""

    def test_delete_edge(self, api_client, auth_headers_admin):
        """Deleting an existing edge returns success."""
        client = mock_age_client()
        client._execute_cypher = MagicMock(return_value={"deleted": 1})

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.delete(
                "/ontology/from-domain/edges/OVERLAPS/to-domain",
                headers=auth_headers_admin,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["deleted"] == 1

    def test_delete_nonexistent_edge_returns_404(self, api_client, auth_headers_admin):
        """Deleting a nonexistent edge returns 404."""
        client = mock_age_client()
        client._execute_cypher = MagicMock(return_value={"deleted": 0})

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.delete(
                "/ontology/a/edges/OVERLAPS/b",
                headers=auth_headers_admin,
            )

        assert response.status_code == 404

    def test_delete_invalid_edge_type_returns_400(self, api_client, auth_headers_admin):
        """Invalid edge type returns 400."""
        client = mock_age_client()

        with patch('api.app.routes.ontology.get_age_client', return_value=client):
            response = api_client.delete(
                "/ontology/a/edges/INVALID_TYPE/b",
                headers=auth_headers_admin,
            )

        assert response.status_code == 400
