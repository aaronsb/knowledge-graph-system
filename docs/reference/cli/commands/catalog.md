# kg catalog

> Auto-generated

## catalog

Deterministic, filesystem-like browse of what is stored in the knowledge graph. Walk from ontologies down to documents and concepts, filter by name fragment, and inspect single nodes. Distinct from "kg search" (semantic) and "kg storage" (raw S3 admin). Add --json to any subcommand for machine-readable output.

**Usage:**
```bash
kg catalog [options]
```

**Subcommands:**

- `ls` - List children of a node, or root ontologies if no id given
- `stat` - Show full metadata for a single catalog node

---

### ls

List children of a node, or root ontologies if no id given

**Usage:**
```bash
kg ls [id]
```

**Arguments:**

- `<id>` - Parent node id (ontology or document). Omit to list ontologies.

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-k, --kind <kind>` | Parent kind hint (ontology|document) if id is ambiguous | - |
| `-q, --query <fragment>` | Filter children by case-insensitive name fragment | - |
| `-s, --sort <field>` | Sort: name | child_count | created | `"name"` |
| `-l, --limit <n>` | Max results | `"100"` |
| `-o, --offset <n>` | Pagination offset | `"0"` |
| `--json` | Output raw JSON instead of formatted text for scripting | - |

### stat

Show full metadata for a single catalog node

**Usage:**
```bash
kg stat <id>
```

**Arguments:**

- `<id>` - Node id (ontology_id, document_id, or concept_id)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-k, --kind <kind>` | Disambiguate kind if id collides across kinds | - |
| `--json` | Output raw JSON instead of formatted text for scripting | - |
