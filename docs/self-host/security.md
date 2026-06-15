# Security and Access

Kappa Graph uses OAuth 2.0 client credentials for API authentication, role-based access control (RBAC) for authorization, and Fernet-encrypted storage for LLM API keys.

---

## Authentication

### How the OAuth client credentials grant works

Kappa Graph uses OAuth 2.0 client credentials grant (ADR-054). There is no session login endpoint — `POST /auth/login` was removed. All clients obtain a short-lived access token by exchanging long-lived client credentials.

| Credential type | Created by | Stored in | Lifetime |
|---|---|---|---|
| OAuth client (client_id + client_secret) | `kg login` or `kg oauth create-mcp` | `~/.config/kg/config.json` (CLI) or MCP env | Never expires until revoked |
| Access token | OAuth token grant | Memory only, never persisted | 1 hour, auto-refreshed |
| User password | `kg admin user create` | PostgreSQL (bcrypt) | Until changed |

Passwords are used only once — to create an OAuth client. Subsequent API requests use the client credentials grant, not the password.

### First-time setup

Run `./operator.sh init` before starting the API. This creates the admin user, generates a JWT signing key, and writes infrastructure secrets to `.env`.

```
./operator.sh init
```

The initializer prompts for an admin password (minimum 8 characters; at least one uppercase, one lowercase, one digit, one special character), generates `JWT_SECRET_KEY`, and saves it to `.env`. Restart the API after init:

```
./operator.sh restart api
```

### CLI login

```bash
kg login
```

The CLI prompts for username and password, calls `POST /auth/oauth/clients/personal`, and stores the returned `client_id` and `client_secret` in `~/.config/kg/config.json`. The password is not saved.

To check the current login state:

```bash
kg config list
```

### Obtaining an access token manually

For direct API access without the CLI:

```bash
curl -X POST http://localhost:8000/auth/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=kg-cli-admin-20251102" \
  -d "client_secret=your-client-secret" \
  -d "scope=read:* write:*"
```

```json
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 3600,
  "scope": "read:* write:*"
}
```

Include the token in subsequent requests:

```bash
curl http://localhost:8000/users \
  -H "Authorization: Bearer eyJhbGci..."
```

### OAuth client management

**Create a client for the MCP server:**

```bash
kg oauth create-mcp
```

The command prints the client credentials and the exact JSON block to add to your MCP config. The secret is shown only once.

**List clients:**

```bash
kg oauth clients
```

**Revoke a client:**

```bash
kg oauth revoke kg-cli-admin-20251102
```

Revoking your current CLI client logs you out. The CLI will warn before proceeding; pass `--force` or use `kg logout`.

### OAuth endpoints

| Endpoint | Description |
|---|---|
| `POST /auth/oauth/token` | Get access token (client credentials grant) |
| `GET /auth/oauth/clients/personal` | List personal OAuth clients |
| `POST /auth/oauth/clients/personal/new` | Create additional OAuth client |
| `DELETE /auth/oauth/clients/personal/{client_id}` | Revoke OAuth client |

---

## User management

User management requires admin authentication. All user endpoints are under `/users`.

### Create a user

```bash
# Interactive password prompt
kg admin user create alice --role contributor

# Non-interactive
kg admin user create bob --role curator --password "SecurePass123!"
```

### List and inspect users

```bash
kg admin user list
kg admin user list --role admin
kg admin user get 3
```

### Update a user

```bash
# Change role
kg admin user update 3 --role curator

# Change password (interactive)
kg admin user update 3 --password

# Disable / enable
kg admin user update 3 --disable
kg admin user update 3 --enable
```

Disabling a user preserves the audit trail. Prefer disable over delete for inactive accounts.

### Delete a user

```bash
kg admin user delete 3
```

The CLI requires a re-authentication challenge before deletion. You cannot delete your own account.

### User API endpoints

| Endpoint | Description |
|---|---|
| `GET /users` | List all users (admin) |
| `POST /users` | Create user (admin) |
| `GET /users/{user_id}` | Get user details |
| `PUT /users/{user_id}` | Update user |
| `DELETE /users/{user_id}` | Delete user |

---

## Role-based access control

Kappa Graph implements dynamic RBAC (ADR-028). Roles can inherit from parent roles, and permissions can be scoped globally, to a specific resource instance, or filtered.

Permission precedence: **DENY → Instance → Filter → Global → Inherited**

### Built-in roles

| Role | Capabilities |
|---|---|
| `read_only` | Read concepts, search, view own jobs |
| `contributor` | All read_only + create/update content, cancel own jobs |
| `curator` | All contributor + approve jobs, view all user jobs |
| `admin` | All curator + manage users/roles/permissions, cancel any job, bulk delete user jobs |
| `platform_admin` | All admin + manage system jobs and scheduled tasks |

Built-in roles cannot be deleted. They can be modified, but do so with care.

### Job permission scopes

| Scope | Who can use | Example |
|---|---|---|
| `own` | contributor and up | Cancel your own ingestion job |
| `global` | curator and up | View all user jobs |
| `system` | platform_admin only | Manage scheduler jobs |

### Custom roles

```bash
# Create a role inheriting from contributor
kg admin rbac roles create \
  -n "ml_researcher" \
  -d "ML Researcher" \
  --description "Machine learning research team" \
  -p contributor

# Grant specific permissions
kg admin rbac permissions grant -r ml_researcher -t concepts -a read
kg admin rbac permissions grant -r ml_researcher -t concepts -a write

# Assign to a user
kg admin rbac assign add -u 10 -r ml_researcher
```

### Scoped permissions

```bash
# Global permission
kg admin rbac permissions grant -r data_scientist -t concepts -a read

# Instance-scoped permission (one ontology)
kg admin rbac permissions grant \
  -r data_scientist -t ontology -a write \
  -s instance --scope-id "research-2024"

# Explicit deny (overrides inherited grant)
kg admin rbac permissions grant \
  -r contributor -t users -a delete --deny
```

### Time-limited access

```bash
kg admin rbac assign add \
  -u 7 -r curator \
  --expires "2026-10-15T23:59:59Z"
```

Expired assignments are revoked automatically.

### Audit a user's permissions

```bash
kg admin user get 5
kg admin rbac assign list 5
kg admin rbac permissions list --role data_scientist
```

### RBAC API endpoints

```
GET    /api/rbac/roles
POST   /api/rbac/roles
GET    /api/rbac/roles/{name}
DELETE /api/rbac/roles/{name}

GET    /api/rbac/permissions
POST   /api/rbac/permissions
DELETE /api/rbac/permissions/{id}

GET    /api/rbac/user-roles/{user_id}
POST   /api/rbac/user-roles
DELETE /api/rbac/user-roles/{id}

POST   /api/rbac/check-permission
```

---

## LLM API key storage

LLM API keys (OpenAI, Anthropic) are encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256) and stored as binary blobs in PostgreSQL (ADR-031). Plaintext keys are never returned via API.

The master encryption key is separate from the database. The fallback chain is:

1. Encrypted storage (tried first)
2. Environment variable (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)
3. `.env` file

Existing `.env` configurations continue to work without migration.

### Store or rotate a key

```bash
curl -X POST http://localhost:8000/admin/keys/openai \
  -F "api_key=sk-proj-..."
```

The API validates the key format, tests it against the provider, encrypts it, and stores it. It rejects invalid or expired keys before writing.

```bash
# List configured providers (no plaintext keys returned)
curl http://localhost:8000/admin/keys

# Remove a key
curl -X DELETE http://localhost:8000/admin/keys/openai
```

**Supported providers:** `openai`, `anthropic`

### Configure the master encryption key (production)

In development, the system auto-generates a temporary encryption key on each restart. Keys stored with that key become unreadable after a restart — you must re-store them.

In production, set a persistent key before storing any LLM API keys.

**Option 1 — Docker/Podman secrets (recommended):**

```bash
# Generate a Fernet key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Create the secret
echo "gAAAAABe..." | docker secret create encryption_master_key -
```

Mount it in `docker-compose.yml`:

```yaml
services:
  api:
    secrets:
      - encryption_master_key

secrets:
  encryption_master_key:
    external: true
```

The API loads from `/run/secrets/encryption_master_key` automatically.

**Option 2 — Environment variable:**

```bash
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
echo "ENCRYPTION_KEY=$ENCRYPTION_KEY" >> .env
```

Do not commit `.env` to version control.

**Option 3 — File path (external secrets managers):**

```bash
echo "gAAAAABe..." > /secure/path/encryption.key
chmod 600 /secure/path/encryption.key
export ENCRYPTION_KEY_FILE=/secure/path/encryption.key
```

### Internal service token

Worker threads must present a capability token to decrypt LLM API keys. Configure this in production to prevent arbitrary code from accessing keys:

```bash
echo "INTERNAL_KEY_SERVICE_SECRET=$(openssl rand -hex 32)" >> .env
./operator.sh restart api
```

### Key rotation

Rotate LLM API keys by storing the new key via `POST /admin/keys/{provider}`. The new key replaces the old one immediately. Revoke the old key at the provider after confirming ingestion works.

Rotating the master encryption key requires re-encrypting all stored LLM keys with the new master. Until an automated re-encryption script exists, use blue-green deployment: spin up a new instance with the new master, re-enter LLM API keys, then migrate traffic.

Recommended schedule:

| Secret | Rotation interval |
|---|---|
| LLM API keys | Every 90 days |
| Master encryption key | Every 6–12 months |
| Internal service token | Every 6 months |

### Key management API endpoints

| Endpoint | Description |
|---|---|
| `GET /admin/keys` | List configured providers |
| `POST /admin/keys/{provider}` | Store or rotate a key |
| `DELETE /admin/keys/{provider}` | Remove a key |

---

## Password recovery

When the API is unreachable or the admin password is lost, reset passwords directly through PostgreSQL using the reset script. The API does not need to be running.

```bash
./operator/admin/reset-password.sh
```

The script lists existing users, prompts for the new password (same strength requirements as `kg admin user create`), hashes it with bcrypt (cost factor 12), and writes it to `kg_auth.users` directly.

After reset, log in:

```bash
kg login
```

**When to use `reset-password.sh` vs `./operator.sh init`:**

- `reset-password.sh` — reset the password for any existing user; no secrets are regenerated
- `./operator.sh init` — first-time setup; generates `.env` secrets and creates the admin user; re-running it regenerates the JWT signing key, which invalidates all existing OAuth tokens

### Recover lost admin access

If no users have the admin role, use the operator shell:

```bash
./operator.sh shell
configure.py users
```

Then log back in:

```bash
kg login --username admin
```

---

## Threat model

To read a stored LLM API key, an attacker must compromise all of:

1. HTTP API authentication (bypass OAuth + RBAC)
2. Job queue (inject a malicious job into PostgreSQL)
3. Worker thread (execute code in the worker context)
4. Capability token (present a valid internal secret)
5. Master encryption key (decrypt the stored ciphertext)

The system does not protect against code execution within a worker thread, memory inspection during active LLM calls, or compromise of the master encryption key itself. Use system hardening, process isolation, and monitoring as complementary controls.

---

## ADR references

- ADR-027 — User management API
- ADR-028 — Dynamic RBAC system
- ADR-031 — Encrypted API key storage
- ADR-054 — Unified OAuth authentication (removed `POST /auth/login`)
- ADR-074 — Platform admin role
