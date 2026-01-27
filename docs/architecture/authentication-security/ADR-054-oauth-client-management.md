---
status: Accepted
date: 2025-11-01
deciders:
  - aaronsb
  - claude
---

# ADR-054: OAuth 2.0 Client Management for Multi-Client Authentication

## Overview

Authentication gets complicated when you have multiple types of clients. A web browser can't safely store secrets. A command-line tool needs to work on headless servers where you can't open a browser. A background service shouldn't require a user to be logged in. Using the same authentication approach for all three creates security holes.

This is the situation we faced with the knowledge graph system. Our initial JWT password flow worked fine for the CLI - type username and password, get a token. But what about the web visualization app? We can't have users typing their password into JavaScript that runs in the browser; that's a security nightmare. And what about the MCP server that runs in the background? It shouldn't need a human to log in every time it starts.

OAuth 2.0 solves this by providing different "flows" for different client types. Web apps use "Authorization Code + PKCE" where the browser redirects through an authorization page and never sees the password. CLI tools use "Device Authorization" where you get a code to enter in a browser (like pairing a Roku). Background services use "Client Credentials" with a secret that acts like a service account. Each flow is designed for its specific security context.

This ADR implements proper OAuth 2.0 client management, replacing our simple JWT password flow with a comprehensive system that knows the difference between a web browser, CLI tool, and background service. It provides client identification (who accessed the API), audit trails, per-client token revocation, and refresh tokens for long-lived sessions. It's the professional-grade authentication that multi-client systems need.

---

## Context

The knowledge graph system currently uses JWT tokens (password flow) and API keys for authentication. This works for the CLI but creates security problems for other client types:

### Current Authentication Limitations

**Web Application (viz-app):**
- Would require password flow (username/password sent to JavaScript)
- **Security risk:** Credentials exposed to browser environment
- No standard way to handle browser-based authentication
- No refresh tokens for long-lived sessions

**CLI (kg):**
- JWT works but lacks client application identity
- Can't distinguish `kg` CLI from other tools using the API
- No refresh mechanism (user must re-login after 60 minutes)
- No audit trail per client application

**MCP Server:**
- No dedicated machine-to-machine authentication
- Currently shares user's JWT or API key (not ideal)
- No service account concept
- Requires user to be logged in (doesn't work for background services)

### Why OAuth 2.0?

OAuth 2.0 provides **appropriate authentication flows for each client type:**

| Client | OAuth Flow | Client Type | Why |
|--------|------------|-------------|-----|
| **viz-app** | Authorization Code + PKCE | Public (no secret) | Standard for browser apps, no password exposure |
| **kg CLI** | Device Authorization Grant | Public (no secret) | User-friendly, works on headless machines |
| **MCP Server** | Client Credentials | Confidential (has secret) | Machine-to-machine, no user interaction |

**Key benefits:**
1. **Client identification** - Know which app/tool accessed the API
2. **Audit trail** - "User X via web app" vs. "User X via CLI"
3. **Per-client revocation** - Revoke web app without affecting CLI
4. **Refresh tokens** - Long-lived sessions without re-authentication
5. **Industry standard** - Well-understood security properties

## Decision

Implement **OAuth 2.0 client registration and token management** with support for three grant types:

1. **Authorization Code + PKCE** (web apps)
2. **Device Authorization Grant** (CLI tools)
3. **Client Credentials** (background services)

**Key principle:** OAuth 2.0 **replaces** JWT password flow and API keys as the primary authentication mechanism. Legacy systems removed immediately (no users to migrate).

### Database Schema

#### New Tables (5 tables)

**`kg_auth.oauth_clients` - Registered client applications**
```sql
CREATE TABLE kg_auth.oauth_clients (
    client_id VARCHAR(255) PRIMARY KEY,
    client_secret_hash VARCHAR(255),  -- bcrypt hash, NULL for public clients
    client_name VARCHAR(255) NOT NULL,
    client_type VARCHAR(50) NOT NULL,  -- 'public' or 'confidential'
    grant_types TEXT[] NOT NULL,  -- Allowed grant types
    redirect_uris TEXT[],  -- For authorization code flow
    scopes TEXT[],  -- Allowed scopes
    is_active BOOLEAN DEFAULT true,
    created_by INTEGER REFERENCES kg_auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);
```

**`kg_auth.oauth_authorization_codes` - Temporary codes (authorization code flow)**
```sql
CREATE TABLE kg_auth.oauth_authorization_codes (
    code VARCHAR(255) PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL REFERENCES kg_auth.oauth_clients(client_id),
    user_id INTEGER NOT NULL REFERENCES kg_auth.users(id),
    redirect_uri TEXT NOT NULL,
    scopes TEXT[],
    code_challenge VARCHAR(255),  -- PKCE
    code_challenge_method VARCHAR(10),  -- 'S256' or 'plain'
    expires_at TIMESTAMPTZ NOT NULL,  -- 10 minutes
    used BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**`kg_auth.oauth_device_codes` - Device authorization codes (CLI flow)**
```sql
CREATE TABLE kg_auth.oauth_device_codes (
    device_code VARCHAR(255) PRIMARY KEY,
    user_code VARCHAR(50) UNIQUE NOT NULL,  -- Human-friendly: ABCD-1234
    client_id VARCHAR(255) NOT NULL REFERENCES kg_auth.oauth_clients(client_id),
    user_id INTEGER REFERENCES kg_auth.users(id),  -- NULL until authorized
    scopes TEXT[],
    status VARCHAR(50) DEFAULT 'pending',  -- pending, authorized, denied, expired
    expires_at TIMESTAMPTZ NOT NULL,  -- 10 minutes
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**`kg_auth.oauth_access_tokens` - Issued access tokens**
```sql
CREATE TABLE kg_auth.oauth_access_tokens (
    token_hash VARCHAR(255) PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL REFERENCES kg_auth.oauth_clients(client_id),
    user_id INTEGER REFERENCES kg_auth.users(id),  -- NULL for client_credentials
    scopes TEXT[],
    expires_at TIMESTAMPTZ NOT NULL,  -- 1 hour
    revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**`kg_auth.oauth_refresh_tokens` - Long-lived refresh tokens**
```sql
CREATE TABLE kg_auth.oauth_refresh_tokens (
    token_hash VARCHAR(255) PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL REFERENCES kg_auth.oauth_clients(client_id),
    user_id INTEGER NOT NULL REFERENCES kg_auth.users(id),
    scopes TEXT[],
    access_token_hash VARCHAR(255) REFERENCES kg_auth.oauth_access_tokens(token_hash) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,  -- 7-30 days
    revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used TIMESTAMPTZ
);
```

#### Existing Table Changes

**Rename `kg_auth.oauth_tokens` to clarify purpose:**
```sql
ALTER TABLE kg_auth.oauth_tokens RENAME TO oauth_external_provider_tokens;

COMMENT ON TABLE kg_auth.oauth_external_provider_tokens IS
  'OAuth tokens FROM external providers (Google, GitHub, etc.) - not tokens issued by our system';
```

**Remove legacy auth tables (no migration needed - no users exist):**
```sql
DROP TABLE IF EXISTS kg_auth.api_keys CASCADE;  -- Replaced by OAuth
-- Keep kg_auth.users table (still needed for user accounts)
```

### API Endpoints

#### Client Registration (Admin Only)

```
POST   /auth/oauth/clients          # Register new client
GET    /auth/oauth/clients          # List clients
GET    /auth/oauth/clients/{id}     # Get client details
PATCH  /auth/oauth/clients/{id}     # Update client
DELETE /auth/oauth/clients/{id}     # Delete client
POST   /auth/oauth/clients/{id}/rotate-secret  # Rotate confidential client secret
```

#### OAuth Flows

```
GET    /auth/oauth/authorize        # Authorization endpoint (web flow)
POST   /auth/oauth/device           # Device authorization request (CLI flow)
POST   /auth/oauth/token            # Token endpoint (all flows)
POST   /auth/oauth/revoke           # Revoke token
GET    /auth/oauth/device-status    # Check device code status (for UI)
```

#### User Management (Updated)

```
POST   /auth/register               # Create user (unchanged)
DELETE /auth/login                  # REMOVED (use OAuth flows instead)
DELETE /auth/me                     # REMOVED (get user from OAuth token)
GET    /users/me                    # Get current user from OAuth token
```

### Flow Implementations

#### 1. Authorization Code + PKCE (Web App)

```
┌─────────┐                                  ┌─────────┐
│ Browser │                                  │   API   │
└────┬────┘                                  └────┬────┘
     │                                             │
     │ 1. User clicks "Login"                     │
     │────────────────────────────────────────────▶
     │                                             │
     │ 2. Redirect to /auth/oauth/authorize       │
     │    ?client_id=viz-app                      │
     │    &redirect_uri=https://viz.../callback   │
     │    &code_challenge=<hash>                  │
     │◀────────────────────────────────────────────
     │                                             │
     │ 3. User enters credentials                 │
     │────────────────────────────────────────────▶
     │                                             │
     │ 4. Redirect with authorization code        │
     │    ?code=xyz123                            │
     │◀────────────────────────────────────────────
     │                                             │
     │ 5. Exchange code for tokens                │
     │    POST /auth/oauth/token                  │
     │────────────────────────────────────────────▶
     │                                             │
     │ 6. access_token + refresh_token            │
     │◀────────────────────────────────────────────
```

#### 2. Device Authorization Grant (CLI)

```
┌─────────┐                                  ┌─────────┐
│   CLI   │                                  │   API   │
└────┬────┘                                  └────┬────┘
     │                                             │
     │ 1. kg login                                │
     │────────────────────────────────────────────▶
     │                                             │
     │ 2. device_code + user_code                 │
     │    "Visit https://.../device"              │
     │    "Enter code: ABCD-1234"                 │
     │◀────────────────────────────────────────────
     │                                             │
     │ [User opens browser, enters code]          │
     │                                             │
     │ 3. Poll /auth/oauth/token every 5s         │
     │────────────────────────────────────────────▶
     │                                             │
     │ 4. authorization_pending...                │
     │◀────────────────────────────────────────────
     │                                             │
     │ [User completes auth in browser]           │
     │                                             │
     │ 5. access_token + refresh_token            │
     │◀────────────────────────────────────────────
```

#### 3. Client Credentials (MCP Server)

```
┌─────────┐                                  ┌─────────┐
│   MCP   │                                  │   API   │
└────┬────┘                                  └────┬────┘
     │                                             │
     │ 1. POST /auth/oauth/token                  │
     │    grant_type=client_credentials           │
     │    client_id=mcp-server-123                │
     │    client_secret=<secret>                  │
     │────────────────────────────────────────────▶
     │                                             │
     │ 2. access_token (no refresh token)         │
     │◀────────────────────────────────────────────
     │                                             │
     │ [Use token until expiry, then re-auth]     │
```

### Builtin Clients

The system will include three pre-registered clients:

```sql
INSERT INTO kg_auth.oauth_clients (client_id, client_name, client_type, grant_types, redirect_uris, scopes)
VALUES
  ('kg-cli', 'Knowledge Graph CLI', 'public',
   ARRAY['urn:ietf:params:oauth:grant-type:device_code', 'refresh_token'],
   NULL,
   ARRAY['read:*', 'write:*']),

  ('kg-viz', 'Knowledge Graph Visualizer', 'public',
   ARRAY['authorization_code', 'refresh_token'],
   ARRAY['http://localhost:3000/callback', 'https://viz.kg.example.com/callback'],
   ARRAY['read:*', 'write:*']),

  ('kg-mcp', 'Knowledge Graph MCP Server', 'confidential',
   ARRAY['client_credentials'],
   NULL,
   ARRAY['read:*', 'write:*']);
```

**Note:** For `kg-mcp` confidential client, a client secret must be generated during setup:
```bash
kg admin oauth clients rotate-secret kg-mcp
```

### Token Lifetimes

| Token Type | Lifetime | Rationale |
|-----------|----------|-----------|
| Authorization Code | 10 minutes | Single-use, short-lived |
| Device Code | 10 minutes | User must act quickly |
| Access Token | 1 hour | Balance security vs. UX |
| Refresh Token (CLI) | 7 days | Weekly re-auth acceptable |
| Refresh Token (Web) | 30 days | Monthly re-auth acceptable |
| Client Credentials Token | 1 hour | Can re-auth automatically |

### Scopes

Initial scope set (aligned with RBAC resources from ADR-028):

```
read:concepts       - Read concept graph
write:concepts      - Create/modify concepts
delete:concepts     - Delete concepts

read:vocabulary     - Read edge vocabulary
write:vocabulary    - Manage edge vocabulary
approve:vocabulary  - Approve vocabulary changes

read:jobs           - View ingestion jobs
write:jobs          - Submit ingestion jobs
approve:jobs        - Approve job execution

read:users          - List users (admin)
write:users         - Manage users (admin)
delete:users        - Delete users (admin)

admin:*             - Full administrative access
read:*              - Read-only access to everything
write:*             - Read + write access to everything
```

**Wildcard support:** `*` can be used for "all actions on all resources"

## Consequences

### Positive

1. **Security**
   - Web app no longer exposes passwords to JavaScript
   - Each client type uses appropriate flow
   - PKCE prevents authorization code interception

2. **Client Identification**
   - Audit trail shows which app accessed API
   - Per-client token revocation
   - Usage statistics per client

3. **Token Management**
   - Refresh tokens enable long-lived sessions
   - Automatic token expiry and cleanup
   - Token revocation per client or user

4. **Standards Compliance**
   - OAuth 2.0 is industry standard (RFC 6749)
   - Well-understood security properties
   - Many libraries and tools available

5. **User Experience**
   - CLI: User-friendly device flow (enter code in browser)
   - Web: Standard redirect-based flow
   - MCP: Automatic machine-to-machine auth

### Negative

1. **Complexity**
   - More database tables (5 new tables)
   - More API endpoints (6 new endpoints)
   - More flows to implement and test

2. **Breaking Changes**
   - Removes JWT password flow (`POST /auth/login`)
   - Removes API keys (`kg_auth.api_keys` table)
   - Clients must adopt OAuth flows
   - **Mitigation:** No existing users, can make immediate changes

3. **Token Storage**
   - More database records (codes, tokens)
   - Cleanup jobs required
   - Monitoring token usage

4. **Implementation Effort**
   - Estimated 2-3 weeks development
   - Testing all flows thoroughly
   - Client library updates
   - Documentation

### Neutral

1. **RBAC Integration**
   - OAuth scopes map to RBAC permissions
   - Token contains scopes, API checks against RBAC
   - No changes to RBAC system (ADR-028)

2. **External OAuth Providers**
   - Table already exists (`oauth_external_provider_tokens`)
   - Can add "Login with Google/GitHub" later
   - Orthogonal to our OAuth server implementation

## Alternatives Considered

### Alternative 1: Keep JWT Password Flow

**Pros:** No changes needed, already works
**Cons:** Insecure for web apps, no client identification, not following standards
**Verdict:** ❌ Not suitable for web application

### Alternative 2: API Keys Only

**Pros:** Simple, already implemented
**Cons:** No user interaction flow, no refresh mechanism, no client identification
**Verdict:** ❌ Not suitable for interactive applications

### Alternative 3: External OAuth Provider (Auth0, Okta)

**Pros:** Professionally maintained, advanced features (MFA, SSO)
**Cons:** External dependency, cost, less control, privacy concerns
**Verdict:** ⚠️ Consider for enterprise, overkill for most users

### Alternative 4: Session-Based Auth (Cookies)

**Pros:** Simple for web apps, no token management
**Cons:** Doesn't work for CLI/MCP, not RESTful, CSRF concerns
**Verdict:** ❌ Not suitable for multi-client architecture

## Implementation Plan

### Phase 1: Database Schema (1 week) ✅ COMPLETED
- [x] Create 5 new OAuth tables
- [x] Rename `oauth_tokens` → `oauth_external_provider_tokens`
- [x] Drop `api_keys` table
- [x] Add indexes for performance
- [x] Seed builtin clients

### Phase 2: API Endpoints (1 week) ✅ COMPLETED
- [x] Client registration API (admin)
- [x] Authorization endpoint (`GET /auth/oauth/authorize`) - Placeholder
- [x] Device authorization endpoint (`POST /auth/oauth/device`)
- [x] Token endpoint (`POST /auth/oauth/token`) - all grant types
- [x] Token revocation endpoint (`POST /auth/oauth/revoke`)
- [x] Remove legacy endpoints (`/auth/login`)

### Phase 3: Client Libraries (1 week) 🚧 IN PROGRESS
**Priority:** CLI (device flow) and MCP (client credentials) first

- [ ] Update `KnowledgeGraphClient` to support OAuth
- [ ] Implement device flow for CLI (`DeviceAuthFlow` class)
- [ ] Implement client credentials for MCP (`ClientCredentialsAuth` class)
- [ ] Add token refresh logic
- [ ] Update token storage in config

**Deferred to future:** viz-app Authorization Code + PKCE flow will be implemented once CLI and MCP are stable and tested. The `kg-viz` client is pre-registered in the database and the backend endpoints are ready, but the frontend implementation is postponed.

### Phase 4: CLI Commands (3 days)
- [ ] Update `kg login` to use device flow
- [ ] Update `kg logout` to revoke tokens
- [ ] Add `kg admin oauth clients` commands
- [ ] Add `kg admin oauth tokens` commands (list/revoke)

### Phase 5: Testing & Documentation (1 week)
- [ ] Unit tests for all flows
- [ ] Integration tests
- [ ] Security tests (PKCE, token validation, etc.)
- [ ] Update authentication guide
- [ ] Create OAuth integration guides (web/CLI/MCP)
- [ ] API reference documentation

**Total estimated time:** 4-5 weeks (excluding viz-app frontend)

## References

**OAuth 2.0 Specifications:**
- RFC 6749: OAuth 2.0 Authorization Framework
- RFC 7636: Proof Key for Code Exchange (PKCE)
- RFC 8628: OAuth 2.0 Device Authorization Grant
- RFC 7009: OAuth 2.0 Token Revocation

**Related:**
- ADR-027: User Management API (superseded for OAuth)
- ADR-028: Dynamic RBAC System (unchanged)
- ADR-024: Multi-Schema PostgreSQL Architecture (kg_auth schema)

**Implementation Resources:**
- https://oauth.net/2/
- https://www.oauth.com/
- https://auth0.com/docs/authenticate/protocols/oauth
- https://github.com/panva/oauth4webapi (JavaScript OAuth library)
- https://authlib.org/ (Python OAuth library)

---

**Decision Date:** 2025-11-01
**Implementation Status:** Accepted, Ready for Implementation
**Breaking Changes:** Yes (removes JWT password flow and API keys)
**Migration Required:** No (no existing users)
