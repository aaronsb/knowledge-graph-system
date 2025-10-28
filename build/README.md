# Build, Deploy, and Install Tooling

This directory contains scripts and configurations for building, deploying, and installing the Knowledge Graph system. This is distinct from `/scripts/` which contains operational tools for running and managing an existing installation.

## Architecture Overview

The Knowledge Graph system consists of five major components:

1. **Database** - Apache AGE + PostgreSQL (containerized)
2. **API Server** - Python FastAPI server (to be containerized)
3. **Visualization Server** - Web-based graph visualization (to be containerized)
4. **CLI Tool** - TypeScript command-line interface
5. **MCP Server** - TypeScript Model Context Protocol server (shares code with CLI)

## Deployment Strategies

### Local Development (Developer Workflow)

Build artifacts and deploy locally for development:

```bash
# Build all components
./build/local/build-all.sh

# Deploy locally for development
./deploy/local/deploy-all.sh
```

**Use case:** Active development, testing changes, debugging

### Local Installation (Production-like)

Install from locally built artifacts:

```bash
# Build and install locally (production mode)
./install/install-local.sh
```

**Use case:** Local production deployment, testing release process

### Remote Installation (End-user Deployment)

Deploy from GitHub release artifacts:

```bash
# Install from latest GitHub release
./install/install-remote.sh
```

**Use case:** End-user installation, production deployment without source

## Directory Structure

```
build/
├── README.md              # This file - architecture overview
├── local/                 # Local development builds
│   ├── build-all.sh       # Build all components
│   ├── build-database.sh  # Build database container
│   ├── build-api.sh       # Build API server (Docker + artifacts)
│   ├── build-viz.sh       # Build visualization server
│   ├── build-cli.sh       # Build CLI tool
│   ├── build-mcp.sh       # Build MCP server
│   └── README.md
├── deploy/                # Deployment scripts
│   ├── local/            # Deploy locally (dev environment)
│   │   ├── deploy-all.sh
│   │   ├── deploy-database.sh
│   │   ├── deploy-api.sh
│   │   ├── deploy-viz.sh
│   │   └── README.md
│   ├── remote/           # Deploy from GitHub artifacts
│   │   ├── deploy-from-release.sh
│   │   └── README.md
│   └── README.md
├── install/              # Installation scripts (end-user)
│   ├── install-local.sh  # Install from local build
│   ├── install-remote.sh # Install from GitHub release
│   └── README.md
├── docker/               # Docker configurations
│   ├── api.Dockerfile         # API server container
│   ├── viz.Dockerfile         # Visualization server container
│   ├── compose/
│   │   ├── docker-compose.local.yml    # Local dev stack
│   │   └── docker-compose.release.yml  # Release stack
│   └── README.md
└── github/              # GitHub Actions workflows (CI/CD)
    ├── build-artifacts.yml    # Build and publish artifacts
    ├── create-release.yml     # Create GitHub releases
    └── README.md
```

## Component Status

| Component | Local Build | Containerized | GitHub Artifacts | Status |
|-----------|-------------|---------------|------------------|--------|
| Database | ✓ (docker-compose) | ✓ | ⏳ TODO | Functional |
| API Server | ⏳ TODO | ⏳ TODO | ⏳ TODO | Stub |
| Visualization | ⏳ TODO | ⏳ TODO | ⏳ TODO | Stub |
| CLI Tool | ✓ (npm build) | N/A | ⏳ TODO | Functional |
| MCP Server | ✓ (npm build) | N/A | ⏳ TODO | Functional |

## Roadmap

### Phase 1: Local Development Builds (Current)
- [x] Directory structure
- [ ] Database build script
- [ ] API server build script (prepare for Docker)
- [ ] CLI build integration
- [ ] MCP build integration
- [ ] Local deployment scripts

### Phase 2: Containerization
- [ ] API server Dockerfile
- [ ] Visualization server Dockerfile
- [ ] Docker Compose for full stack
- [ ] Local container orchestration

### Phase 3: GitHub Artifacts & Releases
- [ ] GitHub Actions for builds
- [ ] Publish Docker images to GHCR
- [ ] Create releases with binaries
- [ ] Remote installation from releases

### Phase 4: Production Deployment
- [ ] Production Docker Compose
- [ ] Kubernetes manifests (optional)
- [ ] Deployment documentation
- [ ] Migration tools

## Design Principles

1. **Separation of Concerns**
   - `/scripts/` - Operating an existing installation
   - `/build/` - Building and deploying new installations

2. **Progressive Enhancement**
   - Start with local builds (dev workflow)
   - Add containerization (consistency)
   - Add remote artifacts (distribution)

3. **Flexibility**
   - Support both local and remote deployment
   - Allow partial component updates
   - Enable development and production modes

4. **Automation**
   - Scriptable builds
   - CI/CD integration
   - One-command installations

## Related Documentation

- [Deployment Guide](../docs/guides/DEPLOYMENT.md) - End-user deployment instructions
- [Development Guide](../CLAUDE.md) - Developer setup and workflow
- [Docker Documentation](./docker/README.md) - Container configuration details

## Usage Examples

### Developer: Build and test locally
```bash
# Build components
./build/local/build-all.sh

# Deploy to local environment
./deploy/local/deploy-all.sh

# Run tests
cd client && npm test
```

### DevOps: Install from release
```bash
# Install latest release
./install/install-remote.sh --version v0.2.0

# Verify installation
kg health
```

### CI/CD: Build release artifacts
```bash
# GitHub Actions will:
# 1. Build Docker images
# 2. Publish to GHCR
# 3. Create GitHub release
# 4. Attach binaries

# Triggered by:
git tag v0.2.0
git push origin v0.2.0
```

## Contributing

When adding new components or build steps:

1. Add build script to `build/local/`
2. Add deployment script to `deploy/local/`
3. Update `build-all.sh` and `deploy-all.sh`
4. Document in component's README
5. Add to GitHub Actions if applicable

## Questions & Support

- **Development setup:** See [CLAUDE.md](../CLAUDE.md)
- **Deployment issues:** See [docs/guides/DEPLOYMENT.md](../docs/guides/DEPLOYMENT.md)
- **Build issues:** Open GitHub issue with `build` label
