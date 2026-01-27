---
status: Superseded
date: 2025-10-11
deciders:
  - aaronsb
  - claude
related:
  - ADR-024
  - ADR-054
---

# ADR-027: User Management API with Lightweight JWT Authentication

## Overview

Every multi-user application eventually faces the same questions: How do users log in? How do we know they're allowed to perform certain actions? How do we let automated tools (like CI/CD pipelines) access the API without passwords? This ADR was our first attempt to answer those questions with a lightweight authentication system.

We chose JWT (JSON Web Tokens) as our foundation - think of them like digital boarding passes that prove who you are without requiring the API to check a database on every request. Password-based login would give you a JWT that's valid for an hour. For automated tools, we'd issue long-lived API keys. Both approaches are stateless, meaning the API can verify credentials without database lookups, which keeps things fast and scalable.

However, this design had a fundamental limitation: it mixed up the concept of "our users" (people using the knowledge graph) with "our API clients" (different applications that need to access the system). A CLI tool, web app, and MCP server are fundamentally different types of clients with different security needs. Cramming them all into a simple username/password + JWT model wasn't elegant or secure.

That's why this ADR was superseded by ADR-054, which implements proper OAuth 2.0 with different authorization flows for each client type. This document remains valuable as historical context - it shows our thinking about authentication fundamentals and why we ultimately needed something more sophisticated.

---

## ⚠️ Superseded Notice

**This ADR described a JWT password flow implementation that has been replaced by a comprehensive OAuth 2.0 system (ADR-054).**

**Key Changes:**
- JWT password flow (`POST /auth/login`) → OAuth 2.0 flows (authorization code, device, client credentials)
- API keys (`kg_auth.api_keys`) → OAuth client credentials for machine-to-machine auth
- Single authentication method → Multiple flows appropriate for each client type (web, CLI, MCP)

**See ADR-054** for the current OAuth 2.0 implementation which provides:
- Authorization Code + PKCE for web applications
- Device Authorization Grant for CLI tools
- Client Credentials for machine-to-machine (MCP server)

**This document is retained for historical context.**

---

## Context

The knowledge graph system requires user authentication and authorization to:
- Control access to API endpoints based on role permissions
- Support multiple authentication methods (password-based, API keys, future OAuth)
- Track user actions in audit logs
- Enable collaboration features (shared ontologies, team permissions)

The `kg_auth` schema (ADR-024) provides the foundation with users, API keys, OAuth tokens, and role permissions tables. We need to implement REST API endpoints for user management that leverage this existing schema.

### Requirements

**Security:**
- Password hashing with industry-standard bcrypt
- Stateless authentication with JWT tokens
- Support for long-lived API keys
- Role-based access control (RBAC)
- Audit logging for all authentication events

**User Roles:**
- `read_only` - View concepts, vocabulary, jobs
- `contributor` - Create concepts and jobs
- `curator` - Approve vocabulary changes and jobs
- `admin` - Full system access including user management

**Authentication Methods:**
1. **Password-based login** - Username/password → JWT token
2. **API key authentication** - Long-lived tokens for programmatic access
3. **Session-based** (optional) - Using `kg_api.sessions` table
4. **OAuth (future)** - GitHub, Google, Microsoft providers

## Decision

Implement a **lightweight JWT-based authentication system** using minimal, battle-tested libraries that integrate cleanly with FastAPI and the existing `kg_auth` schema.

### Libraries Selected

**Core Authentication (Phase 1):**
```python
pip install passlib[bcrypt] python-jose[cryptography] python-multipart
```

1. **passlib[bcrypt]** - Password hashing and verification
   - Industry standard bcrypt algorithm
   - Compatible with existing `$2b$12$...` hashes in schema
   - Automatic salt generation

2. **python-jose[cryptography]** - JWT token generation/validation
   - Recommended cryptography backend (not deprecated RSA)
   - HS256 algorithm for symmetric signing
   - Built-in expiration handling

3. **python-multipart** - Form data parsing
   - Required for OAuth2PasswordRequestForm
   - Handles `application/x-www-form-urlencoded` login forms

**Future OAuth Integration (Phase 2):**
```python
pip install authlib itsdangerous
```

4. **authlib** - OAuth 2.0 client integration
   - Official FastAPI support
   - Provider registration (GitHub, Google, etc.)
   - Token refresh handling

### API Endpoint Structure

#### Public Endpoints (No Authentication)

**POST /auth/register**
- Create new user account
- Validate password requirements
- Hash password with bcrypt
- Return user details (no token - must login)
- Option: Admin-only creation vs. open registration

**POST /auth/login**
- OAuth2 password flow (`OAuth2PasswordRequestForm`)
- Verify username/password against `kg_auth.users`
- Update `last_login` timestamp
- Return JWT access token
- Log to `kg_logs.audit_trail`

#### Authenticated Endpoints (JWT Required)

**GET /auth/me**
- Get current user profile
- Returns: username, role, created_at, last_login

**PUT /auth/me**
- Update own profile
- Allowed: password change only
- Not allowed: role change, username change

**POST /auth/logout**
- Optional: Invalidate JWT (if using session table)
- Clear session from `kg_api.sessions` if used
- Return success message

**GET /auth/api-keys**
- List current user's API keys
- Returns: id, name, scopes, created_at, last_used, expires_at
- Does NOT return actual key (only shown once at creation)

**POST /auth/api-keys**
- Generate new API key
- Input: name, scopes (optional), expires_at (optional)
- Generate random key, hash with bcrypt
- Store hash in `kg_auth.api_keys`
- Return plain key ONCE (user must save it)

**DELETE /auth/api-keys/{key_id}**
- Revoke API key
- Only owner can delete their own keys

#### Admin-Only Endpoints (Role Check)

**GET /users**
- List all users (paginated)
- Query params: role, disabled, skip, limit
- Returns: id, username, role, created_at, last_login, disabled

**GET /users/{user_id}**
- Get user details
- Includes: API key count, last activity

**PUT /users/{user_id}**
- Update user
- Allowed: role, disabled status
- Cannot modify: username, password (user must change own password)

**DELETE /users/{user_id}**
- Delete user
- Cascade deletes: API keys, sessions, OAuth tokens
- Cannot delete self

**GET /users/{user_id}/api-keys**
- Admin view of user's API keys
- Does not show actual keys

### Authentication Flow

#### JWT Token Authentication

```python
# 1. Login
POST /auth/login
{
  "username": "alice",
  "password": "secure_password"
}

# Response
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600
}

# 2. Use token for API requests
GET /concepts
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...

# 3. Token payload
{
  "sub": "alice",           # Username
  "role": "curator",        # For permission checks
  "exp": 1696876543         # Expiration timestamp
}
```

#### API Key Authentication

```python
# 1. Create API key
POST /auth/api-keys
Authorization: Bearer <admin_jwt>
{
  "name": "CI/CD Pipeline",
  "scopes": ["read:concepts", "write:ingest"],
  "expires_at": "2026-01-01T00:00:00Z"
}

# Response (key shown ONCE)
{
  "key": "kg_sk_a1b2c3d4e5f6...",  # Save this!
  "key_id": 42,
  "name": "CI/CD Pipeline",
  "scopes": ["read:concepts", "write:ingest"]
}

# 2. Use API key for requests
GET /concepts
Authorization: Bearer kg_sk_a1b2c3d4e5f6...
```

### Permission Checking

Leverage existing `kg_auth.role_permissions` table:

```python
async def check_permission(user: User, resource: str, action: str):
    """
    Check if user's role grants permission for action on resource.

    Query: SELECT granted FROM kg_auth.role_permissions
           WHERE role = %s AND resource = %s AND action = %s
    """
    result = db.execute(
        "SELECT granted FROM kg_auth.role_permissions "
        "WHERE role = %s AND resource = %s AND action = %s",
        (user.role, resource, action)
    )
    return result and result['granted']

# Usage in endpoint
@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(get_current_user)
):
    if not await check_permission(current_user, "users", "delete"):
        raise HTTPException(status_code=403, detail="Permission denied")
    # ... proceed with deletion
```

### Security Implementation Details

#### Password Requirements
- Minimum length: 8 characters
- Must contain: uppercase, lowercase, number, special character
- No common passwords (check against list)
- Rate limit: 5 failed attempts per 15 minutes

#### JWT Token Configuration
```python
SECRET_KEY = os.getenv("JWT_SECRET_KEY")  # Generate: openssl rand -hex 32
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour default
REFRESH_TOKEN_EXPIRE_DAYS = 7     # Optional refresh tokens
```

#### API Key Format
```
kg_sk_<random_32_bytes_hex>

Example: kg_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```
- Prefix `kg_sk_` identifies key type
- 32 random bytes = 64 hex characters
- Hash stored in database, never plaintext

#### Bcrypt Configuration
```python
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12  # Cost factor (2^12 iterations)
)
```

### Audit Logging

All authentication events logged to `kg_logs.audit_trail`:

| Action | Resource Type | Resource ID | Details |
|--------|---------------|-------------|---------|
| `user_login` | `user` | user_id | {success: true/false, ip_address, user_agent} |
| `user_logout` | `user` | user_id | {session_id} |
| `user_register` | `user` | user_id | {role} |
| `api_key_created` | `api_key` | key_id | {name, scopes} |
| `api_key_revoked` | `api_key` | key_id | {revoked_by} |
| `password_changed` | `user` | user_id | {changed_by: self/admin} |
| `role_changed` | `user` | user_id | {old_role, new_role, changed_by} |

### ~~Future OAuth Integration (Phase 2)~~ → Superseded by ADR-054

**⚠️ This section described a plan for external OAuth providers (Login with GitHub/Google). This has been superseded by ADR-054 which implements:**

1. **OAuth 2.0 Server** - Our system issues OAuth tokens to client applications
2. **Multiple Grant Types** - Authorization code (web), device (CLI), client credentials (MCP)
3. **Client Registration** - Register client applications (`kg-cli`, `kg-viz`, `kg-mcp`)
4. **Proper Token Management** - Access tokens, refresh tokens, authorization codes

**For external OAuth providers (Login with GitHub/Google):**
- The `kg_auth.oauth_external_provider_tokens` table (renamed from `oauth_tokens`) can store these
- This is orthogonal to ADR-054 (our OAuth server)
- Can be implemented later if needed

**See ADR-054** for complete OAuth 2.0 architecture.

## Alternatives Considered

### 1. FastAPI Users

**Pros:**
- Batteries-included user management
- Built-in OAuth support
- Cookie and JWT strategies

**Cons:**
- Opinionated SQLAlchemy-based models
- Requires adapting to custom `kg_auth` schema
- More complex than needed
- Harder to understand/customize

**Verdict:** Rejected - Too much coupling with SQLAlchemy models, doesn't fit our psycopg2-based multi-schema architecture.

### 2. Auth0 / Clerk / Supabase

**Pros:**
- Fully managed authentication
- Built-in UI components
- Advanced features (MFA, social login)

**Cons:**
- External dependency / vendor lock-in
- Monthly costs scale with users
- Requires internet connectivity
- Data leaves our infrastructure

**Verdict:** Rejected - System should be self-hosted and work offline.

### 3. Custom OAuth2 Implementation (No Libraries)

**Pros:**
- Full control over implementation
- No external dependencies

**Cons:**
- High risk of security vulnerabilities
- Time-consuming to implement correctly
- Reinventing the wheel

**Verdict:** Rejected - python-jose and passlib are battle-tested and minimal.

### 4. Session-Only Authentication (No JWT)

**Pros:**
- Simpler to implement
- Easy to invalidate sessions
- Uses existing `kg_api.sessions` table

**Cons:**
- Stateful (requires database lookup on every request)
- Harder to scale horizontally
- Not suitable for API-first architecture
- CLI/MCP integration more complex

**Verdict:** Rejected - Stateless JWT is better for API/CLI usage patterns.

## Consequences

### Positive

✅ **Minimal Dependencies** - Only 3 packages for core auth, all well-maintained
✅ **FastAPI-Native** - Uses built-in `OAuth2PasswordBearer` and security utilities
✅ **Schema Integration** - Works perfectly with existing `kg_auth` tables
✅ **Stateless** - JWT tokens don't require database lookups on every request
✅ **Flexible** - Supports password, API keys, and future OAuth
✅ **Production-Ready** - Industry standard bcrypt + JWT approach
✅ **Scalable** - Stateless tokens scale horizontally
✅ **CLI-Friendly** - API keys work well for `kg` CLI tool
✅ **MCP-Compatible** - JWT tokens can be stored in MCP config
✅ **Audit Trail** - All auth events logged to `kg_logs.audit_trail`
✅ **Future-Proof** - OAuth integration path is clear and non-breaking

### Negative

⚠️ **Token Revocation** - JWTs can't be invalidated before expiration (unless using session table)
⚠️ **Secret Management** - Must securely manage JWT_SECRET_KEY
⚠️ **Token Size** - JWTs larger than session IDs (usually 200-500 bytes)
⚠️ **Clock Skew** - Token expiration requires synchronized clocks
⚠️ **Initial Setup** - Need to implement auth utilities from scratch

### Mitigations

**Token Revocation:**
- Keep token expiration short (60 minutes)
- Optionally track tokens in `kg_api.sessions` for revocation
- Refresh token pattern for long-lived sessions

**Secret Management:**
- Use `.env` file (never commit to git)
- Rotate secrets periodically
- Use different secrets for dev/staging/prod

**Token Size:**
- Not a concern for API usage
- Slightly larger HTTP headers
- Cache in CLI/MCP to avoid re-auth

## Implementation Plan

### Phase 1: Core Authentication (Week 1)

**Dependencies:**
```bash
pip install passlib[bcrypt] python-jose[cryptography] python-multipart
```

**Implementation Order:**
1. Create `src/api/lib/auth.py` - Password hashing, JWT utilities
2. Create `src/api/models/auth.py` - Pydantic request/response models
3. Create `src/api/routes/auth.py` - Public endpoints (register, login)
4. Create `src/api/dependencies/auth.py` - `get_current_user` dependency
5. Add auth router to `src/api/main.py`
6. Test with curl/Postman

### Phase 2: User Management (Week 1)

**Implementation Order:**
1. Add `/auth/me` endpoints (get profile, update password)
2. Add API key management endpoints
3. Add admin user management endpoints
4. Implement permission checking
5. Add audit logging for all auth events
6. Update kg CLI to support API keys

### Phase 3: OAuth Integration (Future)

**Dependencies:**
```bash
pip install authlib itsdangerous
```

**Implementation Order:**
1. Add SessionMiddleware
2. Configure OAuth providers (GitHub, Google)
3. Create `/auth/{provider}` and `/auth/{provider}/callback` endpoints
4. Implement user linking (find or create in `kg_auth.users`)
5. Store tokens in `kg_auth.oauth_tokens`
6. Issue standard JWT after OAuth success
7. Add "Login with..." buttons to docs

## Testing Strategy

### Unit Tests
- Password hashing/verification
- JWT token creation/validation
- Permission checking logic
- API key generation/validation

### Integration Tests
- Full login flow (username/password → JWT)
- API key authentication
- Role-based access control
- Token expiration handling
- Failed login attempts (rate limiting)

### Security Tests
- Weak password rejection
- Brute force protection
- Token tampering detection
- Expired token rejection
- Invalid signature rejection

### Manual Testing
```bash
# 1. Register user
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "SecurePass123!", "role": "contributor"}'

# 2. Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=alice&password=SecurePass123!"

# 3. Access protected endpoint
curl -X GET http://localhost:8000/auth/me \
  -H "Authorization: Bearer <token_from_step_2>"

# 4. Create API key
curl -X POST http://localhost:8000/auth/api-keys \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Key", "scopes": ["read:concepts"]}'

# 5. Use API key
curl -X GET http://localhost:8000/concepts \
  -H "Authorization: Bearer <api_key_from_step_4>"
```

## References

### External Documentation
- FastAPI Security Tutorial: https://fastapi.tiangolo.com/tutorial/security/
- Passlib Documentation: https://passlib.readthedocs.io/
- Python-JOSE Documentation: https://python-jose.readthedocs.io/
- Authlib FastAPI Integration: https://docs.authlib.org/en/latest/client/fastapi.html
- JWT Best Practices: https://datatracker.ietf.org/doc/html/rfc8725

### Related ADRs
- ADR-024: Multi-Schema PostgreSQL Architecture (defines `kg_auth` schema)
- ADR-025: Dynamic Relationship Vocabulary (permission model usage)
- ADR-026: Autonomous Vocabulary Curation (curator role integration)

### Schema Tables Used
- `kg_auth.users` - User accounts
- `kg_auth.api_keys` - API key authentication
- `kg_auth.oauth_tokens` - OAuth provider tokens (future)
- `kg_auth.role_permissions` - RBAC definitions
- `kg_api.sessions` - Optional session tracking
- `kg_logs.audit_trail` - Authentication event logging

---

**Review Date:** 2025-11-11 (1 month after implementation)
**Success Criteria:**
- All endpoints functioning and tested
- Zero security vulnerabilities in auth code
- Documentation complete for users
- kg CLI supports API key authentication
- Average login latency < 100ms
