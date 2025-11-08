# Container Images

The Knowledge Graph System publishes pre-built container images to GitHub Container Registry (GHCR), making it easy to deploy without building from source.

## Available Images

All images are published to `ghcr.io/aaronsb/knowledge-graph-system/`:

- **kg-api** - FastAPI REST API server (ingestion + queries)
- **kg-web** - React visualization web app
- **kg-operator** - Platform configuration and management container

## Image Tags

### Latest (main branch)
```bash
ghcr.io/aaronsb/knowledge-graph-system/kg-api:latest
ghcr.io/aaronsb/knowledge-graph-system/kg-web:latest
ghcr.io/aaronsb/knowledge-graph-system/kg-operator:latest
```

The `latest` tag always points to the most recent build from the `main` branch. Since `main` represents a functional platform, `latest` is always stable.

### Version Tags (releases)
```bash
ghcr.io/aaronsb/knowledge-graph-system/kg-api:1.2.3
ghcr.io/aaronsb/knowledge-graph-system/kg-web:1.2
ghcr.io/aaronsb/knowledge-graph-system/kg-operator:1.2.3
```

Semantic version tags (e.g., `1.2.3`) are created for official releases. Both full version (`1.2.3`) and major.minor (`1.2`) tags are available.

### Commit Tags (development)
```bash
ghcr.io/aaronsb/knowledge-graph-system/kg-api:main-abc1234
```

Every commit to `main` also gets tagged with its git SHA for traceability.

## Using Pre-Built Images

### Option 1: Docker Compose Override

Use the provided override file to pull from GHCR instead of building locally:

```bash
cd docker
docker-compose -f docker-compose.yml -f docker-compose.ghcr.yml up -d
```

This works with the standard operator workflow:

```bash
# Start infrastructure with GHCR images
cd docker
docker-compose -f docker-compose.yml -f docker-compose.ghcr.yml up -d postgres garage operator

# Start application with GHCR images
docker-compose -f docker-compose.yml -f docker-compose.ghcr.yml up -d api web
```

### Option 2: Pull Manually

Pull specific version images:

```bash
# Pull a specific version
docker pull ghcr.io/aaronsb/knowledge-graph-system/kg-api:1.2.3
docker pull ghcr.io/aaronsb/knowledge-graph-system/kg-web:1.2.3
docker pull ghcr.io/aaronsb/knowledge-graph-system/kg-operator:1.2.3

# Or pull latest
docker pull ghcr.io/aaronsb/knowledge-graph-system/kg-api:latest
docker pull ghcr.io/aaronsb/knowledge-graph-system/kg-web:latest
docker pull ghcr.io/aaronsb/knowledge-graph-system/kg-operator:latest
```

Then tag for local use:

```bash
docker tag ghcr.io/aaronsb/knowledge-graph-system/kg-api:latest kg-api:latest
docker tag ghcr.io/aaronsb/knowledge-graph-system/kg-web:latest kg-web:latest
docker tag ghcr.io/aaronsb/knowledge-graph-system/kg-operator:latest kg-operator:latest
```

## Using with Podman

GHCR images work identically with Podman:

```bash
# Pull with podman
podman pull ghcr.io/aaronsb/knowledge-graph-system/kg-api:latest

# Use podman-compose
podman-compose -f docker-compose.yml -f docker-compose.ghcr.yml up -d
```

## Authentication

Public images don't require authentication, but if you encounter rate limits:

```bash
# Docker
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Podman
echo $GITHUB_TOKEN | podman login ghcr.io -u USERNAME --password-stdin
```

## Release Process

### Creating a New Release

Releases are created manually via GitHub Actions:

1. Navigate to **Actions** → **Create Release**
2. Click **Run workflow**
3. Enter version bump type:
   - `patch` - Bug fixes (1.2.3 → 1.2.4)
   - `minor` - New features (1.2.3 → 1.3.0)
   - `major` - Breaking changes (1.2.3 → 2.0.0)
   - Or specify exact version: `1.5.0`
4. Optionally enable **dry run** to preview without creating the release

The workflow will:
- Calculate the next version number
- Generate a changelog from git commits
- Create a git tag (e.g., `v1.2.3`)
- Trigger container builds
- Create a GitHub Release with pull instructions

### Build Process

When a tag is pushed, the **Build and Push Containers** workflow:

1. Builds all three images (api, web, operator)
2. Tags with version numbers:
   - Full version: `1.2.3`
   - Major.minor: `1.2`
   - Latest: `latest` (only for main branch)
   - Commit SHA: `main-abc1234`
3. Pushes to GHCR with metadata labels
4. Uses GitHub Actions cache for faster builds

### Manual Version Tag

You can also create version tags manually:

```bash
git tag -a v1.2.3 -m "Release 1.2.3"
git push origin v1.2.3
```

This will trigger the container build workflow automatically.

## Image Metadata

All images include OCI-compliant metadata labels:

```bash
# Inspect image labels
docker inspect ghcr.io/aaronsb/knowledge-graph-system/kg-api:latest

# Shows:
# - org.opencontainers.image.revision: git commit SHA
# - org.opencontainers.image.created: build timestamp
# - org.opencontainers.image.version: semantic version
```

## Troubleshooting

### Image Pull Failures

If pulling fails, ensure you're using the full image path:

```bash
# ❌ Wrong
docker pull kg-api:latest

# ✅ Correct
docker pull ghcr.io/aaronsb/knowledge-graph-system/kg-api:latest
```

### Rate Limiting

GitHub Container Registry has generous rate limits for public images:
- Authenticated: Unlimited
- Anonymous: Very high (typically not an issue)

If you hit rate limits, authenticate with a GitHub token (see Authentication above).

### Version Not Found

Check available tags at:
https://github.com/aaronsb/knowledge-graph-system/pkgs/container/knowledge-graph-system%2Fkg-api

Or list tags via API:

```bash
curl -s https://api.github.com/users/aaronsb/packages/container/knowledge-graph-system%2Fkg-api/versions | jq -r '.[].metadata.container.tags[]'
```

## Local Development

For active development, continue using local builds:

```bash
# Use standard docker-compose (builds locally)
cd docker
docker-compose up -d

# Or use rebuild scripts
./scripts/development/build/rebuild-api.sh
./scripts/development/build/rebuild-web.sh
./scripts/development/build/rebuild-operator.sh
```

See [QUICKSTART.md](QUICKSTART.md) for the full development workflow.
