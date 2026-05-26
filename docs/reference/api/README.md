# REST API Reference

Interactive REST API documentation for the Knowledge Graph System.

## API Overview

The Knowledge Graph API provides RESTful endpoints for:

- **Authentication** - User registration and OAuth 2.0 token flows (ADR-054)
- **Ingestion** - Document, text, and image submission
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

The API uses OAuth 2.0 (ADR-054). All authentication flows issue bearer
tokens via `/auth/oauth/token`:

- **Client credentials** - CLI personal clients and MCP servers
- **Authorization code + PKCE** - viz-app browser sign-in
- **Device authorization** - third-party tools (`/auth/oauth/device`)

Include the bearer token in requests:

```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/jobs
```

## Interactive Documentation

Explore the full API specification below using the interactive Swagger UI interface:

<swagger-ui src="../openapi.json"/>

## Alternative Formats

The API server also provides these documentation endpoints when running:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json
