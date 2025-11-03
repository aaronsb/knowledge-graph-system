# RBAC Operations Guide

**Role-Based Access Control (RBAC) - Administrative Operations**

This guide covers day-to-day operations for managing users, roles, and permissions in the Knowledge Graph system.

## Table of Contents

- [Overview](#overview)
- [Built-in Roles](#built-in-roles)
- [User Management](#user-management)
- [Role Management](#role-management)
- [Permission Management](#permission-management)
- [User Role Assignments](#user-role-assignments)
- [Common Workflows](#common-workflows)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Knowledge Graph system implements a dynamic RBAC system (ADR-028) with:

- **Dynamic resource types**: Register new resource types at runtime
- **Role hierarchy**: Roles can inherit permissions from parent roles
- **Multi-level scoping**: Global, instance-level, and filter-based permissions
- **Permission precedence**: DENY → Instance → Filter → Global → Inherited

All RBAC operations require admin authentication and are accessed via `kg admin rbac` commands.

---

## Built-in Roles

The system includes four built-in roles:

| Role | Description | Default Permissions |
|------|-------------|---------------------|
| `read_only` | Read-only access to public resources | Read concepts, search |
| `contributor` | Can create and modify content | All read_only + create/update content |
| `curator` | Can approve and manage content | All contributor + approve jobs, view RBAC |
| `admin` | Full system access | All curator + manage users, roles, permissions |

**Note**: Built-in roles cannot be deleted but can be modified with caution.

---

## User Management

### Prerequisites

You must be logged in with admin role:

```bash
kg login --username admin
```

### Create a User

**Interactive (prompts for password):**
```bash
kg admin user create alice --role contributor
```

**Non-interactive (with password):**
```bash
kg admin user create alice --role contributor --password "SecurePass123!"
```

### List Users

```bash
# List all users
kg admin user list

# Filter by role
kg admin user list --role admin

# Pagination
kg admin user list --skip 10 --limit 20
```

### View User Details

```bash
kg admin user get <user_id>
```

Example:
```bash
kg admin user get 3
```

Output:
```
User Details

ID:         3
Username:   alice
Role:       contributor
Created:    10/12/2025, 12:00:00 AM
Last Login: 10/12/2025, 1:30:15 AM
Status:     Active
```

### Update User

**Change role:**
```bash
kg admin user update 3 --role curator
```

**Change password (interactive):**
```bash
kg admin user update 3 --password
```

**Change password (non-interactive):**
```bash
kg admin user update 3 --password "NewSecurePass123!"
```

**Disable user:**
```bash
kg admin user update 3 --disable
```

**Enable user:**
```bash
kg admin user update 3 --enable
```

### Delete User

```bash
kg admin user delete 3
```

**Note**: Requires re-authentication challenge for safety. Cannot delete your own account.

---

## Role Management

### List Roles

```bash
# Active roles only
kg admin rbac roles list

# Include inactive roles
kg admin rbac roles list --all
```

Output:
```
────────────────────────────────────────────────────────────
Role Name            Display Name         Active  Builtin  Parent
────────────────────────────────────────────────────────────
admin                Administrator        ●       Yes      -
contributor          Contributor          ●       Yes      -
curator              Curator              ●       Yes      -
data_scientist       Data Scientist       ●       No       contributor
read_only            Read Only            ●       Yes      -
────────────────────────────────────────────────────────────
```

### Show Role Details

```bash
kg admin rbac roles show data_scientist
```

Output:
```
Role: Data Scientist
ID: data_scientist
Description: Advanced analytics and data exploration
Status: Active
Builtin: No
Inherits from: contributor
Created: 10/12/2025, 12:30:00 AM

Permissions (3):
  ✓ read on concepts (global)
  ✓ read on vocabulary (global)
  ✓ write on concepts (filter)
```

### Create a Custom Role

**Basic role:**
```bash
kg admin rbac roles create \
  -n "data_analyst" \
  -d "Data Analyst" \
  --description "Analytics and reporting access"
```

**Role with inheritance:**
```bash
kg admin rbac roles create \
  -n "senior_analyst" \
  -d "Senior Data Analyst" \
  --description "Advanced analytics with additional permissions" \
  -p data_analyst
```

### Delete a Role

```bash
kg admin rbac roles delete data_analyst
```

**Note**:
- Cannot delete built-in roles
- Cannot delete roles with assigned users
- Requires confirmation (use `--force` to skip)

---

## Permission Management

### List Permissions

**All permissions:**
```bash
kg admin rbac permissions list
```

**Filter by role:**
```bash
kg admin rbac permissions list --role data_scientist
```

**Filter by resource type:**
```bash
kg admin rbac permissions list --resource-type concepts
```

Output:
```
────────────────────────────────────────────────────────────
Role              Action  Resource      Scope     Granted
────────────────────────────────────────────────────────────
admin             delete  resources     global    ✓
admin             read    resources     global    ✓
admin             write   resources     global    ✓
data_scientist    read    concepts      global    ✓
────────────────────────────────────────────────────────────
```

### Grant Permissions

**Global permission:**
```bash
kg admin rbac permissions grant \
  -r data_scientist \
  -t concepts \
  -a read
```

**Instance-scoped permission:**
```bash
kg admin rbac permissions grant \
  -r data_scientist \
  -t ontology \
  -a write \
  -s instance \
  --scope-id "research-2024"
```

**Filter-scoped permission:**
```bash
kg admin rbac permissions grant \
  -r data_scientist \
  -t concepts \
  -a write \
  -s filter
```

**Explicit deny:**
```bash
kg admin rbac permissions grant \
  -r contributor \
  -t users \
  -a delete \
  --deny
```

### Revoke Permissions

```bash
kg admin rbac permissions revoke <permission_id>
```

**Note**: Use `kg admin rbac permissions list` to find the permission ID.

---

## User Role Assignments

The system supports dynamic role assignments beyond the primary role.

### List User's Role Assignments

```bash
kg admin rbac assign list <user_id>
```

Example:
```bash
kg admin rbac assign list 5
```

Output:
```
────────────────────────────────────────────────────────────
Role              Scope Type  Scope ID    Assigned          Expires
────────────────────────────────────────────────────────────
data_scientist    global      -           Oct 12, 12:00 AM  Never
curator           workspace   ws-001      Oct 12, 01:00 AM  Oct 13, 01:00 AM
────────────────────────────────────────────────────────────
```

### Assign Role to User

**Global assignment:**
```bash
kg admin rbac assign add \
  -u 5 \
  -r data_scientist
```

**Scoped assignment:**
```bash
kg admin rbac assign add \
  -u 5 \
  -r curator \
  -s workspace \
  --scope-id ws-001
```

### Remove Role Assignment

```bash
kg admin rbac assign remove <assignment_id>
```

**Note**: Use `kg admin rbac assign list <user_id>` to find the assignment ID.

---

## Common Workflows

### Onboard a New User

```bash
# 1. Create user account
kg admin user create alice --role contributor --password "TempPass123!"

# 2. Assign additional roles if needed
kg admin rbac assign add -u <alice_id> -r data_scientist

# 3. Send credentials to user (use secure channel)
echo "Username: alice, Temporary password: TempPass123!"

# 4. User logs in and changes password
# (User runs: kg login, then kg admin user update <id> --password)
```

### Create a Project-Specific Role

```bash
# 1. Create the role with inheritance
kg admin rbac roles create \
  -n "ml_researcher" \
  -d "ML Researcher" \
  --description "Machine learning research team" \
  -p contributor

# 2. Grant specific permissions
kg admin rbac permissions grant -r ml_researcher -t concepts -a read
kg admin rbac permissions grant -r ml_researcher -t concepts -a write
kg admin rbac permissions grant -r ml_researcher -t vocabulary -a read
kg admin rbac permissions grant -r ml_researcher -t jobs -a approve

# 3. Assign to team members
kg admin rbac assign add -u 10 -r ml_researcher
kg admin rbac assign add -u 11 -r ml_researcher
```

### Temporary Access (Time-Limited)

```bash
# Grant temporary curator access for code review
kg admin rbac assign add \
  -u 7 \
  -r curator \
  --expires "2025-10-15T23:59:59Z"
```

**Note**: The system will automatically revoke expired assignments.

### Audit User Permissions

```bash
# 1. View user details
kg admin user get 5

# 2. List all role assignments
kg admin rbac assign list 5

# 3. Check specific role permissions
kg admin rbac roles show data_scientist

# 4. Review all permissions for that role
kg admin rbac permissions list --role data_scientist
```

---

## Best Practices

### Role Design

1. **Use role hierarchy**: Create specific roles that inherit from base roles
   ```bash
   contributor → data_scientist → senior_data_scientist
   ```

2. **Principle of least privilege**: Grant minimum necessary permissions
   ```bash
   # Good: Specific permissions
   kg admin rbac permissions grant -r analyst -t concepts -a read

   # Avoid: Overly broad permissions
   kg admin rbac permissions grant -r analyst -t concepts -a write
   ```

3. **Use scoped permissions**: Limit access to specific resources when possible
   ```bash
   # Project-specific write access
   kg admin rbac permissions grant -r dev -t ontology -a write -s instance --scope-id "project-x"
   ```

### User Management

1. **Standardize usernames**: Use consistent naming (e.g., `firstname.lastname`, `email_prefix`)

2. **Require strong passwords**: Use password validation (min 8 chars, uppercase, lowercase, digit, special char)

3. **Regular audits**: Periodically review user list and assignments
   ```bash
   kg admin user list > users_$(date +%Y%m%d).txt
   ```

4. **Disable instead of delete**: Preserve audit trail by disabling inactive users
   ```bash
   kg admin user update <id> --disable
   ```

### Permission Management

1. **Document custom roles**: Keep track of why custom roles were created

2. **Test permissions**: Create test users to verify permission behavior
   ```bash
   kg admin user create test_analyst --role data_analyst --password "TestPass123!"
   ```

3. **Use explicit denies sparingly**: Only use when you need to override inherited permissions

4. **Regular permission reviews**: Audit permissions quarterly
   ```bash
   kg admin rbac permissions list > permissions_$(date +%Y%m%d).txt
   ```

---

## Troubleshooting

### "Permission denied" errors

**Symptom**: User cannot perform an action

**Diagnosis**:
1. Check user's primary role:
   ```bash
   kg admin user get <user_id>
   ```

2. Check role assignments:
   ```bash
   kg admin rbac assign list <user_id>
   ```

3. Check role permissions:
   ```bash
   kg admin rbac permissions list --role <role_name>
   ```

4. Check for explicit denies:
   ```bash
   kg admin rbac permissions list --role <role_name> | grep "✗"
   ```

**Solution**: Grant missing permission or adjust role assignment

### Cannot delete role

**Symptom**: Error when trying to delete a role

**Common causes**:
- Role is builtin (cannot delete)
- Role has assigned users (must remove assignments first)

**Solution**:
```bash
# 1. Find users with this role
kg admin user list --role <role_name>

# 2. Change their role or remove assignment
kg admin user update <user_id> --role <new_role>
# OR
kg admin rbac assign remove <assignment_id>

# 3. Delete the role
kg admin rbac roles delete <role_name>
```

### User locked out

**Symptom**: User cannot login

**Diagnosis**:
1. Check if user is disabled:
   ```bash
   kg admin user get <user_id>
   ```

2. Check if password was recently changed

**Solution**:
```bash
# Enable user
kg admin user update <user_id> --enable

# Reset password
kg admin user update <user_id> --password "NewTempPass123!"
```

### Permission not taking effect

**Symptom**: Granted permission doesn't work

**Common causes**:
- Permission precedence (explicit deny overrides)
- Scope mismatch (global vs instance)
- Resource type mismatch

**Solution**:
1. Check permission precedence order: DENY → Instance → Filter → Global → Inherited
2. Verify resource type spelling matches exactly
3. Check if there's an explicit deny:
   ```bash
   kg admin rbac permissions list --role <role_name> | grep "✗"
   ```

### Lost admin access

**Symptom**: No users have admin role

**Recovery**:
1. Use the initialization script to reset admin account:
   ```bash
   ./scripts/setup/initialize-platform.sh
   ```

2. This will prompt to reset the admin password
3. Login as admin and restore access

---

## API Reference

All RBAC operations are also available via REST API:

```bash
# Resources
GET    /api/rbac/resources
POST   /api/rbac/resources
GET    /api/rbac/resources/{type}
DELETE /api/rbac/resources/{type}

# Roles
GET    /api/rbac/roles
POST   /api/rbac/roles
GET    /api/rbac/roles/{name}
DELETE /api/rbac/roles/{name}

# Permissions
GET    /api/rbac/permissions
POST   /api/rbac/permissions
DELETE /api/rbac/permissions/{id}

# User Role Assignments
GET    /api/rbac/user-roles/{user_id}
POST   /api/rbac/user-roles
DELETE /api/rbac/user-roles/{id}

# Permission Check
POST   /api/rbac/check-permission
```

See API documentation at `http://localhost:8000/docs` for detailed schemas.

---

## See Also

- [ADR-028: Dynamic RBAC](../../architecture/ADR-028-dynamic-rbac-system.md) - Architecture decision record
- [ADR-027: User Management API](../../architecture/ADR-027-user-management-api.md) - Authentication system
- [Authentication Guide](../04-security-and-access/01-AUTHENTICATION.md) - Login and authentication flows
- [API Documentation](../api/) - REST API reference

---

**Version**: 1.0
**Last Updated**: October 2025
**Maintainer**: Knowledge Graph Team
