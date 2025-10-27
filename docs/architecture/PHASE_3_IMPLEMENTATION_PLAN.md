# Phase 3 Implementation Plan: Vocabulary as Graph Nodes

**Status:** In Progress
**Date:** 2025-10-27
**Branch:** `feature/phase3-vocabulary-as-graph`
**Related:** ADR-048, ADR-047

## Current State

### What Exists
- ✅ SQL tables in `kg_api` schema
  - `relationship_vocabulary` (139 types: 30 builtin + 109 custom)
  - `vocabulary_history`, `vocabulary_config`, `synonym_clusters`, etc.
- ✅ Phase 1: GraphQueryFacade (namespace safety)
- ✅ Phase 2: All unsafe queries fixed (0 unsafe queries)
- ✅ Categories assigned to all types (causation, semantic, composition, etc.)

### What Doesn't Exist
- ❌ :VocabType nodes in graph
- ❌ :VocabCategory nodes in graph
- ❌ Graph relationships: -[:IN_CATEGORY]->, -[:SIMILAR_TO]->, -[:HAS_SEED]->

## Phase 3 Goals

Migrate vocabulary from SQL to graph while maintaining backward compatibility.

**Strategy:** Parallel SQL/graph approach
1. Create graph nodes alongside existing SQL
2. Keep both in sync during transition
3. Update queries incrementally
4. Eventually deprecate SQL (optional)

## Implementation Steps

### Step 1: Create Schema Migration
**File:** `schema/migrations/014_vocabulary_as_graph.sql`

**Create Node Initialization Function:**
```sql
-- Function to create :VocabType and :VocabCategory nodes from SQL data
CREATE OR REPLACE FUNCTION kg_api.sync_vocabulary_to_graph()
RETURNS void AS $$
DECLARE
    vocab_row RECORD;
    category_row RECORD;
BEGIN
    -- Create :VocabCategory nodes (one per unique category)
    FOR category_row IN
        SELECT DISTINCT category, COUNT(*) as type_count
        FROM kg_api.relationship_vocabulary
        WHERE is_active = true
        GROUP BY category
    LOOP
        -- Create or update category node
        PERFORM * FROM cypher('knowledge_graph', $$
            MERGE (c:VocabCategory {name: $1})
            SET c.type_count = $2,
                c.updated_at = NOW()
        $$, array[category_row.category, category_row.type_count]::text[]);
    END LOOP;

    -- Create :VocabType nodes (one per vocabulary type)
    FOR vocab_row IN
        SELECT
            relationship_type,
            category,
            edge_count,
            is_active,
            is_builtin,
            embedding
        FROM kg_api.relationship_vocabulary
    LOOP
        -- Create or update vocab type node
        PERFORM * FROM cypher('knowledge_graph', $$
            MERGE (v:VocabType {name: $1})
            SET v.edge_count = $2,
                v.is_active = $3,
                v.is_builtin = $4,
                v.updated_at = NOW()
        $$, array[
            vocab_row.relationship_type,
            vocab_row.edge_count::text,
            vocab_row.is_active::text,
            vocab_row.is_builtin::text
        ]::text[]);

        -- Create -[:IN_CATEGORY]-> relationship
        PERFORM * FROM cypher('knowledge_graph', $$
            MATCH (v:VocabType {name: $1})
            MATCH (c:VocabCategory {name: $2})
            MERGE (v)-[:IN_CATEGORY]->(c)
        $$, array[vocab_row.relationship_type, vocab_row.category]::text[]);
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

**Add Trigger for Auto-Sync:**
```sql
-- Trigger function to sync changes to graph
CREATE OR REPLACE FUNCTION kg_api.sync_vocabulary_change_to_graph()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR TG_OP = 'UPDATE' THEN
        -- Update :VocabType node
        PERFORM * FROM cypher('knowledge_graph', $$
            MERGE (v:VocabType {name: $1})
            SET v.edge_count = $2,
                v.is_active = $3,
                v.is_builtin = $4,
                v.updated_at = NOW()
        $$, array[
            NEW.relationship_type,
            NEW.edge_count::text,
            NEW.is_active::text,
            NEW.is_builtin::text
        ]::text[]);

        -- Update -[:IN_CATEGORY]-> relationship
        PERFORM * FROM cypher('knowledge_graph', $$
            MATCH (v:VocabType {name: $1})
            MATCH (c:VocabCategory {name: $2})
            MERGE (v)-[:IN_CATEGORY]->(c)
        $$, array[NEW.relationship_type, NEW.category]::text[]);

        RETURN NEW;
    ELSIF TG_OP = 'DELETE' THEN
        -- Mark node as inactive instead of deleting
        PERFORM * FROM cypher('knowledge_graph', $$
            MATCH (v:VocabType {name: $1})
            SET v.is_active = false,
                v.updated_at = NOW()
        $$, array[OLD.relationship_type]::text[]);

        RETURN OLD;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Attach trigger
CREATE TRIGGER vocabulary_sync_trigger
AFTER INSERT OR UPDATE OR DELETE ON kg_api.relationship_vocabulary
FOR EACH ROW EXECUTE FUNCTION kg_api.sync_vocabulary_change_to_graph();
```

### Step 2: Add GraphQueryFacade Methods
**File:** `src/api/lib/query_facade.py`

Add methods for vocabulary namespace:

```python
def match_vocab_types(self, where: str = None, params: dict = None):
    """SAFE: Always includes :VocabType label."""
    query = "MATCH (v:VocabType)"
    if where:
        query += f" WHERE {where}"
    query += " RETURN v"

    self._log_query(query, params, namespace="vocabulary")
    return self.db._execute_cypher(query, params)

def match_vocab_categories(self, where: str = None, params: dict = None):
    """SAFE: Always includes :VocabCategory label."""
    query = "MATCH (c:VocabCategory)"
    if where:
        query += f" WHERE {where}"
    query += " RETURN c"

    self._log_query(query, params, namespace="vocabulary")
    return self.db._execute_cypher(query, params)

def find_vocabulary_synonyms(self, category: str, threshold: float):
    """SAFE: Explicit :VocabType and :VocabCategory labels."""
    query = """
        MATCH (v1:VocabType)-[:IN_CATEGORY]->(c:VocabCategory {name: $category})
        MATCH (v2:VocabType)-[:IN_CATEGORY]->(c)
        MATCH (v1)-[s:SIMILAR_TO]->(v2)
        WHERE s.similarity > $threshold
        RETURN v1, v2, s.similarity
    """

    self._log_query(query, {"category": category, "threshold": threshold}, namespace="vocabulary")
    return self.db._execute_cypher(query, {"category": category, "threshold": threshold})
```

### Step 3: Update AGEClient with Graph-Native Methods
**File:** `src/api/lib/age_client.py`

Add new methods that use graph instead of SQL:

```python
def get_vocabulary_from_graph(self) -> List[Dict]:
    """Get all vocabulary types from graph (namespace-aware)."""
    query = """
        MATCH (v:VocabType)-[:IN_CATEGORY]->(c:VocabCategory)
        RETURN v.name as relationship_type,
               c.name as category,
               v.edge_count as edge_count,
               v.is_active as is_active,
               v.is_builtin as is_builtin
        ORDER BY v.name
    """
    return self.facade.execute_raw(query, namespace="vocabulary")

def get_vocabulary_size_from_graph(self) -> int:
    """Get vocabulary size from graph (namespace-aware)."""
    query = """
        MATCH (v:VocabType)
        WHERE v.is_active = true
        RETURN count(v) as size
    """
    result = self.facade.execute_raw(query, namespace="vocabulary")
    return result[0]['size'] if result else 0
```

### Step 4: Add Feature Flag for Gradual Rollout
**File:** `.env` (add configuration)

```bash
# Phase 3: Vocabulary as Graph (ADR-048)
USE_VOCABULARY_GRAPH=false  # Start with SQL, flip to true after testing
```

**File:** `src/api/lib/age_client.py` (add dual-mode support)

```python
def get_vocabulary_size(self) -> int:
    """Get vocabulary size (supports SQL and graph modes)."""
    if os.getenv('USE_VOCABULARY_GRAPH', 'false').lower() == 'true':
        return self.get_vocabulary_size_from_graph()
    else:
        return self._get_vocabulary_size_from_sql()
```

### Step 5: Testing Plan

**Unit Tests:**
- Test graph node creation from SQL data
- Test trigger sync (INSERT, UPDATE, DELETE)
- Test GraphQueryFacade vocabulary methods
- Test AGEClient dual-mode (SQL vs graph)

**Integration Tests:**
1. Initialize vocabulary graph from SQL
2. Verify node counts match SQL counts
3. Test sync: update SQL, verify graph updates
4. Test category relationships
5. Flip feature flag, verify queries work

**Verification Commands:**
```bash
# Check node counts
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT * FROM ag_catalog.cypher('knowledge_graph', \$\$
    MATCH (v:VocabType)
    RETURN count(v) as vocab_count
\$\$) AS (vocab_count integer)"

# Check categories
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT * FROM ag_catalog.cypher('knowledge_graph', \$\$
    MATCH (c:VocabCategory)
    RETURN c.name as category, c.type_count as count
\$\$) AS (category text, count integer)"

# Verify relationships
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
SELECT * FROM ag_catalog.cypher('knowledge_graph', \$\$
    MATCH (v:VocabType)-[:IN_CATEGORY]->(c:VocabCategory)
    RETURN v.name, c.name
    LIMIT 10
\$\$) AS (vocab_type text, category text)"
```

## Success Criteria

- [ ] All 139 vocabulary types exist as :VocabType nodes
- [ ] All 8 categories exist as :VocabCategory nodes
- [ ] All types connected to categories via -[:IN_CATEGORY]->
- [ ] SQL changes automatically sync to graph (trigger works)
- [ ] GraphQueryFacade methods work correctly
- [ ] Feature flag allows switching between SQL/graph
- [ ] All existing tests pass
- [ ] Linter shows 0 unsafe queries

## Rollback Plan

If issues occur:
1. Set `USE_VOCABULARY_GRAPH=false` (revert to SQL)
2. All code still works (dual-mode support)
3. Fix issues in graph layer
4. Re-test and flip flag again

## Timeline

- **Day 1:** Create migration + sync function
- **Day 2:** Add GraphQueryFacade methods + AGEClient support
- **Day 3:** Testing + verification
- **Day 4:** PR review + merge

## Related Files

- `schema/migrations/014_vocabulary_as_graph.sql` (NEW)
- `src/api/lib/query_facade.py` (UPDATE)
- `src/api/lib/age_client.py` (UPDATE)
- `docs/architecture/QUERY_SAFETY_BASELINE.md` (UPDATE with new baseline)
- `.env.example` (ADD feature flag)

---

**Last Updated:** 2025-10-27
**Status:** Planning Complete - Ready for Implementation
