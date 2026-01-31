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
        assert params['created_by'] is None

    def test_create_with_created_by(self, mock_age_client):
        """created_by parameter is passed to the Cypher query."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            'o': {'properties': {'created_by': 'testuser'}}
        })

        mock_age_client.create_ontology_node(
            ontology_id='ont_prov',
            name='provenance-test',
            created_by='testuser'
        )

        call_args = mock_age_client._execute_cypher.call_args
        params = call_args.kwargs.get('params') or call_args[1].get('params')
        assert params['created_by'] == 'testuser'

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


@pytest.mark.unit
class TestUpdateOntologyLifecycle:
    """Tests for update_ontology_lifecycle() (ADR-200 Phase 2)."""

    def test_update_returns_properties(self, mock_age_client):
        """Updating lifecycle returns updated node properties."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            'o': {
                'properties': {
                    'ontology_id': 'ont_lc',
                    'name': 'test-ontology',
                    'lifecycle_state': 'frozen',
                }
            }
        })

        result = mock_age_client.update_ontology_lifecycle('test-ontology', 'frozen')

        assert result is not None
        assert result['lifecycle_state'] == 'frozen'

    def test_update_not_found_returns_none(self, mock_age_client):
        """Updating nonexistent ontology returns None."""
        mock_age_client._execute_cypher = MagicMock(return_value=None)

        result = mock_age_client.update_ontology_lifecycle('ghost', 'frozen')

        assert result is None

    def test_update_invalid_state_raises(self, mock_age_client):
        """Invalid lifecycle state raises ValueError."""
        with pytest.raises(ValueError, match="Invalid lifecycle state"):
            mock_age_client.update_ontology_lifecycle('test', 'invalid_state')

    def test_update_passes_params(self, mock_age_client):
        """Name and new_state are passed to query."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            'o': {'properties': {}}
        })

        mock_age_client.update_ontology_lifecycle('my-onto', 'pinned')

        call_args = mock_age_client._execute_cypher.call_args
        params = call_args.kwargs.get('params') or call_args[1].get('params')
        assert params['name'] == 'my-onto'
        assert params['new_state'] == 'pinned'


@pytest.mark.unit
class TestIsOntologyFrozen:
    """Tests for is_ontology_frozen() (ADR-200 Phase 2)."""

    def test_frozen_returns_true(self, mock_age_client):
        """Frozen ontology returns True."""
        mock_age_client.get_ontology_node = MagicMock(return_value={
            'lifecycle_state': 'frozen'
        })

        assert mock_age_client.is_ontology_frozen('frozen-one') is True

    def test_active_returns_false(self, mock_age_client):
        """Active ontology returns False."""
        mock_age_client.get_ontology_node = MagicMock(return_value={
            'lifecycle_state': 'active'
        })

        assert mock_age_client.is_ontology_frozen('active-one') is False

    def test_nonexistent_returns_false(self, mock_age_client):
        """Nonexistent ontology returns False (no protection)."""
        mock_age_client.get_ontology_node = MagicMock(return_value=None)

        assert mock_age_client.is_ontology_frozen('no-such') is False

    def test_pinned_returns_false(self, mock_age_client):
        """Pinned ontology returns False (not frozen)."""
        mock_age_client.get_ontology_node = MagicMock(return_value={
            'lifecycle_state': 'pinned'
        })

        assert mock_age_client.is_ontology_frozen('pinned-one') is False


# =========================================================================
# ADR-200 Phase 3a: Scoring & Breathing Control Surface
# =========================================================================


@pytest.mark.unit
class TestGetOntologyStats:
    """Tests for get_ontology_stats() (ADR-200 Phase 3a)."""

    def test_returns_stats_for_existing_ontology(self, mock_age_client):
        """Returns stat counts for an existing ontology."""
        mock_age_client.get_ontology_node = MagicMock(return_value={
            'name': 'test-onto', 'lifecycle_state': 'active'
        })
        mock_age_client._execute_cypher = MagicMock(side_effect=[
            {'source_count': 10, 'file_count': 3},   # source query
            {'concept_count': 25},                     # concept query
            {'evidence_count': 50},                    # evidence query
            {'internal_count': 15},                    # internal rels
            {'cross_count': 5},                        # cross-ontology rels
        ])

        result = mock_age_client.get_ontology_stats('test-onto')

        assert result is not None
        assert result['ontology'] == 'test-onto'
        assert result['source_count'] == 10
        assert result['concept_count'] == 25
        assert result['evidence_count'] == 50
        assert result['internal_relationship_count'] == 15
        assert result['cross_ontology_relationship_count'] == 5

    def test_returns_none_for_nonexistent(self, mock_age_client):
        """Returns None if ontology doesn't exist."""
        mock_age_client.get_ontology_node = MagicMock(return_value=None)

        result = mock_age_client.get_ontology_stats('ghost')

        assert result is None

    def test_returns_zeros_on_error(self, mock_age_client):
        """Returns partial stats with zeros on query errors."""
        mock_age_client.get_ontology_node = MagicMock(return_value={
            'name': 'error-onto', 'lifecycle_state': 'active'
        })
        mock_age_client._execute_cypher = MagicMock(side_effect=Exception("db error"))

        result = mock_age_client.get_ontology_stats('error-onto')

        assert result is not None
        assert result['concept_count'] == 0
        assert result['source_count'] == 0


@pytest.mark.unit
class TestGetConceptDegreeRanking:
    """Tests for get_concept_degree_ranking() (ADR-200 Phase 3a)."""

    def test_returns_ranked_concepts(self, mock_age_client):
        """Returns concepts ranked by degree."""
        mock_age_client._execute_cypher = MagicMock(return_value=[
            {'concept_id': 'c_1', 'label': 'Top', 'degree': 10, 'in_degree': 6, 'out_degree': 4},
            {'concept_id': 'c_2', 'label': 'Second', 'degree': 5, 'in_degree': 3, 'out_degree': 2},
        ])

        result = mock_age_client.get_concept_degree_ranking('test-onto', limit=5)

        assert len(result) == 2
        assert result[0]['label'] == 'Top'
        assert result[0]['degree'] == 10

    def test_returns_empty_on_error(self, mock_age_client):
        """Returns empty list on database error."""
        mock_age_client._execute_cypher = MagicMock(side_effect=Exception("fail"))

        result = mock_age_client.get_concept_degree_ranking('test-onto')

        assert result == []


@pytest.mark.unit
class TestGetCrossOntologyAffinity:
    """Tests for get_cross_ontology_affinity() (ADR-200 Phase 3a)."""

    def test_returns_affinity_scores(self, mock_age_client):
        """Returns other ontologies with shared concept counts."""
        mock_age_client._execute_cypher = MagicMock(return_value=[
            {'other_ontology': 'related', 'shared_concept_count': 10, 'total_concepts': 50, 'affinity_score': 0.2},
        ])

        result = mock_age_client.get_cross_ontology_affinity('test-onto')

        assert len(result) == 1
        assert result[0]['other_ontology'] == 'related'
        assert result[0]['affinity_score'] == 0.2


@pytest.mark.unit
class TestGetAllOntologyScores:
    """Tests for get_all_ontology_scores() (ADR-200 Phase 3a)."""

    def test_returns_cached_scores(self, mock_age_client):
        """Returns cached score properties from Ontology nodes."""
        mock_age_client._execute_cypher = MagicMock(return_value=[
            {
                'ontology': 'onto-1',
                'mass_score': 0.75,
                'coherence_score': 0.6,
                'raw_exposure': 0.3,
                'weighted_exposure': 0.35,
                'protection_score': 0.42,
                'last_evaluated_epoch': 10,
            }
        ])

        result = mock_age_client.get_all_ontology_scores()

        assert len(result) == 1
        assert result[0]['mass_score'] == 0.75
        assert result[0]['protection_score'] == 0.42

    def test_handles_null_scores(self, mock_age_client):
        """Null scores (never evaluated) default to 0."""
        mock_age_client._execute_cypher = MagicMock(return_value=[
            {
                'ontology': 'unscored',
                'mass_score': None,
                'coherence_score': None,
                'raw_exposure': None,
                'weighted_exposure': None,
                'protection_score': None,
                'last_evaluated_epoch': None,
            }
        ])

        result = mock_age_client.get_all_ontology_scores()

        assert result[0]['mass_score'] == 0.0
        assert result[0]['last_evaluated_epoch'] == 0


@pytest.mark.unit
class TestUpdateOntologyScores:
    """Tests for update_ontology_scores() (ADR-200 Phase 3a)."""

    def test_update_returns_true(self, mock_age_client):
        """Updating scores on existing ontology returns True."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            'ontology_id': 'ont_scored'
        })

        result = mock_age_client.update_ontology_scores(
            'test-onto', mass=0.5, coherence=0.6, protection=0.3, epoch=10
        )

        assert result is True

    def test_update_not_found_returns_false(self, mock_age_client):
        """Updating scores on nonexistent ontology returns False."""
        mock_age_client._execute_cypher = MagicMock(return_value=None)

        result = mock_age_client.update_ontology_scores(
            'ghost', mass=0.5, coherence=0.6, protection=0.3, epoch=10
        )

        assert result is False


@pytest.mark.unit
class TestReassignSources:
    """Tests for reassign_sources() (ADR-200 Phase 3a)."""

    def test_reassign_success(self, mock_age_client):
        """Successfully moves sources between ontologies."""
        mock_age_client.get_ontology_node = MagicMock(side_effect=[
            {'name': 'from-onto', 'lifecycle_state': 'active'},  # from
            {'name': 'to-onto', 'lifecycle_state': 'active'},    # to
        ])
        mock_age_client._execute_cypher = MagicMock(side_effect=[
            {'updated': 2},    # update document
            {'deleted': 2},    # delete old edges
            {'created': 2},    # create new edges
        ])

        result = mock_age_client.reassign_sources(
            ['s1', 's2'], 'from-onto', 'to-onto'
        )

        assert result['success'] is True
        assert result['sources_reassigned'] == 2

    def test_reassign_frozen_source_rejected(self, mock_age_client):
        """Cannot reassign from a frozen ontology."""
        mock_age_client.get_ontology_node = MagicMock(side_effect=[
            {'name': 'frozen-onto', 'lifecycle_state': 'frozen'},
            {'name': 'to-onto', 'lifecycle_state': 'active'},
        ])

        result = mock_age_client.reassign_sources(
            ['s1'], 'frozen-onto', 'to-onto'
        )

        assert result['success'] is False
        assert 'frozen' in result['error']

    def test_reassign_source_not_found(self, mock_age_client):
        """Rejects if source ontology doesn't exist."""
        mock_age_client.get_ontology_node = MagicMock(return_value=None)

        result = mock_age_client.reassign_sources(
            ['s1'], 'ghost', 'to-onto'
        )

        assert result['success'] is False
        assert 'not found' in result['error']


@pytest.mark.unit
class TestDissolveOntology:
    """Tests for dissolve_ontology() (ADR-200 Phase 3a)."""

    def test_dissolve_success(self, mock_age_client):
        """Successfully dissolves an active ontology."""
        mock_age_client.get_ontology_node = MagicMock(side_effect=[
            {'name': 'dissolve-me', 'lifecycle_state': 'active'},  # dissolve check
            {'name': 'dissolve-me', 'lifecycle_state': 'active'},  # reassign from
            {'name': 'target', 'lifecycle_state': 'active'},       # reassign to
        ])
        mock_age_client._execute_cypher = MagicMock(side_effect=[
            [{'source_id': 's1'}, {'source_id': 's2'}],  # get source IDs
            {'updated': 2},   # update document
            {'deleted': 2},   # delete old edges
            {'created': 2},   # create new edges
        ])
        mock_age_client.delete_ontology_node = MagicMock(return_value=True)

        result = mock_age_client.dissolve_ontology('dissolve-me', 'target')

        assert result['success'] is True
        assert result['sources_reassigned'] == 2
        assert result['ontology_node_deleted'] is True

    def test_dissolve_pinned_rejected(self, mock_age_client):
        """Cannot dissolve a pinned ontology."""
        mock_age_client.get_ontology_node = MagicMock(return_value={
            'name': 'pinned-onto', 'lifecycle_state': 'pinned'
        })

        result = mock_age_client.dissolve_ontology('pinned-onto', 'target')

        assert result['success'] is False
        assert 'pinned' in result['error']

    def test_dissolve_frozen_rejected(self, mock_age_client):
        """Cannot dissolve a frozen ontology."""
        mock_age_client.get_ontology_node = MagicMock(return_value={
            'name': 'frozen-onto', 'lifecycle_state': 'frozen'
        })

        result = mock_age_client.dissolve_ontology('frozen-onto', 'target')

        assert result['success'] is False
        assert 'frozen' in result['error']

    def test_dissolve_not_found(self, mock_age_client):
        """Cannot dissolve nonexistent ontology."""
        mock_age_client.get_ontology_node = MagicMock(return_value=None)

        result = mock_age_client.dissolve_ontology('ghost', 'target')

        assert result['success'] is False
        assert 'not found' in result['error']


# ==========================================================================
# ADR-200 Phase 5: Ontology-to-Ontology Edge Methods
# ==========================================================================


@pytest.mark.unit
class TestUpsertOntologyEdge:
    """Tests for upsert_ontology_edge()."""

    def test_upsert_creates_edge(self, mock_age_client):
        """Upserting an edge returns True on success."""
        mock_age_client._execute_cypher = MagicMock(return_value={"type": "OVERLAPS"})

        result = mock_age_client.upsert_ontology_edge(
            from_name="ontology-a",
            to_name="ontology-b",
            edge_type="OVERLAPS",
            score=0.5,
            shared_concept_count=10,
            epoch=5,
            source="breathing_worker",
        )

        assert result is True
        mock_age_client._execute_cypher.assert_called_once()

    def test_upsert_passes_params(self, mock_age_client):
        """All parameters are forwarded to Cypher."""
        mock_age_client._execute_cypher = MagicMock(return_value={"type": "SPECIALIZES"})

        mock_age_client.upsert_ontology_edge(
            from_name="domain-a",
            to_name="domain-b",
            edge_type="SPECIALIZES",
            score=0.75,
            shared_concept_count=20,
            epoch=10,
            source="manual",
        )

        call_args = mock_age_client._execute_cypher.call_args
        params = call_args.kwargs.get('params') or call_args[1].get('params')
        assert params['from_name'] == 'domain-a'
        assert params['to_name'] == 'domain-b'
        assert params['score'] == 0.75
        assert params['shared_count'] == 20
        assert params['epoch'] == 10
        assert params['source'] == 'manual'

    def test_upsert_rejects_invalid_edge_type(self, mock_age_client):
        """Invalid edge type raises ValueError."""
        with pytest.raises(ValueError, match="Invalid ontology edge type"):
            mock_age_client.upsert_ontology_edge(
                from_name="a", to_name="b",
                edge_type="INVALID_TYPE",
                score=0.5, shared_concept_count=0, epoch=0,
            )

    def test_upsert_failure_returns_false(self, mock_age_client):
        """Database error returns False."""
        mock_age_client._execute_cypher = MagicMock(
            side_effect=Exception("connection lost")
        )

        result = mock_age_client.upsert_ontology_edge(
            from_name="a", to_name="b",
            edge_type="OVERLAPS",
            score=0.5, shared_concept_count=0, epoch=0,
        )

        assert result is False


@pytest.mark.unit
class TestGetOntologyEdges:
    """Tests for get_ontology_edges()."""

    def test_get_returns_edges(self, mock_age_client):
        """Returns list of edge dicts for existing edges."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            "edges": [
                {
                    "from_ontology": "a",
                    "to_ontology": "b",
                    "edge_type": "OVERLAPS",
                    "score": 0.5,
                    "shared_concept_count": 10,
                    "computed_at_epoch": 5,
                    "source": "breathing_worker",
                    "direction": "outgoing",
                },
                {
                    "from_ontology": "c",
                    "to_ontology": "a",
                    "edge_type": "SPECIALIZES",
                    "score": 0.8,
                    "shared_concept_count": 15,
                    "computed_at_epoch": 5,
                    "source": "breathing_worker",
                    "direction": "incoming",
                },
            ]
        })

        result = mock_age_client.get_ontology_edges("a")

        assert len(result) == 2
        assert result[0]["edge_type"] == "OVERLAPS"
        assert result[1]["direction"] == "incoming"

    def test_get_filters_null_entries(self, mock_age_client):
        """Null entries from empty OPTIONAL MATCH are filtered out."""
        mock_age_client._execute_cypher = MagicMock(return_value={
            "edges": [
                {"edge_type": None, "from_ontology": None},
                {
                    "from_ontology": "a",
                    "to_ontology": "b",
                    "edge_type": "OVERLAPS",
                    "score": 0.5,
                    "shared_concept_count": 10,
                    "computed_at_epoch": 5,
                    "source": "breathing_worker",
                    "direction": "outgoing",
                },
            ]
        })

        result = mock_age_client.get_ontology_edges("a")

        assert len(result) == 1
        assert result[0]["edge_type"] == "OVERLAPS"

    def test_get_empty_returns_empty_list(self, mock_age_client):
        """No edges returns empty list."""
        mock_age_client._execute_cypher = MagicMock(return_value=None)

        result = mock_age_client.get_ontology_edges("lonely")

        assert result == []

    def test_get_error_returns_empty_list(self, mock_age_client):
        """Database error returns empty list (graceful degradation)."""
        mock_age_client._execute_cypher = MagicMock(
            side_effect=Exception("connection lost")
        )

        result = mock_age_client.get_ontology_edges("broken")

        assert result == []


@pytest.mark.unit
class TestDeleteDerivedOntologyEdges:
    """Tests for delete_derived_ontology_edges()."""

    def test_delete_returns_count(self, mock_age_client):
        """Deleting derived edges returns total count across all types/directions."""
        # Each call returns 1 deleted; 3 types * 2 directions = 6 calls
        mock_age_client._execute_cypher = MagicMock(return_value={"deleted": 1})

        result = mock_age_client.delete_derived_ontology_edges("test-ontology")

        # 3 types * 2 directions * 1 each = 6
        assert result == 6

    def test_delete_specific_type(self, mock_age_client):
        """Can delete specific edge type only (2 directions)."""
        mock_age_client._execute_cypher = MagicMock(return_value={"deleted": 1})

        result = mock_age_client.delete_derived_ontology_edges(
            "test-ontology", edge_type="OVERLAPS"
        )

        # 1 type * 2 directions * 1 each = 2
        assert result == 2
        # All queries should reference OVERLAPS
        for call in mock_age_client._execute_cypher.call_args_list:
            query = call.args[0] if call.args else call.kwargs.get('query', '')
            assert 'OVERLAPS' in query

    def test_delete_error_returns_zero(self, mock_age_client):
        """Database error returns 0."""
        mock_age_client._execute_cypher = MagicMock(
            side_effect=Exception("error")
        )

        result = mock_age_client.delete_derived_ontology_edges("broken")

        assert result == 0


@pytest.mark.unit
class TestDeleteAllDerivedOntologyEdges:
    """Tests for delete_all_derived_ontology_edges()."""

    def test_delete_all_returns_count(self, mock_age_client):
        """Deleting all derived edges returns total count across all types."""
        # 3 types, each returning 2 deleted = 6 total
        mock_age_client._execute_cypher = MagicMock(return_value={"deleted": 2})

        result = mock_age_client.delete_all_derived_ontology_edges()

        assert result == 6  # 3 types * 2 each

    def test_delete_all_error_returns_zero(self, mock_age_client):
        """Database error returns 0."""
        mock_age_client._execute_cypher = MagicMock(
            side_effect=Exception("error")
        )

        result = mock_age_client.delete_all_derived_ontology_edges()

        assert result == 0
