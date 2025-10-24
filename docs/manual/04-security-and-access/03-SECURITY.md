# Security Guide

**Operational guide for Knowledge Graph System security infrastructure**

This guide explains the security architecture and how to manage sensitive credentials in the knowledge graph system. Learn how to store LLM API keys securely, understand the defense-in-depth approach, and follow security best practices.

## Table of Contents

- [Security Architecture Overview](#security-architecture-overview)
- [Encrypted API Key Storage](#encrypted-api-key-storage)
- [Cold Start: First-Time Setup](#cold-start-first-time-setup)
- [Managing LLM API Keys](#managing-llm-api-keys)
- [Production Deployment](#production-deployment)
- [Security Model & Threat Boundaries](#security-model--threat-boundaries)
- [Troubleshooting](#troubleshooting)
- [Security Best Practices](#security-best-practices)

---

## Security Architecture Overview

The knowledge graph system implements **defense-in-depth** security with multiple protection layers:

```
┌─────────────────────────────────────────────────────────────────┐
│                      HTTP API Layer                              │
│  • Authentication (JWT tokens, API keys)                         │
│  • RBAC authorization                                            │
│  • Rate limiting (future)                                        │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                  Job Queue Layer                                 │
│  • PostgreSQL persistence                                        │
│  • Content deduplication (SHA-256)                              │
│  • Job isolation (one job per worker thread)                    │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│                  Worker Thread Layer                             │
│  • Thread isolation                                              │
│  • Capability tokens (internal authentication)                  │
│  • Limited module access to key service                         │
└────────────────────┬────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────────────────┐
│              Encrypted Key Service (ADR-031)                     │
│  • Fernet encryption (AES-128-CBC + HMAC-SHA256)                │
│  • Keys encrypted at rest in PostgreSQL                         │
│  • Master encryption key in Docker/Podman secrets               │
│  • Capability token verification                                │
└─────────────────────────────────────────────────────────────────┘
```

**Why This Matters:**

An attacker needs to compromise **multiple isolation boundaries** to access LLM API keys:

1. **HTTP Layer** → Exploit API endpoint
2. **Job Queue** → Inject malicious job into PostgreSQL
3. **Worker Thread** → Execute code in worker context
4. **Key Service** → Present valid capability token

This layered approach means a single vulnerability doesn't expose your credentials.

---

## Encrypted API Key Storage

### What Gets Protected

The system uses LLM APIs for:
- **OpenAI** - Text embeddings (text-embedding-3-small), concept extraction (GPT-4)
- **Anthropic** - Concept extraction (Claude 3.5 Sonnet)
- **Future providers** - OpenRouter, local Ollama, custom models

These API keys are **shard-scoped** (one set per deployment) and used by background workers for document ingestion.

### How Protection Works

**ADR-031: Encrypted API Key Storage**

1. **Encryption at Rest**
   - Keys encrypted with Fernet (AES-128-CBC + HMAC-SHA256)
   - Stored as binary blobs in PostgreSQL (`ag_catalog.system_api_keys`)
   - Never stored in plaintext

2. **Master Key Management**
   - Master encryption key stored separately from database
   - Production: Docker/Podman secrets (`/run/secrets/encryption_master_key`)
   - Development: Environment variable or auto-generated temporary key

3. **Access Control**
   - Only authorized worker threads can decrypt keys
   - Capability token verification (configuration-based shared secret)
   - Module allowlist enforcement

4. **Validation Before Storage**
   - API keys tested against provider API before accepting
   - Rejects invalid keys immediately
   - Prevents storing expired or malformed credentials

### Backward Compatibility

The system maintains **full backward compatibility** with existing deployments:

**Fallback Chain (Priority Order):**
1. **Encrypted storage** (ADR-031) - Tried first
2. **Environment variables** - `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
3. **`.env` file** - Development fallback

**Migration is optional** - existing `.env` configurations continue working without changes.

---

## Cold Start: First-Time Setup

When deploying the system for the first time, you have two options:

### Option 1: Use Existing `.env` Configuration (Legacy)

**No changes required!** The system works exactly as before:

```bash
# In .env file
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

Workers will load keys from environment variables.

### Option 2: Migrate to Encrypted Storage (Recommended)

**Benefits:**
- Keys encrypted at rest (protects against database dumps)
- Centralized key rotation via API
- Audit logging of key access
- Supports key-per-provider without environment pollution

**Prerequisites:**
1. PostgreSQL container running: `docker-compose up -d`
2. API server running: `python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000`
3. Encryption master key configured (auto-generated in development)

**Steps:**

```bash
# 1. Check API health
curl http://localhost:8000/health

# 2. List current key configuration
curl http://localhost:8000/admin/keys

# Response shows which providers are configured:
# [
#   {"provider": "openai", "configured": false, "updated_at": null},
#   {"provider": "anthropic", "configured": false, "updated_at": null}
# ]

# 3. Store OpenAI key (validates before accepting)
curl -X POST http://localhost:8000/admin/keys/openai \
  -F "api_key=sk-proj-..."

# Response on success:
# {
#   "status": "success",
#   "message": "openai API key configured for this shard",
#   "provider": "openai"
# }

# 4. Store Anthropic key (optional)
curl -X POST http://localhost:8000/admin/keys/anthropic \
  -F "api_key=sk-ant-..."

# 5. Verify keys are stored
curl http://localhost:8000/admin/keys

# Response now shows:
# [
#   {"provider": "openai", "configured": true, "updated_at": "2025-10-13T..."},
#   {"provider": "anthropic", "configured": false, "updated_at": null}
# ]
```

**Development Note:** In development mode (no `ENCRYPTION_KEY` set), the system auto-generates a temporary encryption key on startup. This key is **regenerated on every restart**, so you'll need to re-store API keys after restarting the server.

---

## Managing LLM API Keys

### Store or Rotate a Key

```bash
# Store new key (or rotate existing)
curl -X POST http://localhost:8000/admin/keys/openai \
  -F "api_key=sk-proj-NEW_KEY_HERE"
```

**What happens:**
1. ✅ Key format validation (must start with `sk-` or `sk-ant-`)
2. ✅ Live API test (minimal request to provider)
3. ✅ Encryption with Fernet
4. ✅ Storage in PostgreSQL
5. ❌ **Rejects** invalid, expired, or malformed keys

**Error responses:**

```json
// Invalid format
{
  "detail": "Invalid OpenAI API key format (must start with 'sk-')"
}

// API validation failed
{
  "detail": "API key validation failed: Error code: 401 - Incorrect API key provided"
}
```

### List Configured Providers

```bash
curl http://localhost:8000/admin/keys
```

**Response:**

```json
[
  {
    "provider": "openai",
    "configured": true,
    "updated_at": "2025-10-13T13:23:45.539554+00:00"
  },
  {
    "provider": "anthropic",
    "configured": false,
    "updated_at": null
  }
]
```

**Security note:** Plaintext keys are **never returned** via API (only configuration status).

### Delete a Key

```bash
curl -X DELETE http://localhost:8000/admin/keys/openai
```

**Response:**

```json
{
  "status": "success",
  "message": "openai API key removed",
  "provider": "openai"
}
```

**⚠️ Warning:** After deletion, any ingestion jobs using this provider will fail until a new key is configured.

### Verify Encryption in Database

To confirm keys are encrypted (not plaintext):

```bash
docker exec -i knowledge-graph-postgres psql -U admin -d knowledge_graph <<'EOF'
\x
SELECT
    provider,
    length(encrypted_key) as encrypted_key_length,
    substring(encode(encrypted_key, 'base64'), 1, 50) || '...' as encrypted_preview,
    updated_at
FROM ag_catalog.system_api_keys;
EOF
```

**Expected output:**

```
-[ RECORD 1 ]--------+---------------------------------------------------
provider             | openai
encrypted_key_length | 312
encrypted_preview    | Z0FBQUFBQm83UDFoclozMUlVdlVxRmZrRUE2YjdONzd...
updated_at           | 2025-10-13 13:23:45.539554+00
```

The `encrypted_key` is a binary blob (BYTEA) - **not human-readable plaintext**.

---

## Production Deployment

### Master Encryption Key Management

In production, **never use auto-generated temporary keys**. Configure a persistent master encryption key.

#### Option 1: Docker/Podman Secrets (Recommended)

**Why this is best:**
- Secrets never written to disk in plaintext
- Not visible in container environment
- Works across container orchestration (Docker Swarm, Kubernetes)
- Automatically mounted at `/run/secrets/`

**Setup:**

```bash
# 1. Generate master encryption key (Fernet-compatible)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Output: gAAAAABe... (44 characters, base64-encoded)

# 2. Create Docker secret
echo "gAAAAABe..." | docker secret create encryption_master_key -

# 3. Update docker-compose.yml to mount secret
services:
  api:
    secrets:
      - encryption_master_key

secrets:
  encryption_master_key:
    external: true

# 4. Restart services
docker-compose up -d
```

The API server will automatically load from `/run/secrets/encryption_master_key`.

#### Option 2: Environment Variable

**For environments without Docker secrets support:**

```bash
# Generate key
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Add to .env (NEVER commit to git!)
echo "ENCRYPTION_KEY=$ENCRYPTION_KEY" >> .env

# Or set in container environment
docker run -e ENCRYPTION_KEY="$ENCRYPTION_KEY" ...
```

#### Option 3: File Path

**For systems using external secret management (Vault, AWS Secrets Manager):**

```bash
# Write key to secure file
echo "gAAAAABe..." > /secure/path/encryption.key
chmod 600 /secure/path/encryption.key

# Point to file path in environment
export ENCRYPTION_KEY_FILE=/secure/path/encryption.key
```

### Internal Service Authentication

Production deployments should configure the **internal capability token** for worker-to-key-service authentication:

```bash
# Generate random token
INTERNAL_SECRET=$(openssl rand -hex 32)

# Add to .env or Docker secrets
echo "INTERNAL_KEY_SERVICE_SECRET=$INTERNAL_SECRET" >> .env
```

**Why this matters:** Prevents arbitrary code from accessing encrypted keys. Workers must present this token to decrypt LLM API keys.

### Key Rotation Strategy

**Recommended schedule:**
- **LLM API keys**: Rotate every 90 days
- **Master encryption key**: Rotate every 6-12 months
- **Internal service token**: Rotate every 6 months

**How to rotate LLM keys:**

```bash
# 1. Generate new key at provider (OpenAI, Anthropic dashboard)
# 2. Store new key via API
curl -X POST http://localhost:8000/admin/keys/openai \
  -F "api_key=sk-proj-NEW_KEY"

# 3. Test ingestion with new key
kg ingest file -o "Test" document.txt

# 4. If successful, revoke old key at provider
```

**How to rotate master encryption key:**

⚠️ **Complex operation** - requires decrypting all keys with old master, re-encrypting with new master.

**Recommended approach:** Use blue-green deployment:
1. Deploy new instance with new master key
2. Manually configure LLM keys in new instance
3. Migrate traffic to new instance
4. Decommission old instance

(Automated re-encryption script is a future enhancement.)

---

## Security Model & Threat Boundaries

### What This Protects Against

✅ **Database Dump Exposure**
- Attacker gains read access to PostgreSQL
- LLM API keys are encrypted blobs (unusable without master key)

✅ **Backup File Theft**
- Database backups contain encrypted keys
- Master encryption key stored separately

✅ **Accidental Logging**
- Keys never logged in plaintext
- Only encrypted representations logged

✅ **Unauthorized Internal Access**
- Workers require capability token to decrypt keys
- Prevents arbitrary code from reading keys

✅ **Key Leakage via API**
- GET /admin/keys never returns plaintext keys
- Only configuration status exposed

### What This Does NOT Protect Against

❌ **Code Execution in Worker Thread**
- If attacker runs code in ingestion worker, they can read keys
- Mitigation: Defense-in-depth (requires exploiting multiple layers)

❌ **Memory Dumps**
- Decrypted keys exist in memory during LLM API calls
- Mitigation: Short-lived, process isolation, system hardening

❌ **Master Key Compromise**
- If master encryption key is stolen, all LLM keys can be decrypted
- Mitigation: Docker secrets, secure key management, monitoring

❌ **Authenticated Admin Access**
- Admin with valid credentials can store/rotate keys
- Mitigation: Strong authentication, audit logging, RBAC

### Threat Model Summary

**Attacker needs to compromise ALL of:**
1. HTTP API authentication (bypass JWT/RBAC)
2. Job queue isolation (inject malicious job)
3. Worker thread execution (run arbitrary code)
4. Capability token (present valid internal secret)
5. Master encryption key (decrypt stored keys)

**Risk reduction:** Each layer reduces probability of successful attack by an order of magnitude.

---

## Troubleshooting

### Problem: API returns "No encryption key configured"

**Symptom:**

```bash
curl http://localhost:8000/admin/keys
# Returns: "configured": false for all providers
```

**Cause:** Master encryption key not available

**Solution:**

```bash
# Development: Auto-generated key (restart API)
pkill -f uvicorn
python -m uvicorn src.api.main:app --reload

# Production: Configure persistent key
# See "Production Deployment" section above
```

### Problem: Keys disappear after server restart

**Symptom:** Need to re-store API keys after every restart

**Cause:** Using auto-generated temporary encryption key

**Why this happens:** Temporary key is regenerated on startup, so previously encrypted keys can't be decrypted with the new key.

**Solution:** Configure persistent master encryption key (see Production Deployment).

### Problem: "API key validation failed"

**Symptom:**

```bash
curl -X POST http://localhost:8000/admin/keys/openai \
  -F "api_key=sk-..."

# Response:
# {"detail": "API key validation failed: Error code: 401 - Incorrect API key provided"}
```

**Possible causes:**
1. Key is invalid or expired
2. Key is for wrong provider (OpenAI key used for Anthropic endpoint)
3. Network issue connecting to provider API
4. Provider API is down

**Solution:**

```bash
# Test key manually with provider
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer sk-..."

# Check provider status
# OpenAI: https://status.openai.com/
# Anthropic: https://status.anthropic.com/
```

### Problem: Ingestion fails with "No API key configured"

**Symptom:**

```bash
kg ingest file -o "Test" document.txt
# Job fails with: "No openai API key configured for this shard"
```

**Cause:** No key configured in encrypted storage OR `.env`

**Solution:**

```bash
# Option 1: Store in encrypted storage
curl -X POST http://localhost:8000/admin/keys/openai \
  -F "api_key=sk-..."

# Option 2: Set in .env (legacy mode)
echo "OPENAI_API_KEY=sk-..." >> .env
pkill -f uvicorn  # Restart to load new env
```

### Problem: "Internal server error storing API key"

**Symptom:**

```bash
curl -X POST http://localhost:8000/admin/keys/openai \
  -F "api_key=sk-..."

# Response:
# {"detail": "Internal server error storing API key"}
```

**Check API logs:**

```bash
# Find log file
ls -lt logs/

# Recent errors
tail -50 logs/api_$(date +%Y%m%d).log | grep -i error
```

**Common causes:**
- PostgreSQL connection failed
- `ag_catalog.system_api_keys` table doesn't exist
- Encryption key invalid format (not Fernet-compatible)

**Solution:**

```bash
# Test database connection
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "\dt ag_catalog.*"

# Verify encryption key format
python3 -c "from cryptography.fernet import Fernet; Fernet(b'${ENCRYPTION_KEY}')"
```

### Problem: Can't access keys from worker

**Symptom:** Worker logs show "Invalid service token" when trying to decrypt keys

**Cause:** Internal capability token mismatch or not configured

**Solution:**

```bash
# Ensure consistent internal secret across all services
echo "INTERNAL_KEY_SERVICE_SECRET=$(openssl rand -hex 32)" >> .env

# Restart all services
docker-compose restart
pkill -f uvicorn
python -m uvicorn src.api.main:app --reload
```

---

## Security Best Practices

### ✅ DO:

**Key Management:**
- ✅ Use Docker/Podman secrets for master encryption key in production
- ✅ Rotate LLM API keys every 90 days
- ✅ Store master encryption key separately from database backups
- ✅ Use encrypted storage instead of `.env` in production
- ✅ Test new keys in staging before production deployment
- ✅ Revoke old keys at provider after rotation

**Access Control:**
- ✅ Configure internal capability token in production
- ✅ Restrict admin endpoint access with authentication (ADR-027)
- ✅ Use RBAC to limit who can manage keys
- ✅ Monitor API logs for suspicious key access patterns

**Operations:**
- ✅ Document your key rotation schedule
- ✅ Set up alerts for failed API calls (may indicate key issues)
- ✅ Keep backup of master encryption key in secure vault
- ✅ Test key recovery procedures regularly

### ❌ DON'T:

**Key Management:**
- ❌ Commit `.env` to version control (in `.gitignore`)
- ❌ Store keys in plaintext anywhere (use encrypted storage)
- ❌ Use the same master encryption key across environments
- ❌ Share master encryption key in Slack, email, or chat
- ❌ Leave expired keys configured (revoke after rotation)

**Access Control:**
- ❌ Expose admin key endpoints without authentication
- ❌ Use auto-generated temporary keys in production
- ❌ Grant admin access to too many users
- ❌ Skip capability token configuration in production

**Operations:**
- ❌ Forget to test keys after rotation
- ❌ Include master encryption key in database backups
- ❌ Log decrypted keys (only log "key loaded" events)
- ❌ Skip key rotation (set calendar reminders)

---

## Quick Reference

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /admin/keys` | GET | List configured providers |
| `POST /admin/keys/{provider}` | POST | Store/rotate API key |
| `DELETE /admin/keys/{provider}` | DELETE | Remove API key |

**Supported providers:** `openai`, `anthropic`

### Environment Variables

```bash
# Master encryption key (production)
ENCRYPTION_KEY=<fernet-key>              # Direct key value
ENCRYPTION_KEY_FILE=/path/to/key         # File path
# Or: /run/secrets/encryption_master_key (Docker secrets)

# Internal service authentication
INTERNAL_KEY_SERVICE_SECRET=<hex-secret>

# Legacy mode (backward compatible)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Key Format Requirements

| Provider | Format | Example |
|----------|--------|---------|
| OpenAI | Starts with `sk-` or `sk-proj-` | `sk-proj-abc123...` |
| Anthropic | Starts with `sk-ant-` | `sk-ant-api03-...` |

### Database Tables

```sql
-- Encrypted keys stored in:
ag_catalog.system_api_keys
  - provider VARCHAR(50) PRIMARY KEY
  - encrypted_key BYTEA NOT NULL
  - updated_at TIMESTAMP WITH TIME ZONE
```

---

## Architecture References

- **[ADR-031](../../architecture/ADR-031-encrypted-api-keys.md)** - Encrypted API key storage design
- **[ADR-027](../../architecture/ADR-027-user-management-api.md)** - Authentication system
- **[ADR-028](../../architecture/ADR-028-rbac.md)** - Role-based access control
- **[01-AUTHENTICATION.md](01-AUTHENTICATION.md)** - User authentication guide

---

## Related Guides

- **[01-QUICKSTART.md](01-QUICKSTART.md)** - Initial system setup
- **[01-AI_PROVIDERS.md](01-AI_PROVIDERS.md)** - Configure LLM providers
- **[01-BACKUP_RESTORE.md](01-BACKUP_RESTORE.md)** - Database backup security

---

**Security Questions?**

For security concerns or vulnerability reports, please file an issue at the project repository with the `security` label.
