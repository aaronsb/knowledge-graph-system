# ADR-031: Encrypted API Key Storage with Container Secrets

**Status:** Proposed
**Date:** 2025-10-12
**Deciders:** Development Team
**Related:** ADR-027 (User Management), ADR-024 (PostgreSQL Architecture)

## Context

The knowledge graph system requires inference API keys (OpenAI, Anthropic) to extract concepts from documents. Currently, these are stored in `.env` files, which presents several issues:

1. **Single shared key**: All users share one API key, limiting cost tracking and accountability
2. **Static storage**: Keys are plaintext in `.env` files, discoverable by anyone with filesystem access
3. **Rotation friction**: Changing keys requires editing `.env` and restarting services
4. **Risk of exposure**: Database dumps, backups, or accidental commits could expose keys
5. **No user choice**: Users cannot bring their own keys (BYOK)

For self-hosted deployments (Docker/Podman), we need a solution that:
- ✅ Allows user-provided API keys (bring your own key)
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
│ │ Table: user_api_keys                │ │
│ │ ┌─────────────────────────────────┐ │ │
│ │ │ user_id | provider | encrypted  │ │ │
│ │ │ uuid    | string   | bytea      │ │ │
│ │ └─────────────────────────────────┘ │ │
│ └─────────────────────────────────────┘ │
└─────────────────────────────────────────┘
                   │
                   ↓ decrypt when needed
┌─────────────────────────────────────────┐
│ Application Runtime (Layer 3)           │
│ - API keys exist in memory only         │
│ - Decrypted on demand for API calls     │
│ - Garbage collected after use           │
└─────────────────────────────────────────┘
```

### Key Principles

1. **Separation of Concerns**
   - `jwt_secret`: Signs/verifies authentication tokens (ADR-027)
   - `encryption_master_key`: Encrypts/decrypts API keys (this ADR)
   - `postgres_password`: Database authentication

2. **Encryption at Rest**
   - User API keys encrypted with Fernet (AES-128-CBC + HMAC-SHA256)
   - Master key stored in Docker/Podman secrets (not in database)
   - Keys decrypted only when needed, held in memory briefly

3. **User-Provided Keys (BYOK)**
   - Users upload their own OpenAI/Anthropic keys via API
   - Per-user cost tracking and quota management
   - Keys validated before storage

4. **Threat Model**
   - ✅ **Protects against**: Database dumps, SQL injection, backup theft, DBA snooping
   - ❌ **Does NOT protect against**: Runtime memory access, container root compromise, host compromise
   - **Trade-off**: Acceptable for self-hosted private network deployment

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
echo "  3. Initialize database: ./scripts/initialize-auth.sh"
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
# src/api/lib/secrets.py
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
# src/api/lib/encrypted_keys.py
"""
User API key storage with encryption at rest.
"""

from cryptography.fernet import Fernet
import psycopg2
from datetime import datetime, timedelta
from typing import Optional
from .secrets import ENCRYPTION_KEY

class EncryptedKeyStore:
    """Manage user API keys with encryption at rest"""

    def __init__(self, db_connection):
        self.db = db_connection
        self.cipher = Fernet(ENCRYPTION_KEY.encode())
        self._ensure_table()

    def _ensure_table(self):
        """Create user_api_keys table if it doesn't exist"""
        with self.db.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_api_keys (
                    user_id UUID NOT NULL,
                    provider VARCHAR(50) NOT NULL,
                    encrypted_key BYTEA NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    last_used TIMESTAMP WITH TIME ZONE,
                    last_rotated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    PRIMARY KEY (user_id, provider),
                    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_user_api_keys_last_used
                ON user_api_keys(last_used);
            """)
            self.db.commit()

    def store_key(self, user_id: str, provider: str, plaintext_key: str) -> None:
        """
        Encrypt and store user's API key.

        Args:
            user_id: User UUID
            provider: 'openai' or 'anthropic'
            plaintext_key: The actual API key
        """
        encrypted = self.cipher.encrypt(plaintext_key.encode())

        with self.db.cursor() as cur:
            cur.execute("""
                INSERT INTO user_api_keys (user_id, provider, encrypted_key)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, provider)
                DO UPDATE SET
                    encrypted_key = EXCLUDED.encrypted_key,
                    last_rotated = NOW()
            """, (user_id, provider, encrypted))
            self.db.commit()

    def get_key(self, user_id: str, provider: str) -> str:
        """
        Decrypt and return user's API key.
        Updates last_used timestamp.

        Args:
            user_id: User UUID
            provider: 'openai' or 'anthropic'

        Returns:
            Plaintext API key

        Raises:
            ValueError: If key not found
        """
        with self.db.cursor() as cur:
            cur.execute("""
                SELECT encrypted_key
                FROM user_api_keys
                WHERE user_id = %s AND provider = %s
            """, (user_id, provider))

            row = cur.fetchone()
            if not row:
                raise ValueError(f"No {provider} API key found for user {user_id}")

            encrypted = bytes(row[0])
            plaintext = self.cipher.decrypt(encrypted).decode()

            # Update last_used timestamp
            cur.execute("""
                UPDATE user_api_keys
                SET last_used = NOW()
                WHERE user_id = %s AND provider = %s
            """, (user_id, provider))
            self.db.commit()

            return plaintext

    def delete_key(self, user_id: str, provider: str) -> bool:
        """
        Remove user's API key.

        Returns:
            True if key was deleted, False if not found
        """
        with self.db.cursor() as cur:
            cur.execute("""
                DELETE FROM user_api_keys
                WHERE user_id = %s AND provider = %s
            """, (user_id, provider))
            self.db.commit()
            return cur.rowcount > 0

    def check_rotation_needed(self, user_id: str, provider: str, days: int = 90) -> bool:
        """
        Check if key should be rotated based on age.

        Args:
            user_id: User UUID
            provider: 'openai' or 'anthropic'
            days: Rotation threshold in days (default: 90)

        Returns:
            True if rotation recommended
        """
        with self.db.cursor() as cur:
            cur.execute("""
                SELECT last_rotated
                FROM user_api_keys
                WHERE user_id = %s AND provider = %s
            """, (user_id, provider))

            row = cur.fetchone()
            if not row:
                return False

            last_rotated = row[0]
            return datetime.now() - last_rotated > timedelta(days=days)
```

#### API Endpoints

```python
# src/api/routes/user_keys.py
"""
API endpoints for user API key management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Literal
import anthropic
import openai

from ..lib.encrypted_keys import EncryptedKeyStore
from ..dependencies.auth import get_current_active_user
from ..lib.age_client import get_age_client

router = APIRouter(prefix="/api/keys", tags=["user-keys"])

class APIKeyUpload(BaseModel):
    provider: Literal["openai", "anthropic"]
    api_key: str

class APIKeyStatus(BaseModel):
    provider: str
    has_key: bool
    last_used: Optional[str]
    rotation_needed: bool

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_api_key(
    key_data: APIKeyUpload,
    current_user = Depends(get_current_active_user),
    age_client = Depends(get_age_client)
):
    """
    Upload and encrypt user's API key.
    Key is validated before storage.
    """
    # Validate key format
    if key_data.provider == "anthropic":
        if not key_data.api_key.startswith("sk-ant-"):
            raise HTTPException(400, "Invalid Anthropic API key format")
    elif key_data.provider == "openai":
        if not key_data.api_key.startswith("sk-"):
            raise HTTPException(400, "Invalid OpenAI API key format")

    # Test the key by making a minimal API call
    try:
        if key_data.provider == "anthropic":
            client = anthropic.Anthropic(api_key=key_data.api_key)
            client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
        else:  # openai
            client = openai.OpenAI(api_key=key_data.api_key)
            client.chat.completions.create(
                model="gpt-3.5-turbo",
                max_tokens=1,
                messages=[{"role": "user", "content": "test"}]
            )
    except Exception as e:
        raise HTTPException(400, f"API key validation failed: {str(e)}")

    # Store encrypted
    key_store = EncryptedKeyStore(age_client.conn)
    key_store.store_key(current_user.user_id, key_data.provider, key_data.api_key)

    return {
        "status": "success",
        "message": f"{key_data.provider} API key stored securely"
    }

@router.get("/status", response_model=list[APIKeyStatus])
async def get_key_status(
    current_user = Depends(get_current_active_user),
    age_client = Depends(get_age_client)
):
    """Get status of user's API keys"""
    key_store = EncryptedKeyStore(age_client.conn)

    statuses = []
    for provider in ["openai", "anthropic"]:
        try:
            # Check if key exists and get metadata
            with age_client.conn.cursor() as cur:
                cur.execute("""
                    SELECT last_used, last_rotated
                    FROM user_api_keys
                    WHERE user_id = %s AND provider = %s
                """, (current_user.user_id, provider))
                row = cur.fetchone()

                if row:
                    last_used, last_rotated = row
                    rotation_needed = key_store.check_rotation_needed(
                        current_user.user_id, provider
                    )
                    statuses.append(APIKeyStatus(
                        provider=provider,
                        has_key=True,
                        last_used=last_used.isoformat() if last_used else None,
                        rotation_needed=rotation_needed
                    ))
                else:
                    statuses.append(APIKeyStatus(
                        provider=provider,
                        has_key=False,
                        last_used=None,
                        rotation_needed=False
                    ))
        except Exception:
            pass

    return statuses

@router.delete("/{provider}")
async def delete_api_key(
    provider: Literal["openai", "anthropic"],
    current_user = Depends(get_current_active_user),
    age_client = Depends(get_age_client)
):
    """Delete user's API key"""
    key_store = EncryptedKeyStore(age_client.conn)

    deleted = key_store.delete_key(current_user.user_id, provider)
    if not deleted:
        raise HTTPException(404, f"No {provider} API key found")

    return {"status": "success", "message": f"{provider} API key deleted"}
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

3. **✅ Per-user keys (BYOK)**
   - Cost tracking per user
   - Users control their own quotas
   - No shared key bottleneck

4. **✅ Runtime rotation**
   - Users can update keys without redeployment
   - API endpoint for key management
   - Rotation reminders based on age

5. **✅ Docker/Podman agnostic**
   - Same interface for both runtimes
   - Detection scripts handle differences
   - Portable across environments

6. **✅ Clear operational docs**
   - Step-by-step setup instructions
   - Automated scripts reduce errors
   - Verification steps included

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

2. **Per-user API cost**
   - Users must provide their own keys
   - Could be positive (better cost control) or negative (friction)

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
# src/api/lib/secret_backend.py
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
# src/api/lib/backends/container_secrets.py
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
# src/api/lib/backends/vault_secrets.py
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
# src/api/lib/backends/cloud_kms_secrets.py
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
# src/api/lib/secrets.py (Updated with backend support)
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
- [ ] Create `src/api/lib/secrets.py` (secret loading utility)
- [ ] Create `src/api/lib/encrypted_keys.py` (encryption layer)
- [ ] Update `src/api/lib/auth.py` to load JWT from secret
- [ ] Create `src/api/routes/user_keys.py` (key management endpoints)
- [ ] Update database schema with `user_api_keys` table
- [ ] Add key validation on upload (test with provider API)

### Documentation
- [ ] Write operator guide: `docs/deployment/SECRETS_MANAGEMENT.md`
- [ ] Update `README.md` with secrets setup section
- [ ] Create troubleshooting section for common issues
- [ ] Add security best practices document

### Testing
- [ ] Test Docker secrets flow end-to-end
- [ ] Test Podman secrets flow end-to-end
- [ ] Test key upload/delete/rotation endpoints
- [ ] Test migration script with existing `.env`
- [ ] Verify encryption/decryption round-trip
- [ ] Test key validation with invalid keys

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
