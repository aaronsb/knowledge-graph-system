# kg ontology

Manage ontologies (knowledge domains).

## Usage

```bash
kg ontology|onto [options] [command]
```

**Alias:** `onto`

## Description

The `ontology` command provides management operations for ontologies - named collections that organize concepts into knowledge domains. An ontology groups related documents and concepts together, making it easier to organize and query knowledge by topic or project.

**What is an Ontology?**

An ontology in this system is:
- A **named collection** of documents and concepts
- A **knowledge domain** (e.g., "Research Papers 2024", "Company Docs", "Personal Notes")
- A **namespace** for organizing related knowledge
- An **ingestion target** (documents are ingested into ontologies)

## Options

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

## Subcommands

| Command | Description | Doc |
|---------|-------------|-----|
| `list` | List all ontologies | [↓](#list) |
| `info <name>` | Get detailed information about an ontology | [↓](#info) |
| `files <name>` | List files in an ontology | [↓](#files) |
| `rename <old-name> <new-name>` | Rename an ontology | [↓](#rename) |
| `delete <name>` | Delete an ontology and all its data | [↓](#delete) |

## Command Tree

```
kg ontology (onto)
├── list
├── info <name>
├── files <name>
├── rename <old-name> <new-name>
└── delete <name>
```

---

## Subcommand Details

### list

List all ontologies in the knowledge graph.

**Usage:**
```bash
kg ontology list [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

**What You Get:**

A table showing all ontologies with:
- **Ontology** - Ontology name
- **Files** - Number of source files
- **Chunks** - Number of document chunks
- **Concepts** - Number of concepts extracted

**Examples:**

```bash
# List all ontologies
kg ontology list

# Use alias
kg onto list
```

**Output Example:**

```
📚 Ontologies in Knowledge Graph

────────────────────────────────────────────────────────────────────────────────
Ontology                                 Files      Chunks      Concepts
────────────────────────────────────────────────────────────────────────────────
Research Papers 2024                        12          45           234
Company Documentation                       8          32           156
Personal Notes                              5          18            89
Project XYZ                                 3          12            67
────────────────────────────────────────────────────────────────────────────────

Showing 4 row(s)
```

**Understanding the Columns:**

- **Files** - Number of distinct source documents
- **Chunks** - Number of text chunks (each chunk ~1000 words)
- **Concepts** - Total concepts extracted from all files

**Use Cases:**

- **Overview** - Get a bird's-eye view of all knowledge domains
- **Size Estimation** - Understand how much content is in each ontology
- **Organization** - See how knowledge is distributed across domains
- **Verification** - Confirm ingestion added content to correct ontology

**Tips:**

```bash
# Save list for comparison
kg ontology list > ontologies-$(date +%Y%m%d).txt

# Count total ontologies
kg ontology list | grep -c "^[^─]"
```

---

### info

Get detailed information about a specific ontology.

**Usage:**
```bash
kg ontology info [options] <name>
```

**Arguments:**
- `<name>` - Ontology name

**Options:**

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

**What You Get:**

1. **Statistics**
   - Files count
   - Chunks count
   - Concepts count
   - Evidence instances count
   - Relationships count

2. **Files List**
   - All source files in the ontology

**Examples:**

```bash
# Get ontology info
kg ontology info "Research Papers 2024"

# Use alias
kg onto info "Personal Notes"

# With quotes if name has spaces
kg ontology info "Project XYZ"
```

**Output Example:**

```
────────────────────────────────────────────────────────────────────────────────
📖 Ontology: Research Papers 2024
────────────────────────────────────────────────────────────────────────────────

Statistics
  Files: 12
  Chunks: 45
  Concepts: 234
  Evidence: 456
  Relationships: 389

Files
────────────────────────────────────────────────────────────────────────────────
  ● attention-is-all-you-need.pdf
  ● bert-pretraining.pdf
  ● gpt-3-paper.pdf
  ● transformer-xl.pdf
  ... (8 more)

────────────────────────────────────────────────────────────────────────────────
```

**Understanding Statistics:**

- **Files** - Source documents
- **Chunks** - Text segments processed
- **Concepts** - Core ideas extracted
- **Evidence** - Supporting quotes/instances
- **Relationships** - Concept-to-concept edges

**Use Cases:**

- **Detailed View** - Understand ontology composition
- **Verification** - Confirm expected files are present
- **Size Analysis** - See how much data is in an ontology
- **Troubleshooting** - Verify ingestion completed successfully

**Tips:**

```bash
# Check if specific file was ingested
kg ontology info "My Docs" | grep "filename.txt"

# Count relationships per concept
kg ontology info "My Docs" | awk '/Relationships:/ {rel=$2} /Concepts:/ {con=$2; print rel/con " relationships per concept"}'
```

---

### files

List files in a specific ontology with per-file statistics.

**Usage:**
```bash
kg ontology files [options] <name>
```

**Arguments:**
- `<name>` - Ontology name

**Options:**

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

**What You Get:**

For each file in the ontology:
- **File path** - Original file path
- **Chunks** - Number of chunks from this file
- **Concepts** - Number of concepts extracted from this file

**Examples:**

```bash
# List files in ontology
kg ontology files "Research Papers 2024"

# Use alias
kg onto files "Personal Notes"
```

**Output Example:**

```
────────────────────────────────────────────────────────────────────────────────
📁 Files in: Research Papers 2024
────────────────────────────────────────────────────────────────────────────────

✓ Found 12 files:

attention-is-all-you-need.pdf
  Chunks: 8
  Concepts: 42

bert-pretraining.pdf
  Chunks: 6
  Concepts: 31

gpt-3-paper.pdf
  Chunks: 12
  Concepts: 67

transformer-xl.pdf
  Chunks: 5
  Concepts: 28

... (8 more files)

────────────────────────────────────────────────────────────────────────────────
```

**Understanding Output:**

- **File path** - May show original path or temporary path (for text ingestion)
- **Chunks** - Indicates document length (1 chunk ≈ 1000 words)
- **Concepts** - Shows extraction density

**Typical Ratios:**
- Small document: 1-3 chunks, 5-15 concepts
- Medium document: 4-10 chunks, 20-50 concepts
- Large document: 10+ chunks, 50+ concepts

**Use Cases:**

- **File-Level Analysis** - See which files contributed most concepts
- **Verification** - Confirm specific files are present
- **Re-Ingestion Decisions** - Identify files that may need re-processing
- **Debugging** - Check if file was ingested successfully

**Tips:**

```bash
# Find largest contributor
kg ontology files "My Docs" | grep "Concepts:" | sort -t: -k2 -n | tail -1

# Find files with low extraction
kg ontology files "My Docs" | grep -B1 "Concepts: [0-5]$"
```

---

### rename

Rename an ontology while preserving all its data.

**Usage:**
```bash
kg ontology rename [options] <old-name> <new-name>
```

**Arguments:**
- `<old-name>` - Current ontology name
- `<new-name>` - New ontology name

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-y, --yes` | Skip confirmation prompt | requires confirmation |
| `-h, --help` | Display help for command | - |

**Behavior:**

1. Validates old ontology exists
2. Checks new name is not already taken
3. Prompts for confirmation (unless `-y` flag)
4. Renames ontology in database
5. Preserves all concepts, sources, relationships

**Examples:**

```bash
# Rename with confirmation
kg ontology rename "Old Name" "New Name"

# Skip confirmation
kg ontology rename -y "Old Name" "New Name"

# Use alias
kg onto rename "Research 2023" "Research 2023 Archive"
```

**Interactive Confirmation:**

```
About to rename ontology:
  From: "Research 2023"
  To:   "Research 2023 Archive"

This will:
  - Update ontology name for 45 concepts
  - Update 12 source files
  - Preserve all relationships

Continue? [y/N]:
```

**Success Output:**

```
✓ Ontology renamed successfully
  From: "Research 2023"
  To:   "Research 2023 Archive"

Updated:
  - 45 concepts
  - 12 source files
  - 0 relationships (no change needed)
```

**Error Cases:**

```bash
# Old ontology doesn't exist
kg ontology rename "NonExistent" "NewName"
# Error: Ontology "NonExistent" not found

# New name already exists
kg ontology rename "OldName" "ExistingName"
# Error: Ontology "ExistingName" already exists
```

**Use Cases:**

- **Reorganization** - Restructure ontology naming scheme
- **Archiving** - Rename old ontologies to "Archive" suffix
- **Typo Correction** - Fix spelling mistakes in names
- **Clarity** - Make ontology names more descriptive

**Safety:**

- Non-destructive operation (preserves all data)
- Atomic transaction (all or nothing)
- Confirmation required by default
- Validates both old and new names

**Tips:**

```bash
# Archive old ontologies
for onto in $(kg ontology list | grep "2023" | awk '{print $1}'); do
  kg ontology rename -y "$onto" "$onto Archive"
done

# Batch rename with prefix
kg ontology rename -y "Notes" "Personal: Notes"
kg ontology rename -y "Research" "Personal: Research"
```

---

### delete

Delete an ontology and **ALL** its data. **Destructive operation.**

**Usage:**
```bash
kg ontology delete [options] <name>
```

**Arguments:**
- `<name>` - Ontology name

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-f, --force` | Skip confirmation and force deletion | requires confirmation |
| `-h, --help` | Display help for command | - |

**Behavior:**

1. Validates ontology exists
2. Shows what will be deleted
3. Requires double confirmation (unless `-f` flag)
4. Deletes:
   - All concepts in ontology
   - All source files
   - All evidence instances
   - All relationships involving concepts
5. **CANNOT BE UNDONE**

**Examples:**

```bash
# Delete with confirmation
kg ontology delete "Old Project"

# Force delete without confirmation
kg ontology delete -f "Test Ontology"

# Use alias
kg onto delete "Temporary Data"
```

**Interactive Confirmation:**

```
⚠ WARNING: This will DELETE the following ontology:

Name: "Research 2023"

This will permanently delete:
  - 234 concepts
  - 12 source files
  - 456 evidence instances
  - 389 relationships

This action CANNOT be undone.

Type the ontology name to confirm deletion:
```

**After Confirmation:**

```
Deleting ontology "Research 2023"...

✓ Deleted 234 concepts
✓ Deleted 12 source files
✓ Deleted 456 evidence instances
✓ Deleted 389 relationships

Ontology "Research 2023" has been deleted.
```

**Force Mode (`-f` flag):**

```bash
kg ontology delete -f "Test"
# Deletes immediately without confirmation
# ⚠ USE WITH CAUTION
```

**Error Cases:**

```bash
# Ontology doesn't exist
kg ontology delete "NonExistent"
# Error: Ontology "NonExistent" not found

# Wrong confirmation text
kg ontology delete "My Ontology"
# Type the ontology name to confirm deletion: Wrong Name
# Error: Confirmation failed. Deletion cancelled.
```

**Use Cases:**

- **Remove Test Data** - Clean up test ontologies
- **Delete Old Projects** - Remove outdated knowledge domains
- **Start Fresh** - Clear ontology for re-ingestion
- **Free Space** - Remove unused ontologies

**Safety Features:**

- Double confirmation required (unless `-f` flag)
- Shows exactly what will be deleted
- Requires exact name match for confirmation
- Cannot delete non-existent ontology
- Atomic operation (all or nothing)

**⚠️ DANGER ZONE:**

```bash
# Delete ALL ontologies (DANGEROUS!)
# ❌ DO NOT USE IN PRODUCTION
for onto in $(kg ontology list | grep -v "^─" | awk 'NR>2 {print $1}'); do
  kg ontology delete -f "$onto"
done

# Instead, use kg admin reset if you want to wipe everything
```

**Recovery:**

**Cannot recover deleted ontology.** To restore:
1. Re-ingest original documents
2. Extraction may differ slightly
3. New concept IDs will be generated

**Alternatives to Deletion:**

Before deleting, consider:
- **Rename** - Add "Archive" suffix instead
- **Export** - Dump data first (future feature)
- **Selective cleanup** - Delete specific files instead

---

## Common Use Cases

### Organize Knowledge by Domain

```bash
# Create ontologies via ingestion
kg ingest file -o "AI Research" paper1.pdf
kg ingest file -o "Company Docs" handbook.pdf
kg ingest directory -o "Personal Notes" ./notes/

# View organization
kg ontology list
```

### Verify Ingestion Success

```bash
# Before ingestion
kg ontology info "Research Papers"
# Concepts: 100

# Ingest new document
kg ingest file -o "Research Papers" new-paper.pdf -w

# After ingestion
kg ontology info "Research Papers"
# Concepts: 125 (+25)
```

### Archive Old Projects

```bash
# Rename to archive
kg ontology rename "Project 2023" "Project 2023 Archive"

# Or delete if no longer needed
kg ontology delete "Project 2023"
```

### Find Files That Need Re-Ingestion

```bash
# List files with low concept extraction
kg ontology files "My Docs" | grep -B1 "Concepts: [0-5]$"

# These may have been empty or failed to extract
```

### Reorganize Ontology Structure

```bash
# Before: Single ontology
kg ontology list
# "All Research" (1000 concepts)

# After: Split by topic
kg ingest directory --directories-as-ontologies ./research/
kg ontology list
# "Machine Learning" (300 concepts)
# "Computer Vision" (250 concepts)
# "NLP" (450 concepts)
```

---

## Scripting and Automation

### Backup Ontology Names Before Deletion

```bash
#!/bin/bash
# backup-ontology-list.sh

kg ontology list > "ontologies-backup-$(date +%Y%m%d-%H%M%S).txt"
echo "Backup saved"
```

### Monitor Ontology Growth

```bash
#!/bin/bash
# monitor-ontology.sh

ONTOLOGY=$1

while true; do
  clear
  echo "=== Monitoring: $ONTOLOGY ==="
  echo "Timestamp: $(date)"
  echo ""
  kg ontology info "$ONTOLOGY"
  sleep 60
done
```

### Batch Delete Test Ontologies

```bash
#!/bin/bash
# cleanup-test-ontologies.sh

# Delete all ontologies starting with "Test"
kg ontology list | grep "^Test" | awk '{print $1}' | while read onto; do
  echo "Deleting: $onto"
  kg ontology delete -f "$onto"
done
```

### Verify Ingestion Pipeline

```bash
#!/bin/bash
# verify-ingestion.sh

ONTOLOGY=$1
FILE=$2

# Capture before state
BEFORE=$(kg ontology info "$ONTOLOGY" 2>/dev/null | grep "Concepts:" | awk '{print $2}')
if [ -z "$BEFORE" ]; then
  BEFORE=0
fi

# Ingest
kg ingest file -o "$ONTOLOGY" -w "$FILE"

# Capture after state
AFTER=$(kg ontology info "$ONTOLOGY" | grep "Concepts:" | awk '{print $2}')

# Report
echo "Concepts added: $((AFTER - BEFORE))"
```

---

## Understanding Ontologies

### Ontology Naming Guidelines

**Good Ontology Names:**
- Descriptive: "AI Research Papers 2024"
- Project-based: "Project XYZ Documentation"
- Topic-based: "Machine Learning Concepts"
- Personal: "Meeting Notes"

**Avoid:**
- Single words: "Data" (too vague)
- Versions in names: "Docs v2" (use rename instead)
- Special characters: "Docs/Notes" (may cause issues)

### When to Create Multiple Ontologies

Create separate ontologies when:
- **Different topics** - "Chemistry" vs "Physics"
- **Different projects** - "Project A" vs "Project B"
- **Different time periods** - "2023 Research" vs "2024 Research"
- **Different sources** - "Internal Docs" vs "Public Papers"

Keep in one ontology when:
- Related topics that benefit from cross-referencing
- Same project or knowledge domain
- Documents that reference each other

### Ontology Size Considerations

**Small Ontology (1-10 files, <100 concepts):**
- Fast queries
- Easy to manage
- Good for focused topics

**Medium Ontology (10-50 files, 100-500 concepts):**
- Balanced performance
- Good cross-referencing
- Most common size

**Large Ontology (50+ files, 500+ concepts):**
- Rich interconnections
- Slower queries (marginal)
- Consider splitting if unrelated topics

---

## Troubleshooting

### Ontology Not Found

**Symptom:**
```bash
kg ontology info "MyOntology"
# Error: Ontology "MyOntology" not found
```

**Causes:**

1. **Typo in name** - Names are case-sensitive
   ```bash
   kg ontology list  # Check exact spelling
   ```

2. **Ontology never created** - Created during ingestion
   ```bash
   # Create by ingesting
   kg ingest file -o "MyOntology" document.txt
   ```

### No Concepts in Ontology

**Symptom:**
```bash
kg ontology info "MyOntology"
# Concepts: 0
```

**Causes:**

1. **Ingestion failed** - Check job status
   ```bash
   kg job list failed
   kg job status <job-id>
   ```

2. **Document had no extractable content**
   ```bash
   # Try with different document
   kg ingest file -o "MyOntology" -f better-document.txt
   ```

3. **Extraction model issues**
   ```bash
   kg admin extraction status
   kg admin extraction test
   ```

### Cannot Delete Ontology

**Symptom:**
```bash
kg ontology delete "MyOntology"
# Error: Cannot delete ontology
```

**Solutions:**

1. **Use force flag**
   ```bash
   kg ontology delete -f "MyOntology"
   ```

2. **Check exact name**
   ```bash
   kg ontology list  # Copy exact name
   ```

### Rename Fails

**Symptom:**
```bash
kg ontology rename "Old" "New"
# Error: Ontology "New" already exists
```

**Solutions:**

1. **Choose different name**
   ```bash
   kg ontology rename "Old" "New2"
   ```

2. **Delete conflicting ontology first** (if safe)
   ```bash
   kg ontology delete "New"
   kg ontology rename "Old" "New"
   ```

---

## Related Commands

- [`kg ingest`](../ingest/) - Ingest documents into ontologies
- [`kg database stats`](../database/#stats) - System-wide statistics (includes all ontologies)
- [`kg search query`](../search/#query) - Search across ontologies
- [`kg admin reset`](../admin/#reset) - Delete ALL ontologies and data

---

## See Also

- [Ingestion Guide](../../01-getting-started/ingestion.md)
- [Ontology Management](../../06-reference/ontologies.md)
- [Knowledge Organization](../../02-concepts/knowledge-organization.md)
