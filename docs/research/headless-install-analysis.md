# Headless Install Analysis

Research into improving the platform installation experience for remote/headless deployments.

## Current State

### What We Have

The platform already supports headless installation via `operator.sh`:

```bash
./operator.sh init --headless \
  --container-prefix=kg \
  --image-source=ghcr \
  --web-hostname=kg.example.com \
  --ai-provider=openai \
  --ai-model=gpt-4o \
  --ai-key="$OPENAI_API_KEY"
```

**Capabilities:**
- Non-interactive mode with CLI flags
- GPU auto-detection (nvidia, amd, mac, cpu)
- GHCR image support (`--image-source=ghcr`)
- Configurable container naming
- AI provider configuration
- Web hostname for OAuth redirects

**Current Workflow:**
1. Clone the repository (or have docker-compose files)
2. Run `./operator.sh init --headless [OPTIONS]`
3. Script generates secrets, starts containers, configures services

### Gap: No Remote Install Script

The current process requires having the repository files locally. There's no:
- `curl | bash` one-liner that works from scratch
- Standalone installer that downloads compose files
- Bootstrap script for fresh servers

---

## How Other Platforms Do It

### Coolify (Reference Implementation)

**Install command:**
```bash
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

**What the script does:**
1. Detects OS and installs dependencies (curl, wget, git, jq, openssl)
2. Verifies SSH server is running
3. Installs/configures Docker 27.0
4. Downloads docker-compose files from CDN
5. Manages .env with backup/merge logic
6. Generates security credentials (APP_ID, APP_KEY, DB passwords)
7. Generates SSH keys for container-host communication
8. Pulls and starts containers
9. Monitors health status
10. Displays access URLs

**Key patterns:**
- Single script handles everything
- Downloads compose files (doesn't require git clone)
- Auto-generates all secrets
- Health check validation before declaring success
- Shows IP addresses for access

Source: [Coolify Installation Docs](https://coolify.io/docs/get-started/installation)

### n8n-auto-install

**Install command:**
```bash
curl -sSL https://raw.githubusercontent.com/liamdmcgarrigle/n8n-auto-install/main/install.sh | bash
bash n8n-auto-install/setup.sh
```

**What the script does:**
1. Detects OS (Ubuntu, Debian, Fedora, CentOS, macOS)
2. Installs dependencies via package manager
3. Clones repository
4. Prompts for configuration (interactive)
5. Generates docker-compose.yaml and .env from templates
6. Optionally sets up Cloudflare tunnel

**Key patterns:**
- Two-phase: download then configure
- Template-based compose generation
- Supports multiple Linux distros

Source: [n8n-auto-install GitHub](https://github.com/liamdmcgarrigle/n8n-auto-install)

### Docker Official Pattern

```bash
curl -fsSL https://get.docker.com | bash
```

**Pattern:** Single script that handles all OS detection and installation.

Source: [docker/docker-install](https://github.com/docker/docker-install)

---

## Comparison

| Feature | KG System | Coolify | n8n-auto-install |
|---------|-----------|---------|------------------|
| curl \| bash install | ❌ | ✅ | ✅ |
| No git clone needed | ❌ | ✅ | ❌ |
| Auto-installs Docker | ❌ | ✅ | ❌ |
| Headless mode | ✅ | ✅ | ❌ (interactive) |
| GPU detection | ✅ | ❌ | ❌ |
| Secret generation | ✅ | ✅ | ✅ |
| Health monitoring | ✅ | ✅ | ❌ |
| Multi-container | ✅ (5) | ✅ | ✅ (1-2) |
| Registry images | ✅ (GHCR) | ✅ | ✅ |

---

## Proposed Improvements

### Option 1: Remote Install Script (Recommended)

Create a standalone `install.sh` that can be curl'd:

```bash
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/install.sh | bash
```

**Script would:**
1. Check prerequisites (Docker, docker-compose)
2. Create install directory (e.g., `/opt/knowledge-graph` or `~/knowledge-graph`)
3. Download required files from GitHub:
   - `docker-compose.yml`
   - `docker-compose.prod.yml`
   - `docker-compose.ghcr.yml`
   - `.env.example`
   - `operator/` scripts (or embed logic)
4. Generate `.env` with secrets
5. Pull GHCR images
6. Start containers
7. Run initial configuration (admin user, OAuth clients)
8. Display access information

**Flags to support:**
```bash
# Full headless
curl ... | bash -s -- \
  --hostname kg.example.com \
  --ai-provider openai \
  --ai-key "$OPENAI_API_KEY"

# Interactive (prompts for config)
curl ... | bash
```

### Option 2: Docker Compose Only (Simpler)

Publish a minimal "quick start" that just needs docker-compose:

```bash
# Download compose files
curl -fsSL https://raw.githubusercontent.com/.../docker-compose.standalone.yml > docker-compose.yml

# Generate secrets and start
docker compose up -d
```

This would require a self-contained compose file that:
- Uses GHCR images
- Auto-generates secrets on first run (via init container)
- Has sensible defaults

**Tradeoff:** Less flexible, harder to configure AI providers.

### Option 3: Helm Chart (Kubernetes)

For K8s deployments, a Helm chart would be the standard approach:

```bash
helm repo add kg https://aaronsb.github.io/knowledge-graph-system
helm install kg kg/knowledge-graph --set hostname=kg.example.com
```

**Scope:** Larger effort, different target audience.

---

## Recommendation

**Start with Option 1** - a remote install script that:

1. Works on fresh Ubuntu/Debian servers (primary target)
2. Installs Docker if missing
3. Downloads compose files from GitHub
4. Generates secrets
5. Supports both interactive and headless modes
6. Uses GHCR images by default

This gives us the "curl | bash" experience while reusing the existing headless-init logic.

---

## Implementation Sketch

```bash
#!/bin/bash
# install.sh - Knowledge Graph Platform Installer

set -e

KG_VERSION="${KG_VERSION:-latest}"
KG_INSTALL_DIR="${KG_INSTALL_DIR:-$HOME/knowledge-graph}"
KG_REPO="https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main"

# 1. Check/install Docker
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com | bash
fi

# 2. Create install directory
mkdir -p "$KG_INSTALL_DIR"
cd "$KG_INSTALL_DIR"

# 3. Download compose files
curl -fsSL "$KG_REPO/docker/docker-compose.yml" > docker-compose.yml
curl -fsSL "$KG_REPO/docker/docker-compose.ghcr.yml" > docker-compose.ghcr.yml
# ... more files

# 4. Generate secrets
generate_secrets() {
    ENCRYPTION_KEY=$(python3 -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())")
    # ... etc
}

# 5. Create .env
cat > .env << EOF
ENCRYPTION_KEY=$ENCRYPTION_KEY
...
EOF

# 6. Pull and start
docker compose -f docker-compose.yml -f docker-compose.ghcr.yml pull
docker compose -f docker-compose.yml -f docker-compose.ghcr.yml up -d

# 7. Wait for health
wait_for_health

# 8. Configure (admin user, etc.)
docker exec kg-operator python /workspace/operator/configure.py admin

# 9. Display info
echo "Knowledge Graph installed!"
echo "Access: http://$(hostname -I | awk '{print $1}'):3000"
```

---

## Next Steps

1. [ ] Decide on approach (Option 1 recommended)
2. [ ] Create `install.sh` script
3. [ ] Test on fresh Ubuntu 22.04/24.04 VMs
4. [ ] Add to repository root
5. [ ] Document in README
6. [ ] Consider adding to releases as downloadable asset

---

## References

- [Coolify Installation](https://coolify.io/docs/get-started/installation)
- [n8n-auto-install](https://github.com/liamdmcgarrigle/n8n-auto-install)
- [Docker Install Script](https://github.com/docker/docker-install)
- [Haxxnet/Compose-Examples](https://github.com/Haxxnet/Compose-Examples)
