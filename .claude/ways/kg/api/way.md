---
match: regex
pattern: \bapi\b|AGEClient|routes/|FastAPI|endpoint|backend
files: api/app/
---
# API Way

## Structure

```
api/app/
├── main.py              # FastAPI app entry
├── routes/              # Endpoint handlers
│   ├── queries.py       # Graph queries, polarity
│   ├── artifacts.py     # Artifact CRUD
│   ├── ontology.py      # Ontology management
│   └── ...
├── lib/
│   ├── age_client.py    # Apache AGE operations
│   ├── permissions.py   # RBAC checker
│   └── garage/          # S3 storage clients
└── workers/             # Background job workers
```

## Query Safety (ADR-048)

Always use `client.facade` for graph queries:

```python
# SAFE
client.facade.match_concepts(where="c.label = $label")
client.facade.count_concepts()

# UNSAFE - can match vocabulary nodes
client._execute_cypher("MATCH (n) RETURN n")
```

## GraphFacade (graph_accel integration)

`GraphFacade` in `api/app/lib/graph_facade.py` wraps graph_accel with
Cypher fallback. Key patterns:

- **Dedicated connection**: `_accel_conn` is pinned so the in-memory graph
  persists across requests. Don't use the regular AGEClient connection.
- **Optional params → NULL, not NaN**: Rust `Option<f64>` maps `NULL` to
  `None` (skip filter). `float('nan')` maps to `Some(NaN)` which silently
  rejects all comparisons (`x >= NaN` is always false in IEEE 754).
- **GUC lifecycle**: GUCs are set once on first load (`_set_accel_gucs`),
  then `ensure_fresh()` handles generation-based reloads using the
  session-level GUCs already in place.

## After API Changes

```bash
./operator.sh restart api    # or hot-reload (dev mode watches for changes)
```

## Testing Endpoints

```bash
curl http://localhost:8000/health
curl http://localhost:8000/docs  # OpenAPI UI
```
