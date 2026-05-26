# Tool & API Reference

Reference documentation for the Knowledge Graph System's tools and REST API.

## 📚 Tool Reference

### [CLI Commands](cli/)
Complete reference for all `kg` command-line interface commands.

**Coverage:** commands include `health`, `config`, `login`, `logout`, `oauth`,
`ingest`, `search`, `job`, `database`, `ontology`, `vocabulary`, and `admin`
(see [cli/commands/](cli/commands/) for the current generated list).

All CLI commands are auto-generated from the actual command definitions, ensuring documentation stays synchronized with the code.

### [MCP Tools](mcp/)
Complete reference for all Model Context Protocol (MCP) tools exposed to
Claude Desktop / Claude Code.

The generated set lives under [mcp/tools/](mcp/tools/) and covers
search/query, ingestion, concept and graph inspection, ontology, job
management, polarity / epistemic-status analysis, source/document/artifact
inspection, programs (executable graph operations), epoch tracking, and
session context.

All MCP tool documentation is auto-generated from the tool schemas, ensuring accuracy and completeness.

## 🌐 API Reference

### [REST API](api/)
Interactive OpenAPI/Swagger documentation for the Knowledge Graph HTTP API.

**Coverage:** All REST endpoints organized by tag (see `openapi.json` for the
authoritative list). Current top-level tags:
- health - Liveness/readiness probes
- authentication - OAuth 2.0 login, tokens, API keys (ADR-054)
- ingestion - Document submission and processing
- jobs - Async job management and monitoring
- queries - Graph exploration and concept search
- database - Database introspection and admin
- ontology - Knowledge domain organization
- vocabulary - Relationship type management
- embedding - Embedding configuration and inspection
- extraction - Extraction configuration
- admin - System administration
- rbac - Role-based access control

API documentation uses industry-standard Swagger UI for interactive exploration, testing, and schema browsing.

## 🤖 Auto-Generation

### Tool Documentation (CLI + MCP)
Generated during the build process:

```bash
cd cli && npm run build
```

**Features:**
- Extracts from source code (CLI commands, MCP tool schemas)
- Git churn prevention (only writes if content changed)
- Synchronized with code changes
- No manual maintenance required

**Generators (in `cli/scripts/`):**
- `simple-doc-gen.mjs` - CLI documentation
- `generate-mcp-docs.mjs` - MCP documentation
- `doc-utils.mjs` - Smart write utilities
- `check-docs.js` - Lint/check rendered docs

### API Documentation
Exported from running API server:

```bash
curl http://localhost:8000/openapi.json > docs/reference/openapi.json
```

**Features:**
- ✅ Standard OpenAPI 3.1.0 specification
- ✅ Interactive Swagger UI (mkdocs-swagger-ui-tag plugin)
- ✅ Matches FastAPI's auto-generated schema
- ✅ Industry-standard documentation approach

## 📖 Structure

```
reference/
├── README.md                       (this file)
├── ARCHITECTURE_OVERVIEW.md        (system architecture)
├── OPERATOR_ARCHITECTURE.md        (install.sh + operator.sh + kg-operator)
├── RECURSIVE_UPSERT_ARCHITECTURE.md (concept matching pattern)
├── STORAGE-ARCHITECTURE.md         (PostgreSQL + Garage + AGE tiers)
├── openapi.json                    (exported FastAPI schema)
├── cli/
│   ├── README.md                   (CLI index)
│   ├── commands/                   (auto-generated)
│   └── media/                      (screenshots, diagrams)
├── mcp/
│   ├── README.md                   (MCP index)
│   ├── tools/                      (auto-generated)
│   └── media/                      (screenshots, diagrams)
├── fuse/
│   └── README.md                   (FUSE driver reference)
└── api/
    └── README.md                   (REST API with embedded Swagger UI)
```

## 🔗 Related Documentation

- **Manual:** User-facing guides and tutorials
- **Architecture:** System design and ADRs
- **Development:** Contributing guidelines and dev workflows
