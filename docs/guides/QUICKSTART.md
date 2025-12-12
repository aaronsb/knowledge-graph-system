# Knowledge Graph System - Quick Start Guide

**Get from zero to operational knowledge graph system in under 10 minutes.**

This guide uses the **operator architecture (ADR-061)** - the official containerized deployment method. All configuration happens through dedicated operator containers - no local Python installation required.

## Prerequisites

- Docker or Podman with Docker Compose
- OpenAI API key (or use local embeddings)
- (Optional) Node.js + npm for `kg` CLI tool

**Supported Platforms:**
- ✅ **Linux with NVIDIA GPU** - Full GPU acceleration (CUDA)
- ✅ **Linux without GPU** - CPU-based embeddings
- ✅ **Mac (Intel/Apple Silicon)** - MPS acceleration on M1/M2/M3
- ✅ **Windows with WSL2** - Same as Linux

## Quick Start (Recommended)

```bash
# One command does everything:
./operator.sh init
```

The init wizard will:
1. Generate infrastructure secrets (`.env`)
2. Detect your GPU (NVIDIA/Mac/CPU)
3. Start all containers (postgres, garage, operator, api, web)
4. Prompt for admin password
5. Prompt for AI provider configuration

**After init completes:**
```bash
# Check status
./operator.sh status

# Access services
curl http://localhost:8000/health  # API
open http://localhost:3000          # Web UI
```

**Daily operations:**
```bash
./operator.sh start   # Start platform
./operator.sh stop    # Stop platform
./operator.sh shell   # Enter configuration shell
```

---

## Manual Setup (Step by Step)

If you prefer more control, here are the individual steps:

### Step 1: Generate Infrastructure Secrets

```bash
./operator/lib/init-secrets.sh --dev
```

**Flags:**
- `--dev` - Uses simple database password for local development
- Without `--dev` - All secrets are cryptographically secure (production)

### Step 2: Start Infrastructure

```bash
./operator/lib/start-infra.sh
```

Starts PostgreSQL, Garage S3 storage, and operator container. Applies database migrations automatically.

### Step 3: Configure Platform

```bash
# Enter operator shell
./operator.sh shell

# Inside the shell:
configure.py admin                           # Create admin user
configure.py ai-provider openai --model gpt-4o  # Set AI provider
configure.py embedding 2                     # Activate local embeddings
configure.py api-key openai                  # Store API key
configure.py status                          # Verify configuration

# Exit shell
exit
```

### Step 4: Start Application

```bash
./operator/lib/start-app.sh
```

Starts API server and web visualization app.

### Step 5: Verify

```bash
./operator.sh status

# Should show all 5 containers:
# - knowledge-graph-postgres (healthy)
# - knowledge-graph-garage (healthy)
# - kg-operator (running)
# - kg-api-dev (healthy)
# - kg-web-dev (healthy)
```

---

## Configuration Reference

### Available Embedding Profiles

```bash
./operator.sh shell
configure.py embedding   # List profiles
```

| ID | Provider | Model | Dimensions | Notes |
|----|----------|-------|------------|-------|
| 1 | openai | text-embedding-3-small | 1536 | Cloud API, requires key |
| 2 | local | nomic-embed-text-v1.5 | 768 | Local, auto-detects GPU |

### Available AI Providers

```bash
# OpenAI
configure.py ai-provider openai --model gpt-4o
configure.py ai-provider openai --model gpt-4o-mini

# Anthropic
configure.py ai-provider anthropic --model claude-sonnet-4-20250514

# Ollama (local)
configure.py ai-provider ollama --model mistral:7b-instruct
```

### Operator Shell Aliases

Inside `./operator.sh shell`:
- `status` - View platform configuration
- `pg` - Connect to database (credentials auto-loaded)
- `configure` - Run configure.py
- `operator-help [topic]` - Help system

---

## Cleanup

```bash
# Stop services (keeps data)
./operator.sh stop

# Complete teardown (removes all data)
./operator.sh teardown --full

# Keep secrets, remove everything else
./operator.sh teardown --keep-env
```

---

## Troubleshooting

**Check logs:**
```bash
./operator.sh logs api      # API logs
./operator.sh logs postgres # Database logs
```

**Restart a service:**
```bash
./operator.sh restart api
```

**Rebuild after code changes:**
```bash
./operator.sh rebuild api
```

**Complete reset:**
```bash
./operator.sh teardown --full
./operator.sh init
```

---

## Next Steps

Test the platform:
```bash
# Install kg CLI (optional)
cd client && ./install.sh && cd ..

# Test
kg health
kg database stats

# Ingest a document
kg ingest file -o "Test Ontology" document.txt
```

---

## Architecture Notes

- **Secrets:** Infrastructure secrets in `.env`, application secrets encrypted in database
- **Configuration:** All stored in PostgreSQL, managed via operator container
- **GPU:** Auto-detected at startup (NVIDIA CUDA, Apple MPS, or CPU fallback)
- **Platform:** Works with Docker Compose and Podman Compose
