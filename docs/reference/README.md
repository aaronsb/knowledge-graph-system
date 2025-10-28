# Tool & API Reference

Reference documentation for the Knowledge Graph System's tools and REST API.

## 📚 Tool Reference

### [CLI Commands](cli/)
Complete reference for all `kg` command-line interface commands.

**Coverage:** 8 commands (health, config, ingest, search, database, ontology, vocabulary, admin)

All CLI commands are auto-generated from the actual command definitions, ensuring documentation stays synchronized with the code.

### [MCP Tools](mcp/)
Complete reference for all Model Context Protocol (MCP) tools exposed to Claude Desktop.

**Coverage:** 19 tools across 6 categories
- Search & Query (5 tools)
- Database (3 tools)
- Ontology (4 tools)
- Job Management (4 tools)
- Ingestion (1 tool)
- System (2 tools)

All MCP tool documentation is auto-generated from the tool schemas, ensuring accuracy and completeness.

## 🌐 API Reference

### [REST API](api/)
Interactive OpenAPI/Swagger documentation for the Knowledge Graph HTTP API.

**Coverage:** All REST endpoints organized by tag
- Authentication - User registration, login, API keys
- Ingestion - Document submission and processing
- Jobs - Async job management and monitoring
- Queries - Graph exploration and concept search
- Ontology - Knowledge domain organization
- Vocabulary - Relationship type management
- Admin - System administration
- RBAC - Role-based access control

API documentation uses industry-standard Swagger UI for interactive exploration, testing, and schema browsing.

## 🤖 Auto-Generation

### Tool Documentation (CLI + MCP)
Generated during the build process:

```bash
cd client && npm run build
```

**Features:**
- ✅ Extracts from source code (CLI commands, MCP tool schemas)
- ✅ Git churn prevention (only writes if content changed)
- ✅ Synchronized with code changes
- ✅ No manual maintenance required

**Generators:**
- `client/scripts/simple-doc-gen.mjs` - CLI documentation
- `client/scripts/generate-mcp-docs.mjs` - MCP documentation
- `client/scripts/doc-utils.mjs` - Smart write utilities

### API Documentation
Exported from running API server:

```bash
curl http://localhost:8000/openapi.json > docs/openapi.json
```

**Features:**
- ✅ Standard OpenAPI 3.1.0 specification
- ✅ Interactive Swagger UI (mkdocs-swagger-ui-tag plugin)
- ✅ Matches FastAPI's auto-generated schema
- ✅ Industry-standard documentation approach

## 📖 Structure

```
reference/
├── README.md                   (this file)
├── cli/
│   ├── README.md              (CLI index)
│   ├── commands/              (auto-generated)
│   └── media/                 (screenshots, diagrams)
├── mcp/
│   ├── README.md              (MCP index)
│   ├── tools/                 (auto-generated)
│   └── media/                 (screenshots, diagrams)
└── api/
    └── README.md              (REST API with embedded Swagger UI)
```

## 🔗 Related Documentation

- **Manual:** User-facing guides and tutorials
- **Architecture:** System design and ADRs
- **Development:** Contributing guidelines and dev workflows
