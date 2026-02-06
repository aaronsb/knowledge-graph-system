"""
Tests for the Cypher safety guard (ADR-500 Phase 2a).

Validates that the guard correctly rejects write operations and unbounded
paths while allowing legitimate read queries through.

These are unit tests — no database, no Docker, no running platform needed.
"""

import pytest

from api.app.services.cypher_guard import check_cypher_safety


class TestWriteKeywordRejection:
    """Guard rejects Cypher containing write keywords (V010-V016)."""

    def test_create_rejected(self):
        issues = check_cypher_safety("CREATE (n:Concept {label: 'test'})")
        assert any(i.rule_id == 'V010' for i in issues)

    def test_set_rejected(self):
        issues = check_cypher_safety("MATCH (n) SET n.label = 'hacked'")
        assert any(i.rule_id == 'V011' for i in issues)

    def test_delete_rejected(self):
        issues = check_cypher_safety("MATCH (n) DELETE n")
        assert any(i.rule_id == 'V012' for i in issues)

    def test_merge_rejected(self):
        issues = check_cypher_safety("MERGE (n:Concept {label: 'test'})")
        assert any(i.rule_id == 'V013' for i in issues)

    def test_remove_rejected(self):
        issues = check_cypher_safety("MATCH (n) REMOVE n.label")
        assert any(i.rule_id == 'V014' for i in issues)

    def test_drop_rejected(self):
        issues = check_cypher_safety("DROP GRAPH my_graph CASCADE")
        assert any(i.rule_id == 'V015' for i in issues)

    def test_detach_delete_rejected(self):
        """Little Nicky Nodes' classic move."""
        issues = check_cypher_safety("MATCH (n) DETACH DELETE n")
        assert any(i.rule_id == 'V016' for i in issues)
        assert any(i.rule_id == 'V012' for i in issues)

    def test_case_insensitive(self):
        issues = check_cypher_safety("match (n) detach delete n")
        assert any(i.rule_id == 'V016' for i in issues)

    def test_keyword_in_string_literal_allowed(self):
        """'DELETE' inside a string is not a write operation."""
        issues = check_cypher_safety(
            "MATCH (c:Concept) WHERE c.label = 'DELETE this concept' RETURN c"
        )
        assert not any(i.rule_id == 'V012' for i in issues)

    def test_keyword_in_comment_allowed(self):
        issues = check_cypher_safety(
            "MATCH (c:Concept) -- DELETE is not real\nRETURN c"
        )
        assert not any(i.rule_id == 'V012' for i in issues)


class TestVariableLengthPathRejection:
    """Guard rejects unbounded variable-length paths (V030)."""

    def test_unbounded_star_rejected(self):
        issues = check_cypher_safety("MATCH (a)-[*]->(b) RETURN a, b")
        assert any(i.rule_id == 'V030' for i in issues)

    def test_no_upper_bound_rejected(self):
        issues = check_cypher_safety("MATCH (a)-[*3..]->(b) RETURN a, b")
        assert any(i.rule_id == 'V030' for i in issues)

    def test_excessive_depth_rejected(self):
        issues = check_cypher_safety("MATCH (a)-[*1..20]->(b) RETURN a, b")
        assert any(i.rule_id == 'V030' for i in issues)

    def test_bounded_path_allowed(self):
        issues = check_cypher_safety("MATCH (a)-[*1..3]->(b) RETURN a, b")
        assert not any(i.rule_id == 'V030' for i in issues)

    def test_fixed_depth_allowed(self):
        issues = check_cypher_safety("MATCH (a)-[*2]->(b) RETURN a, b")
        assert not any(i.rule_id == 'V030' for i in issues)

    def test_star_in_string_literal_allowed(self):
        issues = check_cypher_safety(
            "MATCH (c:Concept) WHERE c.label = '[*] is a pattern' RETURN c"
        )
        assert not any(i.rule_id == 'V030' for i in issues)


class TestCleanQueriesPass:
    """Legitimate read queries pass through the guard without issues."""

    def test_simple_match(self):
        issues = check_cypher_safety(
            "MATCH (c:Concept)-[r]->(n:Concept) RETURN c, r, n LIMIT 50"
        )
        assert issues == []

    def test_where_clause(self):
        issues = check_cypher_safety(
            "MATCH (c:Concept) WHERE c.label CONTAINS 'graph' RETURN c"
        )
        assert issues == []

    def test_bounded_path_query(self):
        issues = check_cypher_safety(
            "MATCH p=(a:Concept)-[*1..3]->(b:Concept) RETURN p"
        )
        assert issues == []

    def test_aggregation(self):
        issues = check_cypher_safety(
            "MATCH (c:Concept)-[r]->() RETURN c.label, count(r) ORDER BY count(r) DESC"
        )
        assert issues == []

    def test_optional_match(self):
        issues = check_cypher_safety(
            "MATCH (c:Concept) OPTIONAL MATCH (c)-[r]->(n) RETURN c, r, n"
        )
        assert issues == []

    def test_with_clause(self):
        issues = check_cypher_safety(
            "MATCH (c:Concept) WITH c, size((c)-->()) AS degree RETURN c, degree"
        )
        assert issues == []


class TestStatementIndex:
    """Guard uses index -1 since queries aren't part of a program."""

    def test_statement_index_is_negative_one(self):
        issues = check_cypher_safety("MATCH (n) DELETE n")
        assert all(i.statement == -1 for i in issues)
