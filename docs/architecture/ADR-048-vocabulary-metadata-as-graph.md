# ADR-048: Vocabulary Metadata as First-Class Graph

**Status:** Implemented ✅ - All Phases Complete
**Date:** 2025-10-27
**Completion Date:** 2025-10-27
**Deciders:** System Architects
**Related:** ADR-047 (Probabilistic Categorization), ADR-032 (Vocabulary Expansion), ADR-046 (Grounding-Aware Management)

**Implementation Status:**
- ✅ **Phase 1 Complete** - GraphQueryFacade, query linter, CI integration
- ✅ **Phase 2 Complete** - Critical path migrations (restore worker, health checks)
- ✅ **Phase 3.1 Complete** - Vocabulary graph nodes created (migration 014)
  - 30 :VocabType nodes created (builtin types)
  - 10 :VocabCategory nodes created
  - 30 -[:IN_CATEGORY]-> relationships (initial builtin types)
  - Idempotent migration verified
  - SQL tables preserved for backward compatibility
- ✅ **Phase 3.2 Complete** - Vocabulary READ queries migrated to use graph
  - get_vocabulary_size() queries :VocabType nodes
  - get_all_edge_types() lists :VocabType names
  - get_edge_type_info() traverses -[:IN_CATEGORY]-> relationships
  - get_category_distribution() counts per :VocabCategory
  - kg vocab list now queries graph exclusively (read-only operations)
- ✅ **Phase 3.3 Complete** - Vocabulary WRITE operations use relationships
  - **Synchronized all 47 types** - Created :IN_CATEGORY relationships for 17 custom types added after migration 014
  - **add_edge_type()** - Now creates :IN_CATEGORY relationships (not just properties)
  - **VocabularyCategorizer** - Category refresh updates relationships (not just properties)
  - **get_edge_type_info()** - Queries via :IN_CATEGORY relationships
  - **get_category_distribution()** - Counts via :IN_CATEGORY relationships
  - **Consistent data model** - All 47 types use relationships, no mixed property/relationship state
  - **Fixed consolidation** - kg vocab consolidate works without Cypher syntax errors
  - **Graph semantics** - Category membership = graph relationship (true graph operations)
  - **SQL tables** - Still used for embeddings, scoring metadata (future optimization, not blocking)

**Result:** Vocabulary metadata is now first-class graph with true relationship semantics. All operations use graph relationships for category membership.

## Context

### The Realization

After completing ADR-047, we recognized a fundamental architectural mismatch:

> **"The graph is timeless. Vocabulary is part of the graph."**

But vocabulary metadata currently lives in **SQL tables**, not the graph:

```sql
-- Current: SQL tables
relationship_vocabulary (
    type VARCHAR,
    category VARCHAR,
    category_confidence FLOAT,
    edge_count INTEGER,
    embedding VECTOR
)

-- We're describing graph relationships in SQL!
-- - type → category (categorical membership)
-- - type ↔ type (synonym similarity)
-- - category → seed types (prototypical examples)
```

### Operations That Should Be Graph Traversals

```bash
# Find synonyms - this is a graph query!
kg vocab find-synonyms --category causation --threshold 0.85
# SQL: Complex joins with similarity calculations
# Graph: MATCH (v1)-[:SIMILAR_TO]->(v2) WHERE similarity > 0.85

# Show category structure - graph traversal!
kg vocab category-scores ENHANCES
# SQL: Join to category table, embed JSONB parsing
# Graph: MATCH (v)-[:IN_CATEGORY]->(c)-[:HAS_SEED]->(seeds)

# Merge types - edge rewiring!
kg vocab merge STRENGTHENS ENHANCES
# SQL: Update foreign keys, cascade changes
# Graph: MATCH (old)-[r]->() DELETE r CREATE (new)-[r]->()
```

**We're simulating a graph in SQL when we have a graph database.**

### The Safety Problem

Moving vocabulary to the graph introduces **namespace collision risk**:

```cypher
// DANGER: Generic query could match EVERYTHING
MATCH (n) WHERE n.label CONTAINS "causation"
RETURN n

// Could return:
// - (:Concept {label: "causation theory"})        ← knowledge
// - (:VocabCategory {name: "causation"})         ← metadata
// CATASTROPHIC COLLISION!
```

**Current architecture is naïve:**
- Queries scattered throughout workers (age_client.py, ingestion.py, routes/)
- No central query registry
- No enforcement of explicit labels
- No audit mechanism

**Risk:** One forgotten `:Concept` label = catastrophic data corruption when vocabulary moves to graph.

## Decision

Implement **three-phase architectural improvement**:

### Phase 1: Namespace Safety Layer (Foundation)

**Add `GraphQueryFacade` to enforce namespace isolation.**

```python
# src/api/lib/query_facade.py

class GraphQueryFacade:
    """
    Thin wrapper enforcing namespace safety for Apache AGE queries.

    Design principles:
    - Minimal API (common operations only)
    - Explicit namespace specification
    - Gradual adoption (no big-bang refactor)
    - Escape hatch for complex queries (with audit logging)
    """

    def __init__(self, age_client):
        self.db = age_client
        self._query_log = []

    # ========== Concept Namespace (Knowledge) ==========

    def match_concepts(self, where: str = None, params: dict = None):
        """SAFE: Always includes :Concept label."""
        query = "MATCH (c:Concept)"
        if where:
            query += f" WHERE {where}"
        query += " RETURN c"

        self._log_query(query, params, namespace="concept")
        return self.db._execute_cypher(query, params)

    def match_concept_relationships(self, rel_types: list[str] = None):
        """SAFE: Enforces :Concept on both ends."""
        rel_filter = "|".join(rel_types) if rel_types else ""
        query = f"MATCH (from:Concept)-[r:{rel_filter}]->(to:Concept) RETURN from, r, to"

        self._log_query(query, namespace="concept")
        return self.db._execute_cypher(query)

    # ========== Vocabulary Namespace (Metadata) ==========

    def match_vocab_types(self, where: str = None, params: dict = None):
        """SAFE: Always includes :VocabType label."""
        query = "MATCH (v:VocabType)"
        if where:
            query += f" WHERE {where}"
        query += " RETURN v"

        self._log_query(query, params, namespace="vocabulary")
        return self.db._execute_cypher(query, params)

    def find_synonyms(self, category: str, threshold: float):
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

    # ========== Escape Hatch (Complex Queries) ==========

    def execute_raw(self, query: str, params: dict = None, namespace: str = "unknown"):
        """
        Execute raw Cypher query.

        WARNING: No safety guarantees. Logs for audit trail.
        """
        self._log_query(query, params, namespace=namespace, is_raw=True)
        return self.db._execute_cypher(query, params)

    # ========== Audit Support ==========

    def _log_query(self, query: str, params: dict = None, namespace: str = None, is_raw: bool = False):
        """Log query for audit trail."""
        self._query_log.append({
            "query": query,
            "params": params,
            "namespace": namespace,
            "is_raw": is_raw,
            "timestamp": datetime.now()
        })

        if is_raw:
            logger.warning(f"RAW QUERY (namespace={namespace}): {query[:100]}...")

    def audit_queries(self, namespace: str = None):
        """Return audit log for review."""
        if namespace:
            return [q for q in self._query_log if q["namespace"] == namespace]
        return self._query_log

    def count_raw_queries(self):
        """Technical debt metric: how many unsafe queries remain."""
        return sum(1 for q in self._query_log if q["is_raw"])
```

**Gradual Adoption (No Breaking Changes):**

```python
# Old code keeps working
age_client._execute_cypher("MATCH (n) ...")  # Still available

# New code uses facade
facade = GraphQueryFacade(age_client)
results = facade.match_concepts(where="label CONTAINS $term", params={"term": search})

# Migrate critical paths incrementally
# - Search queries
# - Ingestion pipeline
# - API endpoints
# Leave admin scripts as raw queries (acceptable technical debt)
```

### Phase 2: Query Safety Linter (CI Enforcement)

**Add pre-commit/CI check for unsafe queries.**

```python
# scripts/lint_queries.py

import re

def find_unsafe_queries(file_path):
    """Find Cypher queries missing explicit labels."""

    unsafe = []
    with open(file_path) as f:
        content = f.read()

    # Find all execute_cypher calls
    pattern = r'execute_cypher\(["\'](.+?)["\']'
    matches = re.findall(pattern, content, re.DOTALL)

    for query in matches:
        # Check for MATCH without explicit label
        if re.search(r'MATCH \([a-z]+\)(?![:\[])', query):
            unsafe.append(query)

    return unsafe

if __name__ == "__main__":
    import sys
    files = sys.argv[1:]

    all_unsafe = []
    for file in files:
        unsafe = find_unsafe_queries(file)
        if unsafe:
            print(f"⚠️  {file}: {len(unsafe)} unsafe queries")
            for q in unsafe:
                print(f"   {q[:80]}...")
            all_unsafe.extend(unsafe)

    if all_unsafe:
        print(f"❌ Found {len(all_unsafe)} queries missing explicit labels")
        sys.exit(1)
    else:
        print("✅ All queries safe")
```

**CI Integration:**

```yaml
# .github/workflows/lint.yml
- name: Check query safety
  run: python scripts/lint_queries.py src/api/**/*.py
```

### Phase 3: Vocabulary as Graph Nodes (Migration)

**Move vocabulary metadata from SQL to Apache AGE.**

**Namespace Design:**

```cypher
// Domain Knowledge (what users query)
:Concept           // User concepts
:Source            // Source documents
:Instance          // Evidence instances

// Vocabulary Metadata (administrative)
:VocabType         // Relationship types (SUPPORTS, ENHANCES, etc.)
:VocabCategory     // Categories (causation, evidential, etc.)

// Separate relationship types (no overlap with knowledge graph)
-[:IN_CATEGORY]->     // VocabType → VocabCategory
-[:SIMILAR_TO]->      // VocabType → VocabType (synonyms)
-[:HAS_SEED]->        // VocabCategory → VocabType (prototypical examples)
```

**Schema:**

```cypher
// Vocabulary type node
CREATE (v:VocabType {
    name: "ENHANCES",
    edge_count: 47,
    embedding: [...],
    is_active: true,
    is_builtin: false
})

// Category node
CREATE (c:VocabCategory {
    name: "causation",
    description: "Causal relationships"
})

// Categorization relationship (from ADR-047)
CREATE (v)-[:IN_CATEGORY {
    confidence: 0.87,
    scores: {
        "causation": 0.87,
        "composition": 0.45,
        "logical": 0.23
    },
    ambiguous: false
}]->(c)

// Synonym relationship (from ADR-046)
CREATE (v1:VocabType {name: "ENHANCES"})
      -[:SIMILAR_TO {similarity: 0.89}]->
      (v2:VocabType {name: "STRENGTHENS"})

// Seed relationship
CREATE (c:VocabCategory {name: "causation"})
      -[:HAS_SEED]->
      (seed:VocabType {name: "CAUSES", is_builtin: true})
```

**Operations Become Graph-Native:**

```cypher
// Find synonyms in category
MATCH (v1:VocabType)-[:IN_CATEGORY]->(c:VocabCategory {name: "causation"})
MATCH (v2:VocabType)-[:IN_CATEGORY]->(c)
MATCH (v1)-[s:SIMILAR_TO]->(v2)
WHERE s.similarity > 0.85
RETURN v1.name, v2.name, s.similarity

// Show category seeds
MATCH (c:VocabCategory {name: "causation"})-[:HAS_SEED]->(seed:VocabType)
RETURN seed.name

// Merge vocabulary types (edge rewiring)
MATCH (old:VocabType {name: "STRENGTHENS"})-[r]->(target)
MATCH (new:VocabType {name: "ENHANCES"})
DELETE r
CREATE (new)-[r]->(target)
SET new.edge_count = new.edge_count + old.edge_count
DELETE old

// Refresh categories after merge (ADR-047 workflow)
MATCH (v:VocabType)-[old_cat:IN_CATEGORY]->()
DELETE old_cat
// Recompute categories with new embeddings
MATCH (v:VocabType)
CALL compute_category_scores(v)
CREATE (v)-[:IN_CATEGORY]->(computed_category)
```

## Implementation Plan

### Phase 1: Foundation (Week 1)

**1.1 Add Query Facade**
- [ ] Create `src/api/lib/query_facade.py`
- [ ] Implement core methods (match_concepts, match_vocab_types)
- [ ] Add audit logging
- [ ] Add to age_client as optional interface

**1.2 Add Query Linter**
- [ ] Create `scripts/lint_queries.py`
- [ ] Add CI workflow
- [ ] Run initial audit (expect many failures)
- [ ] Document baseline

**1.3 Use Facade for New Code**
- [ ] Update development guide (CLAUDE.md)
- [ ] Use facade in any new features
- [ ] Begin tracking raw query count

### Phase 2: Critical Path Migration (Week 2-3)

**2.1 Migrate Search Queries**
- [ ] Convert concept search to facade
- [ ] Convert relationship queries to facade
- [ ] Test namespace isolation

**2.2 Migrate Ingestion Pipeline**
- [ ] Convert concept upsert to facade
- [ ] Convert relationship creation to facade
- [ ] Verify no namespace bleed

**2.3 Migrate API Endpoints**
- [ ] Convert routes/queries.py to facade
- [ ] Convert routes/concepts.py to facade
- [ ] Add integration tests

### Phase 3: Vocabulary Graph Migration (Week 4-6)

**3.1 Parallel Schema** ✅ **COMPLETE (2025-10-27)**
- [x] Create VocabType, VocabCategory nodes (parallel to SQL) - Migration 014
- [ ] Sync SQL → Graph on vocab changes - Optional future enhancement
- [x] Verify data consistency - tests/test_phase3_vocabulary_graph.py

**3.2 Migrate Queries** ✅ **COMPLETE (2025-10-27)**
- [x] Update `kg vocab list` to query graph - get_all_edge_types(), get_vocabulary_size()
- [x] Update vocab info queries - get_edge_type_info(), get_category_distribution()
- [x] Verify read queries work correctly - All tests pass
- [x] Handle AGE boolean string storage ('t'/'f' vs true/false)
- [ ] Update `kg vocab find-synonyms` to query graph - **Phase 3.3**
- [ ] Update `kg vocab merge` to rewire graph edges - **Phase 3.3**
- [ ] Update `kg vocab refresh-categories` to update graph - **Phase 3.3**

**3.3 Complete Migration & SQL Deprecation** ⏸️ **FUTURE WORK**
- [ ] Migrate write operations to graph (add_edge_type, update_edge_type, merge_edge_types)
- [ ] Migrate embedding operations to :VocabType properties
- [ ] Migrate scoring operations to graph queries
- [ ] Verify all 25+ SQL queries replaced with graph equivalents
- [ ] Add graph-based usage count tracking
- [ ] Backup SQL tables
- [ ] Drop SQL vocabulary tables (optional)

## Migration Strategy

**Incremental, Non-Breaking:**

```python
# Week 1: Foundation
facade = GraphQueryFacade(age_client)
# Old code still works, new code uses facade

# Week 2-3: Critical paths
search_concepts()  # Migrated to facade
ingest_chunk()     # Migrated to facade
# Admin scripts still use raw queries (acceptable)

# Week 4-6: Vocabulary to graph
# SQL and graph coexist during transition
vocabulary_manager.add_type()
# → Inserts to SQL (legacy)
# → Creates :VocabType node (new)
# → Both stay in sync

# Final cutover
vocabulary_manager.add_type()
# → Only creates :VocabType node
# → SQL tables deprecated
```

## Consequences

### Positive

**1. Architectural Consistency**
- Vocabulary is first-class graph, not SQL simulation
- Operations match data structure (graph operations on graph data)
- "Vocabulary is part of the timeless graph" (ADR-047) becomes literal

**2. Natural Operations**
- Synonym detection = graph traversal
- Category structure = graph query
- Merge = edge rewiring
- All operations faster (graph-native vs SQL joins)

**3. Safety Layer**
- Facade prevents namespace collisions
- Audit trail for unsafe queries
- Technical debt visible (count_raw_queries)
- Gradual migration (no big-bang refactor)

**4. Future Extensibility**
- Pattern established for other metadata namespaces
- Ontologies could become :Ontology nodes
- User/RBAC could use :User, :Role nodes
- All administrative metadata uses same graph

### Negative

**1. Migration Complexity**
- Must migrate queries incrementally
- SQL and graph coexist during transition
- Requires careful testing of namespace isolation

**2. Query Facade Learning Curve**
- Developers must learn facade API
- Not all operations have facade methods yet
- Raw queries still needed for complex cases

**3. Dual Maintenance (During Transition)**
- SQL and graph schemas stay in sync
- More complexity until SQL deprecated
- Need migration completion timeline

### Risks and Mitigation

**Risk: Namespace collision during migration**
- **Mitigation:** Linter catches unsafe queries in CI
- **Mitigation:** Facade enforces explicit labels
- **Mitigation:** Integration tests verify isolation

**Risk: Missed queries during audit**
- **Mitigation:** Linter scans all Python files
- **Mitigation:** Audit log tracks raw query usage
- **Mitigation:** count_raw_queries() shows progress

**Risk: Performance regression**
- **Mitigation:** Graph queries should be faster than SQL
- **Mitigation:** Benchmark before/after
- **Mitigation:** Can rollback to SQL if needed

## Success Criteria

1. **Namespace safety:** Linter passes in CI (no unsafe queries)
2. **Facade adoption:** 80% of queries use facade (20% raw acceptable)
3. **Vocabulary operations:** All vocabulary CLI commands query graph
4. **No collisions:** Integration tests verify concept queries don't return vocab nodes
5. **Performance:** Vocabulary operations ≥ current SQL performance

## Alternatives Considered

### Alternative 1: Keep Vocabulary in SQL (Rejected)

**Why rejected:**
- Simulating graph in SQL is architectural mismatch
- Operations awkward (joins instead of traversals)
- Violates "vocabulary is part of graph" principle

### Alternative 2: Separate Apache AGE Graph for Vocabulary (Rejected)

**Why rejected:**
- Apache AGE supports multiple graphs, but adds complexity
- Can't join across graphs easily
- Vocabulary and concepts should share namespace (with isolation)

### Alternative 3: Big-Bang Refactor All Queries (Rejected)

**Why rejected:**
- High risk (all queries change at once)
- Development stalled during refactor
- No incremental progress
- All-or-nothing migration

### Alternative 4: No Facade, Just Manual Label Enforcement (Rejected)

**Why rejected:**
- Relies on developer discipline
- No audit trail
- No technical debt visibility
- One mistake = catastrophic collision

## References

- **ADR-047:** Probabilistic Vocabulary Categorization (categories emerge from embeddings)
- **ADR-046:** Grounding-Aware Vocabulary Management (synonym detection)
- **ADR-032:** Automatic Edge Vocabulary Expansion (pruning weak types)
- **ADR-004:** Pure Graph Design (graph stores knowledge, not business logic)

## Future Enhancements

### Ontologies as Graph Nodes

**Current:**
```cypher
(:Concept {ontology: "KG System Development"})  // String property
```

**Future:**
```cypher
(:Concept)-[:IN_ONTOLOGY]->(:Ontology {name: "KG System Development"})
```

### RBAC as Graph Nodes (ADR-028)

**Future:**
```cypher
(:User)-[:HAS_ROLE]->(:Role)-[:CAN_READ]->(:Ontology)
```

### All Metadata Becomes Graph

**Vision:** All administrative metadata uses graph namespace pattern:
- :VocabType, :VocabCategory (this ADR)
- :Ontology (future)
- :User, :Role (future)
- :Job, :Pipeline (future)

**Unified pattern:** Explicit labels + distinct relationship types = namespace isolation

---

**This ADR represents the next major architectural improvement:**
1. **Safety layer** (query facade + linter)
2. **First-class graph** (vocabulary moves from SQL to Apache AGE)
3. **Better categorization** (ADR-047 probabilistic approach)

Together, these eliminate the SQL simulation and make vocabulary truly part of the timeless graph.

---

**Last Updated:** 2025-10-27
**Status:** In Progress - Phase 3.2 Complete ✅
**Implementation:** Phase 1-2 complete (PR #65, #70), Phase 3.1-3.2 complete (PR #71), Phase 3.3 future work
