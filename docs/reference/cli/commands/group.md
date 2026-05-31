# kg group

> Auto-generated

## group (grp)

Manage groups for collaborative access control. Groups allow sharing resources with multiple users. System groups (public, admins) are managed by the platform.

**Usage:**
```bash
kg group [options]
```

**Subcommands:**

- `list` - List all groups
- `members` - List members of a group
- `create` - Create a new group (admin only)
- `add-member` - Add a user to a group (admin only)
- `remove-member` - Remove a user from a group (admin only)

---

### list

List all groups

**Usage:**
```bash
kg list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--no-system` | Exclude system groups (public, admins) | - |

### members

List members of a group

**Usage:**
```bash
kg members <group-id>
```

**Arguments:**

- `<group-id>` - Group ID

### create

Create a new group (admin only)

**Usage:**
```bash
kg create [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-n, --name <name>` | Group name (unique identifier) | - |
| `-d, --display <name>` | Display name | - |
| `--description <text>` | Group description | - |

### add-member

Add a user to a group (admin only)

**Usage:**
```bash
kg add-member <group-id> <user-id>
```

**Arguments:**

- `<group-id>` - Group ID
- `<user-id>` - User ID to add

### remove-member

Remove a user from a group (admin only)

**Usage:**
```bash
kg remove-member <group-id> <user-id>
```

**Arguments:**

- `<group-id>` - Group ID
- `<user-id>` - User ID to remove
