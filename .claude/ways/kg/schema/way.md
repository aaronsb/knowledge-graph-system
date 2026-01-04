---
match: regex
pattern: schema/|migration|\.sql$|Cypher|openCypher|AGE
files: schema/
---
# Schema Way

## Structure

```
schema/
├── 00_baseline.sql      # Core schema (AGE, auth, API tables)
└── migrations/          # Sequential migrations (NNN_name.sql)
```

## Creating Migrations

1. Create `schema/migrations/NNN_descriptive_name.sql`
2. Use next sequential number
3. Migrations auto-apply on `./operator.sh restart postgres`

## Query Language

**Apache AGE uses openCypher** (not Neo4j Cypher):
- No `ON CREATE SET` / `ON MATCH SET`
- See ADR-016 for compatibility notes

## Graph Data Model

```cypher
(:Concept)-[:APPEARS_IN]->(:Source)
(:Concept)-[:EVIDENCED_BY]->(:Instance)
(:Instance)-[:FROM_SOURCE]->(:Source)
(:Concept)-[:IMPLIES|SUPPORTS|CONTRADICTS]->(:Concept)
```

## Namespaces (ADR-048)

- `kg_core` - Graph data (concepts, sources)
- `kg_auth` - Authentication (users, roles, grants)
- `kg_api` - API state (jobs, artifacts, query_definitions)
