# Remote Deployment (GitHub Artifacts)

Deploy from published GitHub release artifacts without needing source code.

## Overview

Remote deployment pulls pre-built Docker images and binaries from GitHub releases. This is the production deployment path for end users who don't need source code access.

## Scripts

### `deploy-from-release.sh`
Deploy entire stack from GitHub release:
```bash
./deploy-from-release.sh [options]
```

Options:
- `--version <tag>` - Specific release version (e.g., v0.2.0)
- `--latest` - Use latest release (default)
- `--ghcr` - Pull from GitHub Container Registry
- `--clean` - Remove existing containers first

Examples:
```bash
# Deploy latest release
./deploy-from-release.sh --latest

# Deploy specific version
./deploy-from-release.sh --version v0.2.0

# Clean install
./deploy-from-release.sh --version v0.2.0 --clean
```

## What Gets Deployed

When deploying from a release, the script:

1. **Pulls Docker images** from GitHub Container Registry (GHCR):
   - `ghcr.io/aaronsb/kg-database:v0.2.0`
   - `ghcr.io/aaronsb/kg-api:v0.2.0`
   - `ghcr.io/aaronsb/kg-viz:v0.2.0`

2. **Downloads binaries** from GitHub release:
   - CLI tool: `kg-linux-x64`, `kg-darwin-x64`, `kg-darwin-arm64`, `kg-windows-x64.exe`
   - MCP server: `kg-mcp-server-<platform>`

3. **Starts containers** using docker-compose:
   - Database (PostgreSQL + AGE)
   - API server
   - Visualization server

4. **Installs CLI** to system:
   - Linux/macOS: `/usr/local/bin/kg`
   - Windows: `C:\Program Files\Knowledge Graph\kg.exe`

## Prerequisites

- Docker + Docker Compose
- Internet connection (to pull from GitHub)
- Optional: GitHub personal access token (for private repos)

## Configuration

Configuration is managed through environment variables or config file:

```bash
# Create config file
cat > ~/.kg/config.yml <<EOF
api:
  url: http://localhost:8000
database:
  host: localhost
  port: 5432
version: v0.2.0
EOF
```

Or use environment variables:
```bash
export KG_API_URL=http://localhost:8000
export KG_RELEASE_VERSION=v0.2.0
```

## GitHub Authentication

For private repositories, set GitHub token:

```bash
export GITHUB_TOKEN=ghp_xxxxxxxxxxxx
./deploy-from-release.sh --version v0.2.0
```

The script uses the token to:
- Pull from GHCR (if repo is private)
- Download release artifacts
- Check release metadata

## Verifying Release

Before deploying, verify the release:

```bash
# List available releases
gh release list --repo aaronsb/knowledge-graph-system

# View release notes
gh release view v0.2.0 --repo aaronsb/knowledge-graph-system

# Check artifacts
gh release view v0.2.0 --json assets --jq '.assets[].name'
```

## Deployment Process

Detailed steps the script performs:

1. **Validate release**
   - Check release exists on GitHub
   - Verify all required artifacts present
   - Validate checksums

2. **Pull containers**
   ```bash
   docker pull ghcr.io/aaronsb/kg-database:v0.2.0
   docker pull ghcr.io/aaronsb/kg-api:v0.2.0
   docker pull ghcr.io/aaronsb/kg-viz:v0.2.0
   ```

3. **Download binaries**
   ```bash
   # Detect platform
   PLATFORM=$(uname -s)-$(uname -m)

   # Download CLI
   gh release download v0.2.0 --pattern "kg-${PLATFORM}" --dir /tmp

   # Install
   sudo mv /tmp/kg-${PLATFORM} /usr/local/bin/kg
   chmod +x /usr/local/bin/kg
   ```

4. **Start services**
   ```bash
   docker-compose -f docker-compose.release.yml up -d
   ```

5. **Initialize system**
   ```bash
   # Wait for services to be ready
   # Run database migrations
   # Seed initial data
   kg health
   ```

## Rollback

To roll back to a previous version:

```bash
# Stop current version
docker-compose down

# Deploy previous version
./deploy-from-release.sh --version v0.1.9

# Verify
kg --version
```

## Updates

To update to a newer release:

```bash
# Pull latest
./deploy-from-release.sh --latest

# Or specific version
./deploy-from-release.sh --version v0.2.1
```

Data is preserved across updates (stored in Docker volumes).

## Production Considerations

### Security
- Use secrets management (not .env files)
- Enable TLS/SSL
- Configure firewall rules
- Use non-root container users

### Persistence
- Docker volumes for data
- Backup strategy for PostgreSQL
- Configuration in version control

### Monitoring
- Container health checks
- Log aggregation (e.g., ELK, Loki)
- Metrics (Prometheus, Grafana)

### Scaling
- Multiple API server replicas
- Load balancer (nginx, traefik)
- Database replication

## Troubleshooting

### Can't pull Docker images
```bash
# Authenticate to GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Verify image exists
docker pull ghcr.io/aaronsb/kg-database:v0.2.0
```

### Release artifacts not found
```bash
# Check release exists
gh release view v0.2.0 --repo aaronsb/knowledge-graph-system

# List artifacts
gh release view v0.2.0 --json assets --jq '.assets'
```

### Container won't start
```bash
# Check logs
docker-compose logs kg-api

# Verify image
docker images | grep kg-api

# Re-pull image
docker-compose pull kg-api
docker-compose up -d kg-api
```

## See Also

- [Local Deployment](../local/README.md)
- [Installation Scripts](../../install/README.md)
- [GitHub Actions](../../github/README.md)
