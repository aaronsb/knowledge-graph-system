# API Reference

Auto-generated reference documentation for the Knowledge Graph System's command-line interface and MCP tools.

## 📚 Available References

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

## 🤖 Auto-Generation

This documentation is automatically generated during the build process:

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

## 📖 Structure

```
reference/
├── README.md                   (this file)
├── cli/
│   ├── README.md              (CLI index)
│   ├── commands/              (auto-generated)
│   └── media/                 (screenshots, diagrams)
└── mcp/
    ├── README.md              (MCP index)
    ├── tools/                 (auto-generated)
    └── media/                 (screenshots, diagrams)
```

## 🔗 Related Documentation

- **Manual:** User-facing guides and tutorials
- **Architecture:** System design and ADRs
- **Development:** Contributing guidelines and dev workflows
