---
match: regex
pattern: \bpostgres\b|\bpsql\b|database.*query|run.*SQL|kg_admin|SELECT\s.*FROM|INSERT\s+INTO|UPDATE\s+kg_|DELETE\s+FROM|schema_migrations
commands: docker\s+exec.*(postgres|psql)|psql\s+-U
scope: agent, subagent
---
# Database Way

**Don't use `docker exec` to access the database. Use `operator.sh query`.**

```bash
./operator.sh query 'SELECT count(*) FROM kg_auth.users'
./operator.sh pg 'SELECT ...'   # pg is an alias
```

This handles container names, credentials, and non-interactive mode
so you don't have to guess usernames or container names.

## Why not docker exec?

Every one of these fails:
- `docker exec kg-postgres-dev psql -U kg_admin` — wrong container, wrong user
- `docker exec knowledge-graph-postgres psql -U postgres` — wrong user
- `docker exec knowledge-graph-postgres psql -U knowledge_graph` — wrong user

The correct user is `admin`, the correct DB is `knowledge_graph`, and
`operator.sh query` knows both.

## Common schemas

- `kg_auth.*` — users, roles, permissions, OAuth clients
- `kg_core.*` — ontology metadata
- `kg_api.*` — annealing options, query definitions, artifacts
- `ag_catalog.*` — Apache AGE graph internals
- `public.schema_migrations` — migration tracking
