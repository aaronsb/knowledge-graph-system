# Data Contract Pattern: Schema Governance

**Status:** Implemented
**Date:** 2025-10-09
**Location:** `src/api/constants.py`

## Overview

The knowledge graph system uses a **data contract pattern** to centralize schema definitions and enable disciplined schema evolution. This provides a single source of truth for:

- Valid relationship types
- Node labels
- Backup format specifications
- Source types and cognitive leap levels

## Problem Statement

Before implementing the data contract, relationship types and other schema elements were hardcoded in multiple locations:

```python
# src/api/lib/llm_extractor.py
relationship_type: One of [IMPLIES, CONTRADICTS, SUPPORTS, PART_OF]

# src/api/lib/backup_integrity.py
VALID_RELATIONSHIP_TYPES = {"IMPLIES", "SUPPORTS", "CONTRADICTS", "RELATES_TO", "PART_OF"}

# Multiple other locations with inconsistent definitions
```

**Issues:**
- ❌ No single source of truth
- ❌ Schema drift across codebase
- ❌ Difficult to add new relationship types
- ❌ No guarantee of consistency
- ❌ Tests couldn't validate against canonical schema

## Solution: Centralized Data Contract

All schema definitions now live in `src/api/constants.py`:

```python
# src/api/constants.py
from typing import Set, Dict, List

# 30-type semantically sparse relationship taxonomy
# Organized in 8 categories (see ADR-022)
RELATIONSHIP_CATEGORIES: Dict[str, List[str]] = {
    "logical_truth": ["IMPLIES", "CONTRADICTS", "PRESUPPOSES", "EQUIVALENT_TO"],
    "causal": ["CAUSES", "ENABLES", "PREVENTS", "INFLUENCES", "RESULTS_FROM"],
    "structural": ["PART_OF", "CONTAINS", "COMPOSED_OF", "SUBSET_OF", "INSTANCE_OF"],
    "evidential": ["SUPPORTS", "REFUTES", "EXEMPLIFIES", "MEASURED_BY"],
    "similarity": ["SIMILAR_TO", "ANALOGOUS_TO", "CONTRASTS_WITH", "OPPOSITE_OF"],
    "temporal": ["PRECEDES", "CONCURRENT_WITH", "EVOLVES_INTO"],
    "functional": ["USED_FOR", "REQUIRES", "PRODUCES", "REGULATES"],
    "meta": ["DEFINED_AS", "CATEGORIZED_AS"],
}

# Flat set of all 30 types
RELATIONSHIP_TYPES: Set[str] = {
    rel_type
    for category_types in RELATIONSHIP_CATEGORIES.values()
    for rel_type in category_types
}

# Reverse mapping: type -> category
RELATIONSHIP_TYPE_TO_CATEGORY: Dict[str, str] = {
    rel_type: category
    for category, types in RELATIONSHIP_CATEGORIES.items()
    for rel_type in types
}

# For use in LLM prompts (comma-separated dense list)
RELATIONSHIP_TYPES_LIST = ", ".join(sorted(RELATIONSHIP_TYPES))
```

All consumers import from this contract:

```python
# src/api/lib/llm_extractor.py
from src.api.constants import RELATIONSHIP_TYPES_LIST

EXTRACTION_PROMPT = f"""
relationship_type: One of [{RELATIONSHIP_TYPES_LIST}]
"""

# src/api/lib/backup_integrity.py
from ..constants import RELATIONSHIP_TYPES, BACKUP_TYPES

class BackupIntegrityChecker:
    VALID_RELATIONSHIP_TYPES = RELATIONSHIP_TYPES
```

## Benefits

### 1. Single Source of Truth
- Schema defined once in `constants.py`
- All code references the same definitions
- Eliminates drift and inconsistency

### 2. Forward Compatibility
The data contract supports schema evolution naturally:

**Old Backup (Subset):**
```json
{
  "relationships": [
    {"type": "IMPLIES"},  // Valid: subset of current schema
    {"type": "SUPPORTS"}   // Valid: subset of current schema
  ]
}
```
✅ **Valid** - Historical data with fewer relationship types

**Current Schema:**
```python
# 30 types across 8 categories (see ADR-022)
RELATIONSHIP_TYPES = {
    "IMPLIES", "CONTRADICTS", "PRESUPPOSES", "EQUIVALENT_TO",  # logical_truth
    "CAUSES", "ENABLES", "PREVENTS", "INFLUENCES", "RESULTS_FROM",  # causal
    "PART_OF", "CONTAINS", "COMPOSED_OF", "SUBSET_OF", "INSTANCE_OF",  # structural
    "SUPPORTS", "REFUTES", "EXEMPLIFIES", "MEASURED_BY",  # evidential
    "SIMILAR_TO", "ANALOGOUS_TO", "CONTRASTS_WITH", "OPPOSITE_OF",  # similarity
    "PRECEDES", "CONCURRENT_WITH", "EVOLVES_INTO",  # temporal
    "USED_FOR", "REQUIRES", "PRODUCES", "REGULATES",  # functional
    "DEFINED_AS", "CATEGORIZED_AS",  # meta
}
```

**Future Backup (Superset):**
```json
{
  "relationships": [
    {"type": "DERIVES_FROM"}  // Warning: unknown to current validator
  ]
}
```
⚠️ **Valid with warning** - Future schema extensions

### 3. Deliberate Schema Evolution

**Adding a new relationship type:**

1. **Update contract:**
   ```python
   # src/api/constants.py
   RELATIONSHIP_CATEGORIES: Dict[str, List[str]] = {
       "logical_truth": ["IMPLIES", "CONTRADICTS", "PRESUPPOSES", "EQUIVALENT_TO"],
       "causal": ["CAUSES", "ENABLES", "PREVENTS", "INFLUENCES", "RESULTS_FROM"],
       "structural": [
           "PART_OF", "CONTAINS", "COMPOSED_OF", "SUBSET_OF",
           "INSTANCE_OF", "DERIVES_FROM"  # New type added to category
       ],
       # ... other categories
   }
   ```

2. **Run tests:**
   ```bash
   pytest tests/
   ```
   Tests immediately show everywhere that needs updating.

3. **Update consuming code:**
   - LLM extraction prompts automatically include new type
   - Backup validation accepts new type
   - No hidden assumptions or surprises

4. **Commit atomically:**
   All schema changes happen together, reviewed as a unit.

### 4. Test-Driven Schema Changes

The contract + tests form a **support mesh**:

```python
# tests/api/test_backup_integrity.py
def test_all_valid_relationship_types_pass(valid_full_backup):
    """Test that all valid relationship types are accepted"""
    valid_types = ["IMPLIES", "SUPPORTS", "CONTRADICTS", "RELATES_TO", "PART_OF"]

    for rel_type in valid_types:
        backup = valid_full_backup.copy()
        backup["data"]["relationships"][0]["type"] = rel_type

        checker = BackupIntegrityChecker()
        result = checker.check_data(backup)

        assert result.valid is True, f"Valid type {rel_type} should pass"
```

Tests validate against the contract, not hardcoded assumptions. Schema changes are safe and trackable.

## Contract Elements

### Graph Schema

```python
# 30 semantically sparse relationship types (see ADR-022)
# Categories provide internal organization for humans
# LLM sees flat list to avoid category bias
RELATIONSHIP_CATEGORIES: Dict[str, List[str]] = {
    "logical_truth": ["IMPLIES", "CONTRADICTS", "PRESUPPOSES", "EQUIVALENT_TO"],
    "causal": ["CAUSES", "ENABLES", "PREVENTS", "INFLUENCES", "RESULTS_FROM"],
    "structural": ["PART_OF", "CONTAINS", "COMPOSED_OF", "SUBSET_OF", "INSTANCE_OF"],
    "evidential": ["SUPPORTS", "REFUTES", "EXEMPLIFIES", "MEASURED_BY"],
    "similarity": ["SIMILAR_TO", "ANALOGOUS_TO", "CONTRASTS_WITH", "OPPOSITE_OF"],
    "temporal": ["PRECEDES", "CONCURRENT_WITH", "EVOLVES_INTO"],
    "functional": ["USED_FOR", "REQUIRES", "PRODUCES", "REGULATES"],
    "meta": ["DEFINED_AS", "CATEGORIZED_AS"],
}

# Flat set of all types (30 total)
RELATIONSHIP_TYPES: Set[str] = {
    rel_type
    for category_types in RELATIONSHIP_CATEGORIES.values()
    for rel_type in category_types
}

# Node labels
NODE_LABELS: Set[str] = {
    "Concept",   # Core concept node
    "Source",    # Source document/paragraph node
    "Instance",  # Evidence instance linking concept to source
}

# Edge properties for concept relationships
# - confidence: float (0.0-1.0) - LLM confidence score
# - category: str - Semantic category from RELATIONSHIP_CATEGORIES
```

### Backup Schema

```python
# Valid backup types
BACKUP_TYPES: Set[str] = {
    "full_backup",      # Complete database export
    "ontology_backup",  # Single ontology export
}

# Current backup format version
BACKUP_VERSION = "1.0"
```

### Source Types

```python
# Source node type property values
SOURCE_TYPES: Set[str] = {
    "DOCUMENT",  # Extracted from ingested document
    "LEARNED",   # AI/human synthesized knowledge
}

# Cognitive leap levels for learned sources
COGNITIVE_LEAP_LEVELS: Set[str] = {
    "LOW",     # Incremental connection
    "MEDIUM",  # Moderate insight
    "HIGH",    # Significant conceptual leap
}
```

## Usage Patterns

### In LLM Extraction

```python
# src/api/lib/llm_extractor.py
from src.api.constants import RELATIONSHIP_TYPES_LIST

EXTRACTION_PROMPT = f"""
For relationships between concepts, provide:
- from_concept_id: Source concept
- to_concept_id: Target concept
- relationship_type: One of [{RELATIONSHIP_TYPES_LIST}]
- confidence: Score from 0.0 to 1.0
"""
```

The prompt automatically stays in sync with the schema.

### In Validation

```python
# src/api/lib/backup_integrity.py
from ..constants import RELATIONSHIP_TYPES

class BackupIntegrityChecker:
    VALID_RELATIONSHIP_TYPES = RELATIONSHIP_TYPES

    def _check_references(self, data, result):
        if rel_type not in self.VALID_RELATIONSHIP_TYPES:
            result.add_warning(f"Unusual type: {rel_type}")
```

Validation enforces the contract without hardcoding.

### In Tests

```python
# tests/api/test_backup_integrity.py
from src.api.constants import RELATIONSHIP_TYPES

def test_all_relationship_types_valid():
    """Verify all contract types are accepted"""
    for rel_type in RELATIONSHIP_TYPES:
        # Test that each contract type validates correctly
        assert is_valid_relationship_type(rel_type)
```

Tests validate the contract itself, forming a safety net.

## Comparison with Database-Driven Schema

**Alternative approach:** Query database for actual relationship types

```python
def get_relationship_types_from_db(client: AGEClient) -> Set[str]:
    """Query database for actual relationship types"""
    query = "MATCH ()-[r]->() RETURN DISTINCT type(r)"
    return execute_query(query)
```

**Why we don't do this:**

1. **Circular Dependency:** Validating a backup against current database state creates chicken-and-egg problems. A backup should be valid if it conforms to the **schema definition**, not the current database contents.

2. **Schema vs Data:** The contract defines what's **allowed by the schema**, not what currently exists. A fresh database with zero relationships still has a valid schema.

3. **Portability:** Backups validated against the contract work across environments, not just the current database instance.

4. **Determinism:** Contract validation is deterministic and testable. Database-driven validation varies with data state.

## Schema Evolution Principles

### Backward Compatibility

**Old clients reading new schema:**
- Unknown relationship types → warnings (not errors)
- Subset validation: old data remains valid
- Graceful degradation

**New clients reading old schema:**
- Missing types → no problem (subset of current)
- Automatic forward compatibility
- No migration required

### Breaking Changes

Breaking changes require explicit migration:

1. **Rename relationship type:**
   ```python
   # Migration needed: RELATES_TO → ASSOCIATED_WITH
   # 1. Add new type to contract
   # 2. Update database (Cypher migration)
   # 3. Remove old type after grace period
   ```

2. **Change node label:**
   Coordinate with schema initialization (`schema/init.cypher`)

3. **Backup format version bump:**
   Update `BACKUP_VERSION` and add conversion logic

## Best Practices

### Do's ✅

- **Add new types freely** - backward compatible
- **Document semantic meaning** - comments in constants.py
- **Update all at once** - atomic contract changes
- **Test comprehensively** - contract + tests = safety net
- **Review changes carefully** - schema changes affect entire system

### Don'ts ❌

- **Don't hardcode schema elements** - always import from contract
- **Don't query database for schema** - contract is source of truth
- **Don't skip tests** - schema changes must have test coverage
- **Don't make breaking changes lightly** - coordinate across system
- **Don't bypass the contract** - inconsistency breaks guarantees

## Related Documentation

- **ADR-015:** Backup/Restore Streaming Architecture
- **ADR-022:** Semantically Sparse 30-Type Relationship Taxonomy
- **File:** `src/api/constants.py` (implementation)
- **File:** `src/api/lib/relationship_mapper.py` (Porter Stemmer fuzzy matching)
- **File:** `src/api/lib/backup_integrity.py` (consumer)
- **File:** `src/api/lib/llm_extractor.py` (consumer)
- **File:** `tests/api/test_backup_integrity.py` (validation tests)

## Future Considerations

### Versioned Contracts

If schema complexity grows:

```python
# src/api/constants/v1.py
RELATIONSHIP_TYPES_V1 = {...}

# src/api/constants/v2.py
RELATIONSHIP_TYPES_V2 = {...}

# Conversion logic between versions
def migrate_v1_to_v2(backup): ...
```

### Schema Registry

For distributed systems:

```python
# Central schema registry service
# Validates contracts across services
# Ensures consistency in microservices architecture
```

### OpenAPI/JSON Schema

Export contract as machine-readable schema:

```python
# Generate OpenAPI spec from constants
# Enables external tool integration
# API documentation stays in sync
```

## Conclusion

The data contract pattern provides:

- ✅ **Consistency:** Single source of truth
- ✅ **Safety:** Test-driven schema evolution
- ✅ **Flexibility:** Forward/backward compatibility
- ✅ **Clarity:** Explicit schema governance
- ✅ **Maintainability:** Centralized management

This pattern enables deliberate, safe schema evolution while maintaining system integrity across all components.
