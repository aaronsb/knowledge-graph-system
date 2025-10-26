# Knowledge Graph System - Integration Test Plan

**Purpose:** Comprehensive end-to-end validation of the knowledge graph system after ADR-044/045/046 implementation.

**Branch:** `refactor/embedding-grounding-system`

**Date Created:** 2025-01-25

---

## Test Environment Setup

### Prerequisites
- Docker and docker-compose installed
- Python 3.11+ with venv
- Node.js 18+ and npm
- kg CLI installed globally (`cd client && ./install.sh`)
- API keys configured (OpenAI or Anthropic)

### Clean Environment Checklist
- [ ] Stop all running containers: `docker-compose down -v`
- [ ] Remove volumes: `docker volume prune`
- [ ] Clean API logs: `rm -f logs/api_*.log`
- [ ] Fresh Python venv: `rm -rf venv && python3 -m venv venv`

---

## Phase 1: Cold Start & Schema Validation

### 1.1 Database Initialization
```bash
# Start fresh PostgreSQL + AGE
docker-compose up -d

# Wait for database ready
docker logs knowledge-graph-postgres | grep "ready to accept connections"

# Apply migrations
./scripts/migrate-db.sh --dry-run  # Preview
./scripts/migrate-db.sh -y         # Apply
```

**Verify:**
- [ ] PostgreSQL container running
- [ ] Apache AGE extension loaded
- [ ] All migrations applied successfully
- [ ] No migration errors in logs

### 1.2 Schema Audit
```bash
# List all tables
docker exec knowledge-graph-postgres psql -U postgres -d knowledge_graph -c "\dt ag_catalog.*"
docker exec knowledge-graph-postgres psql -U postgres -d knowledge_graph -c "\dt public.*"
```

**Expected Tables:**
- `public.embeddings` - Unified embedding cache (ADR-045)
- `public.vocabulary` - Relationship types with embeddings (ADR-046)
- `public.jobs` - Ingestion job queue
- `public.sources` - Source file metadata
- `public.schema_migrations` - Migration tracking
- `ag_catalog.*` - Apache AGE graph tables

**Verify:**
- [ ] No old/unused tables (e.g., old `concept_embeddings` table should be migrated)
- [ ] All expected tables exist
- [ ] Vocabulary table has SUPPORTS/CONTRADICTS prototypes

### 1.3 API Server Startup
```bash
# Configure AI provider
./scripts/configure-ai.sh

# Start API
./scripts/start-api.sh

# Check health
kg health
curl http://localhost:8000/health
```

**Verify:**
- [ ] API server starts without errors
- [ ] Health endpoint returns 200
- [ ] EmbeddingWorker initialized (check logs)
- [ ] VocabularyScorer initialized (check logs)

---

## Phase 2: Content Ingestion

### 2.1 Test Data Preparation
Create test documents:
```bash
cat > /tmp/test-doc-1.txt <<'EOF'
# Problem Statement
The current configuration management system is manual and error-prone.
It requires ScriptRunner which is a proprietary tool with licensing costs.

# Proposed Solution
Implement atlassian-operator as a REST API-based configuration compiler.
This provides Infrastructure-as-Code for Atlassian platform management.

# Benefits
- Automated configuration management
- Version control for infrastructure
- Reduced manual effort
EOF

cat > /tmp/test-doc-2.txt <<'EOF'
# Apache AGE Benefits
Apache AGE provides graph database capabilities on top of PostgreSQL.
It supports openCypher query language for graph traversal.

# Integration Approach
The knowledge graph system uses AGE for concept storage and relationship mapping.
This enables semantic search and path finding between concepts.
EOF
```

### 2.2 Ingestion Test - Ontology A (OpenAI Embeddings)
```bash
# Ensure using OpenAI
kg admin extraction set --provider openai --model gpt-4o

# Ingest test document 1
kg ingest file -o "TestOntologyA" -y /tmp/test-doc-1.txt

# Monitor job progress
kg jobs list
kg job status <job-id>
```

**Verify:**
- [ ] Job completes successfully
- [ ] Concepts extracted (check: `kg database stats`)
- [ ] Embeddings cached in `embeddings` table
- [ ] Vocabulary populated with relationship types
- [ ] Grounding strength calculated for concepts

### 2.3 Ingestion Test - Ontology B (Local Embeddings - Optional)
```bash
# Switch to local embeddings (if Ollama available)
kg admin extraction set --embeddings local

# Ingest test document 2
kg ingest file -o "TestOntologyB" -y /tmp/test-doc-2.txt
```

**Verify:**
- [ ] Job completes with local embeddings
- [ ] Embeddings in cache use local provider
- [ ] Search still works across both ontologies

### 2.4 Data Verification
```sql
-- Check concepts created
docker exec knowledge-graph-postgres psql -U postgres -d knowledge_graph <<EOF
SELECT * FROM ag_catalog.cypher('knowledge_graph', $$
  MATCH (c:Concept) RETURN c.label, c.concept_id LIMIT 10
$$) as (label agtype, concept_id agtype);
EOF

-- Check embeddings cache
docker exec knowledge-graph-postgres psql -U postgres -d knowledge_graph -c "SELECT COUNT(*) FROM embeddings;"

-- Check vocabulary
docker exec knowledge-graph-postgres psql -U postgres -d knowledge_graph -c "SELECT relationship_type, support_weight FROM vocabulary ORDER BY relationship_type;"
```

**Verify:**
- [ ] Concepts exist in graph
- [ ] Embeddings cached (count > 0)
- [ ] Vocabulary has entries (SUPPORTS, CONTRADICTS, etc.)
- [ ] Support weights are reasonable (SUPPORTS > 0, CONTRADICTS < 0)

---

## Phase 3: Query Testing

### 3.1 CLI Query Tests
```bash
# Search
kg search query "configuration management" --limit 5

# With evidence
kg search query "configuration management" --show-evidence

# Details
CONCEPT_ID=$(kg search query "configuration management" --json | jq -r '.results[0].concept_id')
kg search details $CONCEPT_ID

# Connection
kg search connect "configuration management" "atlassian operator"

# With evidence
kg search connect "configuration management" "atlassian operator" --show-evidence

# Related concepts
kg search related $CONCEPT_ID --depth 2

# JSON output mode
kg search query "Apache AGE" --json | jq .
```

**Verify:**
- [ ] Search returns results with grounding strength
- [ ] Evidence display works (--show-evidence)
- [ ] Grounding strength shown automatically
- [ ] Connection paths found
- [ ] Related concepts discovered
- [ ] JSON mode works for all commands
- [ ] Contradicted concepts (negative grounding) visible

### 3.2 MCP Server Query Tests

**Restart Claude Desktop** to pick up MCP server, then test:

1. **Search test:**
   - Use `search_concepts` tool with "configuration management"
   - Verify formatted markdown output (not JSON)
   - Verify grounding strength appears inline
   - Verify evidence samples shown
   - Verify retrieval hints present

2. **Details test:**
   - Use `get_concept_details` with concept ID
   - Verify ALL evidence shown
   - Verify relationships listed
   - Verify grounding strength shown

3. **Connection test:**
   - Use `find_connection_by_search` with two phrases
   - Verify paths shown in narrative format
   - Verify grounding at each step
   - Verify evidence for path nodes

4. **Related test:**
   - Use `find_related_concepts` with concept ID
   - Verify neighbors grouped by distance

**Verify:**
- [ ] All MCP tools return formatted markdown (not JSON)
- [ ] No ADR references in output
- [ ] Grounding strength displayed with interpretation
- [ ] Evidence includes source_id for retrieval
- [ ] Tool descriptions guide exploration
- [ ] Prompt "explore-graph" available

---

## Phase 4: Embedder Switching

### 4.1 Switch to Different Provider
```bash
# If currently OpenAI, switch to Anthropic (or vice versa)
kg admin extraction set --provider anthropic --model claude-3-5-sonnet-20241022

# Test extraction still works
kg admin extraction test
```

### 4.2 Re-ingest Same Content
```bash
# Ingest same doc into new ontology
kg ingest file -o "TestOntologyC" -y /tmp/test-doc-1.txt
```

**Verify:**
- [ ] Ingestion succeeds with new embedder
- [ ] Search works across ontologies with different embedders
- [ ] Concepts semantically similar despite different embeddings
- [ ] Vocabulary remains consistent

---

## Phase 5: Ontology Management

### 5.1 List Ontologies
```bash
kg ontology list
```

**Verify:**
- [ ] All test ontologies shown
- [ ] Concept counts correct
- [ ] File counts correct

### 5.2 Delete Ontology
```bash
# Delete one test ontology
kg ontology delete "TestOntologyA"
```

**Verify:**
- [ ] Ontology deleted successfully
- [ ] Concepts removed from graph
- [ ] Other ontologies intact
- [ ] Vocabulary integrity maintained (entries used by other ontologies still present)
- [ ] Search in remaining ontologies still works

### 5.3 Graph Integrity Check
```bash
# Verify no orphaned nodes
kg database stats

# Check graph structure
kg search query "Apache AGE"  # Should still work for TestOntologyB
```

**Verify:**
- [ ] No orphaned Source or Instance nodes
- [ ] Remaining concepts accessible
- [ ] Relationships intact

---

## Phase 6: Vocabulary Management

### 6.1 Check Vocabulary Status
```bash
kg vocab status
```

**Verify:**
- [ ] Relationship types listed
- [ ] Support weights shown
- [ ] Embeddings exist

### 6.2 Merge Duplicates (if any)
```bash
# Example: If you see near-duplicates
kg vocab merge "SUPPORTS" "SUPPORTED_BY" --reason "Synonym relationship"
```

**Verify:**
- [ ] Merge succeeds
- [ ] Relationships updated in graph
- [ ] Grounding calculations still work
- [ ] No broken relationships

### 6.3 Vocabulary Cleanup
```bash
# List all vocabulary entries
kg vocab list
```

**Verify:**
- [ ] No obvious duplicates
- [ ] Weights are reasonable
- [ ] All entries have embeddings

---

## Phase 7: Backup & Restore (✅ COMPLETED - 2025-01-26)

**Schema Versioning Implemented:** Migration 013 adds schema version tracking to all backups

### 7.1 Create Backup
```bash
# Backup full database
kg admin backup --type full

# Backup specific ontology
kg admin backup --type ontology --ontology "TestOntologyB"

# List backups
ls -lh ~/.local/share/kg/backups/
```

**Verify:**
- [x] Backup file created with schema_version field
- [x] Backup includes metadata (version, timestamp, ontology, schema_version: 13)
- [x] Backup includes all data (concepts, sources, instances, relationships, vocabulary)
- [x] Backup file size reasonable (JSON serialization)

### 7.2 Schema Version Validation
```bash
# Check backup metadata
head -20 ~/.local/share/kg/backups/<backup_file>.json | grep -E '"version"|"schema_version"|"type"'
```

**Verify:**
- [x] Backup includes "schema_version": 13 (current migration number)
- [x] Backup includes "version": "1.0" (backup format version)
- [x] Backup type correctly identified (full_backup or ontology_backup)

### 7.3 Complete Backup/Restore Cycle Test
```bash
# Create unique test data
cat > /tmp/purple-elephant-test.txt <<'EOF'
Purple Elephant Migration Pattern
A whimsical software architecture pattern for data migration.
Features trunk-based data transfer and herd coordination.
EOF

# Ingest unique test data
kg ingest file --ontology "PurpleElephantTest" /tmp/purple-elephant-test.txt --wait

# Search BEFORE deletion (should find it)
kg search query "purple elephant" --min-similarity 0.7

# Create backup
kg admin backup --type ontology --ontology "PurpleElephantTest"

# Delete ontology
kg ontology delete "PurpleElephantTest" --force

# Search AFTER deletion (should NOT find it)
kg search query "purple elephant" --min-similarity 0.7  # Should return 0 concepts

# Restore from backup (DEFAULT behavior: creates new concepts)
kg admin restore --file purpleelephanttest_backup_*.json

# Search AFTER restore (should find it again!)
kg search query "purple elephant" --min-similarity 0.7  # Should return Purple Elephant
```

**Verify:**
- [x] Data found before deletion
- [x] Data completely gone after deletion (0 concepts)
- [x] Data returns after restore
- [x] Concepts searchable with original similarity scores
- [x] Evidence and relationships intact

### 7.4 Safety Check: Existing Ontology Protection
```bash
# Try to restore when ontology already exists (should ERROR)
kg admin restore --file purpleelephanttest_backup_*.json

# Expected error: "Ontology 'PurpleElephantTest' already exists. Use --merge flag..."
```

**Verify:**
- [x] Error message shown if ontology exists
- [x] Prevents accidental overwrite
- [x] Clear guidance to use --merge flag

### 7.5 Merge Mode Test
```bash
# Restore with --merge flag (merges into existing ontology)
kg admin restore --file purpleelephanttest_backup_*.json --merge

# Should succeed and stitch concepts into existing graph
```

**Verify:**
- [x] Restore succeeds with --merge flag
- [x] Concepts matched to existing ones (stitching behavior)
- [x] Evidence added to matched concepts
- [x] No duplicate concept nodes created

### 7.6 Type Safety Validation
**Issue Fixed:** VARCHAR[] vs JSONB mismatch for synonyms field

```bash
# Verify vocabulary with synonyms can be backed up and restored
kg admin backup --type full
kg admin restore --file <backup_file>.json --merge
```

**Verify:**
- [x] No type mismatch errors during restore
- [x] Vocabulary synonyms restored correctly (VARCHAR[] arrays)
- [x] Embeddings restored with correct JSON format

### 7.7 Data Integrity Check
```bash
# Compare concept counts before/after
kg database stats
```

**Verify:**
- [x] Source count matches expected
- [x] Instance count matches expected
- [x] Relationship count intact
- [x] Concepts accessible via search
- [x] Grounding calculations work post-restore

---

## ✅ Phase 7 Completed - Key Achievements:

**Schema Versioning (Migration 013):**
- ✅ All backups include schema_version field
- ✅ Migration 013 creates schema_migrations table
- ✅ Retroactive tracking for migrations 1-13
- ✅ Enables detection of schema incompatibility

**Restore UX Improvements:**
- ✅ Default behavior: Creates new concepts (full restoration)
- ✅ New --merge flag: Merges into existing ontology
- ✅ Safety check: Errors if ontology exists without --merge
- ✅ Clear error messages guide users

**Type Safety:**
- ✅ Fixed VARCHAR[] vs JSONB mismatch for synonyms
- ✅ Backup serialization handles PostgreSQL arrays correctly
- ✅ Restore no longer fails with type errors

**Testing Completed:**
- ✅ Complete backup/restore cycle (Purple Elephant test)
- ✅ Data disappears on delete, returns on restore
- ✅ Safety check prevents accidental overwrites
- ✅ Merge mode tested and working
- ✅ Schema versioning tested end-to-end

**Documentation:**
- ✅ ADR-015 updated with Schema Versioning section
- ✅ INTEGRATION_TEST_NOTES.md Phase 8 complete
- ✅ Parallel restore procedure documented

---

## Phase 8: Advanced Tests

### 8.1 Empty Ontology Test
```bash
kg ontology create "EmptyOntology"
kg ontology list
kg ontology delete "EmptyOntology"
```

**Verify:**
- [ ] Can create empty ontology
- [ ] Can delete without errors

### 8.2 Single Concept Ontology
```bash
echo "Test concept with minimal content." > /tmp/minimal.txt
kg ingest file -o "MinimalOntology" -y /tmp/minimal.txt
```

**Verify:**
- [ ] Ingestion handles minimal content
- [ ] At least one concept created
- [ ] Grounding calculable (even if only 1 concept)

### 8.3 Concurrent Operations (Manual Test)
Open two terminals:
- Terminal 1: `kg ingest file -o "ConcurrentTest1" -y /tmp/test-doc-1.txt`
- Terminal 2: `kg ingest file -o "ConcurrentTest2" -y /tmp/test-doc-2.txt`

**Verify:**
- [ ] Both jobs complete successfully
- [ ] No deadlocks or race conditions
- [ ] Both ontologies created correctly

---

## Phase 9: Performance & Edge Cases

### 9.1 Large Document Test
```bash
# Create large test document
python3 << 'EOF'
with open('/tmp/large-doc.txt', 'w') as f:
    for i in range(100):
        f.write(f"# Concept {i}\n")
        f.write(f"This is test concept number {i} with some description.\n")
        f.write(f"It relates to concept {i-1} and concept {i+1}.\n\n")
EOF

kg ingest file -o "LargeTest" -y /tmp/large-doc.txt
```

**Verify:**
- [ ] Ingestion completes (may take time)
- [ ] Chunking works correctly
- [ ] Memory usage reasonable
- [ ] Search still performant

### 9.2 Special Characters Test
```bash
cat > /tmp/special-chars.txt <<'EOF'
# Concepts with Special Characters
Test concept with "quotes" and 'apostrophes'
Concept with emoji: 🚀 and unicode: ñáéíó
Code snippets: `const x = { y: "z" };`
URLs: https://example.com/path?param=value&other=123
EOF

kg ingest file -o "SpecialCharsTest" -y /tmp/special-chars.txt
```

**Verify:**
- [ ] Special characters handled correctly
- [ ] Quotes escaped properly
- [ ] Search works with special chars

---

## Phase 10: Cleanup & Documentation

### 10.1 Test Data Cleanup
```bash
# Delete all test ontologies
kg ontology delete "TestOntologyA" 2>/dev/null || true
kg ontology delete "TestOntologyB" 2>/dev/null || true
kg ontology delete "TestOntologyC" 2>/dev/null || true
kg ontology delete "MinimalOntology" 2>/dev/null || true
kg ontology delete "ConcurrentTest1" 2>/dev/null || true
kg ontology delete "ConcurrentTest2" 2>/dev/null || true
kg ontology delete "LargeTest" 2>/dev/null || true
kg ontology delete "SpecialCharsTest" 2>/dev/null || true

# Clean temp files
rm -f /tmp/test-doc-*.txt /tmp/minimal.txt /tmp/large-doc.txt /tmp/special-chars.txt
```

### 10.2 Final Verification
```bash
kg database stats  # Should show only production data
kg ontology list   # Should show only intended ontologies
```

---

## Known Issues & Limitations

*Document any issues discovered during testing here*

### Issues Found:
- [ ] Issue 1: Description
- [ ] Issue 2: Description

### Future Improvements:
- [ ] Improvement 1
- [ ] Improvement 2

---

## Sign-off

### Test Execution
- **Date Executed:** _________________
- **Executed By:** _________________
- **Branch/Commit:** _________________

### Results
- [ ] All critical tests passed
- [ ] Known issues documented
- [ ] System ready for merge to main

### Notes:
_Add any additional observations or concerns here_

---

## Additional Test Areas (Not Yet Covered)

### API Authentication (ADR-027)
- [ ] Test JWT token authentication
- [ ] Test token expiration
- [ ] Test role-based access control

### Rate Limiting
- [ ] Test API rate limits
- [ ] Test concurrent request handling

### Error Recovery
- [ ] Test database connection loss recovery
- [ ] Test API server crash recovery
- [ ] Test incomplete ingestion recovery

### Monitoring & Observability
- [ ] Check API logs for errors
- [ ] Monitor database query performance
- [ ] Check memory usage during large ingestions
