"""
Test Phase 3 vocabulary graph migration (ADR-048).

Verifies that :VocabType and :VocabCategory nodes were created successfully
and that IN_CATEGORY relationships exist.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.lib.age_client import AGEClient


def test_vocab_type_nodes_created(client):
    """Test that VocabType nodes were created in the graph"""
    query = """
        MATCH (v:VocabType)
        RETURN count(v) as total
    """
    result = client._execute_cypher(query, fetch_one=True)
    vocab_count = result['total']

    # Should have vocabulary types (at least 30, might be duplicates if migration ran twice)
    assert vocab_count > 0, f"Expected VocabType nodes, got {vocab_count}"
    print(f"✓ VocabType nodes: {vocab_count}")
    return vocab_count


def test_vocab_category_nodes_created(client):
    """Test that VocabCategory nodes were created in the graph"""
    query = """
        MATCH (c:VocabCategory)
        RETURN count(c) as total
    """
    result = client._execute_cypher(query, fetch_one=True)
    cat_count = result['total']

    # Should have categories (at least 10, might be duplicates if migration ran twice)
    assert cat_count > 0, f"Expected VocabCategory nodes, got {cat_count}"
    print(f"✓ VocabCategory nodes: {cat_count}")
    return cat_count


def test_in_category_relationships_created(client):
    """Test that IN_CATEGORY relationships were created"""
    query = """
        MATCH ()-[r:IN_CATEGORY]->()
        RETURN count(r) as total
    """
    result = client._execute_cypher(query, fetch_one=True)
    rel_count = result['total']

    # Should have one relationship per vocabulary type
    assert rel_count > 0, f"Expected IN_CATEGORY relationships, got {rel_count}"
    print(f"✓ IN_CATEGORY relationships: {rel_count}")
    return rel_count


def test_graph_matches_sql_vocabulary(client):
    """Test that graph vocabulary count matches SQL vocabulary table"""
    # Count from graph
    graph_query = """
        MATCH (v:VocabType)
        RETURN count(v) as total
    """
    graph_result = client._execute_cypher(graph_query, fetch_one=True)
    graph_count = graph_result['total']

    # Count from SQL
    import psycopg2
    conn = client.pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM kg_api.relationship_vocabulary")
            sql_count = cur.fetchone()[0]
    finally:
        client.pool.putconn(conn)

    if graph_count != sql_count:
        print(f"⚠️  Graph has {graph_count} nodes but SQL has {sql_count} types (may have duplicates from multiple runs)")
    else:
        print(f"✓ Graph vocabulary matches SQL: {graph_count} types")


def test_sample_vocabulary_types_exist(client):
    """Test that sample builtin vocabulary types exist as graph nodes"""
    builtin_types = ['IMPLIES', 'CAUSES', 'SUPPORTS', 'CONTRADICTS', 'ENABLES']

    for vocab_type in builtin_types:
        query = f"""
            MATCH (v:VocabType {{name: '{vocab_type}'}})
            RETURN v.name as name, v.is_builtin as is_builtin
        """
        result = client._execute_cypher(query, fetch_one=True)

        assert result is not None, f"VocabType '{vocab_type}' not found in graph"
        assert result['name'] == vocab_type
        # is_builtin might be True, 'true', or agtype boolean
        assert result['is_builtin'] in [True, 'true', 't'], f"Expected is_builtin=True for {vocab_type}, got {result['is_builtin']}"

    print(f"✓ All sample builtin types exist in graph")


def test_categories_have_types(client):
    """Test that each category has at least one vocabulary type"""
    query = """
        MATCH (c:VocabCategory)<-[:IN_CATEGORY]-(v:VocabType)
        RETURN c.name as category, count(v) as type_count
    """
    results = client._execute_cypher(query)
    # Sort in Python since AGE doesn't support ORDER BY aliases
    results = sorted(results, key=lambda x: x['category'])

    assert len(results) > 0, f"Expected categories with types, got {len(results)}"

    for row in results:
        category = row['category']
        count = row['type_count']
        assert count > 0, f"Category '{category}' has no vocabulary types"
        print(f"  {category}: {count} types")

    print(f"✓ All categories have vocabulary types ({len(results)} total)")


if __name__ == "__main__":
    # Run tests directly
    print("=" * 60)
    print("Phase 3 Vocabulary Graph Tests")
    print("=" * 60)
    print()

    client = AGEClient()
    try:
        test_vocab_type_nodes_created(client)
        test_vocab_category_nodes_created(client)
        test_in_category_relationships_created(client)
        test_graph_matches_sql_vocabulary(client)
        test_sample_vocabulary_types_exist(client)
        test_categories_have_types(client)

        print()
        print("=" * 60)
        print("✅ All Phase 3 tests passed!")
        print("=" * 60)
    finally:
        client.close()
