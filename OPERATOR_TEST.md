# Testing the New Operator Architecture

## Clean State - Ready to Test!

All containers stopped and volumes cleaned. Follow these steps to test the new operator architecture.

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
✓ ENCRYPTION_KEY - generated and saved
✓ OAUTH_SIGNING_KEY - generated and saved
✓ POSTGRES_PASSWORD - set to 'password' (dev mode)
✓ GARAGE_RPC_SECRET - generated and saved
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Infrastructure secrets ready
```

## Step 2: Start Infrastructure (Postgres + Garage)

```bash
# Start database and S3 storage
./operator/lib/start-infra.sh

# What this does:
# - Starts postgres container (with AGE extension)
# - Starts garage container (S3-compatible storage)
# - Waits for health checks
# - Applies database migrations automatically
```


warnings on statrtup and inconclusive finish

 ./operator/lib/start-infra.sh
Starting infrastructure containers...

→ Starting postgres and garage...
WARN[0000] The "GARAGE_RPC_SECRET" variable is not set. Defaulting to a blank string. 
WARN[0000] The "ENCRYPTION_KEY" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OAUTH_SIGNING_KEY" variable is not set. Defaulting to a blank string. 
WARN[0000] The "ENCRYPTION_KEY" variable is not set. Defaulting to a blank string. 
WARN[0000] The "OAUTH_SIGNING_KEY" variable is not set. Defaulting to a blank string. 
[+] Running 7/7
 ✔ Network docker_default              Created                                                                                                          0.1s 
 ✔ Volume docker_postgres_import       Created                                                                                                          0.0s 
 ✔ Volume docker_garage_data           Created                                                                                                          0.0s 
 ✔ Volume docker_garage_meta           Created                                                                                                          0.0s 
 ✔ Volume docker_postgres_data         Created                                                                                                          0.0s 
 ✔ Container knowledge-graph-garage    Started                                                                                                          0.4s 
 ✔ Container knowledge-graph-postgres  Started                                                                                                          0.5s 

→ Waiting for PostgreSQL to be healthy...
✓ PostgreSQL is ready
→ Waiting for Garage to be healthy...
⚠  Garage health check timeout (continuing anyway)

✅ Infrastructure ready

Services running:
  • PostgreSQL (port 5432)
  • Garage S3 storage (port 3900)



**Expected output:**
- ✓ PostgreSQL is ready
- ✓ Garage is ready

**Verify:**
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
# Should show:
# - knowledge-graph-postgres (healthy)
# - knowledge-graph-garage (healthy)
```

## Step 3: Start Operator Container

```bash
cd docker
docker-compose up -d operator

# What this does:
# - Builds operator container (if needed)
# - Starts operator with Docker socket access
# - Connects to postgres and garage networks
```

**Verify:**
```bash
docker ps | grep kg-operator
# Should show: kg-operator (running)

# Test operator shell access
docker exec -it kg-operator /bin/bash
# Should drop into operator container
# Type 'exit' to leave
```

## Step 4: Configure Admin User

```bash
# Create admin user in database
docker exec -it kg-operator python /workspace/operator/configure.py admin

# When prompted:
# - Username: admin (default)
# - Password: <your-secure-password>
# - Confirm password: <same-password>
```

**Expected output:** ✅ Created admin user: admin

## Step 5: Configure AI Extraction Provider (OpenAI)

```bash
# Set OpenAI as extraction provider
docker exec kg-operator python /workspace/operator/configure.py ai-provider openai --model gpt-4o
```

**Expected output:** ✅ Configured AI extraction: openai / gpt-4o

## Step 6: Configure Embedding Provider (Local Nomic)

```bash
# Set local Nomic embeddings
docker exec kg-operator python /workspace/operator/configure.py embedding local
```

**Expected output:** ✅ Configured embedding: local / nomic-ai/nomic-embed-text-v1.5 (768 dims)

## Step 7: Store OpenAI API Key (Encrypted)

```bash
# Store encrypted OpenAI API key
docker exec -it kg-operator python /workspace/operator/configure.py api-key openai

# When prompted:
# - Enter API key: sk-...
# (Key will be encrypted using ENCRYPTION_KEY from .env)
```

**Expected output:** ✅ Stored encrypted API key for: openai

## Step 8: Initialize Garage S3 Storage

**Note:** We need to create a Garage init script. For now, you can use the existing script:

```bash
# Initialize Garage bucket and keys
./scripts/garage/init-garage.sh
```

**Expected output:**
- ✓ Garage bucket created
- ✓ Access keys generated

## Step 9: Start Application Containers (API + Web)

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

## Step 10: Check Configuration Status

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
# Stop everything
./operator/lib/stop.sh

# Or stop and remove volumes
cd docker
docker-compose down -v
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
