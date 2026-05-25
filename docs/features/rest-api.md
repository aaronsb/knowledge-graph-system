# REST API

Full programmatic access to all knowledge graph capabilities. Built on FastAPI with automatic OpenAPI documentation.

## Base URL

```
http://localhost:8000
```

## Interactive Documentation

FastAPI generates interactive API documentation automatically:

| URL | What It Is |
|-----|------------|
| `/docs` | Swagger UI — try endpoints directly in your browser |
| `/redoc` | ReDoc — alternative documentation format |
| `/openapi.json` | OpenAPI 3.0 spec — import into Postman, generate clients |

The documentation updates automatically when the API changes.

---

## Authentication

Two methods supported:

### OAuth Bearer Token

The legacy `/auth/login` endpoint was removed (ADR-054). All clients now obtain tokens through OAuth 2.0 flows under `/auth/oauth/`:

- **Programmatic clients (MCP, scripts):** client credentials grant — `POST /auth/oauth/token`
- **Web app (viz):** authorization code with PKCE — `GET /auth/oauth/authorize` → `POST /auth/oauth/token`
- **Headless tools:** device authorization — `POST /auth/oauth/device` → `POST /auth/oauth/token`

```bash
# Get a token via client credentials (MCP-style)
curl -X POST http://localhost:8000/auth/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=...&client_secret=..."

# Use the token
curl http://localhost:8000/concepts \
  -H "Authorization: Bearer <token>"
```

Create credentials via CLI:

```bash
kg oauth create --name my-app          # Generic client
kg oauth create-mcp                    # MCP-shaped client
```

---

## Endpoint Categories

### Ingestion

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/ingest` | POST | Ingest uploaded file (multipart) |
| `/ingest/text` | POST | Ingest raw text |
| `/ingest/image` | POST | Ingest image with vision AI |

Directory ingestion is performed client-side (CLI/web iterate over files and submit `/ingest` per file).

### Search & Query

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/query/search` | POST | Semantic concept search |
| `/query/sources/search` | POST | Search source passages |
| `/query/concept/{concept_id}` | GET | Get concept details |
| `/query/related` | POST | Find related concepts |
| `/query/connect` | POST | Find path between two concepts |
| `/query/connect-by-search` | POST | Path search using query strings |
| `/query/cypher` | POST | Raw Cypher query (namespaced for safety, ADR-048) |
| `/query/documents` | GET | Document-level search |

### Graph Operations (Deterministic CRUD — ADR-089)

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/concepts` | POST | Create concept |
| `/concepts` | GET | List concepts |
| `/concepts/{id}` | GET | Get concept |
| `/concepts/{id}` | PATCH | Update concept |
| `/concepts/{id}` | DELETE | Delete concept |
| `/concepts/{id}/evidence` | POST | Add evidence to a concept |
| `/edges` | POST | Create edge |
| `/edges` | GET | List edges |
| `/edges/{from}/{relationship_type}/{to}` | PATCH | Update edge |
| `/edges/{from}/{relationship_type}/{to}` | DELETE | Delete edge |
| `/graph/batch` | POST | Batch graph operations |

### Job Management

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/jobs` | GET | List jobs |
| `/jobs/{id}` | GET | Get job status |
| `/jobs/{id}/approve` | POST | Approve pending job |
| `/jobs/{id}` | DELETE | Cancel or delete job |
| `/jobs/{id}/stream` | GET | Stream job progress (SSE) |

### Ontologies

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/ontology` | GET | List all ontologies |
| `/ontology/{name}` | GET | Get ontology info |
| `/ontology/{name}/files` | GET | List source files |
| `/ontology/{name}` | DELETE | Delete ontology |

### Documents & Sources

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/documents` | GET | List documents |
| `/documents/{id}/content` | GET | Get document content |
| `/documents/{id}/concepts` | GET | Get concepts from document |
| `/documents/{id}` | DELETE | Delete document |
| `/sources/{id}` | GET | Get source metadata and content |
| `/sources/{id}/document` | GET | Retrieve original document from Garage |
| `/sources/{id}/image` | GET | Retrieve image from source (ADR-057) |

### Analysis

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/query/polarity-axis` | POST | Run polarity axis analysis (synchronous) |
| `/query/polarity-axis/jobs` | POST | Submit polarity analysis as a job |
| `/projection/{ontology}` | GET | Get cached embedding projection (UMAP/t-SNE) |
| `/projection/algorithms` | GET | List available projection algorithms |
| `/artifacts` | GET | List saved artifacts |
| `/vocabulary/status` | GET | Get vocabulary health |
| `/vocabulary/types` | GET | List relationship types |

### Administration

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/health` | GET | API health check |
| `/database/stats` | GET | Database statistics |
| `/admin/status` | GET | System status |
| `/users` | GET | List users (admin) |
| `/rbac/roles` | GET | List roles (admin) |

---

## Example Requests

### Search for Concepts

```bash
curl -X POST http://localhost:8000/query/search \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "machine learning", "limit": 10, "min_similarity": 0.7}'
```

### Create a Concept

```bash
curl -X POST http://localhost:8000/concepts \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Neural Networks",
    "description": "Computing systems inspired by biological neural networks",
    "ontology": "machine-learning"
  }'
```

### Ingest Text

`/ingest/text` accepts form-encoded data (not JSON):

```bash
curl -X POST http://localhost:8000/ingest/text \
  -H "Authorization: Bearer <token>" \
  -F "text=Neural networks consist of layers of interconnected nodes..." \
  -F "ontology=machine-learning" \
  -F "auto_approve=true"
```

---

## Client Libraries

Generate clients from the OpenAPI spec:

```bash
# Download spec
curl http://localhost:8000/openapi.json > openapi.json

# Generate Python client
openapi-generator generate -i openapi.json -g python -o ./client

# Generate TypeScript client
openapi-generator generate -i openapi.json -g typescript-fetch -o ./client
```

Or use the existing TypeScript client in `cli/src/api/client.ts`.

---

## Rate Limiting

No built-in rate limiting. For production, consider:
- Nginx/Traefik reverse proxy with rate limiting
- API gateway (Kong, AWS API Gateway)

---

## CORS

CORS is configured for the web frontend. For other origins, update `api/app/main.py`.
