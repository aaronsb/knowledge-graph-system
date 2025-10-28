# GitHub Actions Workflows

CI/CD workflows for building and publishing Knowledge Graph artifacts.

## Overview

GitHub Actions automate the build, test, and release process. Workflows are triggered by code pushes, pull requests, and release tags.

## Workflows

### `build-artifacts.yml`
Build and publish Docker images and binaries on every push.

**Triggers:**
- Push to `main` branch
- Pull request to `main`
- Manual workflow dispatch

**Jobs:**
1. **Test** - Run test suites
2. **Build Images** - Build Docker images for all architectures
3. **Build Binaries** - Build CLI/MCP binaries for all platforms
4. **Publish** - Push to GHCR (main branch only)

**Artifacts:**
- Docker images → GHCR
- Binaries → Workflow artifacts (30-day retention)

### `create-release.yml`
Create GitHub releases with all artifacts.

**Triggers:**
- Tag push matching `v*.*.*` (e.g., v0.2.0)

**Jobs:**
1. **Build** - Build all components
2. **Test** - Run full test suite
3. **Package** - Create release packages
4. **Publish** - Create GitHub release
5. **Notify** - Send notifications

**Artifacts:**
- Docker images → GHCR (tagged)
- Binaries → GitHub release
- Release notes → GitHub release
- Checksums → GitHub release

## Workflow Details

### Build Artifacts Workflow

```yaml
name: Build Artifacts

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Run Python tests
      - name: Run TypeScript tests
      - name: Run integration tests

  build-images:
    needs: test
    runs-on: ubuntu-latest
    strategy:
      matrix:
        component: [api, viz, database]
        platform: [linux/amd64, linux/arm64]
    steps:
      - name: Set up QEMU
      - name: Set up Docker Buildx
      - name: Build and push

  build-binaries:
    needs: test
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, macos-latest, windows-latest]
        arch: [x64, arm64]
    steps:
      - name: Build CLI
      - name: Build MCP server
      - name: Upload artifacts
```

### Create Release Workflow

```yaml
name: Create Release

on:
  push:
    tags:
      - 'v*.*.*'

jobs:
  build-and-release:
    runs-on: ubuntu-latest
    steps:
      - name: Extract version from tag
      - name: Build all components
      - name: Run tests
      - name: Create release
      - name: Upload Docker images
      - name: Upload binaries
      - name: Generate checksums
      - name: Update release notes
```

## Secrets and Variables

### Required Secrets
- `GHCR_TOKEN` - GitHub token for GHCR access
- `OPENAI_API_KEY` - For integration tests (optional)

### Variables
- `REGISTRY` - Container registry (ghcr.io)
- `IMAGE_PREFIX` - Image prefix (aaronsb/kg)

### Setting Secrets
```bash
# Via GitHub CLI
gh secret set GHCR_TOKEN --body "$TOKEN"

# Via web UI
# Settings → Secrets and variables → Actions → New repository secret
```

## Building Locally (Testing Workflows)

### Using Act
```bash
# Install act
brew install act  # macOS
# or from https://github.com/nektos/act

# Run workflow locally
act -j test  # Run test job
act -j build-images  # Run build job

# Full workflow
act push
```

### Manual Testing
```bash
# Simulate build process
docker build -f build/docker/api.Dockerfile -t test-image .

# Test release script
./build/github/test-release.sh
```

## Release Process

### Automated Release (Recommended)
```bash
# 1. Update version in code
vim client/package.json  # Update version
vim src/api/main.py      # Update version

# 2. Commit changes
git add .
git commit -m "chore: bump version to v0.2.0"

# 3. Create and push tag
git tag -a v0.2.0 -m "Release v0.2.0"
git push origin v0.2.0

# 4. GitHub Actions builds and creates release automatically
```

### Manual Release
```bash
# Build locally
./build/local/build-all.sh

# Create GitHub release
gh release create v0.2.0 \
  --title "v0.2.0" \
  --notes "Release notes here" \
  dist/*

# Upload Docker images
docker tag kg-api:latest ghcr.io/aaronsb/kg-api:v0.2.0
docker push ghcr.io/aaronsb/kg-api:v0.2.0
```

## Docker Image Publishing

Images are published to GitHub Container Registry:

```
ghcr.io/aaronsb/kg-database:latest
ghcr.io/aaronsb/kg-database:v0.2.0
ghcr.io/aaronsb/kg-api:latest
ghcr.io/aaronsb/kg-api:v0.2.0
ghcr.io/aaronsb/kg-viz:latest
ghcr.io/aaronsb/kg-viz:v0.2.0
```

Tags:
- `latest` - Latest build from main
- `v0.2.0` - Specific release version
- `main-abc1234` - Commit-specific builds

## Binary Distribution

Binaries are attached to GitHub releases:

```
kg-linux-x64
kg-linux-arm64
kg-darwin-x64
kg-darwin-arm64
kg-windows-x64.exe
kg-mcp-server-linux-x64
kg-mcp-server-darwin-arm64
...
```

Each binary includes:
- Compiled executable
- Checksum file (SHA256)
- Signature (optional)

## Monitoring Workflows

### View Runs
```bash
# List workflow runs
gh run list

# View specific run
gh run view <run-id>

# Watch run in real-time
gh run watch
```

### Debugging Failures
```bash
# View logs
gh run view <run-id> --log

# Download artifacts
gh run download <run-id>

# Re-run failed jobs
gh run rerun <run-id> --failed
```

## Caching

Workflows use caching to speed up builds:

### Docker Layer Caching
```yaml
- name: Cache Docker layers
  uses: actions/cache@v3
  with:
    path: /tmp/.buildx-cache
    key: ${{ runner.os }}-buildx-${{ github.sha }}
    restore-keys: |
      ${{ runner.os }}-buildx-
```

### Dependency Caching
```yaml
- name: Cache pip dependencies
  uses: actions/cache@v3
  with:
    path: ~/.cache/pip
    key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}

- name: Cache npm dependencies
  uses: actions/cache@v3
  with:
    path: ~/.npm
    key: ${{ runner.os }}-npm-${{ hashFiles('package-lock.json') }}
```

## Matrix Builds

Build for multiple platforms in parallel:

```yaml
strategy:
  matrix:
    os: [ubuntu-latest, macos-latest, windows-latest]
    arch: [x64, arm64]
    exclude:
      - os: windows-latest
        arch: arm64  # Windows ARM not supported yet
```

## Security

### Scanning
Workflows include security scanning:
- Trivy for container vulnerabilities
- CodeQL for code analysis
- Dependency scanning

### SBOM Generation
Generate Software Bill of Materials:
```yaml
- name: Generate SBOM
  uses: anchore/sbom-action@v0
  with:
    image: ghcr.io/aaronsb/kg-api:${{ github.sha }}
    format: cyclonedx-json
```

## Notifications

Post-build notifications:
- GitHub commit status checks
- Pull request comments
- Slack notifications (optional)
- Email notifications (optional)

## Best Practices

1. **Test before merge** - All PRs run tests
2. **Cache aggressively** - Speed up builds
3. **Fail fast** - Stop on first failure
4. **Matrix builds** - Parallel platform builds
5. **Artifact retention** - 30-day retention for builds
6. **Security scanning** - Automated vulnerability checks

## Troubleshooting

### Build fails on specific platform
```bash
# Run locally with same environment
act -P ubuntu-latest=nektos/act-environments-ubuntu:18.04

# Check platform-specific code
grep -r "platform.system()" src/
```

### Docker push fails
```bash
# Check GHCR authentication
echo $GHCR_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Verify permissions
gh api user/packages
```

### Artifacts not uploading
```bash
# Check artifact paths exist
ls -la dist/

# Verify upload action config
cat .github/workflows/build-artifacts.yml | grep -A5 upload-artifact
```

## See Also

- [GitHub Actions Docs](https://docs.github.com/en/actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [Release Please Action](https://github.com/googleapis/release-please-action)
