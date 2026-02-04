---
status: Accepted
date: 2025-10-12
deciders:
  - Development Team
related:
  - ADR-027
  - ADR-024
  - ADR-014
---

# ADR-031: Encrypted API Key Storage with Container Secrets

## Overview

Here's an uncomfortable truth: most applications handle API keys terribly. They sit in plain text in `.env` files or configuration databases, waiting to be discovered by anyone who can access a database dump or peek at a backup. When you need to rotate a compromised key, you edit the file and restart everything - downtime, friction, and stress.

This is especially problematic for a knowledge graph system that needs expensive LLM API keys (OpenAI, Anthropic) to extract concepts from documents. These keys can cost thousands of dollars per month and provide access to powerful AI services. If they leak in a database dump or get committed to GitHub, the financial and security consequences can be severe.

We need a solution that keeps keys encrypted at rest but still allows runtime management. Administrators should be able to rotate keys via API without redeploying containers. The system should protect against database breaches - if someone gets a SQL dump, they shouldn't be able to use the keys. But we also need to balance security with operational simplicity - this has to work seamlessly in Docker and Podman without complex secret management infrastructure.

This ADR describes our two-layer approach: master encryption keys live in container secrets (never in the database), while LLM API keys are encrypted at rest in PostgreSQL and decrypted on-demand in memory. Think of it like a safe deposit box: the box itself (database) is in a vault (encrypted), but you still need the physical key (master encryption key from secrets) to open it. This gives us runtime management with protection against database compromise.

---

## Context

The knowledge graph system requires inference API keys (OpenAI, Anthropic) to extract concepts from documents. Currently, these are stored in `.env` files, which presents several issues:

1. **Static storage**: Keys are plaintext in `.env` files, discoverable by anyone with filesystem access
2. **Rotation friction**: Changing keys requires editing `.env` and restarting services
3. **Risk of exposure**: Database dumps, backups, or accidental commits could expose keys
4. **No runtime management**: Cannot rotate keys via API without redeployment

### Shard Architecture Context

A **shard** is a single deployment of the knowledge graph system with its own:
- PostgreSQL database and Apache AGE graph
- Set of ontologies (concept collections)
- LLM API keys for inference
- Independent API server and configuration

**Key architectural principles:**
- One shard = one set of system-wide LLM API keys
- Each shard manages its own keys independently via admin API
- Multiple shards can exist, each with different keys/quotas
- Keys are shard-scoped, not per-user (users share the shard's keys)

This model reflects operational reality: A single shard has finite compute and storage capacity. Organizations deploying multiple shards do so to distribute load, separate ontology collections, or isolate environments (dev/staging/prod). Each shard is independently managed by its administrators.

For self-hosted deployments (Docker/Podman), we need a solution that:
- ✅ Allows admin-managed API keys (rotatable via API)
- ✅ Encrypts keys at rest in the database
- ✅ Protects against database breach scenarios
- ✅ Works with Docker and Podman equally well
- ✅ **Has minimal operational friction** for deployment
- ✅ Provides clear, simple setup instructions

## Decision

Implement **encrypted API key storage** using a two-layer security model:

### Architecture

```
┌─────────────────────────────────────────┐
│ Docker/Podman Secrets (Layer 1)         │
│ ┌─────────────────────────────────────┐ │
│ │ Master Encryption Key (static)      │ │
│ │ JWT Secret (static)                 │ │
│ │ PostgreSQL Password (static)        │ │
│ └─────────────────────────────────────┘ │
└──────────────────┬──────────────────────┘
                   │
                   ↓ decrypt on demand
┌─────────────────────────────────────────┐
│ PostgreSQL Database (Layer 2)           │
│ ┌─────────────────────────────────────┐ │
│ │ Table: system_api_keys              │ │
│ │ ┌─────────────────────────────────┐ │ │
│ │ │ provider | encrypted_key        │ │ │
│ │ │ string   | bytea                │ │ │
│ │ │ (PRIMARY KEY: provider)         │ │ │
│ │ └─────────────────────────────────┘ │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
                   │
                   ↓ decrypt when needed
┌─────────────────────────────────────────┐
│ Application Runtime (Layer 3)           │
│ - API keys exist in memory only         │
│ - Decrypted on demand for API calls     │
│ - Cached briefly, then cleared          │
└─────────────────────────────────────────┘
```

### Key Principles

1. **Separation of Concerns**
   - `jwt_secret`: Signs/verifies authentication tokens (ADR-027)
   - `encryption_master_key`: Encrypts/decrypts LLM API keys (this ADR)
   - `postgres_password`: Database authentication

2. **Encryption at Rest**
   - System API keys encrypted with Fernet (AES-128-CBC + HMAC-SHA256)
   - Master key stored in Docker/Podman secrets (not in database)
   - Keys decrypted only when needed, held in memory briefly

3. **Shard-Scoped Management**
   - One shard = one set of system-wide LLM API keys
   - Administrators manage keys via admin API endpoints
   - Keys validated before storage
   - Runtime rotation without redeployment

4. **Threat Model**
   - ✅ **Protects against**: Database dumps, SQL injection, backup theft, DBA snooping
   - ❌ **Does NOT protect against**: Runtime memory access, container root compromise, host compromise
   - **Trade-off**: Acceptable for self-hosted private network deployment

5. **Multi-Shard Independence**
   - Each shard manages its own keys independently
   - Different shards can use different providers/keys
   - No cross-shard key sharing or coordination

### Internal Service Authorization (Defense in Depth)

To prevent unauthorized key access within the application, we implement a **service token authorization layer**:

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│ API Endpoint │ ──POST→ │  Job Queue   │ ──pull→ │ Worker Thread│
│  (FastAPI)   │         │ (PostgreSQL) │         │ (Ingestion)  │
└──────────────┘         └──────────────┘         └──────────────┘
                                                           │
                                                           ↓ (with service token)
                                                    ┌──────────────┐
                                                    │  Key Service │
                                                    │  (Encrypted) │
                                                    └──────────────┘
```

**Security Model:**

1. **Configuration-based shared secret**: `INTERNAL_KEY_SERVICE_SECRET`
   - Randomly generated at deployment
   - Stored in Docker/Podman secrets (not in database)
   - Required by workers to access encrypted keys

2. **Authorization Flow:**
   - Worker loads service token from secrets on startup
   - Worker presents token when calling `get_system_api_key()`
   - Key service validates token before decrypting keys
   - Invalid token → denied access, logged as security event

3. **Threat Model:**
   - ✅ **Protects against**: Unauthorized code paths accessing keys
   - ✅ **Limits blast radius**: Attacker must compromise authorized worker
   - ✅ **Audit trail**: All key access logged with caller identity
   - ✅ **Multiple hops required**: Must exploit API → Job Queue → Worker → Key Service

4. **Why This Matters:**
   - In single-process apps, code injection can bypass all checks
   - With job queue architecture, attacker must hop multiple isolation boundaries:
     1. Exploit API endpoint (HTTP layer)
     2. Inject malicious job into queue (database layer)
     3. Execute in worker thread (thread isolation)
     4. Call key service with valid token (capability layer)
   - Each hop is a defense layer that can detect/block attack

**Implementation:**

```python
# api/app/lib/encrypted_keys.py
def get_system_api_key(
    db_connection,
    provider: str,
    service_token: str  # Required capability token
) -> Optional[str]:
    """
    Get decrypted API key - requires service token.

    Args:
        db_connection: PostgreSQL connection
        provider: 'openai' or 'anthropic'
        service_token: Internal service authorization token

    Raises:
        SecurityError: If token invalid or access denied
    """
    # Validate service token
    expected_token = SecretManager.load_secret(
        "internal_key_service_secret",
        "INTERNAL_KEY_SERVICE_SECRET"
    )

    if service_token != expected_token:
        logger.warning(
            f"Unauthorized key access attempt for {provider}",
            extra={"caller": inspect.stack()[1]}
        )
        raise SecurityError("Invalid service token")

    # Token valid - continue with key retrieval
    store = EncryptedKeyStore(db_connection)
    return store.get_key(provider)
```

### Worker Concurrency Fix

**Problem Identified:** FastAPI workers were blocking the entire event loop during ingestion, preventing concurrent API requests.

**Root Cause:**
```python
# Old approach - BLOCKS EVENT LOOP
background_tasks.add_task(queue.execute_job, job_id)  # Still runs in event loop!
```

FastAPI's `BackgroundTasks` runs after the HTTP response but **in the same event loop thread**. Long-running LLM API calls block all concurrent requests.

**Solution:** Execute workers in thread pool (true concurrency):

```python
# job_queue.py - New async execution
import concurrent.futures
from threading import Thread

class PostgreSQLJobQueue(JobQueue):
    def __init__(self, ...):
        # Add thread pool for worker execution
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=4,  # Concurrent ingestion jobs
            thread_name_prefix="kg-worker-"
        )

    def execute_job_async(self, job_id: str):
        """Execute job in thread pool (non-blocking)"""
        self.executor.submit(self.execute_job, job_id)

    def execute_job(self, job_id: str):
        """Worker function (runs in thread pool)"""
        job = self.get_job(job_id)
        # ... load service token from secrets ...
        service_token = SecretManager.load_secret(
            "internal_key_service_secret",
            "INTERNAL_KEY_SERVICE_SECRET"
        )

        # Pass service token to worker
        worker_func = self.worker_registry.get(job["job_type"])
        result = worker_func(job["job_data"], job_id, self, service_token)
        # ...
```

**Updated API Routes:**

```python
# routes/jobs.py - Use async execution
@router.post("/{job_id}/approve")
async def approve_job(job_id: str, background_tasks: BackgroundTasks):
    queue = get_job_queue()

    # Execute in thread pool (non-blocking)
    background_tasks.add_task(queue.execute_job_async, job_id)

    return {"status": "queued", "job_id": job_id}
```

**Benefits:**
- ✅ **True concurrency**: Multiple ingestion jobs run in parallel
- ✅ **Non-blocking API**: Other requests processed while ingestion runs
- ✅ **Bounded resources**: Thread pool limits concurrent jobs
- ✅ **Graceful degradation**: Queue backs up when workers saturated

## Implementation

### Phase 1: Setup (One-Time, ~5 minutes)

#### For Docker

```bash
# 1. Generate secrets
openssl rand -base64 32 > /tmp/jwt_secret.txt
openssl rand -base64 32 > /tmp/encryption_master_key.txt
openssl rand -base64 32 > /tmp/postgres_password.txt

# 2. Create Docker secrets
docker secret create jwt_secret /tmp/jwt_secret.txt
docker secret create encryption_master_key /tmp/encryption_master_key.txt
docker secret create postgres_password /tmp/postgres_password.txt

# 3. Securely delete temp files
shred -u /tmp/*.txt

# 4. Verify
docker secret ls
```

#### For Podman

```bash
# 1. Generate secrets
openssl rand -base64 32 > /tmp/jwt_secret.txt
openssl rand -base64 32 > /tmp/encryption_master_key.txt
openssl rand -base64 32 > /tmp/postgres_password.txt

# 2. Create Podman secrets
cat /tmp/jwt_secret.txt | podman secret create jwt_secret -
cat /tmp/encryption_master_key.txt | podman secret create encryption_master_key -
cat /tmp/postgres_password.txt | podman secret create postgres_password -

# 3. Securely delete temp files
shred -u /tmp/*.txt

# 4. Verify
podman secret ls
```

#### Automated Setup Script

We provide `scripts/init-secrets.sh` that auto-detects Docker/Podman:

```bash
#!/bin/bash
# scripts/init-secrets.sh - Auto-detect and initialize secrets

set -e

# Detect container runtime
if command -v podman &> /dev/null; then
    RUNTIME="podman"
elif command -v docker &> /dev/null; then
    RUNTIME="docker"
else
    echo "❌ Error: Neither Docker nor Podman found"
    exit 1
fi

echo "✓ Detected runtime: $RUNTIME"

# Generate secrets
echo "Generating secrets..."
JWT_SECRET=$(openssl rand -base64 32)
ENCRYPTION_KEY=$(openssl rand -base64 32)
POSTGRES_PASSWORD=$(openssl rand -base64 32)

# Create secrets
echo "$JWT_SECRET" | $RUNTIME secret create jwt_secret - 2>/dev/null || echo "  jwt_secret already exists"
echo "$ENCRYPTION_KEY" | $RUNTIME secret create encryption_master_key - 2>/dev/null || echo "  encryption_master_key already exists"
echo "$POSTGRES_PASSWORD" | $RUNTIME secret create postgres_password - 2>/dev/null || echo "  postgres_password already exists"

echo "✅ Secrets initialized successfully!"
echo ""
echo "Next steps:"
echo "  1. Update docker-compose.yml to use secrets"
echo "  2. Run: docker-compose up -d"
echo "  3. Initialize database: ./scripts/setup/initialize-platform.sh"
```

**Usage:**
```bash
# One command to set up all secrets
./scripts/init-secrets.sh
```

### Phase 2: Docker Compose Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: apache/age:latest
    secrets:
      - postgres_password
    environment:
      - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password
      - POSTGRES_DB=knowledge_graph
      - POSTGRES_USER=admin
    volumes:
      - pgdata:/var/lib/postgresql/data
    networks:
      - internal

  api:
    build: .
    secrets:
      - jwt_secret
      - encryption_master_key
      - postgres_password
    environment:
      # Point to secret files (not values)
      - JWT_SECRET_FILE=/run/secrets/jwt_secret
      - ENCRYPTION_KEY_FILE=/run/secrets/encryption_master_key
      - POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password

      # Database connection
      - POSTGRES_HOST=postgres
      - POSTGRES_PORT=5432
      - POSTGRES_DB=knowledge_graph
      - POSTGRES_USER=admin

      # Other config
      - QUEUE_TYPE=postgresql
    ports:
      - "8000:8000"
    depends_on:
      - postgres
    networks:
      - internal

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    ports:
      - "443:443"
    depends_on:
      - api
    networks:
      - internal

secrets:
  jwt_secret:
    external: true
  encryption_master_key:
    external: true
  postgres_password:
    external: true

networks:
  internal:
    driver: bridge

volumes:
  pgdata:
```

### Phase 3: Application Code

#### Load Secrets from Files

```python
# api/app/lib/secrets.py
"""
Secrets management with Docker/Podman secrets support.
Falls back to environment variables for development.
"""

import os
from pathlib import Path
from typing import Optional

class SecretManager:
    """Load secrets from Docker/Podman secrets or environment variables"""

    @staticmethod
    def load_secret(secret_name: str, env_var: Optional[str] = None) -> str:
        """
        Load secret from multiple sources in priority order:
        1. Docker/Podman secret file (/run/secrets/<secret_name>)
        2. Environment variable file path (e.g., JWT_SECRET_FILE)
        3. Environment variable value (e.g., JWT_SECRET_KEY)
        4. .env file (development only)

        Args:
            secret_name: Name of the Docker/Podman secret
            env_var: Optional environment variable name

        Returns:
            Secret value as string

        Raises:
            ValueError: If secret cannot be found
        """
        # Try Docker/Podman secrets first
        secret_path = Path(f"/run/secrets/{secret_name}")
        if secret_path.exists():
            return secret_path.read_text().strip()

        # Try environment variable pointing to file
        env_name = env_var or f"{secret_name.upper()}_FILE"
        file_path = os.getenv(env_name)
        if file_path and Path(file_path).exists():
            return Path(file_path).read_text().strip()

        # Try environment variable with value directly
        env_name_direct = env_var or secret_name.upper()
        value = os.getenv(env_name_direct)
        if value:
            return value

        # Development fallback: .env file
        if os.path.exists(".env"):
            from dotenv import load_dotenv
            load_dotenv()
            value = os.getenv(env_name_direct)
            if value:
                return value

        raise ValueError(
            f"Secret '{secret_name}' not found. "
            f"Expected: /run/secrets/{secret_name} or ${env_name} or ${env_name_direct}"
        )

# Load secrets once at module import
JWT_SECRET = SecretManager.load_secret("jwt_secret", "JWT_SECRET_KEY")
ENCRYPTION_KEY = SecretManager.load_secret("encryption_master_key")
POSTGRES_PASSWORD = SecretManager.load_secret("postgres_password")
```

#### Encrypted Key Storage

```python
# api/app/lib/encrypted_keys.py
"""
System API key storage with encryption at rest (shard-scoped).
"""

from cryptography.fernet import Fernet
import psycopg2
from datetime import datetime
from typing import Optional
from .secrets import ENCRYPTION_KEY

class EncryptedKeyStore:
    """Manage system-wide API keys with encryption at rest"""

    def __init__(self, db_connection):
        self.db = db_connection
        self.cipher = Fernet(ENCRYPTION_KEY.encode())
        self._ensure_table()

    def _ensure_table(self):
        """Create system_api_keys table if it doesn't exist"""
        with self.db.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_api_keys (
                    provider VARCHAR(50) PRIMARY KEY,
                    encrypted_key BYTEA NOT NULL,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                );
            """)
            self.db.commit()

    def store_key(self, provider: str, plaintext_key: str) -> None:
        """
        Encrypt and store system API key.

        Args:
            provider: 'openai' or 'anthropic'
            plaintext_key: The actual API key
        """
        encrypted = self.cipher.encrypt(plaintext_key.encode())

        with self.db.cursor() as cur:
            cur.execute("""
                INSERT INTO system_api_keys (provider, encrypted_key)
                VALUES (%s, %s)
                ON CONFLICT (provider)
                DO UPDATE SET
                    encrypted_key = EXCLUDED.encrypted_key,
                    updated_at = NOW()
            """, (provider, encrypted))
            self.db.commit()

    def get_key(self, provider: str) -> str:
        """
        Decrypt and return system API key.

        Args:
            provider: 'openai' or 'anthropic'

        Returns:
            Plaintext API key

        Raises:
            ValueError: If key not found
        """
        with self.db.cursor() as cur:
            cur.execute("""
                SELECT encrypted_key
                FROM system_api_keys
                WHERE provider = %s
            """, (provider,))

            row = cur.fetchone()
            if not row:
                raise ValueError(f"No {provider} API key configured for this shard")

            encrypted = bytes(row[0])
            plaintext = self.cipher.decrypt(encrypted).decode()
            return plaintext

    def delete_key(self, provider: str) -> bool:
        """
        Remove system API key.

        Returns:
            True if key was deleted, False if not found
        """
        with self.db.cursor() as cur:
            cur.execute("""
                DELETE FROM system_api_keys
                WHERE provider = %s
            """, (provider,))
            self.db.commit()
            return cur.rowcount > 0

    def list_providers(self) -> list[dict]:
        """
        List configured providers.

        Returns:
            List of provider info dicts: [{'provider': 'openai', 'updated_at': '...'}]
        """
        with self.db.cursor() as cur:
            cur.execute("""
                SELECT provider, updated_at
                FROM system_api_keys
                ORDER BY provider
            """)
            return [
                {'provider': row[0], 'updated_at': row[1].isoformat()}
                for row in cur.fetchall()
            ]
```

#### API Endpoints

```python
# api/app/routes/admin_keys.py
"""
Admin API endpoints for system-wide LLM API key management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Literal
import anthropic
import openai

from ..lib.encrypted_keys import EncryptedKeyStore
from ..dependencies.auth import require_admin
from ..lib.age_client import get_age_client

router = APIRouter(prefix="/admin/keys", tags=["admin-keys"])

class APIKeySet(BaseModel):
    api_key: str

class APIKeyInfo(BaseModel):
    provider: str
    configured: bool
    updated_at: str | None

@router.post("/{provider}", status_code=status.HTTP_201_CREATED)
async def set_api_key(
    provider: Literal["openai", "anthropic"],
    key_data: APIKeySet,
    _admin = Depends(require_admin),
    age_client = Depends(get_age_client)
):
    """
    Set or rotate system API key (admin only).
    Key is validated before storage.
    """
    # Validate key format
    if provider == "anthropic":
        if not key_data.api_key.startswith("sk-ant-"):
            raise HTTPException(400, "Invalid Anthropic API key format")
    elif provider == "openai":
        if not key_data.api_key.startswith("sk-"):
            raise HTTPException(400, "Invalid OpenAI API key format")

    # Test the key by making a minimal API call
    try:
        if provider == "anthropic":
            client = anthropic.Anthropic(api_key=key_data.api_key)
            client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
        else:  # openai
            client = openai.OpenAI(api_key=key_data.api_key)
            client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
    except Exception as e:
        raise HTTPException(400, f"API key validation failed: {str(e)}")

    # Store encrypted
    key_store = EncryptedKeyStore(age_client.conn)
    key_store.store_key(provider, key_data.api_key)

    return {
        "status": "success",
        "message": f"{provider} API key configured for this shard"
    }

@router.get("/", response_model=list[APIKeyInfo])
async def list_api_keys(
    _admin = Depends(require_admin),
    age_client = Depends(get_age_client)
):
    """List configured API providers (admin only)"""
    key_store = EncryptedKeyStore(age_client.conn)
    configured = key_store.list_providers()

    # Return all possible providers, marking which are configured
    all_providers = ["openai", "anthropic"]
    configured_map = {p['provider']: p for p in configured}

    return [
        APIKeyInfo(
            provider=provider,
            configured=provider in configured_map,
            updated_at=configured_map[provider]['updated_at'] if provider in configured_map else None
        )
        for provider in all_providers
    ]

@router.delete("/{provider}")
async def delete_api_key(
    provider: Literal["openai", "anthropic"],
    _admin = Depends(require_admin),
    age_client = Depends(get_age_client)
):
    """Delete system API key (admin only)"""
    key_store = EncryptedKeyStore(age_client.conn)

    deleted = key_store.delete_key(provider)
    if not deleted:
        raise HTTPException(404, f"No {provider} API key configured")

    return {"status": "success", "message": f"{provider} API key removed"}
```

#### CLI Commands

```bash
# kg CLI admin key management commands

# Set/rotate OpenAI key
kg admin keys set openai sk-...

# Set/rotate Anthropic key
kg admin keys set anthropic sk-ant-...

# List configured providers
kg admin keys list
# Output:
# Provider    Configured  Updated
# openai      ✓           2025-10-12T10:30:00Z
# anthropic   ✗           -

# Delete a key
kg admin keys delete openai
```

### Phase 4: Migration from .env

For existing deployments still using `.env`:

```bash
# scripts/migrate-to-secrets.sh
#!/bin/bash
set -e

echo "Migrating from .env to Docker/Podman secrets..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found"
    exit 1
fi

# Source .env
source .env

# Detect runtime
if command -v podman &> /dev/null; then
    RUNTIME="podman"
elif command -v docker &> /dev/null; then
    RUNTIME="docker"
else
    echo "❌ Error: Neither Docker nor Podman found"
    exit 1
fi

# Migrate JWT secret if it exists
if [ -n "$JWT_SECRET_KEY" ] && [ "$JWT_SECRET_KEY" != "CHANGE_THIS_TO_A_RANDOM_SECRET_KEY" ]; then
    echo "$JWT_SECRET_KEY" | $RUNTIME secret create jwt_secret - 2>/dev/null || echo "  jwt_secret already exists"
else
    echo "⚠️  JWT_SECRET_KEY not set in .env, generating new one..."
    openssl rand -base64 32 | $RUNTIME secret create jwt_secret - 2>/dev/null
fi

# Generate new encryption key (there's no old one to migrate)
echo "Generating new encryption master key..."
openssl rand -base64 32 | $RUNTIME secret create encryption_master_key - 2>/dev/null || echo "  encryption_master_key already exists"

# Migrate postgres password if set
if [ -n "$POSTGRES_PASSWORD" ]; then
    echo "$POSTGRES_PASSWORD" | $RUNTIME secret create postgres_password - 2>/dev/null || echo "  postgres_password already exists"
else
    echo "Generating new PostgreSQL password..."
    openssl rand -base64 32 | $RUNTIME secret create postgres_password - 2>/dev/null
fi

echo "✅ Migration complete!"
echo ""
echo "Next steps:"
echo "  1. Update docker-compose.yml to use secrets (see ADR-031)"
echo "  2. Remove sensitive values from .env (keep non-secret config)"
echo "  3. Restart services: docker-compose down && docker-compose up -d"
```

## Consequences

### Positive

1. **✅ Zero-friction deployment**
   - Single script setup: `./scripts/init-secrets.sh`
   - Auto-detects Docker/Podman
   - Clear error messages

2. **✅ Enhanced security**
   - Keys encrypted at rest in PostgreSQL
   - Master key isolated in container secrets
   - Database dumps don't expose API keys

3. **✅ Shard-scoped management**
   - Each shard independently manages its own keys
   - Simple admin API for key rotation
   - No cross-shard coordination needed

4. **✅ Runtime rotation**
   - Admins can rotate keys without redeployment
   - API endpoints + CLI commands for management
   - Validation ensures keys work before storage

5. **✅ Docker/Podman agnostic**
   - Same interface for both runtimes
   - Detection scripts handle differences
   - Portable across environments

6. **✅ Clear operational docs**
   - Step-by-step setup instructions
   - Automated scripts reduce errors
   - Verification steps included

7. **✅ Multi-shard scalability**
   - Multiple shards can use different keys/quotas
   - Supports dev/staging/prod isolation
   - Reflects operational reality of finite shard capacity

### Negative

1. **❌ Cannot protect against runtime compromise**
   - If attacker gains process access, keys can be extracted from memory
   - Trade-off: Acceptable for self-hosted private network deployment

2. **❌ Master key rotation is complex**
   - Requires decrypting all keys with old master, re-encrypting with new
   - Rare operation, but needs careful planning

3. **❌ Additional operational complexity**
   - Operators must understand secrets management
   - Mitigated by comprehensive docs and automation

### Neutral

1. **Container secrets required**
   - Docker Swarm or Podman needed (not plain `docker run`)
   - Acceptable: This is how modern container deployments work

2. **Shared keys within shard**
   - All users on a shard share the same LLM keys
   - Appropriate for self-hosted deployments with trusted users

## Future Extensibility: Enterprise Secret Backends

> **Note on Intent:** This section documents the architectural design for future extensibility.
>
> **Phase 1 delivers:** Docker/Podman secrets (self-hosted, production-ready, complete).
>
> **This section exists to demonstrate:**
> - The architecture has no dead-ends requiring rewrites
> - Enterprise deployments have clear extension points
> - Operations teams can adapt to their specific environment
> - The abstraction layer exists, even if alternative backends aren't implemented
>
> **Reality check:** Enterprise deployments are never turnkey - they require operations teams to fit the solution to their specific infrastructure. This design acknowledges that by providing clear extension points rather than prescriptive "enterprise features."

### Design for Pluggability

The implementation uses an **abstraction layer** to allow swapping secret backends without changing application code. This "knockout" preserves the open-source nature while enabling deployments adapted by operations teams to their specific environments.

#### Abstract Interface

```python
# api/app/lib/secret_backend.py
"""
Abstract interface for secret storage backends.
Allows plugging in different implementations without code changes.
"""

from abc import ABC, abstractmethod
from typing import Optional

class SecretBackend(ABC):
    """Abstract base class for secret storage implementations"""

    @abstractmethod
    def load_secret(self, secret_name: str) -> str:
        """
        Load a secret by name.

        Args:
            secret_name: Name of the secret to retrieve

        Returns:
            Secret value as string

        Raises:
            ValueError: If secret not found or access denied
        """
        pass

    @abstractmethod
    def store_secret(self, secret_name: str, secret_value: str) -> None:
        """
        Store a secret (optional - not all backends support this).

        Args:
            secret_name: Name of the secret
            secret_value: Value to store

        Raises:
            NotImplementedError: If backend is read-only
            ValueError: If operation fails
        """
        pass

    @abstractmethod
    def delete_secret(self, secret_name: str) -> bool:
        """
        Delete a secret (optional - not all backends support this).

        Returns:
            True if deleted, False if not found

        Raises:
            NotImplementedError: If backend is read-only
        """
        pass

    @abstractmethod
    def list_secrets(self) -> list[str]:
        """
        List available secret names.

        Returns:
            List of secret names
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if backend is accessible.

        Returns:
            True if healthy, False otherwise
        """
        pass
```

#### Implementation 1: Docker/Podman (Default)

```python
# api/app/lib/backends/container_secrets.py
"""
Docker/Podman secrets backend (ADR-031 Phase 1).
Read-only access to /run/secrets/* files.
"""

from pathlib import Path
import os
from ..secret_backend import SecretBackend

class ContainerSecretsBackend(SecretBackend):
    """Read secrets from Docker/Podman secret files"""

    def __init__(self, secrets_dir: str = "/run/secrets"):
        self.secrets_dir = Path(secrets_dir)

    def load_secret(self, secret_name: str) -> str:
        """Load secret from mounted file"""
        secret_path = self.secrets_dir / secret_name

        if not secret_path.exists():
            # Fallback to environment variable
            env_value = os.getenv(secret_name.upper())
            if env_value:
                return env_value

            raise ValueError(f"Secret '{secret_name}' not found at {secret_path}")

        return secret_path.read_text().strip()

    def store_secret(self, secret_name: str, secret_value: str) -> None:
        """Not supported - secrets are created outside container"""
        raise NotImplementedError(
            "Docker/Podman secrets are read-only. "
            "Create secrets with: docker secret create <name> -"
        )

    def delete_secret(self, secret_name: str) -> bool:
        """Not supported - secrets managed outside container"""
        raise NotImplementedError(
            "Docker/Podman secrets are read-only. "
            "Delete secrets with: docker secret rm <name>"
        )

    def list_secrets(self) -> list[str]:
        """List available secret files"""
        if not self.secrets_dir.exists():
            return []
        return [f.name for f in self.secrets_dir.iterdir() if f.is_file()]

    def health_check(self) -> bool:
        """Check if secrets directory is accessible"""
        return self.secrets_dir.exists() and os.access(self.secrets_dir, os.R_OK)
```

#### Implementation 2: HashiCorp Vault (Open Source)

```python
# api/app/lib/backends/vault_secrets.py
"""
HashiCorp Vault backend (open source or enterprise).
Supports dynamic secrets, rotation, and audit logging.
"""

import hvac
import os
from pathlib import Path
from ..secret_backend import SecretBackend

class VaultSecretsBackend(SecretBackend):
    """Load secrets from HashiCorp Vault (OSS or Enterprise)"""

    def __init__(
        self,
        vault_addr: str = None,
        vault_namespace: str = None,
        auth_method: str = "kubernetes"
    ):
        self.vault_addr = vault_addr or os.getenv('VAULT_ADDR', 'http://vault:8200')
        self.vault_namespace = vault_namespace or os.getenv('VAULT_NAMESPACE')
        self.auth_method = auth_method

        self.client = hvac.Client(url=self.vault_addr, namespace=self.vault_namespace)
        self._authenticate()

    def _authenticate(self):
        """Authenticate to Vault using configured method"""
        if self.auth_method == "kubernetes":
            # Kubernetes service account JWT
            jwt_path = Path('/var/run/secrets/kubernetes.io/serviceaccount/token')
            if jwt_path.exists():
                jwt = jwt_path.read_text()
                self.client.auth.kubernetes.login(
                    role=os.getenv('VAULT_ROLE', 'kg-api'),
                    jwt=jwt
                )
        elif self.auth_method == "approle":
            # AppRole (for Docker/VM deployments)
            role_id = os.getenv('VAULT_ROLE_ID')
            secret_id = os.getenv('VAULT_SECRET_ID')
            self.client.auth.approle.login(role_id=role_id, secret_id=secret_id)
        elif self.auth_method == "token":
            # Direct token (dev only)
            self.client.token = os.getenv('VAULT_TOKEN')
        else:
            raise ValueError(f"Unknown auth method: {self.auth_method}")

    def load_secret(self, secret_name: str) -> str:
        """Load secret from Vault KV v2 engine"""
        try:
            secret = self.client.secrets.kv.v2.read_secret_version(
                path=secret_name,
                mount_point='kg-api'
            )
            return secret['data']['data']['value']
        except hvac.exceptions.InvalidPath:
            raise ValueError(f"Secret '{secret_name}' not found in Vault")
        except hvac.exceptions.Forbidden:
            raise ValueError(f"Access denied to secret '{secret_name}'")

    def store_secret(self, secret_name: str, secret_value: str) -> None:
        """Store secret in Vault KV v2 engine"""
        self.client.secrets.kv.v2.create_or_update_secret(
            path=secret_name,
            secret={'value': secret_value},
            mount_point='kg-api'
        )

    def delete_secret(self, secret_name: str) -> bool:
        """Delete secret from Vault"""
        try:
            self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                path=secret_name,
                mount_point='kg-api'
            )
            return True
        except hvac.exceptions.InvalidPath:
            return False

    def list_secrets(self) -> list[str]:
        """List secrets in Vault"""
        try:
            result = self.client.secrets.kv.v2.list_secrets(
                path='',
                mount_point='kg-api'
            )
            return result['data']['keys']
        except hvac.exceptions.InvalidPath:
            return []

    def health_check(self) -> bool:
        """Check Vault connectivity and authentication"""
        try:
            return self.client.sys.is_initialized() and self.client.is_authenticated()
        except Exception:
            return False
```

#### Implementation 3: Cloud KMS (For Cloud Deployments)

```python
# api/app/lib/backends/cloud_kms_secrets.py
"""
Cloud KMS backend - works with AWS, GCP, Azure.
Uses cloud-provider SDKs (boto3, google-cloud-kms, azure-keyvault).
"""

import os
from typing import Optional
from ..secret_backend import SecretBackend

class CloudKMSSecretsBackend(SecretBackend):
    """
    Cloud-provider secrets backend.
    Auto-detects AWS Secrets Manager, GCP Secret Manager, or Azure Key Vault.
    """

    def __init__(self, provider: Optional[str] = None):
        self.provider = provider or self._detect_provider()

        if self.provider == "aws":
            import boto3
            self.client = boto3.client('secretsmanager')
        elif self.provider == "gcp":
            from google.cloud import secretmanager
            self.client = secretmanager.SecretManagerServiceClient()
        elif self.provider == "azure":
            from azure.keyvault.secrets import SecretClient
            from azure.identity import DefaultAzureCredential
            vault_url = os.getenv('AZURE_KEY_VAULT_URL')
            self.client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
        else:
            raise ValueError(f"Unknown cloud provider: {self.provider}")

    def _detect_provider(self) -> str:
        """Auto-detect cloud provider from environment"""
        if os.getenv('AWS_REGION'):
            return "aws"
        elif os.getenv('GOOGLE_CLOUD_PROJECT'):
            return "gcp"
        elif os.getenv('AZURE_TENANT_ID'):
            return "azure"
        else:
            raise ValueError("Could not detect cloud provider")

    def load_secret(self, secret_name: str) -> str:
        """Load secret from cloud provider"""
        if self.provider == "aws":
            response = self.client.get_secret_value(SecretId=secret_name)
            return response['SecretString']
        elif self.provider == "gcp":
            project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
            name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
            response = self.client.access_secret_version(request={"name": name})
            return response.payload.data.decode('UTF-8')
        elif self.provider == "azure":
            return self.client.get_secret(secret_name).value

    def store_secret(self, secret_name: str, secret_value: str) -> None:
        """Store secret in cloud provider"""
        if self.provider == "aws":
            self.client.create_secret(Name=secret_name, SecretString=secret_value)
        elif self.provider == "gcp":
            # GCP requires parent resource path
            raise NotImplementedError("GCP secret creation not implemented")
        elif self.provider == "azure":
            self.client.set_secret(secret_name, secret_value)

    # ... (delete_secret, list_secrets, health_check implementations)
```

#### Factory Pattern for Backend Selection

```python
# api/app/lib/secrets.py (Updated with backend support)
"""
Secrets management with pluggable backends.
"""

import os
from .secret_backend import SecretBackend
from .backends.container_secrets import ContainerSecretsBackend

def get_secret_backend() -> SecretBackend:
    """
    Factory function to instantiate the appropriate secret backend.

    Selection order:
    1. SECRETS_BACKEND environment variable
    2. Auto-detect (Vault if VAULT_ADDR set, Cloud if cloud env vars, else Container)

    Returns:
        SecretBackend implementation
    """
    backend_type = os.getenv('SECRETS_BACKEND', 'auto')

    if backend_type == 'auto':
        # Auto-detect based on environment
        if os.getenv('VAULT_ADDR'):
            backend_type = 'vault'
        elif os.getenv('AWS_REGION') or os.getenv('GOOGLE_CLOUD_PROJECT') or os.getenv('AZURE_TENANT_ID'):
            backend_type = 'cloud'
        else:
            backend_type = 'container'

    if backend_type == 'container':
        from .backends.container_secrets import ContainerSecretsBackend
        return ContainerSecretsBackend()

    elif backend_type == 'vault':
        from .backends.vault_secrets import VaultSecretsBackend
        auth_method = os.getenv('VAULT_AUTH_METHOD', 'kubernetes')
        return VaultSecretsBackend(auth_method=auth_method)

    elif backend_type == 'cloud':
        from .backends.cloud_kms_secrets import CloudKMSSecretsBackend
        return CloudKMSSecretsBackend()

    else:
        raise ValueError(f"Unknown secrets backend: {backend_type}")

# Global backend instance
_backend = None

def load_secret(secret_name: str) -> str:
    """
    Load secret using configured backend.
    Backwards compatible with existing code.
    """
    global _backend
    if _backend is None:
        _backend = get_secret_backend()
    return _backend.load_secret(secret_name)

# Public API (backwards compatible)
JWT_SECRET = load_secret("jwt_secret")
ENCRYPTION_KEY = load_secret("encryption_master_key")
POSTGRES_PASSWORD = load_secret("postgres_password")
```

### Configuration Examples

#### Docker/Podman (Default - No Changes Needed)

```yaml
# docker-compose.yml (same as Phase 1)
services:
  api:
    environment:
      - SECRETS_BACKEND=container  # or omit for auto-detect
```

#### HashiCorp Vault (Open Source)

```yaml
# docker-compose.yml with Vault
services:
  vault:
    image: hashicorp/vault:latest
    ports:
      - "8200:8200"
    environment:
      - VAULT_DEV_ROOT_TOKEN_ID=dev-token  # Dev only!
    command: server -dev

  api:
    environment:
      - SECRETS_BACKEND=vault
      - VAULT_ADDR=http://vault:8200
      - VAULT_AUTH_METHOD=token
      - VAULT_TOKEN=dev-token  # Dev only!
    depends_on:
      - vault
```

#### Kubernetes with Vault

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kg-api
spec:
  template:
    spec:
      serviceAccountName: kg-api  # For Vault K8s auth
      containers:
      - name: api
        image: kg-api:latest
        env:
        - name: SECRETS_BACKEND
          value: "vault"
        - name: VAULT_ADDR
          value: "https://vault.example.com"
        - name: VAULT_AUTH_METHOD
          value: "kubernetes"
        - name: VAULT_ROLE
          value: "kg-api"
```

#### Cloud Deployment (AWS Example)

```yaml
# ECS task definition
{
  "containerDefinitions": [{
    "environment": [
      {
        "name": "SECRETS_BACKEND",
        "value": "cloud"
      },
      {
        "name": "AWS_REGION",
        "value": "us-west-2"
      }
    ]
  }]
}
```

### Migration Path

**Phase 1 (Current):** Container secrets
```bash
./scripts/init-secrets.sh
docker-compose up -d
```

**Phase 2 (Optional):** Add Vault support
```bash
# Deploy Vault (open source)
docker-compose -f docker-compose.vault.yml up -d

# Migrate secrets to Vault
./scripts/migrate-to-vault.sh

# Update environment
export SECRETS_BACKEND=vault
docker-compose restart api
```

**Phase 3 (Optional):** Cloud migration
```bash
# Deploy to cloud
# Secrets automatically use cloud provider's secret manager
# No code changes needed - backend auto-detected
```

### Open Source Commitment

This architecture ensures:
- ✅ **No vendor lock-in**: Swap backends without code changes
- ✅ **Open source default**: Docker/Podman secrets work out of the box
- ✅ **Optional enterprise**: Vault OSS, cloud providers as opt-in
- ✅ **Community friendly**: Clear extension points for custom backends
- ✅ **Self-hostable**: All backends can run on-premises

**Adding a new backend:**
1. Implement `SecretBackend` interface (5 methods)
2. Add to factory in `get_secret_backend()`
3. Document configuration
4. No changes to application code needed

## Implementation Checklist

### Infrastructure (Scripts Team)
- [ ] Create `scripts/init-secrets.sh` (auto-detect Docker/Podman)
- [ ] Create `scripts/migrate-to-secrets.sh` (migration from .env)
- [ ] Update `docker-compose.yml` to use secrets
- [ ] Update `.env.example` to document new approach
- [ ] Update `.gitignore` to exclude secret temp files

### Backend (API Team)
- [ ] Create `api/app/lib/secrets.py` (secret loading utility)
- [ ] Create `api/app/lib/encrypted_keys.py` (encryption layer for system keys)
- [ ] Update `api/app/lib/auth.py` to load JWT from secret
- [ ] Create `api/app/routes/admin_keys.py` (admin key management endpoints)
- [ ] Update database schema with `system_api_keys` table
- [ ] Add key validation on upload (test with provider API)
- [ ] Update AI provider initialization to check encrypted store first, then .env fallback

### CLI (Client Team)
- [ ] Add `kg admin keys set <provider> <key>` command
- [ ] Add `kg admin keys list` command
- [ ] Add `kg admin keys delete <provider>` command
- [ ] Update help documentation

### Documentation
- [ ] Write operator guide: `docs/deployment/SECRETS_MANAGEMENT.md`
- [ ] Update `README.md` with secrets setup section
- [ ] Create troubleshooting section for common issues
- [ ] Add security best practices document

### Testing
- [ ] Test Docker secrets flow end-to-end
- [ ] Test Podman secrets flow end-to-end
- [ ] Test admin key set/list/delete endpoints
- [ ] Test migration script with existing `.env`
- [ ] Verify encryption/decryption round-trip
- [ ] Test key validation with invalid keys
- [ ] Test multi-shard: verify each shard has independent keys

## Rollout Plan

### Phase 1: Infrastructure (Week 1)
1. Merge ADR-031
2. Create secrets management scripts
3. Update docker-compose.yml
4. Test on development environment

### Phase 2: Backend Implementation (Week 2)
1. Implement secrets loading utility
2. Implement encrypted key storage
3. Add API endpoints for key management
4. Comprehensive testing

### Phase 3: Documentation (Week 3)
1. Write operator deployment guide
2. Create video walkthrough (optional)
3. Update all relevant docs
4. Internal review

### Phase 4: Migration (Week 4)
1. Announce migration to users/operators
2. Provide migration script and support
3. Deprecate `.env` approach in docs
4. Monitor for issues

## References

- [Docker Secrets Documentation](https://docs.docker.com/engine/swarm/secrets/)
- [Podman Secrets Documentation](https://docs.podman.io/en/latest/markdown/podman-secret.1.html)
- [Cryptography.io Fernet](https://cryptography.io/en/latest/fernet/)
- [OWASP Key Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Key_Management_Cheat_Sheet.html)
- Related: ADR-027 (User Management & Authentication)
- Related: ADR-024 (Multi-Schema PostgreSQL Architecture)
