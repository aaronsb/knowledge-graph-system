# Local Build Scripts

Scripts for building all components locally for development purposes.

## Overview

These scripts build artifacts from source code in your local repository. Use these when:
- Actively developing and testing changes
- Need to rebuild specific components
- Want to test the build process before CI/CD

## Scripts

### `build-all.sh`
Build all components in dependency order:
```bash
./build-all.sh [--clean] [--verbose]
```

Options:
- `--clean` - Clean build artifacts before building
- `--verbose` - Show detailed build output

### `build-database.sh`
Build and prepare the database container:
```bash
./build-database.sh
```

What it does:
- Verifies docker-compose.yml
- Pulls/builds Apache AGE + PostgreSQL image
- Validates schema files
- **Note:** Uses existing docker-compose.yml (not yet creating custom image)

### `build-api.sh`
Build the API server:
```bash
./build-api.sh [--docker]
```

Options:
- `--docker` - Build Docker image (future)

What it does:
- Installs Python dependencies
- Runs tests (if any)
- Prepares venv
- **Future:** Build Docker image

### `build-viz.sh`
Build the visualization server:
```bash
./build-viz.sh
```

**Status:** Stub - visualization server not yet implemented

### `build-cli.sh`
Build the CLI tool:
```bash
./build-cli.sh [--install]
```

Options:
- `--install` - Install globally after building

What it does:
- Installs npm dependencies
- Runs TypeScript compiler
- Generates documentation
- Optionally installs `kg` command globally

### `build-mcp.sh`
Build the MCP server:
```bash
./build-mcp.sh
```

What it does:
- Shares build process with CLI
- Compiles MCP server entry point
- Prepares dist/mcp-server.js

## Build Order

Components are built in dependency order:

1. **Database** - No dependencies
2. **API Server** - Requires database schema knowledge
3. **CLI Tool** - Requires API to be defined
4. **MCP Server** - Shares code with CLI
5. **Visualization** - Requires API server

## Environment Requirements

- **Node.js** 18+ (for CLI/MCP)
- **Python** 3.11+ (for API)
- **Docker** + Docker Compose (for database)
- **Git** (for version info)

## Output Artifacts

| Component | Output Location | Type |
|-----------|----------------|------|
| Database | Docker image | Container |
| API Server | `venv/` | Python venv |
| CLI Tool | `client/dist/` | JS/TS artifacts |
| MCP Server | `client/dist/` | JS/TS artifacts |
| Visualization | TBD | TBD |

## Development Workflow

```bash
# 1. Make changes to code
vim src/api/routes/queries.py

# 2. Rebuild affected component
./build/local/build-api.sh

# 3. Deploy locally for testing
../deploy/local/deploy-api.sh

# 4. Test changes
kg health
```

## Troubleshooting

### Build fails with "command not found"
- Check environment requirements above
- Ensure all tools are in PATH

### TypeScript compilation errors
```bash
cd client
npm install  # Reinstall dependencies
npm run build  # Try direct build
```

### Python dependency issues
```bash
cd /path/to/repo
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## See Also

- [Build Architecture](../README.md)
- [Local Deployment](../deploy/local/README.md)
- [Development Guide](../../CLAUDE.md)
