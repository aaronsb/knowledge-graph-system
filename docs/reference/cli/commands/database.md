# kg database

> Auto-generated

## database (db)

Database operations and information. Provides read-only queries for PostgreSQL + Apache AGE database health, statistics, and connection details.

**Usage:**
```bash
kg database [options]
```

**Subcommands:**

- `stats` - Show comprehensive database statistics including node counts (Concepts, Sources, Instances) and relationship type breakdown. Useful for monitoring graph growth and understanding extraction patterns.
- `info` - Show database connection information including URI, username, connection status, PostgreSQL version, and Apache AGE edition. Use for troubleshooting connection issues and capturing environment details for bug reports.
- `health` - Check database health and connectivity with detailed checks for: connectivity (PostgreSQL reachable), age_extension (Apache AGE loaded), and graph (schema exists). Use for startup verification and diagnosing which component is failing.
- `query` - Execute a custom openCypher/GQL query (ADR-048). Use --namespace for safety: "concept" operates on Concept/Source/Instance nodes (default namespace), "vocab" operates on VocabType/VocabCategory nodes, omit for raw queries (mixed types, use with caution). Examples: kg db query "MATCH (c:Concept) WHERE c.label =~ '.*recursive.*' RETURN c.label LIMIT 5" --namespace concept
- `counters` - Show graph metrics counters organized by type (ADR-079). Counters track: snapshot counts (concepts, edges, sources, vocab_types), activity counters (ingestion, consolidation events), and legacy structure counters. Use --refresh to update from current graph state.

---

### stats

Show comprehensive database statistics including node counts (Concepts, Sources, Instances) and relationship type breakdown. Useful for monitoring graph growth and understanding extraction patterns.

**Usage:**
```bash
kg stats [options]
```

### info

Show database connection information including URI, username, connection status, PostgreSQL version, and Apache AGE edition. Use for troubleshooting connection issues and capturing environment details for bug reports.

**Usage:**
```bash
kg info [options]
```

### health

Check database health and connectivity with detailed checks for: connectivity (PostgreSQL reachable), age_extension (Apache AGE loaded), and graph (schema exists). Use for startup verification and diagnosing which component is failing.

**Usage:**
```bash
kg health [options]
```

### query

Execute a custom openCypher/GQL query (ADR-048). Use --namespace for safety: "concept" operates on Concept/Source/Instance nodes (default namespace), "vocab" operates on VocabType/VocabCategory nodes, omit for raw queries (mixed types, use with caution). Examples: kg db query "MATCH (c:Concept) WHERE c.label =~ '.*recursive.*' RETURN c.label LIMIT 5" --namespace concept

**Usage:**
```bash
kg query <query>
```

**Arguments:**

- `<query>` - openCypher/GQL query string

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--namespace <type>` | Namespace for safety: "concept", "vocab", or omit for raw (ADR-048) | - |
| `--params <json>` | Query parameters as JSON string (e.g., '{"min_score": 0.8}') | - |
| `--limit <n>` | Convenience: Append LIMIT to query (overrides query LIMIT) | - |

### counters

Show graph metrics counters organized by type (ADR-079). Counters track: snapshot counts (concepts, edges, sources, vocab_types), activity counters (ingestion, consolidation events), and legacy structure counters. Use --refresh to update from current graph state.

**Usage:**
```bash
kg counters [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--refresh` | Refresh counters from current graph state before displaying | - |
