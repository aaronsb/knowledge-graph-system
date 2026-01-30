"""
Unit tests for AGE client Ontology methods (ADR-200).

Tests the new Ontology node CRUD methods added in Phase 1:
- create_ontology_node
- get_ontology_node
- list_ontology_nodes
- delete_ontology_node
- rename_ontology_node
- create_scoped_by_edge
- ensure_ontology_exists
- update_ontology_embedding

All tests mock _execute_cypher since the real method needs PostgreSQL.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock


@pytest.fixture
def mock_age_client():
    """Create an AGEClient with mocked database connection."""
    with patch('api.app.lib.age_client.psycopg2') as mock_psycopg2:
        # Mock the connection pool
        mock_pool = MagicMock()
        mock_conn = MagicMock()
        mock_pool.getconn.return_value = mock_conn
        mock_psycopg2.pool.ThreadedConnectionPool.return_value = mock_pool

        from api.app.lib.age_client import AGEClient
        client = AGEClient(
            host="localhost",
            port=5432,
            database="test_db",
            user="test",
            password="test"
        )
        yield client


@pytest.mark.unit
class TestCreateOntologyNode:
    """Tests for create_ontology_node()."""

    def test_create_returns_properties(self, mock_age_client):
        """Creating an ontology node returns its properties."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            'o': {
                'properties': {
                    'ontology_id': 'ont_abc123',
                    'name': 'test-ontology',
                    'lifecycle_state': 'active',
                    'creation_epoch': 0
                }
            }
        })

        result = mock_age_client.create_ontology_node(
            ontology_id='ont_abc123',
            name='test-ontology'
        )

        assert result['ontology_id'] == 'ont_abc123'
        assert result['name'] == 'test-ontology'
        assert result['lifecycle_state'] == 'active'

    def test_create_passes_all_params(self, mock_age_client):
        """All parameters are passed to the Cypher query."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            'o': {'properties': {}}
        })

        mock_age_client.create_ontology_node(
            ontology_id='ont_xyz',
            name='my-ontology',
            description='Test description',
            embedding=[0.1, 0.2, 0.3],
            search_terms=['alt1', 'alt2'],
            lifecycle_state='pinned',
            creation_epoch=42
        )

        call_args = mock_age_client._execute_cypher.call_args
        params = call_args.kwargs.get('params') or call_args[1].get('params')
        assert params['name'] == 'my-ontology'
        assert params['description'] == 'Test description'
        assert params['embedding'] == [0.1, 0.2, 0.3]
        assert params['search_terms'] == ['alt1', 'alt2']
        assert params['lifecycle_state'] == 'pinned'
        assert params['creation_epoch'] == 42

    def test_create_defaults(self, mock_age_client):
        """Default values are applied for optional parameters."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            'o': {'properties': {}}
        })

        mock_age_client.create_ontology_node(
            ontology_id='ont_def',
            name='defaults-test'
        )

        call_args = mock_age_client._execute_cypher.call_args
        params = call_args.kwargs.get('params') or call_args[1].get('params')
        assert params['description'] == ''
        assert params['embedding'] is None
        assert params['search_terms'] == []
        assert params['lifecycle_state'] == 'active'
        assert params['creation_epoch'] == 0

    def test_create_failure_raises(self, mock_age_client):
        """Database error raises exception with ontology name."""
        mock_age_client._execute_cypher = MagicMock(
            side_effect=Exception("unique constraint violation")
        )

        with pytest.raises(Exception, match="Failed to create Ontology node"):
            mock_age_client.create_ontology_node(
                ontology_id='ont_dup',
                name='duplicate'
            )


@pytest.mark.unit
class TestGetOntologyNode:
    """Tests for get_ontology_node()."""

    def test_get_existing_returns_properties(self, mock_age_client):
        """Getting an existing ontology returns its properties."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            'o': {
                'properties': {
                    'ontology_id': 'ont_found',
                    'name': 'found-ontology',
                    'lifecycle_state': 'active'
                }
            }
        })

        result = mock_age_client.get_ontology_node('found-ontology')

        assert result is not None
        assert result['name'] == 'found-ontology'

    def test_get_nonexistent_returns_none(self, mock_age_client):
        """Getting a nonexistent ontology returns None."""
        mock_age_client._execute_cypher = MagicMock(return_value=None)

        result = mock_age_client.get_ontology_node('no-such-ontology')

        assert result is None

    def test_get_passes_name_param(self, mock_age_client):
        """Name parameter is passed to query."""
        mock_age_client._execute_cypher = MagicMock(return_value=None)

        mock_age_client.get_ontology_node('specific-name')

        call_args = mock_age_client._execute_cypher.call_args
        params = call_args.kwargs.get('params') or call_args[1].get('params')
        assert params['name'] == 'specific-name'


@pytest.mark.unit
class TestListOntologyNodes:
    """Tests for list_ontology_nodes()."""

    def test_list_returns_all_ontologies(self, mock_age_client):
        """Listing returns all ontology node properties."""
        mock_age_client._execute_cypher = MagicMock(return_value=[
            {'o': {'properties': {'name': 'ontology-a', 'lifecycle_state': 'active'}}},
            {'o': {'properties': {'name': 'ontology-b', 'lifecycle_state': 'pinned'}}}
        ])

        result = mock_age_client.list_ontology_nodes()

        assert len(result) == 2
        assert result[0]['name'] == 'ontology-a'
        assert result[1]['name'] == 'ontology-b'

    def test_list_empty_graph(self, mock_age_client):
        """Listing on empty graph returns empty list."""
        mock_age_client._execute_cypher = MagicMock(return_value=[])

        result = mock_age_client.list_ontology_nodes()

        assert result == []

    def test_list_error_returns_empty(self, mock_age_client):
        """Database error returns empty list (graceful degradation)."""
        mock_age_client._execute_cypher = MagicMock(
            side_effect=Exception("connection lost")
        )

        result = mock_age_client.list_ontology_nodes()

        assert result == []


@pytest.mark.unit
class TestDeleteOntologyNode:
    """Tests for delete_ontology_node()."""

    def test_delete_existing_returns_true(self, mock_age_client):
        """Deleting an existing ontology returns True."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            'deleted': 1
        })

        result = mock_age_client.delete_ontology_node('to-delete')

        assert result is True

    def test_delete_nonexistent_returns_false(self, mock_age_client):
        """Deleting a nonexistent ontology returns False."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            'deleted': 0
        })

        result = mock_age_client.delete_ontology_node('no-such')

        assert result is False

    def test_delete_error_returns_false(self, mock_age_client):
        """Database error returns False (graceful degradation)."""
        mock_age_client._execute_cypher = MagicMock(
            side_effect=Exception("lock timeout")
        )

        result = mock_age_client.delete_ontology_node('locked')

        assert result is False


@pytest.mark.unit
class TestRenameOntologyNode:
    """Tests for rename_ontology_node()."""

    def test_rename_existing_returns_true(self, mock_age_client):
        """Renaming an existing ontology returns True."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            'ontology_id': 'ont_abc'
        })

        result = mock_age_client.rename_ontology_node('old-name', 'new-name')

        assert result is True

    def test_rename_nonexistent_returns_false(self, mock_age_client):
        """Renaming a nonexistent ontology returns False."""
        mock_age_client._execute_cypher = MagicMock(return_value=None)

        result = mock_age_client.rename_ontology_node('ghost', 'anything')

        assert result is False

    def test_rename_passes_both_names(self, mock_age_client):
        """Both old and new names are passed to query."""
        mock_age_client._execute_cypher = MagicMock(return_value={'ontology_id': 'ont_x'})

        mock_age_client.rename_ontology_node('from-this', 'to-that')

        call_args = mock_age_client._execute_cypher.call_args
        params = call_args.kwargs.get('params') or call_args[1].get('params')
        assert params['old_name'] == 'from-this'
        assert params['new_name'] == 'to-that'


@pytest.mark.unit
class TestCreateScopedByEdge:
    """Tests for create_scoped_by_edge()."""

    def test_create_edge_returns_true(self, mock_age_client):
        """Creating a SCOPED_BY edge returns True."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            'source_id': 'src_123'
        })

        result = mock_age_client.create_scoped_by_edge('src_123', 'my-ontology')

        assert result is True

    def test_create_edge_missing_source_returns_false(self, mock_age_client):
        """SCOPED_BY with nonexistent source returns False."""
        mock_age_client._execute_cypher = MagicMock(return_value=None)

        result = mock_age_client.create_scoped_by_edge('no-source', 'my-ontology')

        assert result is False

    def test_create_edge_passes_params(self, mock_age_client):
        """Source ID and ontology name are passed to query."""
        mock_age_client._execute_cypher = MagicMock(return_value={'source_id': 'src_x'})

        mock_age_client.create_scoped_by_edge('src_x', 'target-ontology')

        call_args = mock_age_client._execute_cypher.call_args
        params = call_args.kwargs.get('params') or call_args[1].get('params')
        assert params['source_id'] == 'src_x'
        assert params['ontology_name'] == 'target-ontology'


@pytest.mark.unit
class TestEnsureOntologyExists:
    """Tests for ensure_ontology_exists()."""

    def test_returns_existing_ontology(self, mock_age_client):
        """If ontology exists, returns it without creating."""
        existing = {
            'ontology_id': 'ont_exists',
            'name': 'already-here',
            'lifecycle_state': 'active'
        }
        mock_age_client.get_ontology_node = MagicMock(return_value=existing)
        mock_age_client.create_ontology_node = MagicMock()

        result = mock_age_client.ensure_ontology_exists('already-here')

        assert result == existing
        mock_age_client.create_ontology_node.assert_not_called()

    def test_creates_when_not_exists(self, mock_age_client):
        """If ontology doesn't exist, creates it."""
        created = {
            'ontology_id': 'ont_new',
            'name': 'fresh',
            'lifecycle_state': 'active'
        }
        mock_age_client.get_ontology_node = MagicMock(return_value=None)
        mock_age_client.create_ontology_node = MagicMock(return_value=created)

        result = mock_age_client.ensure_ontology_exists('fresh')

        assert result == created
        mock_age_client.create_ontology_node.assert_called_once()

    def test_created_node_has_uuid_id(self, mock_age_client):
        """Newly created ontology gets ont_<uuid> identifier."""
        mock_age_client.get_ontology_node = MagicMock(return_value=None)
        mock_age_client.create_ontology_node = MagicMock(return_value={})

        mock_age_client.ensure_ontology_exists('new-one')

        call_args = mock_age_client.create_ontology_node.call_args
        ontology_id = call_args.kwargs.get('ontology_id') or call_args[1].get('ontology_id')
        # If passed as positional arg
        if ontology_id is None and call_args.args:
            ontology_id = call_args.args[0]
        assert ontology_id.startswith('ont_')

    def test_race_condition_returns_winner(self, mock_age_client):
        """Concurrent create race returns the winner's node instead of failing."""
        winner_node = {
            'ontology_id': 'ont_winner',
            'name': 'contested',
            'lifecycle_state': 'active'
        }
        # First get returns None (not exists), create raises (race loser),
        # second get returns the winner's node
        mock_age_client.get_ontology_node = MagicMock(
            side_effect=[None, winner_node]
        )
        mock_age_client.create_ontology_node = MagicMock(
            side_effect=Exception("unique constraint violation")
        )

        result = mock_age_client.ensure_ontology_exists('contested')

        assert result == winner_node
        assert mock_age_client.get_ontology_node.call_count == 2


@pytest.mark.unit
class TestUpdateOntologyEmbedding:
    """Tests for update_ontology_embedding()."""

    def test_update_existing_returns_true(self, mock_age_client):
        """Updating embedding on existing ontology returns True."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            'ontology_id': 'ont_emb'
        })

        result = mock_age_client.update_ontology_embedding(
            'my-ontology',
            [0.1] * 1536
        )

        assert result is True

    def test_update_nonexistent_returns_false(self, mock_age_client):
        """Updating embedding on nonexistent ontology returns False."""
        mock_age_client._execute_cypher = MagicMock(return_value=None)

        result = mock_age_client.update_ontology_embedding(
            'ghost',
            [0.1] * 1536
        )

        assert result is False

    def test_update_passes_embedding(self, mock_age_client):
        """Embedding vector is passed to query."""
        mock_age_client._execute_cypher = MagicMock(return_value={'ontology_id': 'ont_x'})
        embedding = [0.5] * 1536

        mock_age_client.update_ontology_embedding('test', embedding)

        call_args = mock_age_client._execute_cypher.call_args
        params = call_args.kwargs.get('params') or call_args[1].get('params')
        assert params['embedding'] == embedding
        assert params['name'] == 'test'
