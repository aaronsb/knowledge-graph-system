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

### JWT Bearer Token

```bash
# Get token
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "..."}'

# Use token
curl http://localhost:8000/concepts \
  -H "Authorization: Bearer <token>"
```

### API Key

```bash
# Create API key via CLI
kg oauth create --name my-app

# Use API key
curl http://localhost:8000/concepts \
  -H "X-API-Key: <key>"
```

---

## Endpoint Categories

### Ingestion

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/ingest/text` | POST | Ingest raw text |
| `/ingest/file` | POST | Ingest uploaded file |
| `/ingest/directory` | POST | Ingest directory (server-side path) |
| `/ingest/image` | POST | Ingest image with vision AI |

### Search & Query

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/search` | GET | Semantic concept search |
| `/search/sources` | GET | Search source passages |
| `/search/documents` | GET | Document-level search |
| `/concepts/{id}` | GET | Get concept details |
| `/concepts/{id}/related` | GET | Find related concepts |
| `/concepts/connect` | GET | Find path between concepts |

### Graph Operations

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/graph/concepts` | POST | Create concept |
| `/graph/concepts/{id}` | PUT | Update concept |
| `/graph/concepts/{id}` | DELETE | Delete concept |
| `/graph/edges` | POST | Create relationship |
| `/graph/edges/{id}` | DELETE | Delete relationship |

### Job Management

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/jobs` | GET | List jobs |
| `/jobs/{id}` | GET | Get job status |
| `/jobs/{id}/approve` | POST | Approve pending job |
| `/jobs/{id}/cancel` | POST | Cancel running job |
| `/jobs/{id}` | DELETE | Delete job |

### Ontologies

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/ontologies` | GET | List all ontologies |
| `/ontologies/{name}` | GET | Get ontology info |
| `/ontologies/{name}/files` | GET | List source files |
| `/ontologies/{name}` | DELETE | Delete ontology |

### Documents & Sources

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/documents` | GET | List documents |
| `/documents/{id}` | GET | Get document content |
| `/documents/{id}/concepts` | GET | Get concepts from document |
| `/sources/{id}` | GET | Get source content |

### Analysis

| Endpoint | Method | What It Does |
|----------|--------|--------------|
| `/polarity/analyze` | POST | Run polarity axis analysis |
| `/projections` | GET | List embedding projections |
| `/artifacts` | GET | List saved artifacts |
| `/vocabulary/status` | GET | Get vocabulary health |

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
curl "http://localhost:8000/search?query=machine+learning&limit=10" \
  -H "Authorization: Bearer <token>"
```

### Create a Concept

```bash
curl -X POST http://localhost:8000/graph/concepts \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Neural Networks",
    "description": "Computing systems inspired by biological neural networks",
    "ontology": "machine-learning"
  }'
```

### Ingest Text

```bash
curl -X POST http://localhost:8000/ingest/text \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Neural networks consist of layers of interconnected nodes...",
    "ontology": "machine-learning",
    "auto_approve": true
  }'
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
