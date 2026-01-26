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

## After API Changes

```bash
./operator.sh restart api
```

## Testing Endpoints

```bash
curl http://localhost:8000/health
curl http://localhost:8000/docs  # OpenAPI UI
```
