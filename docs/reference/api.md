---
id: 7.R.01
domain: ui
mode: reference
---

# REST API

The Kappa Graph REST API is served by the `kg-api` container on port 8000. The interactive reference below is rendered from the live OpenAPI schema — every endpoint, parameter, and response model comes straight from the running API.

The API groups endpoints into authentication, ingestion, jobs, queries, ontology, vocabulary, admin, and RBAC. Authentication uses OAuth 2.0 (ADR-054): all flows issue bearer tokens from `/auth/oauth/token` — client-credentials for CLI and MCP clients, authorization-code with PKCE for the web app.

```
Base URL: http://localhost:8000
Raw schema: http://localhost:8000/openapi.json
```

<swagger-ui src="openapi.json"/>
