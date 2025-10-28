# kg auth (login/logout)

Authentication commands for the knowledge graph system.

## Commands

### login

Authenticate with username and password.

**Usage:**
```bash
kg login [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-u, --username <username>` | Username | prompts if not provided |
| `-h, --help` | Display help for command | - |

**Examples:**

```bash
# Interactive login (prompts for username and password)
kg login

# Provide username, prompt for password
kg login --username admin

# Short form
kg login -u admin
```

**Interactive Flow:**

```
Username: admin
Password: [hidden]

✓ Authentication successful
Welcome, admin!
```

**Session:**
- Creates authentication token
- Stored in config file
- Used for subsequent commands
- Expires after period of inactivity

**Use Cases:**
- Multi-user systems
- Secure operations (admin commands)
- Audit trail requirements

---

### logout

End authentication session.

**Usage:**
```bash
kg logout [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--forget` | Also forget saved username | `false` |
| `-h, --help` | Display help for command | - |

**Examples:**

```bash
# Logout (preserves username for next login)
kg logout

# Logout and forget username
kg logout --forget
```

**Output:**

```
✓ Logged out successfully

Next login will remember username: admin
Use 'kg logout --forget' to forget username
```

**With `--forget`:**

```
✓ Logged out successfully
Forgot username
```

**What Gets Cleared:**
- Authentication token
- Session data
- (Optional) Saved username

**What's Preserved:**
- Configuration settings
- API keys
- User preferences

---

## Authentication Flow

```
┌─────────────┐
│  kg login   │
└──────┬──────┘
       │
       v
┌─────────────┐
│  Prompt for │
│  username   │ (if not provided)
└──────┬──────┘
       │
       v
┌─────────────┐
│  Prompt for │
│  password   │
└──────┬──────┘
       │
       v
┌─────────────┐
│  Validate   │
│  with API   │
└──────┬──────┘
       │
       ├─success─> ✓ Store token
       │
       └─fail───> ✗ Show error
```

---

## When Authentication is Required

**Always Required:**
- `kg admin reset`
- `kg admin restore`
- `kg admin user create/update/delete`
- `kg admin rbac` commands

**Sometimes Required:**
- Multi-user deployments
- Production environments
- Compliance requirements

**Not Required:**
- Single-user development
- Local testing
- Read-only operations (if configured)

---

## Common Use Cases

### Initial Setup

```bash
# Login as admin
kg login -u admin

# Verify access
kg admin status

# Create additional users
kg admin user create researcher --role editor
```

### Daily Workflow

```bash
# Login at start of day
kg login

# Work with system
kg ingest file -o "Docs" document.txt
kg search query "concepts"

# Logout at end of day
kg logout
```

### Switching Users

```bash
# Logout current user
kg logout --forget

# Login as different user
kg login -u researcher
```

---

## Troubleshooting

### Authentication Fails

**Symptom:**
```bash
kg login -u admin
# Error: Invalid username or password
```

**Solutions:**

1. **Check username/password**
   - Verify credentials
   - Password is case-sensitive

2. **Reset admin password**
   ```bash
   ./scripts/initialize-auth.sh
   ```

3. **Check API server**
   ```bash
   kg health
   # API must be running
   ```

### Token Expired

**Symptom:**
```bash
kg admin status
# Error: Authentication token expired
```

**Solution:**
```bash
kg login
# Re-authenticate
```

### Forgot Password

**Solution:**
```bash
# Admin can reset
./scripts/initialize-auth.sh

# Or have admin reset your password
kg admin user update <user_id> --reset-password
```

---

## Related Commands

- [`kg config`](../config/) - Configuration management
- [`kg admin user`](../admin/#user) - User management
- [`kg admin rbac`](../admin/#rbac) - Role-based access control

---

## See Also

- [ADR-028: Role-Based Access Control](../../../architecture/ADR-028-role-based-access-control.md)
- [Authentication Guide](../../03-guides/authentication.md)
- [User Management](../../05-maintenance/user-management.md)
