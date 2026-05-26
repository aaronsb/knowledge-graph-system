# Authentication Guide

**Operational guide for Knowledge Graph System authentication (ADR-054: OAuth 2.0)**

This guide shows you how to use the OAuth 2.0 authentication system - from cold start initialization to day-to-day operations.

## Table of Contents

- [Overview](#overview)
- [Cold Start: First-Time Setup](#cold-start-first-time-setup)
- [Login & OAuth Client Creation](#login--oauth-client-creation)
- [OAuth Client Management](#oauth-client-management)
- [Using Protected Endpoints](#using-protected-endpoints)
- [Token Lifecycle](#token-lifecycle)
- [User Management (Admin)](#user-management-admin)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Knowledge Graph System uses **OAuth 2.0 client credentials grant** for authentication:

- **kg CLI**: Creates personal OAuth client credentials during login
- **MCP Server**: Uses dedicated OAuth client credentials
- **Programmatic access**: Create OAuth clients via API

**Key Concepts:**

| Component | What it is | Lifetime |
|-----------|------------|----------|
| **OAuth Client** | Long-lived credentials (client_id + client_secret) | Never expires |
| **Access Token** | Short-lived token for API requests | 1 hour (refreshed automatically) |
| **User Account** | Username + password (only for creating OAuth clients) | Permanent |

**Authentication Flow:**

```
1. User logs in → Creates OAuth client credentials
2. Client stores credentials → client_id + client_secret
3. API requests → Exchange credentials for access token
4. Access token → Used in Authorization: Bearer header
5. Token expires → Automatically refresh using client credentials
```

**Visual Flow:**

```mermaid
sequenceDiagram
    participant User
    participant CLI as kg CLI
    participant API as API Server
    participant DB as Database

    %% Initial Login - Create OAuth Client
    rect rgb(200, 220, 240)
        Note over User,DB: Initial Login (kg login)
        User->>CLI: kg login
        CLI->>User: Prompt for username/password
        User->>CLI: Enter credentials
        CLI->>API: POST /auth/oauth/clients/personal<br/>(username + password)
        API->>DB: Verify password hash
        DB-->>API: User authenticated
        API->>DB: Create OAuth client
        DB-->>API: client_id + client_secret
        API-->>CLI: OAuth credentials
        CLI->>CLI: Save to ~/.kg/config.json
        CLI->>User: ✓ Login successful
    end

    %% Making API Requests
    rect rgb(220, 240, 200)
        Note over User,DB: API Request (any kg command)
        User->>CLI: kg admin user list
        CLI->>CLI: Read OAuth credentials
        CLI->>API: POST /auth/oauth/token<br/>(client credentials grant)
        API->>DB: Verify client credentials
        DB-->>API: Client valid
        API->>API: Sign JWT access token
        API-->>CLI: access_token (expires in 1h)
        CLI->>API: GET /admin/users<br/>Authorization: Bearer {token}
        API->>API: Verify access token signature
        API->>DB: Fetch users
        DB-->>API: User list
        API-->>CLI: User data
        CLI->>User: Display formatted output
    end

    %% Token Refresh
    rect rgb(240, 220, 200)
        Note over User,DB: Automatic Token Refresh (after ~55min)
        User->>CLI: kg ontology list
        CLI->>CLI: Check token expiry<br/>(expires in 3 min)
        CLI->>API: POST /auth/oauth/token<br/>(refresh using client credentials)
        API->>DB: Verify client credentials
        DB-->>API: Client valid
        API->>API: Sign new JWT access token
        API-->>CLI: new access_token (expires in 1h)
        CLI->>API: GET /ontology/list<br/>Authorization: Bearer {new_token}
        API-->>CLI: Ontology list
        CLI->>User: Display ontologies
    end
```

---

## Cold Start: First-Time Setup

When deploying the knowledge graph system for the first time, you need to initialize authentication and create the admin user.

### Prerequisites

1. Platform running: `./operator.sh start` (PostgreSQL + API)
2. kg CLI installed: `cd cli && npm run build && ./install.sh`

### Initialization Steps

**Run the platform initializer (creates admin user, generates secrets, sets defaults):**

```bash
./operator.sh init
```

To reset the admin password later, run `./operator.sh admin --username admin --password '<new password>'` from the operator container, or use the password-reset script described in [04-PASSWORD_RECOVERY.md](04-PASSWORD_RECOVERY.md).

**What this does:**

1. ✅ Checks if admin user already exists
2. 🔐 Prompts for admin password (with strength validation)
3. 🔑 Generates cryptographically secure JWT_SECRET_KEY (for OAuth token signing)
4. 💾 Saves JWT_SECRET_KEY to `.env` file
5. 👤 Creates admin user in database with bcrypt-hashed password

**Example session:**

```
╔════════════════════════════════════════════════════════════╗
║   Knowledge Graph System - Authentication Initialization   ║
╚════════════════════════════════════════════════════════════╝

→ Checking PostgreSQL connection...
✓ PostgreSQL is running
→ Checking if admin user exists...
✓ No admin user found (fresh installation)

Admin Password Setup
Password requirements:
  • Minimum 8 characters
  • At least one uppercase letter
  • At least one lowercase letter
  • At least one digit
  • At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)

Enter admin password: ********
Confirm admin password: ********
✓ Password meets requirements

JWT Secret Key Setup
→ No JWT secret found in .env
✓ Generated JWT secret using openssl
✓ JWT secret saved to .env

Database Setup
→ Creating admin user...
✓ Admin user created

╔════════════════════════════════════════════════════════════╗
║              Authentication Initialized!                   ║
╚════════════════════════════════════════════════════════════╝

Admin Credentials:
  Username: admin
  Password: (the password you just set)

Next Steps:
  1. Restart API server: ./operator.sh restart api
  2. Login: kg login
  3. View users: kg admin user list
```

**Why JWT_SECRET_KEY?**

Despite using OAuth 2.0, we still use JWT (JSON Web Tokens) for the access tokens. The JWT_SECRET_KEY signs these tokens to prevent tampering.

---

## Login & OAuth Client Creation

### Interactive Login (kg CLI)

The `kg login` command creates a personal OAuth client for CLI usage:

```bash
kg login
```

**What happens:**

```
Knowledge Graph Login

Username: admin
Password: ********

✓ Creating personal OAuth client credentials...
✓ Login successful

Logged in as: admin (role: admin)
OAuth Client: kg-cli-admin-20251102
Scopes: read:*, write:*

✓ Credentials saved to ~/.kg/config.json
```

**Behind the scenes:**

1. Authenticates with username/password
2. Creates OAuth client via `POST /auth/oauth/clients/personal`
3. Returns `client_id` + `client_secret`
4. Stores credentials in `~/.kg/config.json` (not the password!)
5. Future API requests use client credentials grant to get access tokens

### Check Login Status

```bash
kg config list
```

Output:
```
Configuration

API URL:     http://localhost:8000
Auto-Approve: false

Authentication:
  Client ID:     kg-cli-admin-20251102
  Client Name:   kg CLI (admin)
  Username:      admin
  Scopes:        read:*, write:*
  Created:       2025-11-02T10:30:00Z
```

---

## OAuth Client Management

### List Your OAuth Clients

```bash
kg oauth clients
```

Output:
```
Personal OAuth Clients

Client ID                 Name                 Scopes          Created              Status
────────────────────────────────────────────────────────────────────────────────────────────
kg-cli-admin-20251102     kg CLI (admin)       read:*, write:* 2 hours ago          ✓ Active
kg-mcp-server-admin       kg MCP Server (a...  read:*, write:* 1 day ago            ✓ Active

Showing 2 client(s)
```

### Create OAuth Client for MCP Server

```bash
kg oauth create-mcp
```

Output:
```
🔐 Creating OAuth client for MCP server...

✅ OAuth client created successfully!

════════════════════════════════════════════════════════════════════════════════
CLAUDE DESKTOP CONFIG
════════════════════════════════════════════════════════════════════════════════

Add this to your Claude Desktop config:

  "knowledge-graph": {
    "command": "kg-mcp-server",
    "env": {
      "KG_OAUTH_CLIENT_ID": "kg-mcp-server-admin-20251102",
      "KG_OAUTH_CLIENT_SECRET": "oauth_secret_abc123...",
      "KG_API_URL": "http://localhost:8000"
    }
  }

════════════════════════════════════════════════════════════════════════════════

⚠️  IMPORTANT:
  • Keep these credentials secure!
  • Client secret is shown only once
  • To revoke: kg oauth revoke kg-mcp-server-admin-20251102

Or add using claude CLI:

  claude mcp add knowledge-graph kg-mcp-server \
    --env KG_OAUTH_CLIENT_ID=kg-mcp-server-admin-20251102 \
    --env KG_OAUTH_CLIENT_SECRET=oauth_secret_abc123... \
    --env KG_API_URL=http://localhost:8000 \
    -s local
```

### Revoke OAuth Client

```bash
kg oauth revoke kg-cli-admin-20251102
```

If you try to revoke your current CLI client:

```
⚠️  Warning: This is your current CLI OAuth client
   Client ID: kg-cli-admin-20251102
   Revoking this will log you out.

   To proceed, use: kg oauth revoke kg-cli-admin-20251102 --force
   Or use: kg logout
```

---

## Using Protected Endpoints

### CLI Automatic Authentication

The kg CLI automatically handles authentication:

```bash
# All commands automatically use your OAuth credentials
kg admin user list
kg ontology list
kg search query "linear thinking"
```

**How it works:**

1. kg reads OAuth credentials from `~/.kg/config.json`
2. Exchanges client credentials for access token via OAuth 2.0 grant
3. Includes `Authorization: Bearer <access_token>` in API requests
4. Automatically refreshes token when it expires

### Manual API Requests (curl)

If you're not using kg CLI, authenticate manually:

**Step 1: Get access token**

```bash
curl -X POST http://localhost:8000/auth/oauth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials" \
  -d "client_id=kg-cli-admin-20251102" \
  -d "client_secret=your-client-secret" \
  -d "scope=read:* write:*"
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "scope": "read:* write:*"
}
```

**Step 2: Use access token**

```bash
curl http://localhost:8000/admin/users \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

---

## Token Lifecycle

### OAuth Client Credentials (Long-Lived)

- **Created**: During `kg login` or `kg oauth create-mcp`
- **Stored**: In `~/.kg/config.json` (CLI) or Claude Desktop config (MCP)
- **Lifetime**: Never expires (until explicitly revoked)
- **Revocation**: `kg oauth revoke <client-id>` or `kg logout`

### Access Tokens (Short-Lived)

- **Created**: On-demand via OAuth 2.0 client credentials grant
- **Stored**: In memory (not persisted to disk)
- **Lifetime**: 1 hour (configurable in API server)
- **Refresh**: Automatic (kg CLI and MCP server handle this)

**Token Refresh Flow:**

```
Time 0:00 → Get access token (expires at 1:00)
Time 0:55 → Token refresh triggered (5 min before expiry)
Time 0:55 → New access token obtained (expires at 1:55)
```

**Security Properties:**

- **OAuth credentials**: Never transmitted except during initial creation
- **Access tokens**: Short-lived, minimizes exposure if compromised
- **Passwords**: Never stored, only used during OAuth client creation

---

## User Management (Admin)

### Create Additional Users

```bash
# Interactive (prompts for password)
kg admin user create alice --role contributor

# Non-interactive (provide password)
kg admin user create bob --role curator --password "SecurePass123!"
```

### List Users

```bash
kg admin user list
```

### Grant Admin Role

```bash
kg admin user update 3 --role admin
```

### Reset User Password

```bash
# Interactive password prompt
kg admin user update 3 --password

# Or use the out-of-band reset script
# From the operator container (./operator.sh shell), then:
configure.py admin --username admin --password '<new password>'
```

---

## Troubleshooting

### "Not authenticated" Errors

**Symptom:**
```
❌ Authentication required
   Please login first: kg login
```

**Solution:**
```bash
kg login
```

### "Invalid client credentials" Errors

**Symptom:**
```bash
kg admin user list
# Error: 401 Unauthorized - Invalid client credentials
```

**Cause:** OAuth client was revoked or credentials corrupted

**Solution:**
```bash
# Clear config and re-login
kg logout --force
kg login
```

### Forgot Admin Password

Use the password reset script (bypasses the API; talks directly to PostgreSQL):

```bash
./operator/admin/reset-password.sh
```

Or from inside the operator container shell (`./operator.sh shell`):

```bash
configure.py admin --username admin --password '<new password>'
```

See [04-PASSWORD_RECOVERY.md](04-PASSWORD_RECOVERY.md) for details.

### OAuth Client Not Working

**Verify client exists:**

```bash
kg oauth clients
```

**Check client credentials in config:**

```bash
kg config list
```

**Test authentication:**

```bash
# Should work without errors
kg admin user list
```

### MCP Server Authentication Failures

**Check MCP server logs** for specific error:

**macOS:**
```bash
tail -f ~/Library/Logs/Claude/mcp*.log
```

**Common issues:**

| Error | Cause | Fix |
|-------|-------|-----|
| `Invalid client credentials` | Wrong client_id or client_secret | Verify credentials in Claude Desktop config |
| `Client not found` | OAuth client was revoked | Create new client: `kg oauth create-mcp` |
| `401 Unauthorized` | API server not running | Start platform: `./operator.sh start` |

---

## Security Best Practices

### Do's ✅

- ✅ Create separate OAuth clients for different environments (dev, prod)
- ✅ Revoke OAuth clients when no longer needed
- ✅ Use strong passwords (enforced by validation)
- ✅ Store OAuth credentials securely (kg CLI handles this)
- ✅ Use HTTPS in production
- ✅ Rotate user passwords periodically

### Don'ts ❌

- ❌ Never commit `~/.kg/config.json` to version control
- ❌ Never commit Claude Desktop config with OAuth credentials
- ❌ Never share OAuth client secrets
- ❌ Never reuse passwords across users
- ❌ Never disable password requirements in production

---

## API Reference

### OAuth Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `POST /auth/oauth/token` | POST | Get access token (client credentials grant) |
| `GET /auth/oauth/clients/personal` | GET | List personal OAuth clients |
| `POST /auth/oauth/clients/personal/new` | POST | Create additional OAuth client |
| `DELETE /auth/oauth/clients/personal/{client_id}` | DELETE | Revoke OAuth client |

### User Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /admin/users` | GET | List all users (admin only) |
| `POST /admin/users` | POST | Create user (admin only) |
| `GET /admin/users/{user_id}` | GET | Get user details |
| `PATCH /admin/users/{user_id}` | PATCH | Update user |
| `DELETE /admin/users/{user_id}` | DELETE | Delete user |

---

## Related Documentation

- **ADR-054**: [OAuth 2.0 Unified Architecture](../../architecture/authentication-security/ADR-054-oauth-client-management.md)
- **ADR-027**: [User Management API](../../architecture/authentication-security/ADR-027-user-management-api.md)
- **Password Recovery**: [04-PASSWORD_RECOVERY.md](04-PASSWORD_RECOVERY.md)
- **RBAC**: [02-RBAC.md](02-RBAC.md)

---

**Last Updated:** 2025-11-02
**Authentication Version:** OAuth 2.0 (ADR-054)
