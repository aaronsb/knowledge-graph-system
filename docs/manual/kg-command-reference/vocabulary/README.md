# kg vocabulary

Edge vocabulary management and consolidation.

## Usage

```bash
kg vocabulary|vocab [options] [command]
```

**Alias:** `vocab`

## Description

The `vocabulary` command manages the edge relationship vocabulary - the types of relationships that can exist between concepts in the knowledge graph. This includes:

- **Builtin types** - Predefined relationship types (30 types)
- **Custom types** - LLM-extracted types from documents (emerges naturally)
- **Categories** - Semantic groupings (causation, logical, temporal, etc.)
- **Consolidation** - AI-assisted merging of synonymous types (ADR-032)
- **Auto-categorization** - Probabilistic category assignment via embeddings (ADR-047)

**Key Features:**

1. **Dynamic Vocabulary** - Grows as documents introduce new relationship types
2. **AITL Consolidation** - AI-in-the-loop workflow for controlled merging
3. **Zone-Based Management** - GREEN/WATCH/DANGER/EMERGENCY zones (ADR-032)
4. **Probabilistic Categorization** - Embedding-based category inference (ADR-047)
5. **LLM-Determined Direction** - Semantic orientation of relationships (ADR-049)

## Options

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

## Subcommands

| Command | Description | Doc |
|---------|-------------|-----|
| `status` | Show current vocabulary status and zone | [↓](#status) |
| `list` | List all edge types with statistics | [↓](#list) |
| `consolidate` | AI-assisted vocabulary consolidation workflow (AITL) | [↓](#consolidate) |
| `merge <deprecated-type> <target-type>` | Manually merge one edge type into another | [↓](#merge) |
| `generate-embeddings` | Generate embeddings for vocabulary types | [↓](#generate-embeddings) |
| `category-scores <type>` | Show category similarity scores for a relationship type | [↓](#category-scores) |
| `refresh-categories` | Refresh category assignments for vocabulary types | [↓](#refresh-categories) |

## Command Tree

```
kg vocabulary (vocab)
├── status
├── list
├── consolidate
├── merge <deprecated-type> <target-type>
├── generate-embeddings
├── category-scores <type>
└── refresh-categories
```

---

## Subcommand Details

### status

Show current vocabulary status including size, zone, and thresholds.

**Usage:**
```bash
kg vocabulary status [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

**What You Get:**

1. **Current State**
   - Vocabulary Size (total active types)
   - Zone (GREEN, WATCH, DANGER, EMERGENCY)
   - Aggressiveness (percentage above minimum)
   - Profile (conservative/aggressive)

2. **Thresholds** (ADR-032)
   - Minimum (30)
   - Maximum (90)
   - Emergency (200)

3. **Edge Types Breakdown**
   - Builtin count
   - Custom count
   - Categories count

**Examples:**

```bash
# Check vocabulary status
kg vocabulary status

# Use alias
kg vocab status
```

**Output Example:**

```
────────────────────────────────────────────────────────────────────────────────
📚 Vocabulary Status
────────────────────────────────────────────────────────────────────────────────

Current State
  Vocabulary Size: 55
  Zone: ⚠ WATCH
  Aggressiveness: 40.8%
  Profile: aggressive

Thresholds
  Minimum: 30
  Maximum: 90
  Emergency: 200

Edge Types
  Builtin: 30
  Custom: 25
  Categories: 11

────────────────────────────────────────────────────────────────────────────────
```

**Understanding Zones** (ADR-032):

| Zone | Range | Meaning | Action |
|------|-------|---------|--------|
| **GREEN** | 30-50 | Healthy vocabulary size | Normal operation |
| **WATCH** | 51-90 | Growing vocabulary | Consider consolidation |
| **DANGER** | 91-199 | Bloated vocabulary | Consolidation recommended |
| **EMERGENCY** | 200+ | Vocabulary explosion | Immediate consolidation required |

**Aggressiveness:**
- Measures how far vocabulary has grown above minimum (30)
- Formula: `(size - min) / (max - min) * 100%`
- Higher percentage = more aggressive consolidation recommended

**Use Cases:**

- **Health Check** - Monitor vocabulary growth
- **Pre-Consolidation** - Check zone before consolidating
- **Tracking** - Monitor vocabulary size over time
- **Alerting** - Trigger consolidation workflows

**Tips:**

```bash
# Track vocabulary growth
echo "$(date): $(kg vocab status | grep 'Vocabulary Size')" >> vocab-growth.log

# Check if consolidation needed
if kg vocab status | grep -q "DANGER\|EMERGENCY"; then
  echo "Consolidation recommended!"
fi
```

---

### list

List all edge types with statistics, categories, and confidence scores.

**Usage:**
```bash
kg vocabulary list [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--inactive` | Include inactive/deprecated types | excludes inactive |
| `--no-builtin` | Exclude builtin types | includes builtin |
| `-h, --help` | Display help for command | - |

**What You Get:**

For each edge type:
- **TYPE** - Relationship type name (colored by semantic)
- **CATEGORY** - Assigned category (composition, causation, etc.)
- **CONF** - Confidence score for category assignment (ADR-047)
- **EDGES** - Number of edges using this type
- **STATUS** - Active status (✓ = active)
- **[B]** flag - Builtin type indicator

**Examples:**

```bash
# List all active types
kg vocabulary list

# Include inactive/deprecated types
kg vocabulary list --inactive

# Show only custom types (exclude builtin)
kg vocabulary list --no-builtin

# Use alias
kg vocab list
```

**Output Example:**

```
────────────────────────────────────────────────────────────────────────────────
📋 Edge Types
────────────────────────────────────────────────────────────────────────────────

Total: 55
Active: 55
Builtin: 30
Custom: 25

───────────────────────────────────────────────────────────────────────────────────
TYPE                      CATEGORY          CONF    EDGES     STATUS
───────────────────────────────────────────────────────────────────────────────────
ADDRESSES                 composition        58%        0          ✓
ALTERNATIVE_TO            semantic           63%        0          ✓
ANALOGOUS_TO              semantic          100%⚠       0          ✓ [B]
BUILDS_ON                 llm_generated      --         1          ✓
CAUSES                    causation         100%⚠       1          ✓ [B]
COMPLEMENTS               composition       100%⚠       0          ✓ [B]
CONTRADICTS               logical           100%⚠       0          ✓ [B]
DEFINES                   semantic           86%⚠       1          ✓ [B]
DEPENDS_ON                dependency        100%⚠       0          ✓ [B]
ENABLES                   causation         100%⚠       0          ✓ [B]
... (45 more types)
───────────────────────────────────────────────────────────────────────────────────
```

**Understanding Columns:**

**TYPE:**
- Colored based on semantic meaning
- Orange/Red = High-impact (CAUSES, CONTRADICTS)
- Blue/Purple = Structural (composition, logical)
- White = Neutral or custom

**CATEGORY:**
- **causation** - Cause/effect relationships (CAUSES, ENABLES, PREVENTS)
- **composition** - Part/whole (CONTAINS, PART_OF, COMPOSED_OF)
- **logical** - Logic (IMPLIES, CONTRADICTS, EQUIVALENT_TO)
- **semantic** - Meaning (SIMILAR_TO, DEFINES, CONTRASTS_WITH)
- **temporal** - Time-based (PRECEDES, FOLLOWS)
- **dependency** - Requirements (REQUIRES, DEPENDS_ON)
- **derivation** - Origin (DERIVED_FROM, RESULTS_FROM)
- **evidential** - Support (SUPPORTS, EVIDENCED_BY)
- **llm_generated** - Custom types from extraction (no category yet)

**CONF (Confidence):**
- Similarity to category seed terms (ADR-047)
- `100%⚠` = Perfect match, may be ambiguous (check runner-up)
- `80-99%` = High confidence
- `60-79%` = Moderate confidence
- `<60%` = Low confidence, review needed
- `--` = No embedding yet (llm_generated types)

**[B] Flag:**
- Indicates builtin type (predefined, not from extraction)

**Use Cases:**

- **Vocabulary Overview** - See all relationship types at a glance
- **Consolidation Candidates** - Identify similar types
- **Category Review** - Verify auto-categorization accuracy
- **Usage Statistics** - Find unused types
- **Quality Audit** - Check confidence scores

**Tips:**

```bash
# Find types with low confidence
kg vocab list | grep -E "[0-5][0-9]%"

# Find unused types (candidates for removal)
kg vocab list | grep " 0 "

# Count custom types
kg vocab list --no-builtin | wc -l

# Find ambiguous types (100% with warning)
kg vocab list | grep "100%⚠"
```

---

### consolidate

AI-assisted vocabulary consolidation workflow (AITL - AI-in-the-loop).

**Usage:**
```bash
kg vocabulary consolidate [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-t, --target <size>` | Target vocabulary size | `90` |
| `--threshold <value>` | Auto-execute threshold (0.0-1.0) | `0.90` |
| `--dry-run` | Evaluate candidates without executing merges | `false` |
| `--auto` | Auto-execute high confidence merges (AITL mode) | `false` |
| `-h, --help` | Display help for command | - |

**How It Works** (ADR-032):

1. **Analyze Vocabulary** - Compare all types via embeddings
2. **Identify Candidates** - Find similar pairs above threshold
3. **Present Recommendations** - Show merge suggestions with confidence
4. **Execute or Prompt** - Auto-merge (if `--auto`) or request confirmation
5. **Apply Merges** - Deprecate source, redirect edges to target
6. **Iterate** - Repeat until target size reached or no candidates

**Modes:**

**Interactive (default):**
```bash
kg vocabulary consolidate
# Prompts for each merge
```

**Dry Run:**
```bash
kg vocabulary consolidate --dry-run
# Shows candidates without executing
```

**AITL (Auto):**
```bash
kg vocabulary consolidate --auto
# Auto-executes high confidence merges
```

**Examples:**

```bash
# Interactive consolidation to target 90
kg vocabulary consolidate

# Set custom target size
kg vocabulary consolidate --target 60

# Dry run to see candidates
kg vocabulary consolidate --dry-run

# AITL mode with custom threshold
kg vocabulary consolidate --auto --threshold 0.95

# Use alias
kg vocab consolidate --dry-run
```

**Dry Run Output Example:**

```
────────────────────────────────────────────────────────────────────────────────
🔍 Vocabulary Consolidation (Dry Run)
────────────────────────────────────────────────────────────────────────────────

Current Size: 55
Target Size: 90
Zone: ⚠ WATCH

Merge Candidates (similarity ≥ 0.90):

1. ALTERNATIVE_TO → ANALOGOUS_TO (similarity: 0.95)
   - ALTERNATIVE_TO: 2 edges, semantic, 63% confidence
   - ANALOGOUS_TO: 0 edges, semantic, 100% confidence
   - Recommended: Merge (high similarity, target is builtin)

2. ENFORCES → ENSURES (similarity: 0.92)
   - ENFORCES: 0 edges, causation, 60% confidence
   - ENSURES: 1 edge, llm_generated, -- confidence
   - Recommended: Merge (high similarity, consolidate to stronger type)

3. CONNECTS_TO → LINKS_TO (similarity: 0.91)
   - CONNECTS_TO: 3 edges, composition, 75% confidence
   - LINKS_TO: 1 edge, composition, 68% confidence
   - Recommended: Review (both have edges, verify semantic equivalence)

Total Candidates: 3
Estimated Final Size: 52 (after merges)

[Dry Run - No changes applied]
────────────────────────────────────────────────────────────────────────────────
```

**Interactive Mode Example:**

```
Merge Candidate 1 of 3:
  Source: ALTERNATIVE_TO (2 edges)
  Target: ANALOGOUS_TO (0 edges)
  Similarity: 0.95

Merge this pair? [y/n/skip]:
```

**AITL Mode Output:**

```
AITL Mode: Auto-executing high confidence merges (threshold: 0.90)

✓ Merged: ALTERNATIVE_TO → ANALOGOUS_TO (0.95)
✓ Merged: ENFORCES → ENSURES (0.92)
⏸ Skipped: CONNECTS_TO → LINKS_TO (0.91, requires review)

Results:
  Executed: 2 merges
  Skipped: 1 merge
  New Size: 53

Vocabulary Zone: ⚠ WATCH → ✓ GREEN
```

**Threshold Guidelines:**

| Threshold | Use Case | Risk Level |
|-----------|----------|------------|
| **0.95+** | Very conservative, clear synonyms | Very low |
| **0.90-0.95** | Balanced, AITL recommended | Low |
| **0.85-0.90** | Aggressive, requires review | Moderate |
| **<0.85** | Very aggressive, manual review required | High |

**Use Cases:**

- **Vocabulary Cleanup** - Consolidate redundant types
- **Zone Management** - Bring vocabulary back to GREEN zone
- **Quality Improvement** - Merge similar custom types to builtins
- **Periodic Maintenance** - Run quarterly to prevent bloat

**Safety Features:**

- Similarity threshold prevents false positives
- Dry run mode for preview
- Interactive confirmation by default
- Atomic operations (all or nothing per merge)
- Audit trail (reason, timestamp, user)

**⚠️ Important:**

- **Review ambiguous merges** - 0.90-0.92 similarity may need manual check
- **Check edge counts** - Merging types with many edges affects queries
- **Test after consolidation** - Verify no semantic loss
- **Backup vocabulary** - Capture `kg vocab list` before consolidating

---

### merge

Manually merge one edge type into another (for consolidation or correction).

**Usage:**
```bash
kg vocabulary merge [options] <deprecated-type> <target-type>
```

**Arguments:**
- `<deprecated-type>` - Edge type to deprecate (becomes inactive)
- `<target-type>` - Target edge type to merge into (receives all edges)

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `-r, --reason <text>` | Reason for merge (audit trail) | - |
| `-u, --user <email>` | User performing the merge | `cli-user` |
| `-h, --help` | Display help for command | - |

**Behavior:**

1. Validates both types exist
2. Redirects all edges from deprecated type to target type
3. Marks deprecated type as inactive
4. Records audit trail (reason, user, timestamp)
5. Preserves edge provenance

**Examples:**

```bash
# Basic merge
kg vocabulary merge CONNECTS_TO LINKS_TO

# With reason
kg vocabulary merge ALTERNATIVE_TO ANALOGOUS_TO \
  --reason "Synonym consolidation"

# With user attribution
kg vocabulary merge ENFORCES ENSURES \
  --reason "Semantic duplicate" \
  --user "admin@example.com"

# Use alias
kg vocab merge OLD_TYPE NEW_TYPE --reason "Consolidation"
```

**Output Example:**

```
Merging: CONNECTS_TO → LINKS_TO

Validation:
  ✓ CONNECTS_TO exists (3 edges)
  ✓ LINKS_TO exists (1 edge)

Executing merge...
  ✓ Redirected 3 edges
  ✓ Marked CONNECTS_TO as inactive
  ✓ Recorded audit trail

Result:
  CONNECTS_TO: inactive (0 edges)
  LINKS_TO: active (4 edges)

Reason: Synonym consolidation
User: admin@example.com
Timestamp: 2024-01-15 14:30:22
```

**Use Cases:**

- **Manual Consolidation** - Merge specific type pairs
- **Correction** - Fix misnamed types from extraction
- **Bulk Operations** - Script multiple merges
- **Targeted Cleanup** - Consolidate specific category

**Safety:**

- Non-destructive (edges preserved)
- Atomic transaction
- Audit trail for compliance
- Can be reviewed in inactive types list

**Tips:**

```bash
# Merge all types to a canonical form
kg vocab merge LEADS_TO CAUSES --reason "Canonical form"
kg vocab merge RESULTS_IN CAUSES --reason "Canonical form"
kg vocab merge PRODUCES CAUSES --reason "Canonical form"

# Check result
kg vocab list | grep CAUSES
# CAUSES: now has combined edge count
```

**Error Cases:**

```bash
# Source type doesn't exist
kg vocab merge NONEXISTENT TARGET
# Error: Type "NONEXISTENT" not found

# Target type doesn't exist
kg vocab merge SOURCE NONEXISTENT
# Error: Type "NONEXISTENT" not found

# Merging to itself
kg vocab merge CAUSES CAUSES
# Error: Cannot merge type to itself
```

---

### generate-embeddings

Generate vector embeddings for vocabulary types (required for consolidation and categorization).

**Usage:**
```bash
kg vocabulary generate-embeddings [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--force` | Regenerate ALL embeddings regardless of existing state | `false` |
| `--all` | Process all active types (not just missing) | `false` |
| `-h, --help` | Display help for command | - |

**What It Does:**

1. Identifies types without embeddings
2. Generates embeddings using configured embedding model
3. Stores embeddings for similarity comparison
4. Enables consolidation and auto-categorization

**When to Use:**

- **After Fresh Install** - Bootstrap vocabulary embeddings
- **New Custom Types** - After ingestion introduces new types
- **Model Change** - Regenerate if switching embedding models
- **Inconsistency** - Force regeneration if embeddings corrupted

**Examples:**

```bash
# Generate embeddings for types missing them
kg vocabulary generate-embeddings

# Process all types (update existing)
kg vocabulary generate-embeddings --all

# Force regenerate everything
kg vocabulary generate-embeddings --force

# Use alias
kg vocab generate-embeddings
```

**Output Example:**

```
────────────────────────────────────────────────────────────────────────────────
🔄 Generating Vocabulary Embeddings
────────────────────────────────────────────────────────────────────────────────

Scanning vocabulary...
  Total types: 55
  Missing embeddings: 8
  Will process: 8 types

Generating embeddings...
  ✓ BUILDS_ON (1/8)
  ✓ DECIDES (2/8)
  ✓ DOCUMENTS (3/8)
  ✓ ENHANCES (4/8)
  ✓ ENSURES (5/8)
  ✓ EXEMPLIFIES (6/8)
  ✓ INFLUENCES (7/8)
  ✓ VALIDATES (8/8)

Results:
  Generated: 8
  Failed: 0
  Duration: 3.2s

✓ All types now have embeddings
────────────────────────────────────────────────────────────────────────────────
```

**Performance:**

- ~100-200ms per embedding (OpenAI)
- ~20-50ms per embedding (local models)
- Parallel generation (batches of 10)
- Progress bar for large sets

**Use Cases:**

- **Post-Ingestion** - Generate embeddings for new custom types
- **System Initialization** - First-time vocabulary setup
- **Model Migration** - Regenerate after switching embedding providers
- **Maintenance** - Periodic regeneration for consistency

**Tips:**

```bash
# Check which types need embeddings
kg vocab list | grep "llm_generated"
# These types likely need embeddings

# Generate after ingestion
kg ingest file -o "Docs" document.txt -w
kg vocab generate-embeddings

# Force regeneration with new embedding model
kg admin embedding set --model text-embedding-3-large
kg vocab generate-embeddings --force
```

---

### category-scores

Show category similarity scores for a specific relationship type (ADR-047).

**Usage:**
```bash
kg vocabulary category-scores [options] <type>
```

**Arguments:**
- `<type>` - Relationship type to analyze (e.g., CAUSES, ENABLES)

**Options:**

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

**What You Get:**

1. **Assignment**
   - Assigned category
   - Confidence score
   - Ambiguous flag (if runner-up is close)
   - Runner-up category (if ambiguous)

2. **Similarity to Category Seeds**
   - Scores for all categories (0-100%)
   - Visual bar chart
   - Sorted by similarity (highest first)

**Examples:**

```bash
# Show scores for a type
kg vocabulary category-scores CAUSES

# Check ambiguous type
kg vocabulary category-scores ENABLES

# Use alias
kg vocab category-scores DEFINES
```

**Output Example:**

```
────────────────────────────────────────────────────────────────────────────────
📊 Category Scores: CAUSES
────────────────────────────────────────────────────────────────────────────────

Assignment
  Category: causation
  Confidence: 100%
  Ambiguous: Yes
  Runner-up: derivation (82%)

Similarity to Category Seeds
  causation       100%  ████████████████████
  derivation       82%  ████████████████
  dependency       82%  ████████████████
  composition      81%  ████████████████
  logical          80%  ████████████████
  evidential       80%  ████████████████
  semantic         77%  ███████████████
  temporal         76%  ███████████████
  (3 more categories <70%)

────────────────────────────────────────────────────────────────────────────────
```

**Understanding Output:**

**Confidence:**
- Calculated as: `max_score / second_max_score * 100`
- 100% = Perfect match to category seeds
- High confidence but marked ambiguous = Runner-up is close

**Ambiguous Flag:**
- Set when runner-up is within 20% of winner
- Indicates type could belong to multiple categories
- Review semantics manually

**Use Cases:**

- **Verify Categorization** - Check if auto-assignment makes sense
- **Debug Low Confidence** - Understand why confidence is low
- **Resolve Ambiguity** - Decide between close categories
- **Quality Audit** - Review all types for misassignments

**Tips:**

```bash
# Check all ambiguous types
for type in $(kg vocab list | grep "100%⚠" | awk '{print $1}'); do
  echo "=== $type ==="
  kg vocab category-scores "$type"
done

# Find types in wrong category
kg vocab category-scores TEMPORAL_RELATION
# If top score is not temporal, may be miscategorized
```

---

### refresh-categories

Refresh category assignments for vocabulary types using latest embeddings (ADR-047).

**Usage:**
```bash
kg vocabulary refresh-categories [options]
```

**Options:**

| Option | Description | Default |
|--------|-------------|---------|
| `--computed-only` | Refresh only types with `category_source=computed` | all active types |
| `-h, --help` | Display help for command | - |

**What It Does:**

1. Identifies types needing category refresh
2. Recalculates similarity to all category seeds
3. Assigns best-matching category
4. Updates confidence scores
5. Flags ambiguous assignments

**When to Use:**

- **After Model Change** - Recalculate with new embedding model
- **Category Definition Update** - Refresh after changing seed terms
- **Periodic Maintenance** - Quarterly review of categorization
- **Quality Improvement** - Re-evaluate low confidence assignments

**Examples:**

```bash
# Refresh all active types
kg vocabulary refresh-categories

# Refresh only computed categories (not manual)
kg vocabulary refresh-categories --computed-only

# Use alias
kg vocab refresh-categories
```

**Output Example:**

```
────────────────────────────────────────────────────────────────────────────────
🔄 Refreshing Category Assignments
────────────────────────────────────────────────────────────────────────────────

Scanning vocabulary...
  Total types: 55
  Will refresh: 55 types

Recalculating categories...
  ✓ ADDRESSES: composition → composition (no change)
  ✓ ALTERNATIVE_TO: semantic → semantic (no change)
  ⚠ ENFORCES: causation → dependency (changed!)
  ✓ ENABLES: causation → causation (no change)
  ⚠ TEMPORAL_RELATION: temporal → semantic (changed!)
  ... (50 more types)

Results:
  Refreshed: 55 types
  Changed: 2 assignments
  Unchanged: 53 assignments
  Ambiguous: 8 types
  Duration: 2.8s

Changed Assignments:
  ENFORCES: causation → dependency (confidence: 78%)
  TEMPORAL_RELATION: temporal → semantic (confidence: 62%)

✓ Category assignments refreshed
────────────────────────────────────────────────────────────────────────────────
```

**Understanding Output:**

**No Change:**
- Category assignment confirmed
- Confidence may have changed slightly

**Changed:**
- Category reassigned based on new similarity scores
- Review semantics to verify correctness
- May indicate improved embeddings or seed terms

**Ambiguous:**
- Type has close runner-up category
- Requires manual review
- Use `category-scores` for details

**Use Cases:**

- **Model Migration** - Refresh after changing embedding model
- **Quality Audit** - Periodic review of auto-assignments
- **Seed Update** - Recalculate after changing category definitions
- **Inconsistency Fix** - Correct miscategorizations

**Safety:**

- Non-destructive (doesn't affect edges)
- Preserves manual assignments (unless `--force` added in future)
- Atomic operation per type
- Audit trail recorded

**Tips:**

```bash
# Refresh after model change
kg admin embedding set --model text-embedding-3-large
kg vocab generate-embeddings --force
kg vocab refresh-categories

# Check changed assignments
kg vocab refresh-categories | grep "changed!"

# Focus on low confidence types
kg vocab list | grep "[0-5][0-9]%" > low-confidence.txt
# Review these manually
kg vocab refresh-categories --computed-only
```

---

## Common Use Cases

### Monitor Vocabulary Health

```bash
# Check status regularly
kg vocab status

# If in WATCH/DANGER, consolidate
if kg vocab status | grep -q "DANGER\|EMERGENCY"; then
  kg vocab consolidate --dry-run
fi
```

### Consolidate Redundant Types

```bash
# Review candidates
kg vocab consolidate --dry-run

# Run interactive consolidation
kg vocab consolidate

# Or auto-execute high confidence
kg vocab consolidate --auto --threshold 0.92
```

### Bootstrap New Installation

```bash
# After first ingestion
kg ingest file -o "Test" document.txt -w

# Generate embeddings for new types
kg vocab generate-embeddings

# Categorize types
kg vocab refresh-categories

# Check results
kg vocab list
```

### Fix Miscategorized Types

```bash
# Find low confidence assignments
kg vocab list | grep "[0-5][0-9]%"

# Check specific type
kg vocab category-scores TEMPORAL_RELATION

# Refresh if needed
kg vocab refresh-categories --computed-only
```

### Merge Similar Custom Types

```bash
# Find synonyms
kg vocab consolidate --dry-run

# Merge manually
kg vocab merge CONNECTS_TO LINKS_TO \
  --reason "Synonym found during consolidation"

# Verify
kg vocab list | grep -E "CONNECTS_TO|LINKS_TO"
```

---

## Understanding the Vocabulary System

### Vocabulary Lifecycle

```
Document Ingestion
  ↓
LLM Extracts Relationships
  ↓
New Edge Types Created (llm_generated)
  ↓
Generate Embeddings (kg vocab generate-embeddings)
  ↓
Auto-Categorize (kg vocab refresh-categories)
  ↓
Review & Consolidate (kg vocab consolidate)
  ↓
Stable Vocabulary
```

### Zone-Based Management (ADR-032)

**GREEN Zone (30-50 types):**
- Healthy vocabulary size
- Good semantic coverage
- Easy to understand
- **Action:** None needed

**WATCH Zone (51-90 types):**
- Growing vocabulary
- Some redundancy likely
- Still manageable
- **Action:** Consider consolidation

**DANGER Zone (91-199 types):**
- Vocabulary bloat
- High redundancy
- Harder to query
- **Action:** Consolidation recommended

**EMERGENCY Zone (200+ types):**
- Vocabulary explosion
- System degradation risk
- Query confusion
- **Action:** Immediate consolidation required

### Category System (ADR-047)

**11 Semantic Categories:**

1. **causation** - Cause/effect (CAUSES, ENABLES, PREVENTS)
2. **composition** - Part/whole (CONTAINS, PART_OF, COMPOSED_OF)
3. **logical** - Logic (IMPLIES, CONTRADICTS, EQUIVALENT_TO)
4. **semantic** - Meaning (SIMILAR_TO, DEFINES, CONTRASTS_WITH)
5. **temporal** - Time (PRECEDES, FOLLOWS, CONCURRENT_WITH)
6. **dependency** - Requirements (REQUIRES, DEPENDS_ON, CONSUMES)
7. **derivation** - Origin (DERIVED_FROM, RESULTS_FROM)
8. **evidential** - Support (SUPPORTS, EVIDENCED_BY, CONTRADICTS)
9. **procedural** - Process (LEADS_TO, TRANSITIONS_TO)
10. **attribution** - Ownership (CREATED_BY, AUTHORED_BY)
11. **llm_generated** - Uncategorized custom types

**Probabilistic Assignment:**
- Compare type embedding to category seed embeddings
- Assign to highest similarity category
- Calculate confidence score
- Flag ambiguous (runner-up within 20%)

---

## Scripting and Automation

### Periodic Vocabulary Maintenance

```bash
#!/bin/bash
# vocab-maintenance.sh

echo "=== Vocabulary Maintenance ==="

# Check status
echo "Current status:"
kg vocab status

# Check zone
ZONE=$(kg vocab status | grep "Zone:" | awk '{print $2}')

if [[ "$ZONE" == "DANGER" || "$ZONE" == "EMERGENCY" ]]; then
  echo "⚠ Consolidation recommended"

  # Dry run first
  kg vocab consolidate --dry-run

  # Prompt user
  read -p "Execute consolidation? [y/N]: " CONFIRM
  if [[ "$CONFIRM" == "y" ]]; then
    kg vocab consolidate --auto --threshold 0.92
  fi
fi

echo "✓ Maintenance complete"
```

### Post-Ingestion Vocabulary Processing

```bash
#!/bin/bash
# post-ingest-vocab.sh

FILE=$1
ONTOLOGY=$2

echo "=== Ingesting $FILE ==="
kg ingest file -o "$ONTOLOGY" -w "$FILE"

echo "=== Generating embeddings for new types ==="
kg vocab generate-embeddings

echo "=== Refreshing categories ==="
kg vocab refresh-categories --computed-only

echo "=== Final vocabulary status ==="
kg vocab status
```

### Find and Merge Synonyms

```bash
#!/bin/bash
# merge-synonyms.sh

# Get merge candidates
kg vocab consolidate --dry-run > /tmp/candidates.txt

# Extract pairs with similarity ≥ 0.95
grep "similarity: 0.9[5-9]" /tmp/candidates.txt | while read line; do
  SOURCE=$(echo "$line" | awk -F'→' '{print $1}' | xargs)
  TARGET=$(echo "$line" | awk -F'→' '{print $2}' | awk '{print $1}')
  SIMILARITY=$(echo "$line" | grep -oP 'similarity: \K[0-9.]+')

  echo "Merge: $SOURCE → $TARGET ($SIMILARITY)"
  read -p "Confirm? [y/N]: " CONFIRM

  if [[ "$CONFIRM" == "y" ]]; then
    kg vocab merge "$SOURCE" "$TARGET" \
      --reason "High similarity ($SIMILARITY) synonym consolidation"
  fi
done
```

---

## Troubleshooting

### No Embeddings for Types

**Symptom:**
```bash
kg vocab list
# llm_generated types with -- confidence
```

**Solution:**
```bash
kg vocab generate-embeddings
```

### Low Confidence Assignments

**Symptom:**
```bash
kg vocab list | grep "[0-5][0-9]%"
# Many types with <60% confidence
```

**Causes & Solutions:**

1. **Ambiguous type name**
   ```bash
   kg vocab category-scores AMBIGUOUS_TYPE
   # Review semantics, may need manual categorization
   ```

2. **Wrong embedding model**
   ```bash
   # Switch to better model
   kg admin embedding set --model text-embedding-3-large
   kg vocab generate-embeddings --force
   kg vocab refresh-categories
   ```

### Vocabulary in DANGER Zone

**Symptom:**
```bash
kg vocab status
# Zone: ⚠ DANGER
```

**Solution:**
```bash
# Review candidates
kg vocab consolidate --dry-run

# Execute consolidation
kg vocab consolidate --auto --threshold 0.92
```

### Merge Failed

**Symptom:**
```bash
kg vocab merge SOURCE TARGET
# Error: Type "SOURCE" not found
```

**Solutions:**

1. **Check type exists**
   ```bash
   kg vocab list | grep SOURCE
   ```

2. **Check exact spelling (case-sensitive)**
   ```bash
   kg vocab list | grep -i source
   ```

3. **Type may be inactive**
   ```bash
   kg vocab list --inactive | grep SOURCE
   ```

---

## Related Commands

- [`kg database stats`](../database/#stats) - Shows relationship type distribution
- [`kg search related`](../search/#related) - Uses vocabulary types for filtering
- [`kg admin embedding`](../admin/#embedding) - Configure embedding model
- [`kg ingest`](../ingest/) - Introduces new vocabulary types

---

## See Also

- [ADR-032: AITL Vocabulary Consolidation](../../../architecture/ADR-032-vocabulary-consolidation-ai-in-the-loop.md)
- [ADR-047: Probabilistic Vocabulary Categorization](../../../architecture/ADR-047-probabilistic-vocabulary-categorization.md)
- [ADR-049: LLM-Determined Relationship Direction](../../../architecture/ADR-049-llm-determined-relationship-direction.md)
- [Vocabulary Management Guide](../../06-reference/vocabulary-management.md)
- [Graph Relationships](../../02-concepts/relationships.md)
