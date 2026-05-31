# kg program

> Auto-generated

## program (prog)

Validate, store, and retrieve GraphProgram ASTs (ADR-500). Programs are notarized server-side to ensure safety before execution.

**Usage:**
```bash
kg program [options]
```

**Subcommands:**

- `validate` - Validate a program without storing it (dry run)
- `create` - Notarize and store a program
- `show` - Show a notarized program
- `execute` - Execute a program server-side

---

### validate

Validate a program without storing it (dry run)

**Usage:**
```bash
kg validate <file>
```

**Arguments:**

- `<file>` - JSON file path (use - for stdin)

### create

Notarize and store a program

**Usage:**
```bash
kg create <file>
```

**Arguments:**

- `<file>` - JSON file path (use - for stdin)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-n, --name <name>` | Program name | - |

### show

Show a notarized program

**Usage:**
```bash
kg show <id>
```

**Arguments:**

- `<id>` - Program ID

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output raw JSON | - |

### execute

Execute a program server-side

**Usage:**
```bash
kg execute <source>
```

**Arguments:**

- `<source>` - Program ID (number) or JSON file path (use - for stdin)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--json` | Output raw JSON | - |
| `--log-only` | Show only the execution log, not the graph | - |
