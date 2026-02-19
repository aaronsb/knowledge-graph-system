"""
Unit tests for GraphFacade (ADR-201 Phase 5b).

Tests both graph_accel accelerated paths and Cypher fallback paths.
All tests mock database calls since the real methods need PostgreSQL.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock


@pytest.fixture
def mock_age_client():
    """Create an AGEClient with mocked database connection."""
    with patch('api.app.lib.age_client.base.psycopg2') as mock_psycopg2:
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


@pytest.fixture
def facade(mock_age_client):
    """Get GraphFacade from a mocked client."""
    return mock_age_client.graph


class TestAvailabilityDetection:
    """Test graph_accel extension detection and loading."""

    def test_accel_available_when_loaded(self, facade):
        """Extension installed and loaded → _accel_ready is True."""
        with patch.object(facade, '_execute_sql') as mock_sql:
            mock_sql.return_value = [{'status': 'loaded'}]
            assert facade._accel_ready is True

    def test_accel_available_when_stale(self, facade):
        """Extension installed but stale → still available (auto_reload handles it)."""
        with patch.object(facade, '_execute_sql') as mock_sql:
            mock_sql.return_value = [{'status': 'stale'}]
            assert facade._accel_ready is True

    def test_accel_available_when_not_loaded(self, facade):
        """Extension installed but not loaded → still available.

        _detect_accel only checks if the extension is installed.
        Per-connection loading is handled by _execute_sql.
        """
        with patch.object(facade, '_execute_sql') as mock_sql:
            mock_sql.return_value = [{'status': 'not_loaded'}]
            assert facade._accel_ready is True
            assert mock_sql.call_count == 1

    def test_accel_unavailable_when_extension_missing(self, facade):
        """Extension not installed → _accel_ready is False."""
        with patch.object(facade, '_execute_sql') as mock_sql:
            mock_sql.side_effect = Exception("function graph_accel_status() does not exist")
            assert facade._accel_ready is False

    def test_accel_cached_after_first_check(self, facade):
        """Availability result is cached for facade lifetime."""
        with patch.object(facade, '_execute_sql') as mock_sql:
            mock_sql.return_value = [{'status': 'loaded'}]
            assert facade._accel_ready is True
            assert facade._accel_ready is True  # Second call uses cache
            assert mock_sql.call_count == 1

    def test_is_accelerated_public_api(self, facade):
        """is_accelerated() exposes the cached check."""
        with patch.object(facade, '_execute_sql') as mock_sql:
            mock_sql.return_value = [{'status': 'loaded'}]
            assert facade.is_accelerated() is True


class TestNeighborhoodAccelerated:
    """Test neighborhood() with graph_accel fast path."""

    def test_returns_concept_list(self, facade):
        """Accelerated path returns properly mapped results with hydrated labels."""
        facade._accel_available = True

        with patch.object(facade, '_execute_sql') as mock_sql, \
             patch.object(facade, '_hydrate_concepts') as mock_hydrate:
            mock_sql.return_value = [
                {'app_id': 'c_abc', 'label': 'Concept', 'distance': 1, 'path_types': ['IMPLIES']},
                {'app_id': 'c_def', 'label': 'Concept', 'distance': 2, 'path_types': ['IMPLIES', 'SUPPORTS']},
            ]
            mock_hydrate.return_value = {
                'c_abc': {'concept_id': 'c_abc', 'label': 'Concept A', 'description': ''},
                'c_def': {'concept_id': 'c_def', 'label': 'Concept B', 'description': ''},
            }

            results = facade.neighborhood('c_start', max_depth=2)

            assert len(results) == 2
            assert results[0]['concept_id'] == 'c_abc'
            assert results[0]['label'] == 'Concept A'
            assert results[0]['distance'] == 1
            assert results[0]['path_types'] == ['IMPLIES']
            assert results[1]['distance'] == 2
            mock_hydrate.assert_called_once_with(['c_abc', 'c_def'])

    def test_passes_direction_and_confidence(self, facade):
        """Direction and min_confidence params are forwarded to SQL."""
        facade._accel_available = True

        with patch.object(facade, '_execute_sql') as mock_sql:
            mock_sql.return_value = []
            facade.neighborhood('c_start', direction='outgoing', min_confidence=0.5)

            call_args = mock_sql.call_args
            params = call_args[0][1]
            assert params[2] == 'outgoing'
            assert params[3] == 0.5

    def test_empty_graph_returns_empty_list(self, facade):
        """No neighbors found → empty list, not error."""
        facade._accel_available = True

        with patch.object(facade, '_execute_sql') as mock_sql:
            mock_sql.return_value = []
            results = facade.neighborhood('c_isolated')
            assert results == []


class TestNeighborhoodCypherFallback:
    """Test neighborhood() Cypher fallback when graph_accel unavailable."""

    def test_builds_per_depth_queries(self, facade):
        """Fallback executes one Cypher query per depth level."""
        facade._accel_available = False

        with patch.object(facade._client, '_execute_cypher') as mock_cypher:
            mock_cypher.return_value = [
                {'concept_id': 'c_a', 'label': 'A', 'distance': 1, 'path_types': ['IMPLIES']}
            ]

            results = facade.neighborhood('c_start', max_depth=3)

            # Should call _execute_cypher 3 times (depth 1, 2, 3)
            assert mock_cypher.call_count == 3

    def test_merges_by_minimum_distance(self, facade):
        """Same concept found at depth 1 and 3 → keeps depth 1."""
        facade._accel_available = False

        with patch.object(facade._client, '_execute_cypher') as mock_cypher:
            # Depth 1: finds c_a at distance 1
            # Depth 2: finds c_a again at distance 2
            mock_cypher.side_effect = [
                [{'concept_id': 'c_a', 'label': 'A', 'distance': 1, 'path_types': ['X']}],
                [{'concept_id': 'c_a', 'label': 'A', 'distance': 2, 'path_types': ['X', 'Y']}],
            ]

            results = facade.neighborhood('c_start', max_depth=2)

            assert len(results) == 1
            assert results[0]['distance'] == 1

    def test_relationship_type_filter(self, facade):
        """Relationship types are interpolated into Cypher pattern."""
        facade._accel_available = False

        with patch.object(facade._client, '_execute_cypher') as mock_cypher:
            mock_cypher.return_value = []
            facade.neighborhood('c_start', max_depth=1,
                                relationship_types=['IMPLIES', 'SUPPORTS'])

            query = mock_cypher.call_args[0][0]
            assert ':IMPLIES|SUPPORTS' in query

    def test_rejects_invalid_rel_types(self, facade):
        """Invalid relationship type names raise ValueError."""
        facade._accel_available = False

        with pytest.raises(ValueError, match="Invalid relationship type"):
            facade.neighborhood('c_start', relationship_types=['drop table'])


class TestFindPath:
    """Test find_path() with both accelerated and fallback paths."""

    def test_same_node_returns_self_path(self, facade):
        """from_id == to_id returns single-node path."""
        with patch.object(facade, '_hydrate_concepts') as mock_hydrate:
            mock_hydrate.return_value = {
                'c_a': {'concept_id': 'c_a', 'label': 'A', 'description': 'desc'}
            }
            result = facade.find_path('c_a', 'c_a')

            assert result is not None
            assert result['hops'] == 0
            assert len(result['path_nodes']) == 1

    def test_accel_path_maps_to_dict(self, facade):
        """Accelerated path rows are mapped to standard path dict."""
        facade._accel_available = True

        with patch.object(facade, '_execute_sql') as mock_sql, \
             patch.object(facade, '_hydrate_concepts') as mock_hydrate:
            mock_sql.return_value = [
                {'step': 0, 'app_id': 'c_a', 'label': 'Concept', 'rel_type': None, 'direction': None},
                {'step': 1, 'app_id': 'c_b', 'label': 'Concept', 'rel_type': 'IMPLIES', 'direction': 'outgoing'},
                {'step': 2, 'app_id': 'c_c', 'label': 'Concept', 'rel_type': 'SUPPORTS', 'direction': 'outgoing'},
            ]
            mock_hydrate.return_value = {
                'c_a': {'concept_id': 'c_a', 'label': 'A', 'description': ''},
                'c_b': {'concept_id': 'c_b', 'label': 'B', 'description': ''},
                'c_c': {'concept_id': 'c_c', 'label': 'C', 'description': ''},
            }

            result = facade.find_path('c_a', 'c_c')

            assert result['hops'] == 2
            assert len(result['path_nodes']) == 3
            assert result['path_nodes'][0]['concept_id'] == 'c_a'
            assert result['path_rels'][0]['label'] == 'IMPLIES'
            assert result['path_rels'][1]['label'] == 'SUPPORTS'

    def test_no_path_returns_none(self, facade):
        """No path found → returns None."""
        facade._accel_available = True

        with patch.object(facade, '_execute_sql') as mock_sql, \
             patch.object(facade, '_concept_exists', return_value=True):
            mock_sql.return_value = []

            # Also need fallback to return None
            with patch.object(facade, '_find_path_bfs', return_value=None):
                result = facade.find_path('c_a', 'c_z')
                assert result is None


class TestFindPaths:
    """Test find_paths() multiple path discovery."""

    def test_returns_single_path_when_only_one_exists(self, facade):
        """Single shortest path found (BFS fallback) → returns list of one."""
        facade._accel_available = False

        with patch.object(facade, 'find_path') as mock_fp:
            mock_fp.return_value = {
                'path_nodes': [
                    {'concept_id': 'c_a', 'label': 'A', 'description': ''},
                    {'concept_id': 'c_b', 'label': 'B', 'description': ''},
                ],
                'path_rels': [{'label': 'IMPLIES', 'properties': {}}],
                'hops': 1
            }

            with patch.object(facade, '_find_path_bfs_excluding', return_value=None):
                paths = facade.find_paths('c_a', 'c_b', max_paths=5)
                assert len(paths) == 1

    def test_returns_empty_when_no_path(self, facade):
        """No path found → empty list."""
        facade._accel_available = False

        with patch.object(facade, 'find_path', return_value=None):
            paths = facade.find_paths('c_a', 'c_z')
            assert paths == []

    def test_limits_to_max_paths(self, facade):
        """Never returns more than max_paths paths (BFS fallback)."""
        facade._accel_available = False

        mock_path = {
            'path_nodes': [
                {'concept_id': 'c_a', 'label': 'A', 'description': ''},
                {'concept_id': 'c_b', 'label': 'B', 'description': ''},
            ],
            'path_rels': [{'label': 'IMPLIES', 'properties': {}}],
            'hops': 1
        }

        with patch.object(facade, 'find_path', return_value=mock_path), \
             patch.object(facade, '_find_path_bfs_excluding', return_value=mock_path):
            paths = facade.find_paths('c_a', 'c_b', max_paths=2)
            assert len(paths) <= 2

    def test_accel_multi_path(self, facade):
        """graph_accel_paths returns multiple paths grouped by path_index."""
        facade._accel_available = True

        with patch.object(facade, '_execute_sql') as mock_sql, \
             patch.object(facade, '_hydrate_concepts') as mock_hydrate:
            mock_sql.return_value = [
                {'path_index': 0, 'step': 0, 'app_id': 'c_a', 'label': 'Concept', 'rel_type': None, 'direction': None},
                {'path_index': 0, 'step': 1, 'app_id': 'c_b', 'label': 'Concept', 'rel_type': 'IMPLIES', 'direction': 'outgoing'},
                {'path_index': 1, 'step': 0, 'app_id': 'c_a', 'label': 'Concept', 'rel_type': None, 'direction': None},
                {'path_index': 1, 'step': 1, 'app_id': 'c_c', 'label': 'Concept', 'rel_type': 'SUPPORTS', 'direction': 'outgoing'},
                {'path_index': 1, 'step': 2, 'app_id': 'c_b', 'label': 'Concept', 'rel_type': 'IMPLIES', 'direction': 'outgoing'},
            ]
            mock_hydrate.return_value = {
                'c_a': {'concept_id': 'c_a', 'label': 'A', 'description': ''},
                'c_b': {'concept_id': 'c_b', 'label': 'B', 'description': ''},
                'c_c': {'concept_id': 'c_c', 'label': 'C', 'description': ''},
            }

            paths = facade.find_paths('c_a', 'c_b', max_paths=5)

            assert len(paths) == 2
            # Path 0: 1-hop direct
            assert paths[0]['hops'] == 1
            assert paths[0]['path_nodes'][0]['concept_id'] == 'c_a'
            assert paths[0]['path_rels'][0]['label'] == 'IMPLIES'
            # Path 1: 2-hop via c_c
            assert paths[1]['hops'] == 2
            assert paths[1]['path_nodes'][1]['concept_id'] == 'c_c'

    def test_accel_multi_path_empty(self, facade):
        """graph_accel_paths returns no rows → empty list."""
        facade._accel_available = True

        with patch.object(facade, '_execute_sql') as mock_sql:
            mock_sql.return_value = []
            paths = facade.find_paths('c_a', 'c_z', max_paths=5)
            assert paths == []

    def test_accel_single_path_filters_phantom_nodes(self, facade):
        """Single path through non-Concept node (no app_id) → returns None."""
        facade._accel_available = True

        with patch.object(facade, '_execute_sql') as mock_sql, \
             patch.object(facade, '_concept_exists', return_value=True), \
             patch.object(facade, '_find_path_bfs', return_value=None):
            mock_sql.return_value = [
                {'step': 0, 'app_id': 'c_a', 'label': 'Concept', 'rel_type': None, 'direction': None},
                {'step': 1, 'app_id': None, 'label': '', 'rel_type': 'APPEARS', 'direction': 'outgoing'},
                {'step': 2, 'app_id': 'c_b', 'label': 'Concept', 'rel_type': 'APPEARS', 'direction': 'incoming'},
            ]

            result = facade.find_path('c_a', 'c_b')
            # Phantom path filtered, falls through to BFS which returns None
            assert result is None

    def test_accel_multi_path_filters_phantom_paths(self, facade):
        """Paths through non-Concept nodes are excluded from multi-path results."""
        facade._accel_available = True

        with patch.object(facade, '_execute_sql') as mock_sql, \
             patch.object(facade, '_hydrate_concepts') as mock_hydrate:
            mock_sql.return_value = [
                # Path 0: phantom (goes through Source with no app_id)
                {'path_index': 0, 'step': 0, 'app_id': 'c_a', 'label': 'Concept', 'rel_type': None, 'direction': None},
                {'path_index': 0, 'step': 1, 'app_id': None, 'label': '', 'rel_type': 'APPEARS', 'direction': 'outgoing'},
                {'path_index': 0, 'step': 2, 'app_id': 'c_b', 'label': 'Concept', 'rel_type': 'APPEARS', 'direction': 'incoming'},
                # Path 1: clean semantic path
                {'path_index': 1, 'step': 0, 'app_id': 'c_a', 'label': 'Concept', 'rel_type': None, 'direction': None},
                {'path_index': 1, 'step': 1, 'app_id': 'c_c', 'label': 'Concept', 'rel_type': 'CONTAINS', 'direction': 'outgoing'},
                {'path_index': 1, 'step': 2, 'app_id': 'c_b', 'label': 'Concept', 'rel_type': 'CONTAINS', 'direction': 'outgoing'},
            ]
            mock_hydrate.return_value = {
                'c_a': {'concept_id': 'c_a', 'label': 'A', 'description': ''},
                'c_b': {'concept_id': 'c_b', 'label': 'B', 'description': ''},
                'c_c': {'concept_id': 'c_c', 'label': 'C', 'description': ''},
            }

            paths = facade.find_paths('c_a', 'c_b', max_paths=5)

            # Only the clean path survives
            assert len(paths) == 1
            assert paths[0]['hops'] == 2
            assert paths[0]['path_nodes'][1]['concept_id'] == 'c_c'

    def test_same_node_returns_self_path(self, facade):
        """from_id == to_id returns single-node path."""
        with patch.object(facade, '_hydrate_concepts') as mock_hydrate:
            mock_hydrate.return_value = {
                'c_a': {'concept_id': 'c_a', 'label': 'A', 'description': 'desc'}
            }
            paths = facade.find_paths('c_a', 'c_a')
            assert len(paths) == 1
            assert paths[0]['hops'] == 0


class TestDegree:
    """Test degree centrality ranking."""

    def test_accel_degree_returns_ranking(self, facade):
        """Accelerated degree returns sorted ranking."""
        facade._accel_available = True

        with patch.object(facade, '_execute_sql') as mock_sql:
            mock_sql.return_value = [
                {'app_id': 'c_hub', 'out_degree': 20, 'in_degree': 15, 'total_degree': 35},
                {'app_id': 'c_leaf', 'out_degree': 1, 'in_degree': 2, 'total_degree': 3},
            ]

            results = facade.degree(top_n=10)
            assert len(results) == 2
            assert results[0]['app_id'] == 'c_hub'
            assert results[0]['total_degree'] == 35

    def test_fallback_uses_cypher(self, facade):
        """Cypher fallback counts relationships per concept."""
        facade._accel_available = False

        with patch.object(facade._client, '_execute_cypher') as mock_cypher:
            mock_cypher.return_value = [
                {'app_id': 'c_hub', 'out_degree': 20, 'in_degree': 15, 'total_degree': 35}
            ]

            results = facade.degree(top_n=5)
            assert len(results) == 1
            query = mock_cypher.call_args[0][0]
            assert 'OPTIONAL MATCH' in query


class TestInvalidation:
    """Test cache invalidation calls."""

    def test_invalidate_returns_generation(self, facade):
        """invalidate() returns new generation number."""
        with patch.object(facade, '_execute_sql') as mock_sql:
            mock_sql.return_value = [{'generation': 42}]
            gen = facade.invalidate()
            assert gen == 42

    def test_invalidate_returns_none_when_unavailable(self, facade):
        """invalidate() returns None if extension not installed."""
        with patch.object(facade, '_execute_sql') as mock_sql:
            mock_sql.side_effect = Exception("function does not exist")
            gen = facade.invalidate()
            assert gen is None

    def test_status_returns_dict(self, facade):
        """status() returns extension state info."""
        with patch.object(facade, '_execute_sql') as mock_sql:
            mock_sql.return_value = [{
                'source_graph': 'knowledge_graph',
                'status': 'loaded',
                'node_count': 800,
                'edge_count': 2000,
                'memory_bytes': 320000,
                'is_stale': False,
            }]
            s = facade.status()
            assert s['status'] == 'loaded'
            assert s['node_count'] == 800

    def test_status_returns_empty_when_unavailable(self, facade):
        """status() returns empty dict if extension missing."""
        with patch.object(facade, '_execute_sql') as mock_sql:
            mock_sql.side_effect = Exception("not installed")
            s = facade.status()
            assert s == {}


class TestHydration:
    """Test batch concept hydration."""

    def test_hydrate_concepts_batch(self, facade):
        """Hydrates multiple concepts in a single query."""
        with patch.object(facade._client, '_execute_cypher') as mock_cypher:
            mock_cypher.return_value = [
                {'concept_id': 'c_a', 'label': 'A', 'description': 'Desc A'},
                {'concept_id': 'c_b', 'label': 'B', 'description': 'Desc B'},
            ]

            result = facade._hydrate_concepts(['c_a', 'c_b'])

            assert len(result) == 2
            assert result['c_a']['label'] == 'A'
            assert result['c_b']['description'] == 'Desc B'

    def test_hydrate_deduplicates_ids(self, facade):
        """Duplicate IDs in input produce a single query."""
        with patch.object(facade._client, '_execute_cypher') as mock_cypher:
            mock_cypher.return_value = [
                {'concept_id': 'c_a', 'label': 'A', 'description': ''},
            ]

            facade._hydrate_concepts(['c_a', 'c_a', 'c_a'])

            query = mock_cypher.call_args[0][0]
            # Should only contain c_a once
            assert query.count("'c_a'") == 1

    def test_hydrate_empty_list(self, facade):
        """Empty input returns empty dict."""
        result = facade._hydrate_concepts([])
        assert result == {}


class TestMatchSources:
    """Test namespace-safe source queries (carried from QueryFacade)."""

    def test_match_sources_basic(self, facade):
        """Basic source query with no filter."""
        with patch.object(facade._client, '_execute_cypher') as mock_cypher:
            mock_cypher.return_value = [{'s': {'properties': {'source_id': 'src_1'}}}]

            results = facade.match_sources()
            assert len(results) == 1
            query = mock_cypher.call_args[0][0]
            assert 'MATCH (s:Source)' in query

    def test_match_sources_with_where(self, facade):
        """Source query with WHERE clause."""
        with patch.object(facade._client, '_execute_cypher') as mock_cypher:
            mock_cypher.return_value = []
            facade.match_sources(where="s.source_id IN $source_ids",
                                 params={"source_ids": ["s1", "s2"]})
            query = mock_cypher.call_args[0][0]
            assert 'WHERE s.source_id IN $source_ids' in query

    def test_match_concepts_for_sources_batch(self, facade):
        """Batch fetch groups concepts by source_id."""
        with patch.object(facade._client, '_execute_cypher') as mock_cypher:
            mock_cypher.return_value = [
                {'source_id': 's1', 'concept_id': 'c_a', 'label': 'A',
                 'description': '', 'instance_quote': 'quote1'},
                {'source_id': 's1', 'concept_id': 'c_b', 'label': 'B',
                 'description': '', 'instance_quote': 'quote2'},
                {'source_id': 's2', 'concept_id': 'c_a', 'label': 'A',
                 'description': '', 'instance_quote': 'quote3'},
            ]

            result = facade.match_concepts_for_sources_batch(['s1', 's2', 's3'])

            assert len(result['s1']) == 2
            assert len(result['s2']) == 1
            assert len(result['s3']) == 0

    def test_batch_empty_input(self, facade):
        """Empty source_ids list returns empty dict."""
        result = facade.match_concepts_for_sources_batch([])
        assert result == {}
