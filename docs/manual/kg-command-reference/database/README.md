# kg database

Database operations and information.

## Usage

```bash
kg database|db [options] [command]
```

**Alias:** `db`

## Description

The `database` command provides information and health checks for the PostgreSQL + Apache AGE database backend. It offers three types of queries:

1. **stats** - Comprehensive statistics about graph contents
2. **info** - Database connection and version information
3. **health** - Health checks and connectivity status

These commands are read-only and provide observability into the database state.

## Options

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

## Subcommands

| Command | Description | Doc |
|---------|-------------|-----|
| `stats` | Show database statistics | [↓](#stats) |
| `info` | Show database connection information | [↓](#info) |
| `health` | Check database health and connectivity | [↓](#health) |

## Command Tree

```
kg database (db)
├── stats
├── info
└── health
```

---

## Subcommand Details

### stats

Show comprehensive database statistics including node counts and relationship breakdown.

**Usage:**
```bash
kg database stats [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

**What You Get:**

1. **Node Counts**
   - **Concepts** - Total concept nodes in the graph
   - **Sources** - Total source document nodes
   - **Instances** - Total evidence instance nodes

2. **Relationship Statistics**
   - **Total** - Overall relationship count
   - **By Type** - Breakdown showing count for each relationship type (IMPLIES, SUPPORTS, CAUSES, etc.)

**Examples:**

```bash
# Show database stats
kg database stats

# Use db alias
kg db stats
```

**Output Example:**

```
────────────────────────────────────────────────────────────────────────────────
📊 Database Statistics
────────────────────────────────────────────────────────────────────────────────

Nodes
  Concepts: 1,234
  Sources: 45
  Instances: 2,456

Relationships
  Total: 3,567

By Type
  SUPPORTS: 456
  IMPLIES: 398
  CATEGORIZED_AS: 234
  REQUIRES: 178
  CAUSES: 145
  INFLUENCES: 123
  CONTAINS: 98
  DEFINES: 87
  ... (additional types)

────────────────────────────────────────────────────────────────────────────────
```

**Understanding the Numbers:**

**Node Types:**
- **Concepts** - Core ideas extracted from documents
- **Sources** - Paragraphs or sections from ingested documents
- **Instances** - Specific evidence quotes supporting concepts

**Relationship Types:**
The breakdown shows all relationship types found in your graph. Common types include:
- `IMPLIES` - Logical implication
- `SUPPORTS` - Evidential support
- `CONTRADICTS` - Conflicting evidence
- `REQUIRES` - Dependencies
- `CAUSES` - Causal relationships
- `CATEGORIZED_AS` - Ontological categorization
- `ENABLES` - Enabling relationships
- `PART_OF` - Compositional relationships

See `kg vocabulary list` for full vocabulary with descriptions.

**Use Cases:**

- **Growth Tracking** - Monitor how the graph grows over time
- **Relationship Distribution** - Understand what types of relationships dominate
- **Ingestion Verification** - Confirm documents added nodes/edges
- **Capacity Planning** - Gauge database size

**Tips:**

```bash
# Track growth after ingestion
kg db stats > before.txt
kg ingest file -o "Docs" document.txt -w
kg db stats > after.txt
diff before.txt after.txt
```

---

### info

Show database connection information and version details.

**Usage:**
```bash
kg database info [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

**What You Get:**

1. **Connection Details**
   - **URI** - PostgreSQL connection string (host, port, database)
   - **User** - Database username
   - **Status** - Connection status (✓ Connected / ✗ Disconnected)

2. **Version Information**
   - **Version** - Full PostgreSQL version string
   - **Edition** - Database edition (PostgreSQL + Apache AGE)

**Examples:**

```bash
# Show database info
kg database info

# Use db alias
kg db info
```

**Output Example:**

```
────────────────────────────────────────────────────────────────────────────────
🔌 Database Connection
────────────────────────────────────────────────────────────────────────────────

URI: postgresql://localhost:5432/knowledge_graph
User: admin
Status: ✓ Connected
Version: PostgreSQL 16.10 (Debian 16.10-1.pgdg13+1) on x86_64-pc-linux-gnu
Edition: PostgreSQL + Apache AGE

────────────────────────────────────────────────────────────────────────────────
```

**Use Cases:**

- **Connection Verification** - Confirm CLI is connected to correct database
- **Version Checking** - Verify PostgreSQL and AGE versions
- **Troubleshooting** - Diagnose connection issues
- **Documentation** - Capture environment details for bug reports

**Tips:**

```bash
# Include in bug reports
kg db info > db-info.txt

# Verify connection after database restart
./scripts/start-database.sh
kg db info  # Should show ✓ Connected
```

---

### health

Check database health and connectivity with detailed health checks.

**Usage:**
```bash
kg database health [options]
```

**Options:**

| Option | Description |
|--------|-------------|
| `-h, --help` | Display help for command |

**What You Get:**

1. **Overall Status**
   - **Status** - ✓ HEALTHY or ✗ UNHEALTHY
   - **Responsive** - Whether database is responding to queries

2. **Health Checks**
   - **connectivity** - Basic database connection
   - **age_extension** - Apache AGE extension loaded and functional
   - **graph** - Graph schema exists and is queryable

**Examples:**

```bash
# Check database health
kg database health

# Use db alias
kg db health
```

**Output Example:**

```
────────────────────────────────────────────────────────────────────────────────
💚 Database Health
────────────────────────────────────────────────────────────────────────────────

Status: ✓ HEALTHY
Responsive: ✓ Yes

Health Checks
────────────────────────────────────────────────────────────────────────────────
  connectivity: ✓ ok
  age_extension: ✓ ok
  graph: ✓ ok

────────────────────────────────────────────────────────────────────────────────
```

**Health Check Meanings:**

| Check | What It Verifies |
|-------|------------------|
| **connectivity** | PostgreSQL is reachable and accepting connections |
| **age_extension** | Apache AGE extension is installed and loaded |
| **graph** | Knowledge graph schema exists and is queryable |

**Use Cases:**

- **Startup Verification** - Confirm database is ready after starting
- **Pre-Flight Checks** - Verify system health before ingestion
- **Monitoring** - Periodic health checks in automation
- **Troubleshooting** - Diagnose which component is failing

**Troubleshooting:**

**If health check fails:**

```bash
# Check if connectivity fails
kg db health
# ✗ connectivity: failed

# Solutions:
# 1. Start database if not running
./scripts/start-database.sh

# 2. Check Docker container
docker ps | grep postgres

# 3. Check database logs
docker logs knowledge-graph-postgres
```

**If age_extension fails:**

```bash
# AGE extension not loaded
kg db health
# ✗ age_extension: failed

# Solution: Restart database (applies schema)
./scripts/stop-database.sh
./scripts/start-database.sh
```

**If graph fails:**

```bash
# Graph schema missing
kg db health
# ✗ graph: failed

# Solution: Reset database (applies baseline + migrations)
kg admin reset
# OR manually:
./scripts/stop-database.sh
docker-compose down -v
./scripts/start-database.sh
./scripts/initialize-auth.sh
```

---

## Common Use Cases

### System Health Check

```bash
# Quick verification
kg db health

# If all ✓ ok, system is ready
```

### Monitor Graph Growth

```bash
# Before ingestion
kg db stats
# Concepts: 100

# Ingest documents
kg ingest file -o "Research" paper.pdf -w

# After ingestion
kg db stats
# Concepts: 125 (+25)
```

### Troubleshoot Connection Issues

```bash
# Check if database is reachable
kg db health
# ✗ connectivity: failed

# Start database
./scripts/start-database.sh

# Verify connection
kg db info
# Status: ✓ Connected
```

### Capture Environment for Bug Reports

```bash
# Gather diagnostic information
echo "=== System Info ===" > diagnostic.txt
kg db info >> diagnostic.txt
echo "" >> diagnostic.txt
echo "=== Health ===" >> diagnostic.txt
kg db health >> diagnostic.txt
echo "" >> diagnostic.txt
echo "=== Stats ===" >> diagnostic.txt
kg db stats >> diagnostic.txt

# Attach diagnostic.txt to issue
```

### Monitor Relationship Distribution

```bash
# Track which relationships are most common
kg db stats | grep -A 100 "By Type"

# Useful for:
# - Understanding extraction patterns
# - Validating vocabulary usage
# - Identifying dominant relationship types
```

---

## Scripting and Automation

### Health Check Script

```bash
#!/bin/bash
# check-kg-health.sh

set -e

echo "Checking knowledge graph health..."
if kg db health | grep -q "✓ HEALTHY"; then
  echo "✓ System healthy"
  exit 0
else
  echo "✗ System unhealthy"
  exit 1
fi
```

### Growth Monitoring

```bash
#!/bin/bash
# monitor-growth.sh

while true; do
  clear
  echo "=== Knowledge Graph Statistics ==="
  echo "Timestamp: $(date)"
  echo ""
  kg db stats
  sleep 60  # Refresh every minute
done
```

### Pre-Ingestion Verification

```bash
#!/bin/bash
# safe-ingest.sh

FILE=$1
ONTOLOGY=$2

# Verify system health first
if ! kg db health | grep -q "✓ HEALTHY"; then
  echo "Error: Database unhealthy. Aborting ingestion."
  exit 1
fi

# Capture stats before
CONCEPTS_BEFORE=$(kg db stats | grep "Concepts:" | awk '{print $2}')

# Ingest
kg ingest file -o "$ONTOLOGY" -w "$FILE"

# Capture stats after
CONCEPTS_AFTER=$(kg db stats | grep "Concepts:" | awk '{print $2}')

# Report
echo "Added $((CONCEPTS_AFTER - CONCEPTS_BEFORE)) concepts"
```

---

## Performance Considerations

### Command Speed

| Command | Speed | Notes |
|---------|-------|-------|
| `stats` | Moderate (~500ms-2s) | Counts all nodes and relationships |
| `info` | Fast (<100ms) | Simple metadata query |
| `health` | Fast (~100-300ms) | Multiple quick checks |

**Large Databases:**
- `stats` can take 5-10s with >100K nodes
- Consider caching stats output if polling frequently
- Health checks remain fast regardless of size

---

## Related Commands

- [`kg health`](../health/) - Check API server health (complementary to database health)
- [`kg ontology list`](../ontology/#list) - List ontologies (uses database stats internally)
- [`kg admin reset`](../admin/#reset) - Reset database (destructive)
- [`kg admin status`](../admin/#status) - System-wide status including database

---

## Differences from kg health

**`kg health` (API server health):**
- Checks if FastAPI server is running
- Verifies job queue status
- Tests API endpoint responsiveness

**`kg database health` (Database health):**
- Checks if PostgreSQL is reachable
- Verifies Apache AGE extension
- Confirms graph schema exists

**Both are important:**
```bash
# Full system verification
kg health          # API server must be healthy
kg database health # Database must be healthy
# Both ✓ = System ready
```

---

## Troubleshooting

### Database Not Connected

**Symptom:**
```bash
kg db info
# Status: ✗ Disconnected
```

**Causes & Solutions:**

1. **Database not running**
   ```bash
   docker ps | grep postgres
   # If not listed:
   ./scripts/start-database.sh
   ```

2. **Wrong connection string**
   ```bash
   # Check API server .env file
   cat .env | grep DATABASE_URL
   # Should match database container configuration
   ```

3. **Network issues**
   ```bash
   # Check Docker network
   docker network ls
   docker network inspect knowledge-graph-network
   ```

### Stats Show Zero Nodes

**Symptom:**
```bash
kg db stats
# Concepts: 0
# Sources: 0
# Instances: 0
```

**Causes:**

1. **Fresh database** - No data ingested yet
   ```bash
   # Ingest first document
   kg ingest file -o "Test" document.txt -w
   ```

2. **Database reset** - Data was cleared
   ```bash
   # Check if recent reset
   docker logs knowledge-graph-postgres | grep -i "database system is ready"
   ```

3. **Wrong database** - Connected to empty instance
   ```bash
   kg db info  # Verify URI
   ```

### Health Check Fails

See [health](#health) subcommand troubleshooting section above.

---

## See Also

- [Database Architecture](../../06-reference/database-architecture.md)
- [Apache AGE Documentation](../../../CLAUDE.md#graph-database--query-language)
- [ADR-016: Apache AGE Migration](../../../architecture/ADR-016-apache-age-migration.md)
- [Troubleshooting Guide](../../05-maintenance/troubleshooting.md#database)
