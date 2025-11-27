# CLI Development Guide

**Purpose:** Guide for developers working on the `kg` TypeScript CLI client

**Related ADRs:**
- [ADR-027: User Management API](../architecture/ADR-027-user-management-api.md) - Server-side authentication
- [ADR-029: CLI Theory of Operation](../architecture/ADR-029-cli-theory-of-operation.md) - Command structure
- [ADR-031: Encrypted API Key Storage](../architecture/ADR-031-encrypted-api-key-storage.md) - API key management
- [ADR-054: OAuth Client Management](../architecture/ADR-054-oauth-client-management.md) - OAuth flows

---

## Design Principles

1. **Modular Architecture**: Separate concerns into reusable TypeScript modules
2. **Security First**: No plaintext password storage, secure token management
3. **User Experience**: Remember username, persistent token storage, graceful error handling
4. **Multi-Client Support**: Modules designed for CLI, MCP server, and future clients
5. **Backwards Compatibility**: Existing API key authentication continues to work

---

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI Commands Layer                       │
│  kg login, kg logout, kg admin user [commands]              │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   Auth Client Layer                          │
│  AuthClient: login(), logout(), validateToken()            │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                  Token Manager Layer                         │
│  TokenManager: store(), retrieve(), validate(), clear()    │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                 Config Storage Layer                         │
│  ConfigManager: Auth token storage (~/.config/kg/)         │
└─────────────────────────────────────────────────────────────┘
```

**Key modules:**
- `client/src/lib/auth/token-manager.ts` - JWT token lifecycle
- `client/src/lib/auth/auth-client.ts` - HTTP client for auth endpoints
- `client/src/lib/auth/challenge.ts` - Re-auth prompt for sensitive ops
- `client/src/lib/config.ts` - Config file management (extended for auth)
- `client/src/api/client.ts` - Main API client (with auth interceptors)

---

## Authentication Flow

### Login Flow

```
1. User runs: kg login
2. Prompt for username (remember from last login)
3. Prompt for password (hidden input, not stored)
4. POST /auth/login with credentials
5. Receive JWT token + user info
6. Store token in ~/.config/kg/config.json
7. Store expiration timestamp (not just duration)
8. Store username + role for quick access
```

### Token Usage

```
1. User runs any command: kg search query "concept"
2. TokenManager checks for valid token
3. If expired → prompt re-login
4. If valid → add to request: Authorization: Bearer <token>
5. API validates token → returns data
6. If 401 → token expired, prompt re-login
```

### Challenge Flow (Sensitive Operations)

For destructive operations (delete user, reset database):

```
1. User runs: kg admin user delete <id>
2. System prompts: "This is a sensitive operation. Re-enter password:"
3. Pre-fill username, prompt password only
4. Validate credentials → get fresh token
5. Execute operation with fresh token
6. Discard fresh token (keep original session)
```

---

## Token Storage Format

**Location:** `~/.config/kg/config.json`

```json
{
  "auth": {
    "token": "eyJhbGciOiJIUzI1NiIs...",
    "token_type": "bearer",
    "expires_at": 1760230000,
    "username": "admin",
    "role": "admin"
  },
  "username": "admin",
  "api_url": "http://localhost:8000"
}
```

**Key points:**
- Store **expiration timestamp** (Unix timestamp), not duration
- Store **username** and **role** for quick access (avoid JWT decode)
- NEVER store passwords
- Backwards compatible with `secret` (API key) field

---

## Adding Authentication to Commands

### Pattern 1: Protected Command (Requires Auth)

```typescript
import { TokenManager } from '../lib/auth/token-manager';
import { KnowledgeGraphClient } from '../api/client';

async function myCommand() {
  const config = ConfigManager.load();
  const tokenManager = new TokenManager(config);

  // Check authentication
  if (!tokenManager.isLoggedIn()) {
    console.error('Not logged in. Run: kg login');
    process.exit(1);
  }

  // Create client with token
  const client = new KnowledgeGraphClient(config, tokenManager);

  // Make API call (token added automatically)
  const result = await client.myApiCall();
}
```

### Pattern 2: Optional Auth (Public Endpoint)

```typescript
async function myCommand() {
  const config = ConfigManager.load();
  const tokenManager = new TokenManager(config);

  // Create client (will use token if available)
  const client = new KnowledgeGraphClient(config, tokenManager);

  // API call works with or without auth
  const result = await client.publicApiCall();
}
```

### Pattern 3: Sensitive Operation (Challenge Required)

```typescript
import { AuthChallenge } from '../lib/auth/challenge';

async function deleteUser(userId: number) {
  const config = ConfigManager.load();
  const tokenManager = new TokenManager(config);
  const authClient = new AuthClient(config.api_url);

  // Require challenge for sensitive operation
  const challenge = new AuthChallenge(authClient, tokenManager);
  const freshToken = await challenge.challenge({
    reason: 'Delete user account',
    username: tokenManager.getUsername() || undefined,
    allowCancel: true
  });

  if (!freshToken) {
    console.log('Operation cancelled');
    return;
  }

  // Execute with fresh token
  await authClient.deleteUser(freshToken.access_token, userId);
  console.log('User deleted');
}
```

---

## Token Expiration Handling

### Automatic Detection

Tokens are checked before each request:
- **5-minute buffer:** Token considered expired 5 minutes before actual expiration
- **Interceptor:** Axios interceptor catches 401 responses
- **User prompt:** Clear error message directing user to re-login

### User Experience

```
# Token valid - command succeeds
$ kg search query "concept"
Found 5 concepts...

# Token expired - prompt re-login
$ kg search query "concept"
Error: Authentication expired. Please run: kg login

# User logs in again
$ kg login
Username: admin
Password: ********
Logged in successfully as admin (role: admin)

# Command works again
$ kg search query "concept"
Found 5 concepts...
```

---

## Security Considerations

### What We Store

- ✅ JWT token (time-limited, signed by server)
- ✅ Token expiration timestamp
- ✅ Username and role (decoded from JWT)
- ✅ API URL

### What We DON'T Store

- ❌ **Passwords** (NEVER stored, only used during login)
- ❌ Private keys (if using OAuth, keys stay server-side)
- ❌ Unencrypted secrets

### File Permissions

- Config file: `~/.config/kg/config.json` set to **0600** (owner read/write only)
- Automatic permission check on write
- Warning if permissions too permissive

### Token Security

- **Short-lived:** 60 minutes default (configurable server-side)
- **Single-use sensitive ops:** Challenge flow generates fresh token
- **Stateless:** Server validates signature, no revocation (use short expiry)
- **Future:** Refresh tokens for longer sessions (ADR-054)

---

## Authentication Priority

When multiple auth methods are available:

```
1. JWT token (if logged in via kg login)
   → Authorization: Bearer <jwt_token>

2. API key (if configured via kg config set secret)
   → X-API-Key: <api_key>

3. None (unauthenticated)
   → Some endpoints allow public access
```

**Implementation:** Request interceptor in `KnowledgeGraphClient` checks in this order.

---

## Testing Authentication Code

### Unit Tests

Test individual modules in isolation:

```typescript
// Test token expiration logic
describe('TokenManager', () => {
  it('should detect expired tokens', () => {
    const expired = { expires_at: Math.floor(Date.now() / 1000) - 100 };
    expect(tokenManager.isTokenExpired(expired)).toBe(true);
  });
});
```

### Integration Tests

Test full authentication flow:

```bash
# Test login flow
kg login
# Enter credentials
kg admin user list  # Should work
kg logout
kg admin user list  # Should fail with auth error
```

### Manual Testing

```bash
# 1. Fresh login
rm ~/.config/kg/config.json
kg login

# 2. Token persistence
kg admin user list  # Should work without re-login

# 3. Token expiration (wait 60+ minutes or modify config)
kg admin user list  # Should prompt re-login

# 4. Challenge flow
kg admin user delete <id>  # Should prompt password
```

---

## Common Patterns

### Reading Current User Info

```typescript
const tokenManager = new TokenManager(config);
const username = tokenManager.getUsername();
const role = tokenManager.getRole();

if (role === 'admin') {
  // Admin-only functionality
}
```

### Handling 401 Errors Gracefully

```typescript
try {
  const result = await client.someApiCall();
} catch (error) {
  if (error.response?.status === 401) {
    console.error('Authentication expired. Run: kg login');
    process.exit(1);
  }
  throw error;
}
```

### Prompting for Re-authentication

```typescript
import { AuthChallenge } from '../lib/auth/challenge';

const challenge = new AuthChallenge(authClient, tokenManager);
const token = await challenge.challenge({
  reason: 'Perform sensitive operation',
  allowCancel: true
});

if (!token) {
  // User cancelled
  return;
}
```

---

## Future Enhancements

### OAuth 2.0 Support (ADR-054)

- **Device Authorization Grant** for CLI
- Better for headless environments
- Longer-lived sessions with refresh tokens

### Refresh Tokens

- Extend sessions without re-entering password
- Background token refresh
- Revocable at server-side

### MCP Server Integration

- Share token management modules
- Same security model across clients

---

## Quick Reference

**Key Files:**
- `client/src/lib/auth/` - Authentication modules
- `client/src/cli/login.ts` - Login command
- `client/src/cli/admin/user.ts` - User management commands
- `client/src/api/client.ts` - Main API client

**Key Commands:**
- `kg login` - Authenticate user
- `kg logout` - Clear stored token
- `kg admin user list` - List users (admin only)
- `kg admin user create` - Create user (admin only)

**Config Location:**
- `~/.config/kg/config.json` (Linux/macOS)
- `%APPDATA%\kg\config.json` (Windows)

**Token Lifespan:**
- Default: 60 minutes
- Buffer: 5 minutes (55 minutes effective)
- Configurable server-side: `JWT_EXPIRATION_MINUTES`
