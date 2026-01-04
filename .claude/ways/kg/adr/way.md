---
match: regex
pattern: ADR-\d|architecture.*decision|docs/architecture/ADR
files: docs/architecture/ADR
---
# KG ADR Supplement

## ADR Location

```
docs/architecture/
├── ARCHITECTURE_DECISIONS.md   # Master index (update when adding ADRs)
├── ADR-001-*.md
├── ADR-002-*.md
└── ...
```

## Key ADRs for This Project

| ADR | Topic |
|-----|-------|
| ADR-016 | openCypher compatibility (not Neo4j Cypher) |
| ADR-028 | Dynamic RBAC permissions |
| ADR-048 | Query safety & GraphQueryFacade |
| ADR-061 | Operator architecture |
| ADR-082 | User scoping & groups |
| ADR-083 | Artifact persistence pattern |

## When Adding ADRs

1. Create `docs/architecture/ADR-NNN-descriptive-name.md`
2. **Update `ARCHITECTURE_DECISIONS.md`** with entry in index table
3. Link from related ADRs using "Related ADRs" section
