# OAuth Client Management - Feasibility Analysis

**Date:** 2025-11-01
**Status:** Proposal / Analysis
**Purpose:** Evaluate OAuth 2.0 client credential management for web, CLI, and MCP clients

## Executive Summary

This document analyzes adding OAuth 2.0 client ID/secret management to support:
1. **Web Client (viz-app)** - Authorization code flow with PKCE
2. **CLI (kg)** - Device authorization flow or client credentials
3. **MCP Server** - Client credentials flow (machine-to-machine)

**Recommendation:** Implement OAuth 2.0 with client registration system. This provides standard, secure authentication across all client types while maintaining backward compatibility with existing JWT/API key systems.

---

## Current Authentication Architecture

### Existing Systems

#### 1. JWT Tokens (Interactive Users)
```
User → POST /auth/login (username/password)
     ← JWT access token (60 min expiry)
     → Authorization: Bearer <jwt>
```

**Storage:**
- `kg_auth.users` - User accounts with bcrypt password hashes
- Tokens: Stateless JWT signed with `JWT_SECRET_KEY`
- No token storage (stateless)

**Limitations:**
- Short-lived (60 min)
- No refresh tokens
- Password flow only (not suitable for web apps)
- No client identification

#### 2. API Keys (Programmatic Access)
```
User → POST /auth/api-keys (create key with scopes)
     ← API key: kg_sk_...
     → Authorization: Bearer kg_sk_...
```

**Storage:**
- `kg_auth.api_keys` - bcrypt-hashed keys with scopes
- Long-lived (configurable expiration)
- Per-user, not per-client-application

**Limitations:**
- No client application identity
- No rotation mechanism
- Shared secret model (less secure for distributed clients)

#### 3. OAuth Tokens Table (External Providers)
```sql
CREATE TABLE kg_auth.oauth_tokens (
    token_hash VARCHAR(255) PRIMARY KEY,
    user_id INTEGER REFERENCES kg_auth.users(id),
    provider VARCHAR(50),  -- e.g., "google", "github"
    scopes TEXT[],
    expires_at TIMESTAMPTZ NOT NULL
);
```

**Purpose:** Store OAuth tokens FROM external providers (Login with Google/GitHub)
**Not used for:** Issuing our own OAuth tokens to clients

---

## Why OAuth Client Management?

### Problem Statement

**Current situation:**
- Web app (viz-app): Would use password flow (insecure - exposes credentials to JavaScript)
- CLI: Uses JWT but no client identity (can't distinguish kg CLI vs. other tools)
- MCP: No dedicated auth mechanism (shares user's JWT or API key)

**What we need:**
- **Client application identity**: Distinguish between web app, CLI, MCP server, mobile apps, etc.
- **Appropriate flows per client type**: Authorization code for web, device flow for CLI, client credentials for MCP
- **Token lifecycle management**: Refresh tokens, rotation, revocation per client
- **Audit trail**: "User X accessed via CLI" vs. "User X accessed via web app"

---

## OAuth 2.0 Client Types & Flows

### Client Type Matrix

| Client Type | OAuth Flow | Client Credentials | Use Case |
|-------------|------------|-------------------|----------|
| **Web App (viz-app)** | Authorization Code + PKCE | Public (no secret) | Browser-based JavaScript app |
| **CLI (kg)** | Device Authorization Grant | Public (no secret) | Command-line tool on user's machine |
| **MCP Server** | Client Credentials | Confidential (client_id + secret) | Machine-to-machine (runs as service) |
| **Mobile App** | Authorization Code + PKCE | Public (no secret) | Future: iOS/Android apps |
| **Backend Service** | Client Credentials | Confidential (client_id + secret) | Future: CI/CD pipelines, integrations |

### Flow Details

#### 1. Authorization Code Flow + PKCE (Web App)

**Best for:** Browser-based single-page applications (viz-app)

```
┌─────────┐                                       ┌─────────┐
│ Browser │                                       │   API   │
└────┬────┘                                       └────┬────┘
     │                                                  │
     │ 1. User clicks "Login" in viz-app               │
     │────────────────────────────────────────────────▶│
     │                                                  │
     │ 2. Redirect to /auth/authorize?                 │
     │    client_id=viz-app                            │
     │    redirect_uri=https://viz.example.com/callback│
     │    code_challenge=<hash>                        │
     │    code_challenge_method=S256                   │
     │◀────────────────────────────────────────────────│
     │                                                  │
     │ 3. User enters username/password                │
     │────────────────────────────────────────────────▶│
     │                                                  │
     │ 4. Redirect to callback with code               │
     │    https://viz.../callback?code=xyz123          │
     │◀────────────────────────────────────────────────│
     │                                                  │
     │ 5. POST /auth/token                             │
     │    grant_type=authorization_code                │
     │    code=xyz123                                  │
     │    client_id=viz-app                            │
     │    code_verifier=<original>                     │
     │────────────────────────────────────────────────▶│
     │                                                  │
     │ 6. access_token + refresh_token                 │
     │◀────────────────────────────────────────────────│
```

**Key features:**
- No client secret (public client)
- PKCE prevents authorization code interception
- Refresh tokens for long-lived sessions
- Redirect-based (standard for web apps)

#### 2. Device Authorization Grant (CLI)

**Best for:** Command-line tools without browser access (kg CLI)

```
┌─────────┐                                       ┌─────────┐
│   CLI   │                                       │   API   │
└────┬────┘                                       └────┬────┘
     │                                                  │
     │ 1. kg login                                     │
     │────────────────────────────────────────────────▶│
     │                                                  │
     │ 2. device_code + user_code + verification_uri   │
     │    "Visit https://kg.example.com/device"        │
     │    "Enter code: ABCD-1234"                      │
     │◀────────────────────────────────────────────────│
     │                                                  │
     │ [Display instructions to user]                  │
     │ "Visit URL, enter code, then press Enter"       │
     │                                                  │
     │ [User opens browser, enters code, logs in]      │
     │                                                  │
     │ 3. Poll /auth/token (every 5s)                  │
     │    grant_type=urn:...device_code                │
     │    device_code=<device_code>                    │
     │    client_id=kg-cli                             │
     │────────────────────────────────────────────────▶│
     │                                                  │
     │ 4. [Polling] authorization_pending...           │
     │◀────────────────────────────────────────────────│
     │                                                  │
     │ 5. [User completes auth in browser]             │
     │                                                  │
     │ 6. access_token + refresh_token                 │
     │◀────────────────────────────────────────────────│
```

**Key features:**
- No browser redirect needed
- User-friendly code (ABCD-1234)
- Works for headless/remote machines
- Polling-based (not instant)

#### 3. Client Credentials Flow (MCP Server)

**Best for:** Machine-to-machine, background services (MCP server)

```
┌─────────┐                                       ┌─────────┐
│   MCP   │                                       │   API   │
└────┬────┘                                       └────┬────┘
     │                                                  │
     │ 1. MCP server starts, reads client_id + secret  │
     │                                                  │
     │ 2. POST /auth/token                             │
     │    grant_type=client_credentials                │
     │    client_id=mcp-server-123                     │
     │    client_secret=<secret>                       │
     │    scope=read:concepts write:ingest             │
     │────────────────────────────────────────────────▶│
     │                                                  │
     │ 3. access_token (no refresh token)              │
     │◀────────────────────────────────────────────────│
     │                                                  │
     │ [Use token until expiry, then re-authenticate]  │
```

**Key features:**
- No user interaction
- Client secret stored securely
- Service account-style access
- No refresh tokens (just re-authenticate)

---

## Proposed Database Schema

### New Tables

#### `kg_auth.oauth_clients`
```sql
CREATE TABLE kg_auth.oauth_clients (
    client_id VARCHAR(255) PRIMARY KEY,
    client_secret_hash VARCHAR(255),  -- bcrypt hash (NULL for public clients)
    client_name VARCHAR(255) NOT NULL,
    client_type VARCHAR(50) NOT NULL,  -- 'public' or 'confidential'
    grant_types TEXT[] NOT NULL,  -- ['authorization_code', 'refresh_token', 'device_code', 'client_credentials']
    redirect_uris TEXT[],  -- Allowed redirect URIs (for web apps)
    scopes TEXT[],  -- Allowed scopes
    is_active BOOLEAN DEFAULT true,
    created_by INTEGER REFERENCES kg_auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB  -- Extra data: logo_uri, client_uri, etc.
);

CREATE INDEX idx_oauth_clients_type ON kg_auth.oauth_clients(client_type);
CREATE INDEX idx_oauth_clients_active ON kg_auth.oauth_clients(is_active);

COMMENT ON TABLE kg_auth.oauth_clients IS 'Registered OAuth 2.0 clients (web app, CLI, MCP, etc.)';
COMMENT ON COLUMN kg_auth.oauth_clients.client_type IS 'public (no secret) or confidential (has secret)';
COMMENT ON COLUMN kg_auth.oauth_clients.grant_types IS 'Allowed OAuth grant types for this client';
```

#### `kg_auth.oauth_authorization_codes`
```sql
CREATE TABLE kg_auth.oauth_authorization_codes (
    code VARCHAR(255) PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL REFERENCES kg_auth.oauth_clients(client_id),
    user_id INTEGER NOT NULL REFERENCES kg_auth.users(id),
    redirect_uri TEXT NOT NULL,
    scopes TEXT[],
    code_challenge VARCHAR(255),  -- PKCE
    code_challenge_method VARCHAR(10),  -- 'S256' or 'plain'
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_oauth_authz_code_client ON kg_auth.oauth_authorization_codes(client_id);
CREATE INDEX idx_oauth_authz_code_user ON kg_auth.oauth_authorization_codes(user_id);
CREATE INDEX idx_oauth_authz_code_expires ON kg_auth.oauth_authorization_codes(expires_at);

COMMENT ON TABLE kg_auth.oauth_authorization_codes IS 'Temporary authorization codes (10 min lifetime)';
```

#### `kg_auth.oauth_device_codes`
```sql
CREATE TABLE kg_auth.oauth_device_codes (
    device_code VARCHAR(255) PRIMARY KEY,
    user_code VARCHAR(50) UNIQUE NOT NULL,  -- Human-friendly: ABCD-1234
    client_id VARCHAR(255) NOT NULL REFERENCES kg_auth.oauth_clients(client_id),
    user_id INTEGER REFERENCES kg_auth.users(id),  -- NULL until user authorizes
    scopes TEXT[],
    status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'authorized', 'denied', 'expired'
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_oauth_device_code_user_code ON kg_auth.oauth_device_codes(user_code);
CREATE INDEX idx_oauth_device_code_status ON kg_auth.oauth_device_codes(status);
CREATE INDEX idx_oauth_device_code_expires ON kg_auth.oauth_device_codes(expires_at);

COMMENT ON TABLE kg_auth.oauth_device_codes IS 'Device authorization grant codes (CLI login)';
```

#### `kg_auth.oauth_access_tokens`
```sql
CREATE TABLE kg_auth.oauth_access_tokens (
    token_hash VARCHAR(255) PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL REFERENCES kg_auth.oauth_clients(client_id),
    user_id INTEGER REFERENCES kg_auth.users(id),  -- NULL for client_credentials flow
    scopes TEXT[],
    token_type VARCHAR(50) DEFAULT 'Bearer',
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_oauth_access_token_client ON kg_auth.oauth_access_tokens(client_id);
CREATE INDEX idx_oauth_access_token_user ON kg_auth.oauth_access_tokens(user_id);
CREATE INDEX idx_oauth_access_token_expires ON kg_auth.oauth_access_tokens(expires_at);

COMMENT ON TABLE kg_auth.oauth_access_tokens IS 'Issued OAuth access tokens';
```

#### `kg_auth.oauth_refresh_tokens`
```sql
CREATE TABLE kg_auth.oauth_refresh_tokens (
    token_hash VARCHAR(255) PRIMARY KEY,
    client_id VARCHAR(255) NOT NULL REFERENCES kg_auth.oauth_clients(client_id),
    user_id INTEGER NOT NULL REFERENCES kg_auth.users(id),
    scopes TEXT[],
    access_token_hash VARCHAR(255) REFERENCES kg_auth.oauth_access_tokens(token_hash) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used TIMESTAMPTZ
);

CREATE INDEX idx_oauth_refresh_token_client ON kg_auth.oauth_refresh_tokens(client_id);
CREATE INDEX idx_oauth_refresh_token_user ON kg_auth.oauth_refresh_tokens(user_id);
CREATE INDEX idx_oauth_refresh_token_expires ON kg_auth.oauth_refresh_tokens(expires_at);

COMMENT ON TABLE kg_auth.oauth_refresh_tokens IS 'Long-lived refresh tokens for obtaining new access tokens';
```

### Renaming Existing Table

```sql
-- Rename to clarify purpose (stores external OAuth tokens, not ours)
ALTER TABLE kg_auth.oauth_tokens RENAME TO oauth_external_provider_tokens;

COMMENT ON TABLE kg_auth.oauth_external_provider_tokens IS 'OAuth tokens FROM external providers (Google, GitHub, etc.) - not tokens issued by our system';
```

---

## API Endpoints

### Client Registration (Admin Only)

#### `POST /auth/oauth/clients` - Register new client
```json
{
  "client_name": "Knowledge Graph Visualizer",
  "client_type": "public",
  "grant_types": ["authorization_code", "refresh_token"],
  "redirect_uris": ["https://viz.example.com/callback", "http://localhost:3000/callback"],
  "scopes": ["read:concepts", "write:concepts", "read:vocabulary"]
}
```

**Response:**
```json
{
  "client_id": "kg_client_viz_a1b2c3d4e5",
  "client_secret": null,  // Public client has no secret
  "client_name": "Knowledge Graph Visualizer",
  "client_type": "public",
  "grant_types": ["authorization_code", "refresh_token"],
  "redirect_uris": ["https://viz.example.com/callback", "http://localhost:3000/callback"],
  "scopes": ["read:concepts", "write:concepts", "read:vocabulary"],
  "created_at": "2025-11-01T12:00:00Z"
}
```

#### `POST /auth/oauth/clients` - Register confidential client (MCP server)
```json
{
  "client_name": "MCP Server - Production",
  "client_type": "confidential",
  "grant_types": ["client_credentials"],
  "scopes": ["read:concepts", "write:ingest"]
}
```

**Response:**
```json
{
  "client_id": "kg_client_mcp_prod_x9y8z7",
  "client_secret": "kg_secret_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",  // ⚠️ Show only once!
  "client_name": "MCP Server - Production",
  "client_type": "confidential",
  "grant_types": ["client_credentials"],
  "scopes": ["read:concepts", "write:ingest"],
  "created_at": "2025-11-01T12:00:00Z"
}
```

#### `GET /auth/oauth/clients` - List registered clients (Admin)
#### `GET /auth/oauth/clients/{client_id}` - Get client details
#### `PATCH /auth/oauth/clients/{client_id}` - Update client (scopes, URIs, etc.)
#### `DELETE /auth/oauth/clients/{client_id}` - Revoke client registration

### Authorization Endpoints

#### `GET /auth/oauth/authorize` - Authorization endpoint (web flow)
```
GET /auth/oauth/authorize?
    response_type=code
    &client_id=kg_client_viz_a1b2c3d4e5
    &redirect_uri=https://viz.example.com/callback
    &scope=read:concepts write:concepts
    &state=xyz123
    &code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM
    &code_challenge_method=S256
```

**Response (redirect):**
```
HTTP/1.1 302 Found
Location: https://viz.example.com/callback?code=authz_code_abc123&state=xyz123
```

#### `POST /auth/oauth/device` - Device authorization request (CLI flow)
```json
{
  "client_id": "kg_client_cli",
  "scope": "read:concepts write:ingest"
}
```

**Response:**
```json
{
  "device_code": "dev_a1b2c3d4e5f6g7h8",
  "user_code": "ABCD-1234",
  "verification_uri": "https://api.example.com/device",
  "verification_uri_complete": "https://api.example.com/device?user_code=ABCD-1234",
  "expires_in": 600,
  "interval": 5
}
```

#### `POST /auth/oauth/token` - Token endpoint (all flows)

**Authorization Code Flow:**
```json
{
  "grant_type": "authorization_code",
  "code": "authz_code_abc123",
  "client_id": "kg_client_viz_a1b2c3d4e5",
  "redirect_uri": "https://viz.example.com/callback",
  "code_verifier": "<PKCE verifier>"
}
```

**Device Code Flow:**
```json
{
  "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
  "device_code": "dev_a1b2c3d4e5f6g7h8",
  "client_id": "kg_client_cli"
}
```

**Client Credentials Flow:**
```json
{
  "grant_type": "client_credentials",
  "client_id": "kg_client_mcp_prod_x9y8z7",
  "client_secret": "kg_secret_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6",
  "scope": "read:concepts write:ingest"
}
```

**Refresh Token Flow:**
```json
{
  "grant_type": "refresh_token",
  "refresh_token": "refresh_xyz789",
  "client_id": "kg_client_viz_a1b2c3d4e5"
}
```

**Response (success):**
```json
{
  "access_token": "kg_access_a1b2c3d4e5f6g7h8",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "kg_refresh_x9y8z7w6v5u4",  // Not included for client_credentials
  "scope": "read:concepts write:concepts"
}
```

#### `POST /auth/oauth/revoke` - Revoke token
```json
{
  "token": "kg_access_a1b2c3d4e5f6g7h8",
  "token_type_hint": "access_token",  // or "refresh_token"
  "client_id": "kg_client_viz_a1b2c3d4e5"
}
```

---

## Client Configuration

### Web App (viz-app)

**Config file (environment variables):**
```env
OAUTH_CLIENT_ID=kg_client_viz_a1b2c3d4e5
OAUTH_AUTHORIZATION_ENDPOINT=https://api.example.com/auth/oauth/authorize
OAUTH_TOKEN_ENDPOINT=https://api.example.com/auth/oauth/token
OAUTH_REDIRECT_URI=https://viz.example.com/callback
OAUTH_SCOPES=read:concepts write:concepts read:vocabulary
```

**Implementation (JavaScript/React):**
```javascript
import { AuthorizationCodeWithPKCE } from 'oauth4webapi';

const oauth = new AuthorizationCodeWithPKCE({
  clientId: process.env.OAUTH_CLIENT_ID,
  authorizationEndpoint: process.env.OAUTH_AUTHORIZATION_ENDPOINT,
  tokenEndpoint: process.env.OAUTH_TOKEN_ENDPOINT,
  redirectUri: process.env.OAUTH_REDIRECT_URI,
  scopes: process.env.OAUTH_SCOPES.split(' ')
});

// Login button handler
async function handleLogin() {
  const { url, codeVerifier } = await oauth.createAuthorizationURL();
  sessionStorage.setItem('codeVerifier', codeVerifier);
  window.location.href = url;
}

// Callback handler
async function handleCallback(code, state) {
  const codeVerifier = sessionStorage.getItem('codeVerifier');
  const tokens = await oauth.exchangeAuthorizationCode(code, codeVerifier);
  localStorage.setItem('access_token', tokens.access_token);
  localStorage.setItem('refresh_token', tokens.refresh_token);
}
```

### CLI (kg)

**Config file (`~/.config/kg/config.json`):**
```json
{
  "oauth": {
    "client_id": "kg_client_cli",
    "device_authorization_endpoint": "https://api.example.com/auth/oauth/device",
    "token_endpoint": "https://api.example.com/auth/oauth/token"
  },
  "tokens": {
    "access_token": "kg_access_...",
    "refresh_token": "kg_refresh_...",
    "expires_at": 1730462400
  }
}
```

**Implementation (TypeScript):**
```typescript
// src/lib/auth/device-flow.ts
export class DeviceAuthFlow {
  async login(): Promise<TokenInfo> {
    // 1. Request device code
    const deviceResponse = await axios.post('/auth/oauth/device', {
      client_id: this.clientId,
      scope: 'read:concepts write:ingest'
    });

    // 2. Display user instructions
    console.log(`Visit: ${deviceResponse.verification_uri}`);
    console.log(`Enter code: ${deviceResponse.user_code}`);
    console.log('Waiting for authorization...');

    // 3. Poll token endpoint
    return await this.pollForToken(deviceResponse.device_code, deviceResponse.interval);
  }

  private async pollForToken(deviceCode: string, interval: number): Promise<TokenInfo> {
    while (true) {
      await new Promise(resolve => setTimeout(resolve, interval * 1000));

      try {
        const tokenResponse = await axios.post('/auth/oauth/token', {
          grant_type: 'urn:ietf:params:oauth:grant-type:device_code',
          device_code: deviceCode,
          client_id: this.clientId
        });

        return tokenResponse.data;
      } catch (error) {
        if (error.response?.data?.error === 'authorization_pending') {
          continue;  // Keep polling
        }
        throw error;  // Other errors (expired, denied, etc.)
      }
    }
  }
}
```

### MCP Server

**Config file (`.env` or secure vault):**
```env
OAUTH_CLIENT_ID=kg_client_mcp_prod_x9y8z7
OAUTH_CLIENT_SECRET=kg_secret_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
OAUTH_TOKEN_ENDPOINT=https://api.example.com/auth/oauth/token
OAUTH_SCOPES=read:concepts write:ingest
```

**Implementation (TypeScript):**
```typescript
// src/mcp/auth/client-credentials.ts
export class ClientCredentialsAuth {
  private accessToken: string | null = null;
  private expiresAt: number = 0;

  async getAccessToken(): Promise<string> {
    if (this.accessToken && Date.now() < this.expiresAt) {
      return this.accessToken;  // Use cached token
    }

    // Authenticate with client credentials
    const response = await axios.post('/auth/oauth/token', {
      grant_type: 'client_credentials',
      client_id: process.env.OAUTH_CLIENT_ID,
      client_secret: process.env.OAUTH_CLIENT_SECRET,
      scope: process.env.OAUTH_SCOPES
    }, {
      auth: {
        username: process.env.OAUTH_CLIENT_ID,
        password: process.env.OAUTH_CLIENT_SECRET
      }
    });

    this.accessToken = response.data.access_token;
    this.expiresAt = Date.now() + (response.data.expires_in * 1000);

    return this.accessToken;
  }
}
```

---

## Migration Strategy

### Phase 1: OAuth Infrastructure (Foundation)

**Goal:** Add OAuth 2.0 support alongside existing JWT/API key systems

**Implementation:**
1. Create new database tables (oauth_clients, oauth_authorization_codes, etc.)
2. Implement token endpoint (`POST /auth/oauth/token`)
3. Implement authorization endpoint (`GET /auth/oauth/authorize`)
4. Implement device authorization endpoint (`POST /auth/oauth/device`)
5. Add client registration API (admin only)

**Backward Compatibility:**
- Existing JWT login (`POST /auth/login`) continues to work
- Existing API keys continue to work
- No breaking changes

**Testing:**
- Unit tests for token generation/validation
- Integration tests for each OAuth flow
- Manual testing with Postman/curl

### Phase 2: CLI Device Flow

**Goal:** Migrate `kg login` to use device authorization grant

**Implementation:**
1. Register CLI client: `kg_client_cli` (public client)
2. Update `kg login` command to use device flow
3. Store OAuth tokens in `~/.config/kg/config.json`
4. Add `kg logout` to revoke tokens

**User Experience:**
```bash
$ kg login
Visit: https://api.example.com/device
Enter code: ABCD-1234

Waiting for authorization... ⏳

✅ Logged in successfully!
   Username: admin
   Token expires: in 60 minutes
```

**Fallback:**
- Keep old JWT login as `kg login --legacy` for backward compatibility

### Phase 3: Web App Authorization Code Flow

**Goal:** Secure authentication for viz-app (no password exposure)

**Implementation:**
1. Register web client: `kg_client_viz` (public client with PKCE)
2. Implement OAuth library in viz-app (oauth4webapi or similar)
3. Add login/callback routes
4. Store tokens in browser storage (localStorage or httpOnly cookies)

**User Experience:**
1. User clicks "Login" in viz-app
2. Redirected to API `/auth/oauth/authorize`
3. Enters credentials (or already logged in via SSO)
4. Redirected back to viz-app with authorization code
5. viz-app exchanges code for tokens (backend)

### Phase 4: MCP Client Credentials

**Goal:** Secure machine-to-machine auth for MCP server

**Implementation:**
1. Register MCP client: `kg_client_mcp_prod` (confidential client)
2. Store client_id + secret in MCP server config
3. Implement token acquisition in MCP startup
4. Use token for all API requests

**User Experience (admin):**
```bash
$ kg admin oauth clients create \
    --name "MCP Server - Production" \
    --type confidential \
    --grant-types client_credentials \
    --scopes read:concepts,write:ingest

✅ Client created!
   Client ID: kg_client_mcp_prod_x9y8z7
   Client Secret: kg_secret_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6

   ⚠️ IMPORTANT: Save this secret now! You cannot retrieve it later.

   Add to MCP server .env:
     OAUTH_CLIENT_ID=kg_client_mcp_prod_x9y8z7
     OAUTH_CLIENT_SECRET=kg_secret_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

### Phase 5: Deprecate Legacy Auth

**Goal:** Eventually deprecate direct JWT/API key systems

**Timeline:**
- 6 months: OAuth fully supported, legacy still works
- 12 months: Legacy marked deprecated, warnings in docs
- 18 months: Legacy disabled by default, opt-in to enable
- 24 months: Legacy removed entirely

**Communication:**
- Announce OAuth support in release notes
- Update documentation to prefer OAuth
- Add deprecation warnings in API responses
- Provide migration guide

---

## Security Considerations

### Token Storage

| Client | Storage Method | Security |
|--------|---------------|----------|
| **Web App** | localStorage | ⚠️ Vulnerable to XSS attacks |
| **Web App** | httpOnly cookies | ✅ More secure, not accessible via JavaScript |
| **CLI** | `~/.config/kg/config.json` (chmod 600) | ✅ File permissions protect token |
| **MCP Server** | Environment variables or vault | ✅ Never logged, not in version control |

**Recommendations:**
- Web: Use httpOnly, Secure, SameSite cookies
- CLI: File permissions 600 (owner read/write only)
- MCP: Use secret management system (Vault, AWS Secrets Manager, etc.)

### Token Lifetime

| Token Type | Lifetime | Rationale |
|-----------|----------|-----------|
| **Authorization Code** | 10 minutes | Single-use, short-lived |
| **Device Code** | 10 minutes | User must act quickly |
| **Access Token** | 60 minutes | Balance security vs. UX |
| **Refresh Token** | 7 days (CLI), 30 days (web) | Long sessions without re-auth |
| **Client Credentials Token** | 1 hour | Machine-to-machine, can re-auth automatically |

### Client Secret Protection

**Confidential clients (MCP server):**
- Store in environment variables (never hardcode)
- Rotate secrets periodically (quarterly)
- Revoke immediately if compromised
- Use secret management systems in production

**Public clients (web app, CLI):**
- No client secret (can't be kept secret)
- Use PKCE to prevent code interception
- Still secure when combined with proper flows

### Revocation

**Token revocation strategies:**
1. **User logout:** Revoke refresh token → invalidates all access tokens
2. **Client compromise:** Revoke all tokens for client_id
3. **User account disabled:** Revoke all tokens for user_id
4. **Periodic cleanup:** Delete expired tokens (>30 days old)

**Database cleanup job:**
```sql
-- Run daily
DELETE FROM kg_auth.oauth_access_tokens
WHERE expires_at < NOW() - INTERVAL '30 days';

DELETE FROM kg_auth.oauth_refresh_tokens
WHERE expires_at < NOW() - INTERVAL '30 days';

DELETE FROM kg_auth.oauth_authorization_codes
WHERE expires_at < NOW() - INTERVAL '1 day';

DELETE FROM kg_auth.oauth_device_codes
WHERE expires_at < NOW() - INTERVAL '1 day';
```

---

## Advantages

### 1. Standard Protocol
- OAuth 2.0 is industry standard
- Well-understood security properties
- Many libraries available
- Easier to explain to developers

### 2. Client Identification
- Know which app/tool accessed the API
- Audit trail: "User X via CLI" vs. "User X via web app"
- Revoke access per client without affecting others

### 3. Appropriate Flows Per Client
- Web app: Secure redirect-based flow (no password exposure)
- CLI: User-friendly device flow
- MCP: Machine-to-machine with credentials

### 4. Token Management
- Refresh tokens for long-lived sessions
- Automatic token expiry and cleanup
- Per-client token revocation

### 5. Backward Compatible
- Existing JWT/API key systems continue to work
- Gradual migration path
- No breaking changes

---

## Disadvantages

### 1. Complexity
- More database tables (5 new tables)
- More API endpoints (6 new endpoints)
- More flows to implement and test
- Steeper learning curve for users

### 2. Implementation Effort
- Estimated 2-3 weeks of development
- Testing all flows thoroughly
- Documentation updates
- Client library updates

### 3. Token Proliferation
- More tokens to manage
- More database storage
- Cleanup jobs required
- Monitoring token usage

### 4. Migration Required
- Existing users must re-authenticate
- Update client applications
- Documentation and communication

---

## Alternatives Considered

### Alternative 1: Keep Current System (JWT + API Keys)

**Pros:**
- No changes needed
- Already works
- Simple

**Cons:**
- Web app would use password flow (insecure)
- No client identification
- No refresh tokens
- Not following standards

**Verdict:** ❌ Not suitable for web application

### Alternative 2: API Keys Only

**Pros:**
- Simple
- Already implemented
- Works for all clients

**Cons:**
- No user interaction flow
- No refresh mechanism
- Shared secrets (less secure)
- No audit trail per client

**Verdict:** ❌ Not suitable for interactive applications

### Alternative 3: External OAuth Provider (Auth0, Okta)

**Pros:**
- Professionally maintained
- Advanced features (MFA, SSO, etc.)
- Less implementation work

**Cons:**
- External dependency
- Cost ($$$)
- Less control
- Privacy concerns (user data with third party)

**Verdict:** ⚠️ Consider for enterprise deployments, but overkill for most users

### Alternative 4: Hybrid Approach (OAuth + Keep JWT/API Keys)

**Pros:**
- Best of both worlds
- Backward compatible
- Gradual migration
- Flexibility

**Cons:**
- More complex (two systems)
- Maintenance burden
- Confusing for users

**Verdict:** ✅ **RECOMMENDED** - This is what we're proposing

---

## Implementation Checklist

### Database Schema
- [ ] Create `kg_auth.oauth_clients` table
- [ ] Create `kg_auth.oauth_authorization_codes` table
- [ ] Create `kg_auth.oauth_device_codes` table
- [ ] Create `kg_auth.oauth_access_tokens` table
- [ ] Create `kg_auth.oauth_refresh_tokens` table
- [ ] Rename `kg_auth.oauth_tokens` → `oauth_external_provider_tokens`
- [ ] Add indexes for performance
- [ ] Add database constraints (foreign keys, unique, etc.)

### API Endpoints
- [ ] `POST /auth/oauth/clients` - Register client (admin)
- [ ] `GET /auth/oauth/clients` - List clients (admin)
- [ ] `GET /auth/oauth/clients/{id}` - Get client details
- [ ] `PATCH /auth/oauth/clients/{id}` - Update client
- [ ] `DELETE /auth/oauth/clients/{id}` - Delete client
- [ ] `GET /auth/oauth/authorize` - Authorization endpoint
- [ ] `POST /auth/oauth/device` - Device authorization endpoint
- [ ] `POST /auth/oauth/token` - Token endpoint (all grant types)
- [ ] `POST /auth/oauth/revoke` - Token revocation endpoint

### Implementation
- [ ] OAuth client model (Pydantic)
- [ ] OAuth token models (access, refresh, authz code, device code)
- [ ] Client registration logic
- [ ] Authorization code flow handler
- [ ] Device flow handler
- [ ] Client credentials flow handler
- [ ] Refresh token flow handler
- [ ] PKCE validation
- [ ] Token generation/validation
- [ ] Token revocation logic

### Client Libraries
- [ ] Update `KnowledgeGraphClient` to support OAuth
- [ ] Implement device flow for CLI (`DeviceAuthFlow` class)
- [ ] Implement client credentials for MCP (`ClientCredentialsAuth` class)
- [ ] Add token refresh logic
- [ ] Add token storage in config

### CLI Commands
- [ ] `kg admin oauth clients list` - List registered clients
- [ ] `kg admin oauth clients create` - Register new client
- [ ] `kg admin oauth clients show <id>` - Show client details
- [ ] `kg admin oauth clients update <id>` - Update client
- [ ] `kg admin oauth clients delete <id>` - Delete client
- [ ] `kg admin oauth clients rotate-secret <id>` - Rotate client secret
- [ ] `kg admin oauth tokens list` - List active tokens (admin)
- [ ] `kg admin oauth tokens revoke <token>` - Revoke token (admin)
- [ ] Update `kg login` to use device flow
- [ ] Update `kg logout` to revoke tokens

### Testing
- [ ] Unit tests for client registration
- [ ] Unit tests for each OAuth flow
- [ ] Unit tests for token generation/validation
- [ ] Integration tests for authorization code flow
- [ ] Integration tests for device flow
- [ ] Integration tests for client credentials flow
- [ ] Integration tests for refresh token flow
- [ ] Security tests (PKCE validation, secret hashing, etc.)

### Documentation
- [ ] ADR document for OAuth client management
- [ ] Update authentication guide with OAuth flows
- [ ] Add OAuth client registration guide
- [ ] Add web app integration guide
- [ ] Add CLI device flow guide
- [ ] Add MCP client credentials guide
- [ ] Update API reference documentation
- [ ] Create migration guide from JWT/API keys

### Monitoring & Maintenance
- [ ] Add metrics for token issuance
- [ ] Add metrics for token validation failures
- [ ] Add alerts for high token rejection rate
- [ ] Implement token cleanup job (cron)
- [ ] Add audit logging for client registration
- [ ] Add audit logging for token revocation

---

## Recommendation

**Proceed with OAuth 2.0 client management implementation.**

**Rationale:**
1. **Web app security:** Authorization code flow with PKCE is the standard for securing web applications
2. **CLI user experience:** Device flow provides user-friendly authentication without browser redirect
3. **MCP machine-to-machine:** Client credentials flow is designed for background services
4. **Backward compatible:** Hybrid approach maintains existing JWT/API key systems
5. **Industry standard:** OAuth 2.0 is well-understood, documented, and supported

**Recommended phasing:**
- **Phase 1 (Now):** OAuth infrastructure + client registration API
- **Phase 2 (Next sprint):** CLI device flow
- **Phase 3 (Following sprint):** Web app authorization code flow
- **Phase 4 (After web app launch):** MCP client credentials
- **Phase 5 (6-12 months):** Deprecate legacy auth (JWT/API keys)

---

## References

**OAuth 2.0 Specifications:**
- RFC 6749: OAuth 2.0 Authorization Framework
- RFC 7636: Proof Key for Code Exchange (PKCE)
- RFC 8628: OAuth 2.0 Device Authorization Grant
- RFC 7009: OAuth 2.0 Token Revocation

**Related ADRs:**
- ADR-027: User Management API (JWT authentication)
- ADR-028: Dynamic RBAC System (permissions)
- ADR-024: PostgreSQL Multi-Schema Architecture (api keys)

**Implementation Resources:**
- https://oauth.net/2/
- https://www.oauth.com/
- https://auth0.com/docs/authenticate/protocols/oauth
- https://github.com/panva/oauth4webapi (JavaScript OAuth library)

---

**Last Updated:** 2025-11-01
**Author:** Knowledge Graph Team
**Status:** Proposal - Awaiting Review
