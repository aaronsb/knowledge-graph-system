# Quick Start

Get the knowledge graph running in 5 minutes. Choose your path:

| I want to... | Use |
|--------------|-----|
| Deploy on a server | [Production Install](#production-install) |
| Set up for development | [Development Setup](#development-setup) |

---

## Production Install

One command installs everything on a Linux server:

```bash
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/install.sh | bash
```

This starts an interactive installer that:
- Installs Docker if needed
- Downloads container images from GHCR
- Generates secure secrets
- Configures SSL/HTTPS (optional)
- Creates admin user

### Headless Mode

For automation, CI/CD, or scripted deployments:

```bash
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/install.sh | bash -s -- \
  --hostname kg.example.com \
  --ssl letsencrypt \
  --ssl-email admin@example.com \
  --ai-provider openai \
  --ai-key "$OPENAI_API_KEY"
```

**Common options:**

| Option | Description |
|--------|-------------|
| `--hostname` | Public hostname or IP (required for headless) |
| `--ssl MODE` | `offload`, `selfsigned`, `letsencrypt`, or `manual` |
| `--ssl-email` | Email for Let's Encrypt (required for letsencrypt) |
| `--ai-provider` | `openai`, `anthropic`, or `ollama` |
| `--ai-key` | API key for the provider |
| `--skip-ai` | Skip AI configuration (configure later) |
| `--gpu MODE` | `auto`, `nvidia`, `amd`, or `cpu` |

**Minimal headless (configure AI later):**
```bash
curl -fsSL .../install.sh | bash -s -- --hostname 192.168.1.100 --skip-ai
```

### After Installation

The installer shows access URLs and credentials. Your primary management tool is `operator.sh`:

```bash
cd ~/knowledge-graph   # or your install directory

./operator.sh status   # Check platform health
./operator.sh logs api # View API logs
./operator.sh shell    # Configuration shell
```

---

## Development Setup

Clone the repo and use `operator.sh init`:

```bash
git clone https://github.com/aaronsb/knowledge-graph-system.git
cd knowledge-graph-system
./operator.sh init
```

The init wizard will:
- Generate infrastructure secrets (`.env`)
- Detect your GPU (NVIDIA/Mac/CPU)
- Start all containers
- Prompt for admin password and AI configuration

### Headless Development Setup

```bash
./operator.sh init --headless \
  --container-mode dev \
  --gpu auto \
  --skip-ai-config
```

---

## Verify Installation

Check that everything is running:

```bash
./operator.sh status
```

You should see all containers healthy:
```
Container Status:
kg-postgres   Up (healthy)
kg-garage     Up (healthy)
kg-api        Up (healthy)
kg-web        Up (healthy)
kg-operator   Up
```

Access the system:
- **Web UI**: https://your-hostname (or http://localhost:3000 for dev)
- **API Docs**: https://your-hostname/api/docs
- **Login**: Use the admin credentials from installation

---

## Platform Management

After installation, `operator.sh` is your primary tool:

```bash
# Daily operations
./operator.sh start              # Start platform
./operator.sh stop               # Stop platform
./operator.sh status             # Check health

# Logs
./operator.sh logs api           # API logs (last 100 lines)
./operator.sh logs api -f        # Follow logs in real-time
./operator.sh logs web           # Web server logs

# Updates (like apt update/upgrade)
./operator.sh update             # Pull latest images
./operator.sh update operator    # Pull specific service
./operator.sh upgrade            # Pull, migrate, restart

# Configuration
./operator.sh shell              # Enter configuration shell
./operator.sh query 'SQL'        # Run database queries

# Maintenance
./operator.sh restart api        # Restart a service
./operator.sh teardown           # Remove containers (keeps data)
./operator.sh teardown --full    # Complete reset
```

Inside the configuration shell (`./operator.sh shell`):
```bash
configure.py status              # Show current config
configure.py ai-provider openai  # Change AI provider
configure.py api-key openai      # Store API key
configure.py oauth --list        # Manage OAuth clients
```

---

## Optional: Install the CLI

The `kg` CLI provides command-line access:

```bash
cd cli
npm install && npm run build
./install.sh
```

Test it:
```bash
kg health
kg search "your query"
kg ingest file document.pdf
```

---

## What's Next?

- [Production Deployment](production.md) - SSL, scaling, monitoring
- [Configuration Reference](configuration.md) - All settings explained
- [Troubleshooting](troubleshooting.md) - Common issues
- [Upgrading](upgrading.md) - Version updates
