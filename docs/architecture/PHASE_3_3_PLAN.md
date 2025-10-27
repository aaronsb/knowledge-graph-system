# ADR-048 Phase 3.3 Implementation Plan

**Status:** Ready to Begin
**Date:** 2025-10-27
**Goal:** Complete vocabulary graph migration and establish :VocabCategory relationships

---

## Current State (Phase 3.2 Complete)

### What We Have

**Graph Nodes:**
- 47 :VocabType nodes (30 builtin + 17 custom)
- 10 :VocabCategory nodes
- 30 :IN_CATEGORY relationships (ONLY for builtin types)

**Properties:**
- All 47 :VocabType nodes have `v.category` property ✓
- Property is kept in sync when categories are refreshed ✓

**Inconsistency:**
- 17 custom types have NO :IN_CATEGORY relationships
- They were added AFTER migration 014 ran
- Only the property exists, not the relationship

**Example (ENHANCES):**
```cypher
// Property exists
MATCH (v:VocabType {name: 'ENHANCES'})
RETURN v.category  // → "dependency" ✓

// But NO relationship!
MATCH (v:VocabType {name: 'ENHANCES'})-[:IN_CATEGORY]->(c)
RETURN c.name  // → (no results) ✗
```

###What Works

- `kg vocab list` - Queries graph, shows correct categories (uses property fallback)
- `kg vocab refresh-categories` - Updates both table AND graph property
- `get_category_distribution()` - Uses property (Phase 3.2 implementation)
- All READ operations work correctly

### What Doesn't Work

- `get_edge_type_info()` - Tries to traverse `:IN_CATEGORY` relationships (falls back to property)
- Any future code expecting :IN_CATEGORY relationships will fail for custom types
- Inconsistent data model (some types have relationships, some don't)

---

## Phase 3.3 Goals

### 1. **Create Missing :IN_CATEGORY Relationships**

**Task:** Sync the 17 custom types to have relationships matching their properties.

**Implementation:**
```python
# src/api/lib/age_client.py or new migration file

def sync_category_relationships():
    """
    Create :IN_CATEGORY relationships for all :VocabType nodes
    that have v.category property but NO relationship.
    """
    query = """
    MATCH (v:VocabType)
    WHERE v.category IS NOT NULL
      AND NOT EXISTS ((v)-[:IN_CATEGORY]->())
    WITH v
    MATCH (c:VocabCategory {name: v.category})
    MERGE (v)-[:IN_CATEGORY]->(c)
    RETURN v.name as type_name, c.name as category
    """
    results = execute_cypher(query)
    return results
```

**Verification:**
```cypher
// Should return 47 (all types)
MATCH (v:VocabType)-[:IN_CATEGORY]->(c:VocabCategory)
RETURN count(v) as total
```

### 2. **Update add_edge_type() to Create Relationships**

**Current (Phase 3.2):**
```python
# src/api/lib/age_client.py:1372-1379
vocab_query = """
    MERGE (v:VocabType {name: $name})
    SET v.category = $category,  # ← Only sets property
        v.description = $description,
        v.is_builtin = $is_builtin,
        ...
"""
```

**Updated (Phase 3.3):**
```python
# After creating/updating :VocabType node
vocab_query = """
    MERGE (v:VocabType {name: $name})
    SET v.description = $description,
        v.is_builtin = $is_builtin,
        ...
    WITH v
    MERGE (c:VocabCategory {name: $category})
    MERGE (v)-[:IN_CATEGORY]->(c)
    RETURN v.name as name
"""
```

**Note:** Remove `v.category` property once relationships are established.

### 3. **Update VocabularyCategorizer to Create Relationships**

**Current:**
```python
# src/api/lib/vocabulary_categorizer.py:313-343
cypher_query = """
    MATCH (v:VocabType {name: $name})
    SET v.category = $category  # ← Only updates property
    RETURN v.name as name
"""
```

**Updated:**
```python
cypher_query = """
    MATCH (v:VocabType {name: $name})
    // Delete old category relationship
    OPTIONAL MATCH (v)-[r:IN_CATEGORY]->()
    DELETE r
    WITH v
    // Create new category relationship
    MERGE (c:VocabCategory {name: $category})
    MERGE (v)-[:IN_CATEGORY]->(c)
    RETURN v.name as name
"""
```

### 4. **Update get_edge_type_info() to Use Relationship**

**Current (Phase 3.2 - property fallback):**
```python
# src/api/lib/age_client.py:1211-1218
query = """
MATCH (v:VocabType {name: $type_name})
RETURN v.name as relationship_type,
       v.is_active as is_active,
       v.is_builtin as is_builtin,
       v.usage_count as usage_count,
       v.category as category  # ← Property
"""
```

**Updated (Phase 3.3 - relationship):**
```python
query = """
MATCH (v:VocabType {name: $type_name})
OPTIONAL MATCH (v)-[:IN_CATEGORY]->(c:VocabCategory)
RETURN v.name as relationship_type,
       v.is_active as is_active,
       v.is_builtin as is_builtin,
       v.usage_count as usage_count,
       c.name as category  # ← From relationship
"""
```

### 5. **Update get_category_distribution() to Use Relationships**

**Current (Phase 3.2 - property):**
```python
# src/api/lib/age_client.py:1613-1618
query = """
MATCH (v:VocabType)
WHERE v.is_active = 't' AND v.category IS NOT NULL
RETURN v.category as category, count(v) as type_count
ORDER BY type_count DESC, category
"""
```

**Updated (Phase 3.3 - relationship):**
```python
query = """
MATCH (v:VocabType)-[:IN_CATEGORY]->(c:VocabCategory)
WHERE v.is_active = 't'
RETURN c.name as category, count(v) as type_count
ORDER BY type_count DESC, category
"""
```

---

## Implementation Steps

### Step 1: One-Time Sync (Migration or Admin Command)

Create migration 016 or admin command to sync existing nodes:

```bash
kg admin sync-vocabulary-relationships
```

Or migration:
```sql
-- schema/migrations/016_sync_category_relationships.sql
-- Create :IN_CATEGORY relationships from v.category properties
```

### Step 2: Update Code to Use Relationships

Files to update:
1. `src/api/lib/age_client.py`
   - add_edge_type() - Create relationships
   - get_edge_type_info() - Query relationships
   - get_category_distribution() - Count via relationships

2. `src/api/lib/vocabulary_categorizer.py`
   - _store_category_assignment() - Create/update relationships

### Step 3: Testing

```bash
# After sync
kg vocab list  # Should work identically

# Check relationships exist
python3 -c "
from src.api.lib.age_client import AGEClient
client = AGEClient()
query = 'MATCH ()-[r:IN_CATEGORY]->() RETURN count(r) as total'
result = client._execute_cypher(query, fetch_one=True)
print(f'Total relationships: {result[\"total\"]}')  # Should be 47
"

# Test new type creation
kg vocab add CUSTOM_TEST causation --description "Test type"

# Verify it has relationship
python3 -c "
from src.api.lib.age_client import AGEClient
client = AGEClient()
query = '''
MATCH (v:VocabType {name: \"CUSTOM_TEST\"})-[:IN_CATEGORY]->(c)
RETURN c.name as category
'''
result = client._execute_cypher(query, fetch_one=True)
print(f'Category relationship: {result[\"category\"]}')  # Should be "causation"
"
```

### Step 4: Deprecate Property (Optional)

Once all code uses relationships:

1. Remove `SET v.category` from all write operations
2. Add migration to drop property:
   ```cypher
   MATCH (v:VocabType)
   REMOVE v.category
   ```

---

## Benefits of Phase 3.3

### 1. **Consistent Data Model**
- All types use same structure (relationship, not mix of relationship/property)
- No special cases for builtin vs custom types
- Future code can rely on relationships always existing

### 2. **True Graph Semantics**
```cypher
// Find all types in causation category
MATCH (v:VocabType)-[:IN_CATEGORY]->(c:VocabCategory {name: "causation"})
RETURN v.name

// Category structure query
MATCH (c:VocabCategory)<-[:IN_CATEGORY]-(v:VocabType)
RETURN c.name as category, collect(v.name) as types, count(v) as count
ORDER BY count DESC
```

### 3. **Supports Future Extensions**
- Can add properties to :VocabCategory nodes (description, examples, etc.)
- Can add category hierarchy (subcategories)
- Can track category evolution over time

### 4. **Aligns with ADR-048 Vision**
> "Vocabulary is first-class graph, not SQL simulation"

With relationships, operations match data structure:
- Synonym detection = graph traversal
- Category membership = relationship query
- Merge = edge rewiring

---

## Risks and Mitigations

### Risk: Breaking Existing Queries

**Mitigation:**
- Phase 3.2 fallback already works (property exists)
- Test thoroughly before removing property
- Can keep property temporarily for backward compatibility

### Risk: Migration Failures

**Mitigation:**
- Use MERGE (idempotent)
- Transaction safety
- Can re-run migration safely

### Risk: Category Nodes Don't Exist

**Scenario:** New category computed that doesn't have :VocabCategory node

**Mitigation:**
```cypher
// Always MERGE category node before creating relationship
MERGE (c:VocabCategory {name: $category})
MERGE (v)-[:IN_CATEGORY]->(c)
```

---

## Success Criteria

- [ ] All 47 :VocabType nodes have :IN_CATEGORY relationships
- [ ] New types automatically get relationships (not just properties)
- [ ] Category refresh updates relationships (not just properties)
- [ ] get_category_distribution() uses relationships
- [ ] get_edge_type_info() uses relationships
- [ ] All tests pass
- [ ] kg vocab list shows identical results
- [ ] No performance regression

---

## Timeline Estimate

- **Sync existing relationships:** 1-2 hours (migration + testing)
- **Update add_edge_type():** 30 min
- **Update categorizer:** 30 min
- **Update read queries:** 1 hour
- **Testing:** 1-2 hours
- **Total:** 4-6 hours

---

## Next Steps

1. Create sync migration or admin command
2. Test sync on development database
3. Update add_edge_type() to create relationships
4. Update categorizer to use relationships
5. Update read queries to use relationships
6. Test complete workflow end-to-end
7. Update CLAUDE.md to reflect new patterns
8. Mark Phase 3.3 complete in ADR-048

