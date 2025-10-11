# Authentication Guide

**Operational guide for Knowledge Graph System authentication (ADR-027)**

This guide shows you how to use the authentication system - from cold start initialization to day-to-day user management.

## Table of Contents

- [Cold Start: First-Time Setup](#cold-start-first-time-setup)
- [User Registration](#user-registration)
- [Login & JWT Tokens](#login--jwt-tokens)
- [Using Protected Endpoints](#using-protected-endpoints)
- [API Keys (Programmatic Access)](#api-keys-programmatic-access)
- [User Management (Admin)](#user-management-admin)
- [Troubleshooting](#troubleshooting)

---

## Cold Start: First-Time Setup

When deploying the knowledge graph system for the first time, there's no admin user in the database. You need to initialize authentication.

### Prerequisites

1. PostgreSQL container running: `docker-compose up -d`
2. Database schema initialized (happens automatically on first run)
3. Python virtual environment active: `source venv/bin/activate`

### Initialization Steps

**Run the initialization script:**

```bash
./scripts/initialize-auth.sh
```

**What this does:**

1. ✅ Checks if admin user already exists
2. 🔐 Prompts for admin password (with strength validation)
3. 🔑 Generates cryptographically secure JWT_SECRET_KEY
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
  1. Start API server: ./scripts/start-api.sh
  2. Login: curl -X POST http://localhost:8000/auth/login \
           -d 'username=admin&password=YOUR_PASSWORD'
  3. View docs: http://localhost:8000/docs
```

### Manual Initialization (CI/Automated Environments)

If you need to script the initialization:

```bash
# 1. Generate JWT secret
JWT_SECRET=$(openssl rand -hex 32)
echo "JWT_SECRET_KEY=$JWT_SECRET" >> .env

# 2. Create admin user with pgcrypto
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
  INSERT INTO kg_auth.users (username, password_hash, role, created_at)
  VALUES ('admin', crypt('YOUR_SECURE_PASSWORD', gen_salt('bf', 12)), 'admin', NOW())"
```

---

## User Registration

Anyone can register a new account (or restrict to admin-only in production).

### Endpoint

```
POST /auth/register
Content-Type: application/json
```

### Request Body

```json
{
  "username": "alice",
  "password": "SecurePass123!",
  "role": "contributor"
}
```

**Roles:**
- `read_only` - View concepts, vocabulary, jobs
- `contributor` - Create concepts and jobs
- `curator` - Approve vocabulary changes and jobs
- `admin` - Full system access including user management

### Password Requirements

- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one digit
- At least one special character (`!@#$%^&*()_+-=[]{}|;:,.<>?`)

### Example (curl)

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "alice",
    "password": "SecurePass123!",
    "role": "contributor"
  }'
```

### Response (201 Created)

```json
{
  "id": 2,
  "username": "alice",
  "role": "contributor",
  "created_at": "2025-10-11T12:00:00Z",
  "last_login": null,
  "disabled": false
}
```

**Note:** Password hash is NOT returned (security).

### Errors

| Code | Reason |
|------|--------|
| 422 | Password doesn't meet requirements |
| 409 | Username already exists |

---

## Login & JWT Tokens

Get a JWT access token to authenticate API requests.

### Endpoint

```
POST /auth/login
Content-Type: application/x-www-form-urlencoded
```

**OAuth2 password flow compatible** (works with OpenAPI docs).

### Request Body (form data)

```
username=alice&password=SecurePass123!
```

### Example (curl)

```bash
curl -X POST http://localhost:8000/auth/login \
  -d "username=alice&password=SecurePass123!"
```

### Response (200 OK)

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": {
    "id": 2,
    "username": "alice",
    "role": "contributor",
    "created_at": "2025-10-11T12:00:00Z",
    "last_login": "2025-10-11T12:30:00Z",
    "disabled": false
  }
}
```

### JWT Token Details

**Format:**
```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhbGljZSIsInJvbGUiOiJjdXJhdG9yIiwiZXhwIjoxNjk2ODc2NTQzfQ.signature
```

**Payload (decoded):**
```json
{
  "sub": "alice",      // Username
  "role": "curator",   // User role
  "exp": 1696876543    // Expiration timestamp
}
```

**Expiration:** 60 minutes by default (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` in `.env`)

### Errors

| Code | Reason |
|------|--------|
| 401 | Invalid username or password |
| 403 | User account is disabled |

---

## Using Protected Endpoints

Most API endpoints require authentication via JWT token.

### Authorization Header

```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### Example: Get Current User

```bash
# 1. Login and save token
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=alice&password=SecurePass123!" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# 2. Use token for authenticated request
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

### Response

```json
{
  "id": 2,
  "username": "alice",
  "role": "contributor",
  "created_at": "2025-10-11T12:00:00Z",
  "last_login": "2025-10-11T12:30:00Z",
  "disabled": false
}
```

### Token Expired?

Tokens expire after 60 minutes. When you get a `401 Unauthorized`, just login again to get a fresh token.

---

## API Keys (Programmatic Access)

For long-lived access (CLI tools, CI/CD, integrations), use API keys instead of JWT tokens.

### Create API Key

```bash
# Login first
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=alice&password=SecurePass123!" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# Create API key
curl -X POST http://localhost:8000/auth/api-keys \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "CI/CD Pipeline",
    "scopes": ["read:concepts", "write:ingest"],
    "expires_at": "2026-01-01T00:00:00Z"
  }'
```

### Response (201 Created)

```json
{
  "id": 1,
  "key": "kg_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6",
  "name": "CI/CD Pipeline",
  "scopes": ["read:concepts", "write:ingest"],
  "created_at": "2025-10-11T12:00:00Z",
  "last_used": null,
  "expires_at": "2026-01-01T00:00:00Z"
}
```

**⚠️ SAVE THE KEY! It's shown only once.**

### Use API Key

API keys work exactly like JWT tokens:

```bash
curl http://localhost:8000/auth/me \
  -H "Authorization: Bearer kg_sk_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6"
```

### List Your API Keys

```bash
curl http://localhost:8000/auth/api-keys \
  -H "Authorization: Bearer $TOKEN"
```

**Note:** Plaintext keys are NOT returned (only key ID, name, scopes).

### Revoke API Key

```bash
curl -X DELETE http://localhost:8000/auth/api-keys/1 \
  -H "Authorization: Bearer $TOKEN"
```

---

## User Management (Admin)

Admin users can manage all user accounts.

### List All Users

```bash
curl http://localhost:8000/users \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Query parameters:**
- `skip=0` - Pagination offset
- `limit=100` - Max results
- `role=curator` - Filter by role

### Response

```json
{
  "users": [
    {
      "id": 1,
      "username": "admin",
      "role": "admin",
      "created_at": "2025-10-11T00:00:00Z",
      "last_login": "2025-10-11T12:00:00Z",
      "disabled": false
    },
    {
      "id": 2,
      "username": "alice",
      "role": "curator",
      "created_at": "2025-10-11T12:00:00Z",
      "last_login": "2025-10-11T15:30:00Z",
      "disabled": false
    }
  ],
  "total": 2,
  "skip": 0,
  "limit": 100
}
```

### Get User Details

```bash
curl http://localhost:8000/users/2 \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Update User

```bash
# Change role
curl -X PUT http://localhost:8000/users/2 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "curator"
  }'

# Disable account
curl -X PUT http://localhost:8000/users/2 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "disabled": true
  }'

# Reset password (admin can do this)
curl -X PUT http://localhost:8000/users/2 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "password": "NewSecurePass456!"
  }'
```

### Delete User

```bash
curl -X DELETE http://localhost:8000/users/2 \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**Note:** Cannot delete yourself (safety check).

---

## Troubleshooting

### Problem: `401 Unauthorized` on protected endpoints

**Cause:** Missing, invalid, or expired token

**Solution:**
```bash
# Check if token is in Authorization header
curl -v http://localhost:8000/auth/me \
  -H "Authorization: Bearer $TOKEN"

# Look for: Authorization: Bearer eyJhbGci...

# If token expired (>60 min old), login again
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=alice&password=SecurePass123!" \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")
```

### Problem: `403 Forbidden` - permission denied

**Cause:** Your role doesn't have permission for this action

**Solution:** Contact admin to upgrade your role:
```bash
# Admin upgrades alice to curator
curl -X PUT http://localhost:8000/users/2 \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "curator"}'
```

### Problem: Forgot admin password

**Solution 1:** Reset via init script
```bash
./scripts/initialize-auth.sh
# Choose "yes" when asked to reset admin password
```

**Solution 2:** Manual database reset
```bash
# Generate new password hash
python3 << EOF
from src.api.lib.auth import get_password_hash
print(get_password_hash("NewAdminPassword123!"))
EOF

# Update in database
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
  UPDATE kg_auth.users
  SET password_hash = '\$2b\$12\$...'
  WHERE username = 'admin'"
```

### Problem: JWT_SECRET_KEY warnings on startup

**Symptom:**
```
⚠️  Auth Configuration: JWT_SECRET_KEY is using default value - INSECURE!
```

**Cause:** Using the example JWT_SECRET_KEY from `.env.example`

**Solution:**
```bash
# Generate secure secret
openssl rand -hex 32

# Add to .env
echo "JWT_SECRET_KEY=<generated_secret>" >> .env

# Or run init script
./scripts/initialize-auth.sh
```

### Problem: Can't create users (registration disabled)

If you want **admin-only user creation**, modify the endpoint to check permissions:

```python
# In src/api/routes/auth.py
@router.post("/register", response_model=UserRead, dependencies=[Depends(require_role("admin"))])
async def register_user(user: UserCreate):
    # Now only admins can register users
    ...
```

---

## Security Best Practices

### ✅ DO:

- Use strong, unique passwords
- Rotate JWT_SECRET_KEY periodically
- Set API key expiration dates
- Revoke API keys when no longer needed
- Use HTTPS in production (prevents token theft)
- Log all authentication events
- Implement rate limiting on login endpoint
- Store JWT tokens securely in client (HttpOnly cookies for web apps)

### ❌ DON'T:

- Commit `.env` to git (it's in `.gitignore`)
- Share JWT tokens or API keys
- Use default passwords in production
- Log JWT tokens or passwords in plaintext
- Store tokens in localStorage (web apps - use HttpOnly cookies)
- Use weak passwords (enable stronger validation if needed)

---

## Quick Reference

### Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/auth/register` | POST | None | Create user account |
| `/auth/login` | POST | None | Get JWT token |
| `/auth/me` | GET | JWT | Get current user |
| `/auth/me` | PUT | JWT | Update own password |
| `/auth/api-keys` | GET | JWT | List own API keys |
| `/auth/api-keys` | POST | JWT | Create API key |
| `/auth/api-keys/{id}` | DELETE | JWT | Revoke API key |
| `/users` | GET | Admin | List all users |
| `/users/{id}` | GET | Admin | Get user details |
| `/users/{id}` | PUT | Admin | Update user |
| `/users/{id}` | DELETE | Admin | Delete user |

### Roles & Permissions

| Role | Permissions |
|------|-------------|
| `read_only` | View concepts, vocabulary, jobs |
| `contributor` | + Create concepts, submit jobs |
| `curator` | + Approve vocabulary, approve jobs |
| `admin` | + Full user management |

### Environment Variables

```bash
# Required
JWT_SECRET_KEY=<openssl rand -hex 32>

# Optional
ACCESS_TOKEN_EXPIRE_MINUTES=60  # Token lifetime (default: 60)
```

---

## Next Steps

- [QUICKSTART.md](QUICKSTART.md) - System overview
- [ADR-027](../architecture/ADR-027-user-management-api.md) - Architecture decisions
- [OpenAPI Docs](http://localhost:8000/docs) - Interactive API documentation
