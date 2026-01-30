---
match: regex
pattern: kg\s+(cli|command|tool)|\bcli\b.*kg|mcp.*tool|MCP.*server|knowledge.?graph.*cli
commands: kg\s
---
# CLI & MCP Way

## Source Locations

**IMPORTANT**: CLI and MCP sources are at `./cli/` (not `client/`):

```
cli/
├── src/
│   ├── cli/           # kg command implementations
│   │   ├── polarity.ts
│   │   ├── artifact.ts
│   │   ├── search.ts
│   │   └── ...
│   ├── mcp/           # MCP server tools
│   │   └── tools/
│   └── api/
│       └── client.ts  # REST API client
├── install.sh         # Installs `kg` globally
└── package.json
```

## After CLI/MCP Changes

```bash
cd cli
npm run build       # Compile TypeScript
./install.sh        # Install `kg` command globally
```

Both CLI and MCP share the same build - `install.sh` handles everything.

## kg Command Patterns

- `kg <resource> list` - List resources
- `kg <resource> show <id>` - Show details
- `kg <resource> delete <id>` - Delete
- Unix aliases: `kg ls`, `kg cat`, `kg rm`

## MCP Tools

MCP tools call the REST API via `cli/src/api/client.ts`.
Tools are registered in `cli/src/mcp/tools/`.
