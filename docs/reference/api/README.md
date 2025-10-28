# REST API Reference

Interactive REST API documentation for the Knowledge Graph System.

## API Overview

The Knowledge Graph API provides RESTful endpoints for:

- **Authentication** - User registration, login, API key management
- **Ingestion** - Document submission and text processing
- **Jobs** - Async job management and monitoring
- **Queries** - Graph querying and concept exploration
- **Ontology** - Knowledge domain organization
- **Vocabulary** - Relationship type management
- **Admin** - System administration and configuration
- **RBAC** - Role-based access control

## Base URL

```
http://localhost:8000
```

## Authentication

The API supports two authentication methods:

1. **JWT Tokens** - Bearer tokens from `/auth/login`
2. **API Keys** - Long-lived keys from `/auth/api-keys`

Include authentication in requests:

```bash
# JWT Token
curl -H "Authorization: Bearer <token>" http://localhost:8000/jobs

# API Key
curl -H "X-API-Key: <key>" http://localhost:8000/jobs
```

## Interactive Documentation

Explore the full API specification below using the interactive Swagger UI interface:

<swagger-ui src="../openapi.json"/>

## Alternative Formats

The API server also provides these documentation endpoints when running:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json
