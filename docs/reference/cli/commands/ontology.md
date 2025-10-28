# kg ontology

> Auto-generated

## ontology (onto)

Manage ontologies (knowledge domains)

**Usage:**
```bash
kg ontology [options]
```

**Subcommands:**

- `list` - List all ontologies
- `info` - Get detailed information about an ontology
- `files` - List files in an ontology
- `rename` - Rename an ontology
- `delete` - Delete an ontology and all its data

---

### list

List all ontologies

**Usage:**
```bash
kg list [options]
```

### info

Get detailed information about an ontology

**Usage:**
```bash
kg info <name>
```

**Arguments:**

- `<name>` - Ontology name

### files

List files in an ontology

**Usage:**
```bash
kg files <name>
```

**Arguments:**

- `<name>` - Ontology name

### rename

Rename an ontology

**Usage:**
```bash
kg rename <old-name> <new-name>
```

**Arguments:**

- `<old-name>` - Current ontology name
- `<new-name>` - New ontology name

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-y, --yes` | Skip confirmation prompt | - |

### delete

Delete an ontology and all its data

**Usage:**
```bash
kg delete <name>
```

**Arguments:**

- `<name>` - Ontology name

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Skip confirmation and force deletion | - |
