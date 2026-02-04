# Password Recovery and Account Management

## When You're Locked Out

**The Problem:** You've logged out of the Knowledge Graph System and can't remember your password. Or perhaps you need to reset another user's password. The API requires authentication, so you can't use the API to fix this. You need direct database access.

**The Solution:** Use the password reset script (`reset-password.sh`) to update passwords directly in PostgreSQL, bypassing the API authentication entirely.

**When You Need This:**
- Forgot your password and can't login
- Need to reset another user's account
- Initial admin password was lost
- Need to recover from a locked account
- Testing authentication without going through the full API workflow

## Prerequisites

**Required:**
- Docker running with PostgreSQL container
- Python 3 with project dependencies installed (for password hashing)
- Access to the project root directory
- Shell access to run scripts

**Not Required:**
- API server doesn't need to be running
- No existing authentication token needed
- No network access required (all local)

## Workflow

### Quick Password Reset

**Step 1: Run the reset script**

```bash
cd /path/to/knowledge-graph-system
./scripts/reset-password.sh
```

**Step 2: Choose the user**

The script lists all existing users:
```
Available Users:
  • admin
  • curator_alice
  • reader_bob

Enter username to reset: admin
```

**Step 3: Enter new password**

The script enforces password requirements:
```
Password Requirements:
  • Minimum 8 characters
  • At least one uppercase letter
  • At least one lowercase letter
  • At least one digit
  • At least one special character

Enter new password: ********
Confirm new password: ********
✓ Password meets requirements
```

**Step 4: Password updated**

```
✓ Password hashed
✓ Password updated successfully

╔════════════════════════════════════════════════════════════╗
║                Password Reset Complete!                    ║
╚════════════════════════════════════════════════════════════╝

Updated Credentials:
  Username: admin
  Password: (the password you just set)
```

**Step 5: Test login**

```bash
kg login
```

Output:
```
Username: admin
Password: ********

✓ Creating personal OAuth client credentials...
✓ Login successful

Logged in as: admin (role: admin)
OAuth Client: kg-cli-admin-20251102
Scopes: read:*, write:*
```

Success! You're back in. The login command creates OAuth client credentials that don't expire.

## Alternative: Initialize Auth Script

If you need to reset the admin password AND regenerate OAuth token signing keys, use the more comprehensive initialize script:

```bash
./scripts/setup/initialize-platform.sh
```

This script:
- Detects if admin user exists
- Offers to reset admin password
- Optionally regenerates JWT_SECRET_KEY (used to sign OAuth access tokens)
- Updates `.env` file with new secrets
- Provides full setup instructions

**When to use which:**
- **`reset-password.sh`**: Quick password reset for any user
- **`initialize-platform.sh`**: Full authentication setup or admin password + token signing key regeneration

## What This Does Under the Hood

### 1. **Direct Database Access**

The script bypasses the API and talks directly to PostgreSQL:

```bash
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "UPDATE kg_auth.users SET password_hash = '$PASSWORD_HASH' WHERE username = '$USERNAME'"
```

**Why this works:**
- PostgreSQL is running in Docker with known credentials
- We have `docker exec` access to the container
- The `admin` database user has full privileges
- No API authentication required

### 2. **Password Hashing**

Uses the same bcrypt hashing as the API:

```python
from api.app.lib.auth import get_password_hash
hashed = get_password_hash("SecurePass123!")
# Returns: $2b$12$abc123...xyz789
```

**Security details:**
- Bcrypt with 12 rounds (~300ms to hash)
- Same hashing algorithm as API login flow
- Password never stored in plaintext
- Each hash includes random salt

### 3. **Password Validation**

Enforces the same requirements as user registration:

```python
from api.app.lib.auth import validate_password_strength
is_valid, error = validate_password_strength("weak")
# Returns: (False, "Password must be at least 8 characters long")
```

## Troubleshooting

### PostgreSQL Container Not Running

**Error:**
```
✗ PostgreSQL is not running
  Run: docker-compose up -d
```

**Fix:**
```bash
docker-compose up -d
docker ps  # Verify container is running
```

### No Users Found

**Error:**
```
✗ No users found in database
  Run: ./scripts/setup/initialize-platform.sh to create admin user
```

**Fix:**
```bash
./scripts/setup/initialize-platform.sh
# Creates initial admin user
```

### Python Import Errors

**Error:**
```
ModuleNotFoundError: No module named 'passlib'
```

**Fix:**
```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### User Not Found

**Error:**
```
✗ User 'alice' not found
```

**Fix:**
```bash
# List all users directly
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "SELECT username, primary_role FROM kg_auth.users;"

# Use correct username from the list
```

### Password Hashing Failed

**Error:**
```
✗ Failed to hash password
Traceback (most recent call last):
  ...
```

**Fix:**
```bash
# Check Python environment
python3 --version  # Should be 3.11+

# Reinstall crypto dependencies
pip install --upgrade passlib bcrypt

# Try again
./scripts/reset-password.sh
```

## Security Considerations

### This Script is Powerful

**Direct database access means:**
- ✅ Can recover from locked accounts
- ✅ Bypasses API rate limiting
- ✅ Works when API is down
- ⚠️ Can reset ANY user's password
- ⚠️ No audit trail in API logs
- ⚠️ Requires shell access to server

**Best practices:**
- Only run this script when necessary
- Document password resets in security logs
- Restrict shell access to trusted admins
- Consider adding manual audit logging to the script

### Password Requirements

The script enforces ADR-027 password policy:
- Minimum 8 characters
- Mixed case (upper and lower)
- At least one digit
- At least one special character

**Why these requirements:**
- Prevents common weak passwords
- Resists brute force attacks
- Compatible with standard password managers
- Balances security and usability

### Bcrypt Hashing

**Security properties:**
- **Cost factor 12:** 2^12 iterations (~300ms per hash)
- **Adaptive:** Can increase cost factor as CPUs get faster
- **Salted:** Each password gets unique random salt
- **One-way:** Cannot reverse hash back to password

**Why bcrypt:**
- Industry standard for password hashing
- Built-in salt generation
- Resistant to GPU cracking
- Widely audited and trusted

## Advanced Usage

### Bulk Password Reset

Reset multiple users from a file:

```bash
#!/bin/bash
# reset-users.sh

while IFS=',' read -r username password; do
  echo "Resetting password for $username..."

  # Hash password
  HASH=$(python3 -c "
import sys
sys.path.insert(0, '.')
from api.app.lib.auth import get_password_hash
print(get_password_hash('$password'))
")

  # Update database
  docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
    "UPDATE kg_auth.users SET password_hash = '$HASH' WHERE username = '$username'"

  echo "✓ $username password updated"
done < users.csv

# users.csv format:
# alice,SecurePass123!
# bob,AnotherPass456@
```

### Audit Logging

Add audit trail to password resets:

```bash
# In reset-password.sh, after successful reset:
echo "$(date -u +"%Y-%m-%dT%H:%M:%SZ"),password_reset,$USERNAME,$(whoami)" \
  >> logs/password_resets.csv

# logs/password_resets.csv:
# 2025-10-14T15:30:00Z,password_reset,admin,root
# 2025-10-14T16:45:00Z,password_reset,alice,admin_bob
```

### Emergency Admin Access

Create emergency admin account:

```bash
#!/bin/bash
# create-emergency-admin.sh

EMERGENCY_USER="emergency_admin_$(date +%s)"
EMERGENCY_PASS=$(openssl rand -base64 32)

# Hash password
HASH=$(python3 -c "
import sys
sys.path.insert(0, '.')
from api.app.lib.auth import get_password_hash
print(get_password_hash('$EMERGENCY_PASS'))
")

# Create user
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "INSERT INTO kg_auth.users (username, password_hash, primary_role, created_at)
   VALUES ('$EMERGENCY_USER', '$HASH', 'admin', NOW())"

echo "Emergency admin created:"
echo "  Username: $EMERGENCY_USER"
echo "  Password: $EMERGENCY_PASS"
echo ""
echo "SAVE THESE CREDENTIALS SECURELY!"
```

## Related Operations

### View All Users

```bash
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "SELECT username, primary_role, created_at FROM kg_auth.users ORDER BY created_at;"
```

### Delete User

```bash
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "DELETE FROM kg_auth.users WHERE username = 'old_user';"
```

### Change User Role

```bash
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "UPDATE kg_auth.users SET primary_role = 'curator' WHERE username = 'alice';"
```

### View Active OAuth Clients

```bash
# OAuth client credentials are long-lived and stored in database
# Access tokens are short-lived (1 hour) and not persisted

# List all OAuth clients for a user
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c \
  "SELECT client_id, client_name, scopes, created_at
   FROM kg_auth.oauth_clients
   WHERE metadata->>'personal' = 'true'
     AND (metadata->>'user_id')::int = (SELECT id FROM kg_auth.users WHERE username = 'admin');"
```

---

**Last Updated:** 2025-10-14

**Related Documentation:**
- [01-AUTHENTICATION.md](01-AUTHENTICATION.md) - Authentication system overview
- [03-SECURITY.md](03-SECURITY.md) - Security infrastructure and best practices
- [02-RBAC.md](02-RBAC.md) - Role-based access control
- [ADR-027](../../architecture/ADR-027-user-management-api.md) - User management design
