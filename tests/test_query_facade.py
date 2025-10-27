"""
Unit tests for GraphQueryFacade.

Tests namespace-safe query interface for Apache AGE (ADR-048).
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from src.api.lib.query_facade import GraphQueryFacade, QueryAuditLog


class TestQueryAuditLog:
    """Test QueryAuditLog class."""

    def test_log_safe_query(self):
        """Test logging safe queries."""
        audit = QueryAuditLog()

        audit.log_query(
            query="MATCH (c:Concept) RETURN c",
            namespace="concept",
            is_raw=False
        )

        stats = audit.get_stats()
        assert stats['total_queries'] == 1
        assert stats['safe_queries'] == 1
        assert stats['raw_queries'] == 0
        assert stats['safety_ratio'] == 1.0

    def test_log_raw_query(self):
        """Test logging raw queries."""
        audit = QueryAuditLog()

        audit.log_query(
            query="MATCH (n) RETURN n",
            namespace="migration",
            is_raw=True
        )

        stats = audit.get_stats()
        assert stats['total_queries'] == 1
        assert stats['safe_queries'] == 0
        assert stats['raw_queries'] == 1
        assert stats['safety_ratio'] == 0.0

    def test_mixed_queries(self):
        """Test mixed safe and raw queries."""
        audit = QueryAuditLog()

        # 3 safe queries
        for i in range(3):
            audit.log_query(f"MATCH (c:Concept) RETURN c", "concept", is_raw=False)

        # 1 raw query
        audit.log_query("MATCH (n) RETURN n", "unknown", is_raw=True)

        stats = audit.get_stats()
        assert stats['total_queries'] == 4
        assert stats['safe_queries'] == 3
        assert stats['raw_queries'] == 1
        assert stats['safety_ratio'] == 0.75

    def test_empty_audit_log(self):
        """Test audit log with no queries."""
        audit = QueryAuditLog()

        stats = audit.get_stats()
        assert stats['total_queries'] == 0
        assert stats['safe_queries'] == 0
        assert stats['raw_queries'] == 0
        assert stats['safety_ratio'] == 1.0  # Default to perfect score


class TestGraphQueryFacade:
    """Test GraphQueryFacade class."""

    @pytest.fixture
    def mock_age_client(self):
        """Provide mock AGEClient."""
        client = Mock()
        client._execute_cypher = Mock(return_value=[])
        return client

    @pytest.fixture
    def facade(self, mock_age_client):
        """Provide GraphQueryFacade with mock client."""
        return GraphQueryFacade(mock_age_client)

    # =========================================================================
    # Concept Namespace Methods
    # =========================================================================

    def test_match_concepts_basic(self, facade, mock_age_client):
        """Test basic concept matching."""
        mock_age_client._execute_cypher.return_value = [
            {'c': {'properties': {'label': 'Test Concept'}}}
        ]

        results = facade.match_concepts()

        # Verify query structure
        call_args = mock_age_client._execute_cypher.call_args
        query = call_args[0][0]
        assert 'MATCH (c:Concept)' in query
        assert 'RETURN c' in query

        # Verify results
        assert len(results) == 1

    def test_match_concepts_with_where(self, facade, mock_age_client):
        """Test concept matching with WHERE clause."""
        facade.match_concepts(where="c.label =~ '(?i).*test.*'")

        call_args = mock_age_client._execute_cypher.call_args
        query = call_args[0][0]
        assert 'WHERE c.label =~' in query

    def test_match_concepts_with_limit(self, facade, mock_age_client):
        """Test concept matching with limit."""
        facade.match_concepts(limit=10)

        call_args = mock_age_client._execute_cypher.call_args
        query = call_args[0][0]
        assert 'LIMIT 10' in query

    def test_match_concept_relationships(self, facade, mock_age_client):
        """Test matching concept relationships."""
        facade.match_concept_relationships(
            rel_types=["IMPLIES", "SUPPORTS"],
            where="r.edge_count > 5"
        )

        call_args = mock_age_client._execute_cypher.call_args
        query = call_args[0][0]
        assert 'MATCH (c1:Concept)-[r:IMPLIES|SUPPORTS]->(c2:Concept)' in query
        assert 'WHERE r.edge_count > 5' in query
        assert 'RETURN c1, r, c2' in query

    def test_count_concepts(self, facade, mock_age_client):
        """Test counting concepts."""
        mock_age_client._execute_cypher.return_value = {'node_count': 42}

        count = facade.count_concepts()

        assert count == 42

        # Verify query
        call_args = mock_age_client._execute_cypher.call_args
        query = call_args[0][0]
        assert 'MATCH (c:Concept)' in query
        assert 'count(c) as node_count' in query

    def test_count_concepts_with_where(self, facade, mock_age_client):
        """Test counting concepts with filter."""
        mock_age_client._execute_cypher.return_value = {'node_count': 10}

        count = facade.count_concepts(where="c.label =~ '(?i).*graph.*'")

        assert count == 10

        call_args = mock_age_client._execute_cypher.call_args
        query = call_args[0][0]
        assert 'WHERE c.label =~' in query

    # =========================================================================
    # Vocabulary Namespace Methods
    # =========================================================================

    def test_match_vocab_types(self, facade, mock_age_client):
        """Test matching vocabulary types."""
        mock_age_client._execute_cypher.return_value = [
            {'v': {'properties': {'name': 'ENHANCES'}}}
        ]

        results = facade.match_vocab_types(where="v.is_active = true")

        # Verify query structure
        call_args = mock_age_client._execute_cypher.call_args
        query = call_args[0][0]
        assert 'MATCH (v:VocabType)' in query
        assert 'WHERE v.is_active = true' in query
        assert 'RETURN v' in query

    def test_match_vocab_categories(self, facade, mock_age_client):
        """Test matching vocabulary categories."""
        facade.match_vocab_categories()

        call_args = mock_age_client._execute_cypher.call_args
        query = call_args[0][0]
        assert 'MATCH (c:VocabCategory)' in query
        assert 'RETURN c' in query

    def test_find_vocabulary_synonyms(self, facade, mock_age_client):
        """Test finding vocabulary synonyms."""
        facade.find_vocabulary_synonyms(
            min_similarity=0.85,
            category="causation",
            limit=10
        )

        call_args = mock_age_client._execute_cypher.call_args
        query = call_args[0][0]
        assert 'MATCH (v1:VocabType)-[s:SIMILAR_TO]->(v2:VocabType)' in query
        assert 's.similarity >= 0.85' in query
        assert "v1.category = 'causation'" in query
        assert 'LIMIT 10' in query

    def test_count_vocab_types(self, facade, mock_age_client):
        """Test counting vocabulary types."""
        mock_age_client._execute_cypher.return_value = {'node_count': 118}

        count = facade.count_vocab_types()

        assert count == 118

        call_args = mock_age_client._execute_cypher.call_args
        query = call_args[0][0]
        assert 'MATCH (v:VocabType)' in query
        assert 'count(v) as node_count' in query

    # =========================================================================
    # Source & Instance Namespace Methods
    # =========================================================================

    def test_match_sources(self, facade, mock_age_client):
        """Test matching source nodes."""
        facade.match_sources(where="s.document = 'test.md'")

        call_args = mock_age_client._execute_cypher.call_args
        query = call_args[0][0]
        assert 'MATCH (s:Source)' in query
        assert "WHERE s.document = 'test.md'" in query

    def test_match_instances(self, facade, mock_age_client):
        """Test matching instance nodes."""
        facade.match_instances(limit=50)

        call_args = mock_age_client._execute_cypher.call_args
        query = call_args[0][0]
        assert 'MATCH (i:Instance)' in query
        assert 'LIMIT 50' in query

    # =========================================================================
    # Statistics Methods
    # =========================================================================

    def test_get_graph_stats(self, facade, mock_age_client):
        """Test namespace-aware graph statistics."""
        # Mock different counts for different labels
        def mock_execute(query, params=None, fetch_one=False):
            if ':Concept' in query:
                return {'node_count': 2851}
            elif ':Source' in query:
                return {'node_count': 712}
            elif ':Instance' in query:
                return {'node_count': 4486}
            elif ':VocabType' in query:
                return {'node_count': 118}
            elif ':VocabCategory' in query:
                return {'node_count': 8}
            return {'node_count': 0}

        mock_age_client._execute_cypher.side_effect = mock_execute

        stats = facade.get_graph_stats()

        assert stats['concept_graph']['concepts'] == 2851
        assert stats['concept_graph']['sources'] == 712
        assert stats['concept_graph']['instances'] == 4486
        assert stats['vocabulary_graph']['types'] == 118
        assert stats['vocabulary_graph']['categories'] == 8
        assert stats['total_nodes'] == 8175

    # =========================================================================
    # Escape Hatch Methods
    # =========================================================================

    def test_execute_raw_logs_warning(self, facade, mock_age_client, caplog):
        """Test that execute_raw logs warning."""
        facade.execute_raw(
            "MATCH (n) RETURN n",
            namespace="migration"
        )

        # Verify warning was logged
        assert any("escape hatch" in record.message.lower() for record in caplog.records)

    def test_execute_raw_tracks_as_raw(self, facade, mock_age_client):
        """Test that execute_raw queries are tracked as raw."""
        facade.execute_raw("MATCH (n) RETURN n", namespace="test")

        stats = facade.get_audit_stats()
        assert stats['raw_queries'] == 1
        assert stats['safe_queries'] == 0

    def test_execute_raw_with_fetch_one(self, facade, mock_age_client):
        """Test execute_raw with fetch_one parameter."""
        mock_age_client._execute_cypher.return_value = {'result': 'value'}

        result = facade.execute_raw(
            "MATCH (n:Concept) RETURN n LIMIT 1",
            namespace="test",
            fetch_one=True
        )

        # Verify fetch_one was passed through
        call_args = mock_age_client._execute_cypher.call_args
        assert call_args[1]['fetch_one'] is True

    # =========================================================================
    # Audit & Metrics
    # =========================================================================

    def test_audit_tracks_all_queries(self, facade, mock_age_client):
        """Test that all queries are tracked in audit log."""
        mock_age_client._execute_cypher.return_value = []

        # Make various queries
        facade.count_concepts()
        facade.match_vocab_types()
        facade.execute_raw("MATCH (n) RETURN n", namespace="test")

        stats = facade.get_audit_stats()
        assert stats['total_queries'] == 3
        assert stats['safe_queries'] == 2
        assert stats['raw_queries'] == 1
        assert stats['safety_ratio'] == pytest.approx(0.666, rel=0.01)

    def test_get_audit_stats(self, facade):
        """Test getting audit statistics."""
        stats = facade.get_audit_stats()

        assert 'total_queries' in stats
        assert 'safe_queries' in stats
        assert 'raw_queries' in stats
        assert 'safety_ratio' in stats

    def test_log_audit_summary(self, facade, mock_age_client, caplog):
        """Test logging audit summary."""
        import logging
        caplog.set_level(logging.INFO)

        # Make some queries
        facade.count_concepts()

        facade.log_audit_summary()

        # Verify summary was logged
        assert any("Audit Summary" in record.message for record in caplog.records), \
            f"Expected 'Audit Summary' in logs, got: {[r.message for r in caplog.records]}"

    # =========================================================================
    # Parameter Handling
    # =========================================================================

    def test_params_passed_through(self, facade, mock_age_client):
        """Test that query parameters are passed through."""
        params = {'label': 'test'}

        facade.match_concepts(
            where="c.label = $label",
            params=params
        )

        call_args = mock_age_client._execute_cypher.call_args
        assert call_args[0][1] == params

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_count_with_no_results(self, facade, mock_age_client):
        """Test count methods when no results."""
        mock_age_client._execute_cypher.return_value = None

        count = facade.count_concepts()

        assert count == 0

    def test_empty_result_set(self, facade, mock_age_client):
        """Test methods with empty result sets."""
        mock_age_client._execute_cypher.return_value = []

        results = facade.match_concepts()

        assert results == []
        assert isinstance(results, list)


class TestGraphQueryFacadeIntegration:
    """Integration tests for GraphQueryFacade."""

    @pytest.mark.integration
    def test_facade_with_real_client(self):
        """
        Test facade with real AGEClient.

        Requires database connection - marked as integration test.
        """
        pytest.skip("Integration test - requires database")

        from src.api.lib.age_client import AGEClient

        client = AGEClient()
        facade = client.facade

        # Test basic operations
        count = facade.count_concepts()
        assert isinstance(count, int)
        assert count >= 0

        stats = facade.get_graph_stats()
        assert 'concept_graph' in stats
        assert 'vocabulary_graph' in stats

    @pytest.mark.parametrize("method_name,kwargs", [
        ("match_concepts", {"where": "c.label =~ '.*test.*'"}),
        ("match_vocab_types", {"where": "v.is_active = true"}),
        ("match_concept_relationships", {"rel_types": ["IMPLIES"]}),
        ("count_concepts", {}),
        ("count_vocab_types", {}),
    ])
    def test_namespace_isolation(self, method_name, kwargs):
        """
        Test that all methods enforce namespace isolation.

        Verify that queries always include explicit labels.
        """
        # Create fresh mock for each test
        mock_client = Mock()
        mock_client._execute_cypher = Mock(return_value=[])
        facade = GraphQueryFacade(mock_client)

        # Call the method
        method = getattr(facade, method_name)
        method(**kwargs)

        # Get the query that was executed
        call_args = mock_client._execute_cypher.call_args
        query = call_args[0][0]

        # Verify explicit labels are present
        # All queries should have at least one explicit label
        assert (
            ':Concept' in query or
            ':VocabType' in query or
            ':VocabCategory' in query or
            ':Source' in query or
            ':Instance' in query
        ), f"Query missing explicit label: {query}"
