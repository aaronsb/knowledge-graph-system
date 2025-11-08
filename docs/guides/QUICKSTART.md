# Knowledge Graph System - Quick Start Guide

**Get from zero to operational knowledge graph system in under 10 minutes.**

This guide uses the **operator architecture (ADR-061)** - the official containerized deployment method. All configuration happens through dedicated operator containers - no local Python installation required.

**Status:** ✅ Fully tested end-to-end on November 8, 2025

## Prerequisites

- Docker or Podman with Docker Compose
- Docker Compose or Podman Compose
- OpenAI API key (or use local embeddings with Ollama)
- (Optional) Node.js + npm for kg CLI tool

## Overview

The system uses 5 core containers:
1. **PostgreSQL + Apache AGE** - Graph database
2. **Garage** - S3-compatible object storage
3. **kg-api** - FastAPI REST server
4. **kg-web** - React visualization UI
5. **kg-operator** - Platform configuration (admin, secrets, providers)

## Step 1: Generate Infrastructure Secrets

```bash
# Generate encryption keys, OAuth signing key, database password
./operator/lib/init-secrets.sh --dev

# What this does:
# - Creates .env file with cryptographically secure secrets:
#   - ENCRYPTION_KEY (Fernet key for encrypting API keys at rest)
#   - OAUTH_SIGNING_KEY (64-char hex for JWT tokens)
#   - POSTGRES_PASSWORD (URL-safe base64 for database)
#   - GARAGE_RPC_SECRET (64-char hex for Garage cluster)
#
# - Uses CORRECT libraries:
#   ✓ cryptography.fernet.Fernet.generate_key() for ENCRYPTION_KEY
#   ✓ openssl rand -hex 32 or secrets.token_hex(32) for signing keys
#   ✓ openssl rand -base64 32 or secrets.token_urlsafe(32) for passwords
#
# - Interactive prompting:
#   - First run: Generates all secrets
#   - Subsequent runs: Prompts to keep or regenerate
#   - Automated scripts: Use -y flag to skip prompts
```

**For automated install scripts:**
```bash
# Skip prompts, keep existing secrets
./operator/lib/init-secrets.sh --dev -y
```

**Expected output:**
```
╔════════════════════════════════════════════════════════════╗
║       Infrastructure Secret Initialization                 ║
╚════════════════════════════════════════════════════════════╝

Mode: Development (weak passwords allowed)

→ Creating .env from .env.example...
✓ .env created

→ Generating ENCRYPTION_KEY...
✓ ENCRYPTION_KEY - generated and saved
→ Generating OAUTH_SIGNING_KEY...
✓ OAUTH_SIGNING_KEY - generated and saved
✓ POSTGRES_PASSWORD - already configured
→ Generating GARAGE_RPC_SECRET...
✓ GARAGE_RPC_SECRET - generated and saved

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Infrastructure secrets ready
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## Step 2: Start Infrastructure (Postgres + Garage + Operator)

```bash
# Start database, S3 storage, and operator
./operator/lib/start-infra.sh

# What this does:
# - Starts postgres container (with AGE extension)
# - Starts garage container (S3-compatible storage)
# - Waits for health checks
# - Verifies PostgreSQL configuration (database, AGE extension, schemas)
# - Shows applied migrations with table names
# - Initializes Garage (node role, bucket, API keys, permissions)
# - Starts operator container (for platform configuration)
```


**Expected output:**
```
→ Starting postgres and garage...
[+] Running 7/7
 ✔ Network docker_default              Created
 ✔ Volume docker_postgres_data         Created
 ✔ Volume docker_garage_data           Created
 ✔ Container knowledge-graph-postgres  Started
 ✔ Container knowledge-graph-garage    Started

→ Waiting for PostgreSQL to be healthy...
✓ PostgreSQL is ready
→ Waiting for Garage to be healthy...
✓ Garage is ready

→ Verifying PostgreSQL configuration...
  Waiting for database to accept queries...
✓ Database ready for queries
✓ Database 'knowledge_graph' exists
  Applying database migrations...
✓ Applied migrations: 1
  → Migration 003 - add_embedding_config
  → Migration 004 - add_ai_extraction_config
  → Migration 005 - add_api_key_validation
  ... (21 migrations total)
→ Applying migration 003 (add_embedding_config)...
  ✅ Migration 003 applied successfully
→ Applying migration 004 (add_ai_extraction_config)...
  ✅ Migration 004 applied successfully
  ... (additional migrations)
→ Applying migration 024 (add_concept_descriptions)...
  ✅ Migration 024 applied successfully
✅ Migration complete!
✓ Migrations applied
✓ Apache AGE extension loaded
✓ Schema ready (37 tables, 21 migrations applied)
    • 1 - baseline
    • 3 - add_embedding_config
    • 4 - add_ai_extraction_config
    ... (17 more migrations)
    • 22 - oauth_client_management
    • 24 - add_concept_descriptions

→ Initializing Garage configuration...
  Assigning role to node 6f84a9a665a520fb...
✓ Node role assigned and layout applied
✓ Bucket 'knowledge-graph-images' created
✓ API key 'kg-api-key' created
✓ Bucket permissions configured

→ Starting operator container...
[+] Building (operator built successfully)
[+] Running 4/4
 ✔ Container knowledge-graph-postgres  Healthy
 ✔ Container knowledge-graph-garage    Healthy
 ✔ Container kg-operator               Started
  Waiting for operator to start...
✓ Operator is ready

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Infrastructure ready
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Services running:
  • PostgreSQL (port 5432)
    - Database: knowledge_graph
    - Extensions: Apache AGE
    - Migrations: Applied

  • Garage S3 storage (port 3900)
    - Bucket: knowledge-graph-images
    - API key: kg-api-key

  • Operator container
    - Status: Running
    - Access: docker exec -it kg-operator /bin/bash

Next steps:
  1. Configure admin user: docker exec kg-operator python /workspace/operator/configure.py admin
  2. Configure AI provider: docker exec kg-operator python /workspace/operator/configure.py ai-provider openai --model gpt-4o
  3. Configure embeddings: docker exec kg-operator python /workspace/operator/configure.py embedding local
  4. Store API keys: docker exec -it kg-operator python /workspace/operator/configure.py api-key openai
  5. Start application: ./operator/lib/start-app.sh
```

**Verify:**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
# Should show:
# - knowledge-graph-postgres (healthy)
# - knowledge-graph-garage (healthy)
# - kg-operator (running)
```

## Step 3: Configure Admin User

```bash
# Create admin user in database
docker exec -it kg-operator python /workspace/operator/configure.py admin

# When prompted:
# - Username: admin (default)
# - Password: <your-secure-password>
# - Confirm password: <same-password>
```

**Expected output:** ✅ Created admin user: admin

## Step 4: Configure AI Extraction Provider (OpenAI)

```bash
# Set OpenAI as extraction provider
docker exec kg-operator python /workspace/operator/configure.py ai-provider openai --model gpt-4o
```

**Expected output:** ✅ Configured AI extraction: openai / gpt-4o

## Step 5: Configure Embedding Provider

```bash
# List available embedding profiles
docker exec kg-operator python /workspace/operator/configure.py embedding

# You'll see:
# [1] ✓ ACTIVE   openai   - text-embedding-3-small (1536 dims, float32)
# [2]            local    - nomic-ai/nomic-embed-text-v1.5 (768 dims, float16, cpu)

# Activate Nomic local embeddings (profile ID 2)
docker exec kg-operator python /workspace/operator/configure.py embedding 2
```

**Expected output:**
```
📋 Available Embedding Profiles:

  [1] ✓ ACTIVE   openai   - text-embedding-3-small
       1536 dims, float32

  [2]            local    - nomic-ai/nomic-embed-text-v1.5
       768 dims, float16 (cpu)

To activate a profile:
  docker exec kg-operator python /workspace/operator/configure.py embedding <profile_id>

Example:
  docker exec kg-operator python /workspace/operator/configure.py embedding 2
```

**Then activate:**
```
📝 Current: [1] openai / text-embedding-3-small
✅ Activated: [2] local / nomic-ai/nomic-embed-text-v1.5 (768 dims, float16) (cpu)
```

## Step 6: Store OpenAI API Key (Encrypted)

```bash
# Store encrypted OpenAI API key
docker exec -it kg-operator python /workspace/operator/configure.py api-key openai

# When prompted:
# - Enter API key: sk-...
# (Key will be encrypted using ENCRYPTION_KEY from .env)
```

**Expected output:** ✅ Stored encrypted API key for: openai

## Step 7: Start Application Containers (API + Web)

```bash
# Start API server and web app
./operator/lib/start-app.sh

# What this does:
# - Checks infrastructure is running
# - Starts API server (waits for health check)
# - Starts web visualization app
```

**Expected output:**
- ✓ API server is ready
- ✓ Web app starting

**Verify:**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
# Should show all 5 containers healthy:
# - knowledge-graph-postgres (healthy)
# - knowledge-graph-garage (healthy)
# - kg-api-dev (healthy)
# - kg-web-dev (healthy)
# - kg-operator (running)

# Test API
curl http://localhost:8000/health
# Should return: {"status":"healthy"}

# Test web app
curl http://localhost:3000
# Should return HTML
```

## Step 8: Check Configuration Status

```bash
# View all configuration
docker exec kg-operator python /workspace/operator/configure.py status
```

**Expected output:**
```
📊 Platform Configuration Status

Admin users: 1
AI Extraction: openai / gpt-4o
Embedding: local / nomic-ai/nomic-embed-text-v1.5 (768 dims)
API Keys: openai
```

## Complete! 🎉

Your Knowledge Graph platform is now fully configured and running with:
- ✅ Clean infrastructure secrets (not baked into images)
- ✅ Admin user configured
- ✅ OpenAI extraction provider
- ✅ Local Nomic embeddings
- ✅ Encrypted API key storage
- ✅ Garage S3 storage initialized
- ✅ All services running and healthy

## Next Steps

Test the platform:
```bash
# Test with kg CLI
kg health
kg database stats

# Ingest a test document
kg ingest file -o "Test Ontology" path/to/document.txt
```

## Cleanup (When Done Testing)

```bash
# Stop services (keeps data)
./operator/lib/stop.sh

# Complete teardown (removes all data and volumes)
./operator/lib/teardown.sh

# Keep secrets but remove everything else
./operator/lib/teardown.sh --keep-env
```

## Troubleshooting

**Problem: Container won't start**
```bash
# Check logs
docker logs knowledge-graph-postgres
docker logs kg-api-dev

# Check docker-compose status
cd docker && docker-compose ps
```

**Problem: Health check timeout**
```bash
# Check if services are actually running
docker ps -a

# Restart specific service
cd docker
docker-compose restart api
```

**Problem: Can't connect to database**
```bash
# Check postgres logs
docker logs knowledge-graph-postgres

# Check if migrations ran
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "\dt"
```

## Notes

- This is using the new operator architecture (ADR-061)
- All secrets in .env (generated once, never edited)
- All application config in database (managed by operator)
- Works with docker-compose AND podman-compose
