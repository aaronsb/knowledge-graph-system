# CLI Authentication Architecture

## Overview

This document describes the TypeScript authentication architecture for the `kg` CLI client, designed to integrate with the FastAPI authentication system (ADR-027). The architecture prioritizes **reusability** - modules built for the CLI will be reused in the MCP server and future web client.

## Design Principles

1. **Modular Architecture**: Separate concerns into reusable TypeScript modules
2. **Security First**: No plaintext password storage, secure token management, challenge flow for sensitive operations
3. **User Experience**: Remember username, persistent token storage, graceful token expiration handling
4. **Multi-Client Support**: Designed for CLI, MCP server, and future web client
5. **Backwards Compatibility**: Existing API key authentication (ADR-024 Phase 1) continues to work

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLI Commands Layer                            │
│  kg login, kg logout, kg admin user [list|create|update|delete]    │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────────────┐
│                   Auth Client Layer                                  │
│  AuthClient: login(), logout(), validateToken(), refreshToken()    │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────────────┐
│                 Token Manager Layer                                  │
│  TokenManager: store(), retrieve(), validate(), clear()            │
└─────────────────┬───────────────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────────────┐
│                  Config Storage Layer                                │
│  ConfigManager: Extended with auth token storage                   │
└──────────────────────────────────────────────────────────────────────┘
```

## Module Specifications

### 1. Token Manager (`client/src/lib/auth/token-manager.ts`)

**Purpose**: Manage JWT token lifecycle (storage, retrieval, validation, expiration)

**Interface**:
```typescript
export interface TokenInfo {
  access_token: string;
  token_type: string;
  expires_at: number;  // Unix timestamp
  username: string;
  role: string;
}

export class TokenManager {
  constructor(private config: ConfigManager);

  // Store JWT token with metadata
  storeToken(tokenInfo: TokenInfo): void;

  // Retrieve stored token (returns null if expired or not found)
  getToken(): TokenInfo | null;

  // Check if token is expired (with 5-minute buffer)
  isTokenExpired(tokenInfo: TokenInfo): boolean;

  // Clear stored token (logout)
  clearToken(): void;

  // Check if user is logged in (valid token exists)
  isLoggedIn(): boolean;

  // Get current username from token
  getUsername(): string | null;

  // Get current user role from token
  getRole(): string | null;
}
```

**Storage Strategy**:
- Store token in `~/.config/kg/config.json` as `auth.token`
- Store expiration timestamp (not just duration) for accurate validation
- Store username and role for quick access without decoding JWT
- NEVER store passwords (only tokens)

**Token Format in Config**:
```json
{
  "auth": {
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_at": 1760230000,
    "username": "admin",
    "role": "admin"
  },
  "username": "admin",
  "api_url": "http://localhost:8000"
}
```

**Token Expiration Handling**:
- JWT tokens expire after 60 minutes (configurable on server)
- Client checks expiration with 5-minute buffer (55 minutes)
- If expired, prompt user to re-login
- Future: Implement refresh tokens

### 2. Auth Client (`client/src/lib/auth/auth-client.ts`)

**Purpose**: HTTP client for authentication endpoints (wraps REST API calls)

**Interface**:
```typescript
export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;  // Seconds
  user: {
    id: number;
    username: string;
    role: string;
    disabled: boolean;
  };
}

export interface UserCreateRequest {
  username: string;
  password: string;
  role: 'read_only' | 'contributor' | 'curator' | 'admin';
}

export interface UserUpdateRequest {
  role?: 'read_only' | 'contributor' | 'curator' | 'admin';
  password?: string;
  disabled?: boolean;
}

export interface UserResponse {
  id: number;
  username: string;
  role: string;
  created_at: string;
  last_login: string | null;
  disabled: boolean;
}

export interface APIKeyCreateRequest {
  name: string;
  scopes?: string[];
  expires_at?: string;
}

export interface APIKeyResponse {
  id: number;
  name: string;
  key_prefix: string;
  scopes: string[];
  created_at: string;
  last_used: string | null;
  expires_at: string | null;
  key?: string;  // Only present on creation!
}

export class AuthClient {
  constructor(private baseUrl: string);

  // Login with username/password (OAuth2 password flow)
  async login(request: LoginRequest): Promise<LoginResponse>;

  // Validate current token (calls /auth/me)
  async validateToken(token: string): Promise<UserResponse>;

  // Admin: List users
  async listUsers(token: string, skip?: number, limit?: number, role?: string): Promise<{
    users: UserResponse[];
    total: number;
    skip: number;
    limit: number;
  }>;

  // Admin: Get user by ID
  async getUser(token: string, userId: number): Promise<UserResponse>;

  // Admin: Create user
  async createUser(token: string, request: UserCreateRequest): Promise<UserResponse>;

  // Admin: Update user
  async updateUser(token: string, userId: number, request: UserUpdateRequest): Promise<UserResponse>;

  // Admin: Delete user
  async deleteUser(token: string, userId: number): Promise<void>;

  // Create API key for current user
  async createAPIKey(token: string, request: APIKeyCreateRequest): Promise<APIKeyResponse>;

  // List API keys for current user
  async listAPIKeys(token: string): Promise<APIKeyResponse[]>;

  // Revoke API key
  async revokeAPIKey(token: string, keyId: number): Promise<void>;
}
```

**Error Handling**:
- 401 Unauthorized: Token expired or invalid → Prompt re-login
- 403 Forbidden: Insufficient permissions → Show role requirement
- 400 Bad Request: Validation error → Show error message
- Network errors: Retry with backoff, show connection error

### 3. Config Manager Extensions (`client/src/lib/config.ts`)

**Purpose**: Extend existing `ConfigManager` with authentication token storage

**New Methods**:
```typescript
// Add to existing ConfigManager class

/**
 * Store authentication token
 */
storeAuthToken(tokenInfo: TokenInfo): void {
  this.set('auth.token', tokenInfo.access_token);
  this.set('auth.token_type', tokenInfo.token_type);
  this.set('auth.expires_at', tokenInfo.expires_at);
  this.set('auth.username', tokenInfo.username);
  this.set('auth.role', tokenInfo.role);

  // Also update top-level username for backwards compatibility
  this.set('username', tokenInfo.username);
}

/**
 * Retrieve authentication token
 */
getAuthToken(): TokenInfo | null {
  const token = this.get('auth.token');
  if (!token) return null;

  return {
    access_token: token,
    token_type: this.get('auth.token_type') || 'bearer',
    expires_at: this.get('auth.expires_at') || 0,
    username: this.get('auth.username') || '',
    role: this.get('auth.role') || ''
  };
}

/**
 * Clear authentication token
 */
clearAuthToken(): void {
  this.delete('auth');
}

/**
 * Check if user is authenticated
 */
isAuthenticated(): boolean {
  const tokenInfo = this.getAuthToken();
  if (!tokenInfo) return false;

  const now = Math.floor(Date.now() / 1000);
  return tokenInfo.expires_at > now + 300;  // 5-minute buffer
}
```

**Config Schema**:
```typescript
export interface KgConfig {
  username?: string;
  secret?: string;  // API key (legacy, still supported)
  api_url?: string;
  backup_dir?: string;
  auto_approve?: boolean;
  auth?: {
    token?: string;
    token_type?: string;
    expires_at?: number;
    username?: string;
    role?: string;
  };
  mcp?: McpConfig;
}
```

### 4. Challenge Flow Module (`client/src/lib/auth/challenge.ts`)

**Purpose**: Re-authentication prompt for sensitive operations

**Interface**:
```typescript
export interface ChallengeOptions {
  reason: string;  // Why re-auth is required
  username?: string;  // Pre-fill username
  allowCancel?: boolean;  // Allow user to cancel
}

export class AuthChallenge {
  constructor(private authClient: AuthClient, private tokenManager: TokenManager);

  /**
   * Prompt user to re-authenticate for sensitive operation
   * Returns new token on success, null on cancel
   */
  async challenge(options: ChallengeOptions): Promise<TokenInfo | null>;
}
```

**Usage Example**:
```typescript
// Before deleting user or resetting database
const challenge = new AuthChallenge(authClient, tokenManager);
const newToken = await challenge.challenge({
  reason: 'Delete user account',
  username: tokenManager.getUsername() || undefined,
  allowCancel: true
});

if (!newToken) {
  console.log('Operation cancelled');
  return;
}

// Proceed with sensitive operation using newToken
await authClient.deleteUser(newToken.access_token, userId);
```

**Challenge Triggers**:
- `kg admin user delete` - Deleting users
- `kg admin reset` - Resetting database
- `kg admin user update --role admin` - Promoting to admin
- Future: Any operation modifying authentication settings

### 5. KnowledgeGraphClient Extensions (`client/src/api/client.ts`)

**Purpose**: Integrate authentication into existing API client

**Changes Required**:
```typescript
export class KnowledgeGraphClient {
  private client: AxiosInstance;
  private config: ApiConfig;
  private tokenManager?: TokenManager;  // NEW

  constructor(config: ApiConfig, tokenManager?: TokenManager) {  // MODIFIED
    this.config = config;
    this.tokenManager = tokenManager;

    this.client = axios.create({
      baseURL: config.baseUrl,
      headers: {
        ...(config.clientId && { 'X-Client-ID': config.clientId }),
        ...(config.apiKey && { 'X-API-Key': config.apiKey }),
      },
    });

    // NEW: Add request interceptor for JWT token
    this.client.interceptors.request.use((config) => {
      if (this.tokenManager) {
        const tokenInfo = this.tokenManager.getToken();
        if (tokenInfo) {
          config.headers.Authorization = `Bearer ${tokenInfo.access_token}`;
        }
      }
      return config;
    });

    // NEW: Add response interceptor for 401 errors
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401 && this.tokenManager) {
          console.error('Authentication expired. Please run: kg login');
          process.exit(1);
        }
        return Promise.reject(error);
      }
    );
  }

  // All existing methods remain unchanged
  // Authentication header is added automatically by interceptor
}
```

**Token Priority**:
1. JWT token (if logged in via `kg login`)
2. API key (if configured via `kg config set secret <key>`)
3. None (unauthenticated - some endpoints allow this)

## CLI Commands

### `kg login`

**Purpose**: Authenticate with username/password and store JWT token

**Usage**:
```bash
kg login [username]
kg login --username admin
kg login -u admin
```

**Flow**:
1. Prompt for username (if not provided)
2. Prompt for password (hidden input)
3. Call `/auth/login` endpoint (OAuth2 password flow)
4. Store JWT token in config
5. Display success message with expiration time
6. Show user role and permissions

**Example Output**:
```
$ kg login
Username: admin
Password: ********

✅ Logged in successfully!
   Username: admin
   Role: admin
   Token expires: 2025-10-11 15:30:00 (in 60 minutes)

Run 'kg logout' to end your session.
```

**Error Handling**:
- Invalid credentials: Show error, allow retry (3 attempts)
- Network error: Show connection error
- Server error: Show error message

### `kg logout`

**Purpose**: Clear stored JWT token (end session)

**Usage**:
```bash
kg logout
```

**Flow**:
1. Clear token from config
2. Display success message

**Example Output**:
```
$ kg logout
✅ Logged out successfully!
```

### `kg admin user list`

**Purpose**: List all users (admin only)

**Usage**:
```bash
kg admin user list
kg admin user list --role admin
kg admin user list --skip 10 --limit 20
```

**Options**:
- `--role <role>`: Filter by role (read_only, contributor, curator, admin)
- `--skip <n>`: Skip first N users (pagination)
- `--limit <n>`: Limit results (default: 50)

**Example Output**:
```
$ kg admin user list
┌────┬──────────────┬─────────────┬─────────────────────┬──────────────────────┬──────────┐
│ ID │ Username     │ Role        │ Created             │ Last Login           │ Status   │
├────┼──────────────┼─────────────┼─────────────────────┼──────────────────────┼──────────┤
│ 1  │ admin        │ admin       │ 2025-10-11 10:00:00 │ 2025-10-11 14:30:00  │ Active   │
│ 2  │ curator1     │ curator     │ 2025-10-11 10:15:00 │ 2025-10-11 12:00:00  │ Active   │
│ 3  │ contributor1 │ contributor │ 2025-10-11 10:20:00 │ Never                │ Disabled │
└────┴──────────────┴─────────────┴─────────────────────┴──────────────────────┴──────────┘

Total: 3 users
```

### `kg admin user create`

**Purpose**: Create new user (admin only)

**Usage**:
```bash
kg admin user create <username> --role <role>
kg admin user create testuser --role contributor
```

**Options**:
- `--role <role>`: User role (required: read_only, contributor, curator, admin)

**Flow**:
1. Validate username (3-100 chars)
2. Prompt for password (hidden input, with confirmation)
3. Validate password strength (8+ chars, mixed case, digit, special)
4. Call `/auth/register` endpoint
5. Display success message

**Example Output**:
```
$ kg admin user create testuser --role contributor
Password: ********
Confirm password: ********

✅ User created successfully!
   ID: 4
   Username: testuser
   Role: contributor
   Created: 2025-10-11 14:35:00
```

### `kg admin user update`

**Purpose**: Update user role, password, or disabled status (admin only)

**Usage**:
```bash
kg admin user update <user_id> --role <role>
kg admin user update <user_id> --password
kg admin user update <user_id> --disable
kg admin user update <user_id> --enable
```

**Options**:
- `--role <role>`: Change user role
- `--password`: Change password (prompts for new password)
- `--disable`: Disable user account
- `--enable`: Enable user account

**Challenge Flow**:
- If promoting to admin: Requires password re-entry
- Otherwise: Uses existing token

**Example Output**:
```
$ kg admin user update 4 --role curator

✅ User updated successfully!
   ID: 4
   Username: testuser
   Role: curator (changed from contributor)
```

### `kg admin user delete`

**Purpose**: Delete user (admin only, cannot delete self)

**Usage**:
```bash
kg admin user delete <user_id>
kg admin user delete <user_id> --yes
```

**Options**:
- `--yes`: Skip confirmation prompt

**Challenge Flow**:
- Always requires password re-entry (sensitive operation)
- Confirms username before deletion

**Example Output**:
```
$ kg admin user delete 4

⚠️  This will permanently delete user: testuser (ID: 4)
    This action cannot be undone!

Please re-enter your password to confirm:
Password: ********

✅ User deleted successfully!
   Username: testuser
   ID: 4
```

### `kg admin user apikey`

**Purpose**: Manage API keys for current user or other users (admin)

**Subcommands**:
- `kg admin user apikey create --name <name>` - Create API key
- `kg admin user apikey list` - List API keys
- `kg admin user apikey revoke <key_id>` - Revoke API key

**Example Output**:
```
$ kg admin user apikey create --name "CI Pipeline"

✅ API key created successfully!
   Name: CI Pipeline
   Key: kg_sk_a3f8d92c1e4b5f6a7d8e9c0b1a2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d

   ⚠️  IMPORTANT: This key will only be shown once!
      Store it securely. You cannot retrieve it later.

   Use this key in your API calls:
     curl -H "Authorization: Bearer kg_sk_..." http://localhost:8000/...
```

## Authentication Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                            Initial State                                  │
│  User has no token, wants to use authenticated endpoints                 │
└────────────────────────────────┬─────────────────────────────────────────┘
                                 │
                                 ▼
                        ┌────────────────┐
                        │   kg login     │
                        └────────┬───────┘
                                 │
                  ┌──────────────▼──────────────┐
                  │ Prompt username/password    │
                  └──────────────┬──────────────┘
                                 │
                  ┌──────────────▼──────────────────────┐
                  │ POST /auth/login (OAuth2 password)  │
                  │ Returns: JWT + user details         │
                  └──────────────┬──────────────────────┘
                                 │
                  ┌──────────────▼──────────────────────┐
                  │ TokenManager.storeToken()           │
                  │ - Saves JWT to config               │
                  │ - Calculates expiration timestamp   │
                  │ - Stores username/role              │
                  └──────────────┬──────────────────────┘
                                 │
                  ┌──────────────▼──────────────────────┐
                  │ Display success message             │
                  │ Show expiration time                │
                  └──────────────┬──────────────────────┘
                                 │
┌────────────────────────────────▼──────────────────────────────────────────┐
│                       Authenticated State                                  │
│  User can call authenticated endpoints for 60 minutes                     │
└────────────────────────────────┬──────────────────────────────────────────┘
                                 │
           ┌─────────────────────┼─────────────────────┐
           │                     │                     │
           ▼                     ▼                     ▼
  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐
  │ kg admin user  │   │  kg ingest     │   │   kg search    │
  │    list        │   │     file       │   │     query      │
  └────────┬───────┘   └────────┬───────┘   └────────┬───────┘
           │                     │                     │
           └─────────────────────┼─────────────────────┘
                                 │
           ┌─────────────────────▼──────────────────────┐
           │ KnowledgeGraphClient.interceptor           │
           │ - Reads token from TokenManager            │
           │ - Adds: Authorization: Bearer <token>      │
           └─────────────────────┬──────────────────────┘
                                 │
           ┌─────────────────────▼──────────────────────┐
           │ API Request with JWT token                 │
           │ - Server validates token                   │
           │ - Server checks role permissions           │
           └─────────────────────┬──────────────────────┘
                                 │
                    ┌────────────┴────────────┐
                    │                         │
                    ▼                         ▼
          ┌──────────────────┐      ┌──────────────────┐
          │   200 OK         │      │   401/403 Error  │
          │   Success        │      │   Auth Failed    │
          └──────────────────┘      └────────┬─────────┘
                                              │
                                              ▼
                                    ┌──────────────────┐
                                    │ Prompt re-login  │
                                    │ kg login         │
                                    └──────────────────┘
```

## Token Expiration Handling

### Automatic Detection
- Client checks token expiration before every request (5-minute buffer)
- If expired: Show friendly error message

### User Experience
```
$ kg admin user list
❌ Authentication expired!

Your session expired 5 minutes ago. Please login again:
  kg login

Tip: JWT tokens expire after 60 minutes for security.
```

### Future: Refresh Tokens
- Phase 2: Implement refresh token flow (ADR-027 Phase 3)
- Long-lived refresh tokens (7 days)
- Automatic token refresh without re-entering password
- Stored separately from access token

## Security Considerations

### What We Store
- ✅ JWT access token (expires in 60 minutes)
- ✅ Token expiration timestamp
- ✅ Username (for display/convenience)
- ✅ User role (for display/client-side checks)

### What We DON'T Store
- ❌ Password (NEVER stored)
- ❌ Password hash (server-only)
- ❌ Refresh tokens (Phase 2)

### File Permissions
- Config file: `chmod 600 ~/.config/kg/config.json` (owner read/write only)
- Created automatically by ConfigManager on first write

### Token Security
- Tokens expire after 60 minutes (server-controlled)
- Client validates expiration before use
- Invalid tokens are rejected by server (401 Unauthorized)
- Token stored in local config file (not environment variable)

### Password Input
- Always use hidden input (no echo)
- Clear password from memory after use
- Confirm password on user creation

## Migration Strategy

### Backwards Compatibility
1. **Existing API keys continue to work** (ADR-024 Phase 1)
   - Stored in `config.secret`
   - Sent as `X-API-Key` header
   - Independent from JWT authentication

2. **Optional authentication** (Phase 1)
   - Endpoints remain unauthenticated by default
   - Admin endpoints require authentication
   - Future: Gradually enable auth on other endpoints

3. **Graceful degradation**
   - If token expired: Prompt login
   - If login fails: Show error, don't crash
   - If no token: Allow unauthenticated endpoints

### Migration Path for Users
1. **No action required** for basic operations (search, query)
2. **Run `kg login`** to access admin endpoints
3. **Optional**: Create API keys for programmatic access

## Testing Strategy

### Unit Tests
- `TokenManager`: Storage, retrieval, expiration validation
- `AuthClient`: HTTP calls, error handling, response parsing
- `ConfigManager`: Token storage, retrieval, clearing

### Integration Tests
- Full login flow (username → password → token → storage)
- Token expiration detection
- Challenge flow (re-authentication)
- Admin operations (list, create, update, delete users)

### Manual Testing
1. Login with valid credentials
2. Login with invalid credentials
3. Use admin commands with valid token
4. Use admin commands with expired token
5. Logout and verify token cleared
6. Challenge flow for sensitive operations

## Implementation Checklist

- [ ] Create `client/src/lib/auth/token-manager.ts`
- [ ] Create `client/src/lib/auth/auth-client.ts`
- [ ] Create `client/src/lib/auth/challenge.ts`
- [ ] Extend `client/src/lib/config.ts` with auth methods
- [ ] Update `client/src/api/client.ts` with interceptors
- [ ] Create `client/src/cli/login.ts` (kg login command)
- [ ] Create `client/src/cli/logout.ts` (kg logout command)
- [ ] Create `client/src/cli/admin-user.ts` (kg admin user commands)
- [ ] Update `client/src/cli/commands.ts` to register new commands
- [ ] Update `client/src/types/index.ts` with auth types
- [ ] Create unit tests for TokenManager
- [ ] Create unit tests for AuthClient
- [ ] Create integration tests for full flow
- [ ] Update CLI help documentation
- [ ] Update `docs/guides/AUTHENTICATION.md` with CLI examples

## Future Enhancements

### Phase 2: Refresh Tokens
- Long-lived refresh tokens (7 days)
- Automatic token refresh without password
- Separate storage from access token

### Phase 3: MCP Server Integration
- Reuse `TokenManager`, `AuthClient`, `AuthChallenge` modules
- MCP server shares config file with CLI
- Claude Desktop prompts for credentials via MCP dialog

### Phase 4: Web Client Integration
- Browser localStorage for token storage
- HTTP-only cookies for enhanced security
- OAuth2 authorization code flow (not password flow)

## References

- ADR-027: User Management API (server-side authentication)
- ADR-024: PostgreSQL Multi-Schema Architecture (Phase 1 API keys)
- `docs/guides/AUTHENTICATION.md` - Server-side authentication guide
- OAuth2 RFC 6749: https://tools.ietf.org/html/rfc6749
- JWT RFC 7519: https://tools.ietf.org/html/rfc7519
