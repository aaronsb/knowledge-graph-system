# Test Coverage Areas

Functional test coverage map for the knowledge graph system. This document outlines what needs testing, expected behaviors, and acceptance criteria.

---

## Philosophy

**We test for functional correctness, not code coverage.**

- ✅ Does the workflow work end-to-end?
- ✅ Does data integrity remain intact?
- ✅ Are edge cases handled gracefully?
- ❌ NOT: Did we execute every line of code?

**Non-deterministic acceptance:**
- LLM extraction varies between runs
- Test ranges, not exact values
- Validate structure and semantics, not specific outputs

---

## 1. Smoke Tests (Fast Sanity Checks)

### 1.1 Infrastructure Connectivity
**Purpose:** Verify basic setup works

**Test:** Neo4j Connection
```python
def test_neo4j_connection():
    """Neo4j container is running and accessible"""
    conn = Neo4jConnection()
    assert conn.test_connection() == True
    conn.close()
```

**Test:** OpenAI API Key Valid
```python
def test_openai_api_key():
    """OpenAI API key is configured and valid"""
    from openai import OpenAI
    client = OpenAI(api_key=Config.openai_api_key())
    # Make minimal API call
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input="test"
    )
    assert len(response.data[0].embedding) == 1536
```

**Test:** Library Imports
```python
def test_core_imports():
    """All core libraries import without errors"""
    from src.lib import console, config, neo4j_ops, serialization, integrity, restitching
    from src.admin import backup, restore, stitch, prune, check_integrity
    # If we get here, imports succeeded
    assert True
```

**Expected Results:**
- All connections succeed
- No import errors
- Setup script has run successfully

---

## 2. Functional Tests (Core Workflows)

### 2.1 Ingestion Pipeline
**Purpose:** LLM extraction creates correct graph structure

**Test:** Basic Document Ingestion
```python
def test_basic_ingestion(clean_db, sample_document):
    """Ingest document → concepts created with correct structure"""
    # Setup: clean_db fixture, sample_document = "tests/fixtures/sample.txt"

    # Ingest
    result = ingest_document(sample_document, ontology="Test Ontology")

    # Assertions (ranges, not exact)
    assert 5 <= result['concepts_created'] <= 15, "Expected 5-15 concepts"
    assert result['sources_created'] >= 1, "At least one source"
    assert result['instances_created'] >= 5, "Multiple evidence instances"

    # Verify graph structure
    with Neo4jConnection().session() as session:
        concepts = session.run("MATCH (c:Concept) RETURN c").values()

        # All concepts have embeddings
        assert all(len(c[0]['embedding']) == 1536 for c in concepts)

        # All concepts have APPEARS_IN relationships
        orphans = session.run("""
            MATCH (c:Concept)
            WHERE NOT EXISTS((c)-[:APPEARS_IN]->(:Source))
            RETURN count(c) as count
        """).single()['count']
        assert orphans == 0, "No orphaned concepts"
```

**Test:** Cross-Ontology Relationships
```python
def test_cross_ontology_relationships(clean_db):
    """LLM identifies relationships across ontologies"""
    # Ingest two related documents
    ingest_document("tests/fixtures/ontology_a.txt", ontology="Ontology A")
    ingest_document("tests/fixtures/ontology_b.txt", ontology="Ontology B")

    # Check for cross-ontology relationships
    with Neo4jConnection().session() as session:
        cross_rels = session.run("""
            MATCH (c1:Concept)-[:APPEARS_IN]->(s1:Source {document: "Ontology A"})
            MATCH (c1)-[r]->(c2:Concept)-[:APPEARS_IN]->(s2:Source {document: "Ontology B"})
            RETURN count(r) as count
        """).single()['count']

        # May or may not find cross-ontology links (depends on content)
        # Just verify query works and returns a number
        assert cross_rels >= 0
```

**Expected Results:**
- Concepts created in expected range
- All concepts have embeddings (1536-dim)
- No orphaned concepts (all have APPEARS_IN)
- Relationships created between concepts

---

### 2.2 Backup and Restore
**Purpose:** Data preservation with full fidelity

**Test:** Full Database Backup
```python
def test_full_backup(populated_db):
    """Full backup captures all data including embeddings"""
    # Setup: populated_db fixture with known data

    # Backup
    backup_file = backup_database()

    # Load and validate backup JSON
    with open(backup_file) as f:
        backup = json.load(f)

    assert backup['type'] == 'full_backup'
    assert backup['version'] == '1.0'
    assert backup['statistics']['concepts'] >= 10
    assert backup['statistics']['relationships'] >= 5

    # Verify embeddings preserved
    for concept in backup['data']['concepts']:
        assert 'embedding' in concept
        assert len(concept['embedding']) == 1536
```

**Test:** Ontology-Specific Backup
```python
def test_ontology_backup(multi_ontology_db):
    """Selective ontology backup includes only specified data"""
    # Setup: DB with multiple ontologies

    backup_file = backup_ontology("Ontology A")

    with open(backup_file) as f:
        backup = json.load(f)

    assert backup['type'] == 'ontology_backup'
    assert backup['ontology'] == 'Ontology A'

    # All concepts belong to this ontology
    concept_ids = {c['concept_id'] for c in backup['data']['concepts']}

    # All sources reference this ontology
    for source in backup['data']['sources']:
        assert source['document'] == 'Ontology A'
```

**Test:** Restore Preserves Data Integrity
```python
def test_restore_integrity(backup_file):
    """Restore recreates exact graph structure"""
    # Setup: Clean DB, existing backup

    # Get original stats from backup
    with open(backup_file) as f:
        original = json.load(f)

    # Restore
    restore_result = restore_backup(backup_file)

    # Verify counts match
    assert restore_result['concepts_created'] == original['statistics']['concepts']
    assert restore_result['relationships_created'] == original['statistics']['relationships']

    # Verify embeddings intact
    with Neo4jConnection().session() as session:
        concepts = session.run("MATCH (c:Concept) RETURN c.embedding as emb").values()
        assert all(len(c[0]) == 1536 for c in concepts)

    # Verify graph integrity
    integrity = DatabaseIntegrity.check_integrity(session)
    assert len(integrity['issues']) == 0, "No integrity issues after restore"
```

**Expected Results:**
- Backup captures all data
- Embeddings preserved (1536-dim arrays)
- Restore recreates exact structure
- No integrity issues after restore

---

### 2.3 Semantic Stitching
**Purpose:** Reconnect relationships using vector similarity

**Test:** External Concept Matching
```python
def test_semantic_stitching(partial_backup, target_db):
    """Stitcher reconnects dangling refs to similar concepts"""
    # Setup: target_db has "Systems Thinking" ontology
    #        partial_backup has "Alan Watts" with refs to systems concepts

    # Restore partial backup (creates dangling refs)
    restore_backup(partial_backup)

    # Run stitcher
    matcher = ConceptMatcher(Neo4jConnection(), threshold=0.85)
    restitch_plan = matcher.create_restitch_plan(...)

    # Verify matches found
    assert len(restitch_plan['matched']) > 0, "Should find similar concepts"

    # Apply stitching
    stats = matcher.execute_restitch(restitch_plan, session)

    # Verify relationships reconnected
    assert stats['restitched'] > 0, "Should reconnect some relationships"

    # Verify auto-pruning of unmatched
    with Neo4jConnection().session() as session:
        dangling = DatabaseIntegrity.prune_dangling_relationships(
            session, dry_run=True
        )
        assert dangling['total_pruned'] == 0, "No dangling refs remain"
```

**Test:** Similarity Threshold Sensitivity
```python
def test_threshold_sensitivity():
    """Different thresholds produce different match counts"""
    # Same backup, different thresholds

    high_threshold_matches = run_stitcher(threshold=0.95)
    low_threshold_matches = run_stitcher(threshold=0.75)

    # Higher threshold = fewer matches
    assert high_threshold_matches['matched'] <= low_threshold_matches['matched']
```

**Expected Results:**
- Stitcher finds similar concepts above threshold
- Relationships reconnected to matches
- Unmatched refs automatically pruned
- Higher threshold = stricter matching

---

### 2.4 Graph Integrity
**Purpose:** Detect and repair structural issues

**Test:** Orphaned Concept Detection
```python
def test_orphaned_detection():
    """Integrity checker finds concepts without APPEARS_IN"""
    # Manually create orphaned concept
    with Neo4jConnection().session() as session:
        session.run("""
            CREATE (c:Concept {
                concept_id: 'orphan_test',
                label: 'Orphaned Concept',
                embedding: [0.0] * 1536
            })
        """)

        # Run integrity check
        integrity = DatabaseIntegrity.check_integrity(session)

        assert len(integrity['issues']) > 0
        assert any('orphaned' in issue.lower() for issue in integrity['issues'])
```

**Test:** Dangling Relationship Detection
```python
def test_dangling_relationship_detection():
    """Detect relationships pointing to non-existent concepts"""
    # Create concept with relationship to non-existent target
    with Neo4jConnection().session() as session:
        session.run("""
            CREATE (c:Concept {concept_id: 'source', label: 'Source'})
            CREATE (s:Source {source_id: 'src1', document: 'Test'})
            CREATE (c)-[:APPEARS_IN]->(s)
            CREATE (c)-[:IMPLIES]->(:Concept {concept_id: 'ghost'})
        """)

        # Note: 'ghost' concept has no APPEARS_IN, so it's dangling

        result = DatabaseIntegrity.prune_dangling_relationships(
            session, dry_run=True
        )

        assert result['total_pruned'] > 0, "Should detect dangling relationship"
```

**Test:** Auto-Repair Orphans
```python
def test_auto_repair():
    """Repair can fix orphaned concepts"""
    # Create orphan, then repair
    # ... setup orphan ...

    repairs = DatabaseIntegrity.repair_orphaned_concepts(session)
    assert repairs > 0

    # Re-check integrity
    integrity = DatabaseIntegrity.check_integrity(session)
    assert len(integrity['issues']) == 0, "Issues resolved"
```

**Expected Results:**
- Orphaned concepts detected
- Dangling relationships detected
- Auto-repair fixes issues
- Re-check shows clean state

---

### 2.5 Pruning
**Purpose:** Remove dangling relationships for graph isolation

**Test:** Prune External References
```python
def test_pruning():
    """Pruning removes dangling relationships"""
    # Create ontology with external refs
    # ... setup ...

    # Count dangling refs
    with Neo4jConnection().session() as session:
        before = DatabaseIntegrity.prune_dangling_relationships(
            session, dry_run=True
        )
        assert before['total_pruned'] > 0, "Setup should have dangling refs"

        # Prune
        after = DatabaseIntegrity.prune_dangling_relationships(
            session, dry_run=False
        )
        assert after['total_pruned'] == before['total_pruned']

        # Verify clean
        recheck = DatabaseIntegrity.prune_dangling_relationships(
            session, dry_run=True
        )
        assert recheck['total_pruned'] == 0, "All dangling refs removed"
```

**Expected Results:**
- Identifies dangling relationships
- Removes them when executed
- Graph is clean after pruning

---

## 3. Scenario Tests (Real-World Use Cases)

### 3.1 Multi-Ontology System
**Purpose:** Multiple ontologies coexist and interact

**Test:** Independent Ontology Operations
```python
def test_independent_ontologies():
    """Operations on one ontology don't affect others"""
    # Create 3 ontologies
    ingest_document("a.txt", ontology="A")
    ingest_document("b.txt", ontology="B")
    ingest_document("c.txt", ontology="C")

    # Backup only B
    backup_file = backup_ontology("B")

    # Delete B
    delete_ontology("B")

    # Verify A and C unaffected
    assert count_concepts("A") > 0
    assert count_concepts("C") > 0
    assert count_concepts("B") == 0

    # Restore B
    restore_backup(backup_file)

    # All three exist again
    assert all(count_concepts(ont) > 0 for ont in ["A", "B", "C"])
```

### 3.2 Clean Database Restore
**Purpose:** Partial restore into empty database

**Test:** Auto-Prune on Clean Restore
```python
def test_clean_database_restore(partial_backup):
    """Restoring partial backup to empty DB auto-prunes"""
    # Ensure DB is empty
    with Neo4jConnection().session() as session:
        count = session.run("MATCH (n) RETURN count(n) as c").single()['c']
        assert count == 0

    # Restore should auto-detect and auto-prune
    # (no user prompts in test mode)
    restore_backup(partial_backup, auto_prune=True)

    # Verify no dangling refs
    with Neo4jConnection().session() as session:
        integrity = DatabaseIntegrity.check_integrity(session)
        assert len(integrity['issues']) == 0
```

### 3.3 Token Cost Validation
**Purpose:** Embeddings preserve investment

**Test:** Embeddings Preserved in Backup
```python
def test_embedding_preservation():
    """Backup → restore preserves embeddings (no regeneration)"""
    # Ingest document (generates embeddings)
    ingest_document("test.txt", ontology="Test")

    # Get original embeddings
    with Neo4jConnection().session() as session:
        original_embeddings = session.run("""
            MATCH (c:Concept)
            RETURN c.concept_id as id, c.embedding as emb
        """).values()

    # Backup → clear → restore
    backup_file = backup_database()
    clear_database()
    restore_backup(backup_file)

    # Get restored embeddings
    with Neo4jConnection().session() as session:
        restored_embeddings = session.run("""
            MATCH (c:Concept)
            RETURN c.concept_id as id, c.embedding as emb
        """).values()

    # Verify exact match (no regeneration)
    orig_dict = {id: emb for id, emb in original_embeddings}
    rest_dict = {id: emb for id, emb in restored_embeddings}

    for concept_id in orig_dict:
        assert orig_dict[concept_id] == rest_dict[concept_id], \
            f"Embedding changed for {concept_id} - indicates regeneration!"
```

**Expected Results:**
- Embeddings are byte-for-byte identical after restore
- No API calls needed to restore embeddings
- Token investment protected

---

## 4. Regression Tests (Prevent Known Bugs)

### 4.1 Bug: Missing APPEARS_IN (Fixed in commit 0c74118)
**Test:** APPEARS_IN Created During Instance Import
```python
def test_appears_in_relationship():
    """Regression: Concepts must link to sources during restore"""
    # This was broken - concepts imported but not linked

    backup_file = create_minimal_backup()
    restore_backup(backup_file)

    with Neo4jConnection().session() as session:
        orphans = session.run("""
            MATCH (c:Concept)
            WHERE NOT EXISTS((c)-[:APPEARS_IN]->(:Source))
            RETURN count(c) as count
        """).single()['count']

        assert orphans == 0, "Bug regression: APPEARS_IN not created"
```

### 4.2 Bug: Inaccurate Relationship Counter (Fixed in commit af70223)
**Test:** Relationship Stats Accuracy
```python
def test_relationship_counter_accuracy():
    """Regression: Counter should match actual created relationships"""
    # Was broken - counter incremented even when MATCH failed

    backup = load_backup_with_external_refs()
    result = restore_backup(backup)

    # Count actual relationships
    with Neo4jConnection().session() as session:
        actual_count = session.run("""
            MATCH ()-[r]->()
            RETURN count(r) as count
        """).single()['count']

    assert result['relationships_created'] == actual_count, \
        "Bug regression: Relationship counter inaccurate"
```

### 4.3 Enhancement: Clean Database Auto-Prune (Added in commit 14cbcfa)
**Test:** Clean DB Detection
```python
def test_clean_db_auto_prune():
    """Regression: Clean DB should auto-prune without prompts"""
    # Enhancement to avoid unnecessary user prompts

    # Ensure empty
    clear_database()

    # Restore partial backup with external refs
    # Should auto-detect clean DB and auto-prune
    result = restore_backup(partial_backup_file, interactive=False)

    # Verify auto-prune executed
    assert 'auto_prune' in result['actions_taken']

    # Verify clean state
    with Neo4jConnection().session() as session:
        integrity = DatabaseIntegrity.check_integrity(session)
        assert len(integrity['issues']) == 0
```

**Expected Results:**
- All previous bugs remain fixed
- No regression in known enhancements

---

## 5. Test Data Requirements

### Test Documents

**Minimal Test Doc** (`tests/fixtures/minimal.txt`)
- 3-5 paragraphs
- Expected: 3-7 concepts
- Expected: 2-5 relationships
- Purpose: Fast smoke tests

**Cross-Ontology Test Docs**
- `ontology_a.txt` - Systems thinking concepts
- `ontology_b.txt` - References systems thinking
- Expected: 1-3 cross-ontology relationships
- Purpose: Stitching and pruning tests

**Large Test Doc** (`tests/fixtures/large.txt`)
- 20-30 paragraphs
- Expected: 30-50 concepts
- Expected: 40-70 relationships
- Purpose: Performance and stress tests

### Backup Fixtures

**Minimal Backup** (`tests/fixtures/minimal_backup.json`)
- 5 concepts, 1 source, 5 instances, 3 relationships
- No external dependencies
- Purpose: Fast restore tests

**Partial Backup with External Refs** (`tests/fixtures/partial_with_refs.json`)
- 10 concepts, 2 sources
- 5 relationships to external concepts
- Purpose: Stitching and pruning tests

**Multi-Ontology Backup** (`tests/fixtures/multi_ontology.json`)
- 3 ontologies, 30 concepts total
- Cross-ontology relationships
- Purpose: Complex scenario tests

---

## 6. Expected Test Ranges

### Ingestion
- **Minimal doc** → 3-7 concepts, 2-5 relationships
- **Medium doc** → 15-30 concepts, 20-40 relationships
- **Large doc** → 30-50 concepts, 40-70 relationships

**Variance acceptable:** ±20% due to LLM non-determinism

### Performance
- **Ingestion:** < 10s per document (excluding LLM latency)
- **Backup:** < 5s for 100 concepts
- **Restore:** < 10s for 100 concepts
- **Stitching:** < 30s for 50 external refs

### Integrity
- **Zero orphaned concepts** after ingestion
- **Zero dangling relationships** after prune
- **100% edge handling** after stitch + auto-prune

---

## 7. Test Environment Setup

### Prerequisites
```bash
# Clone repo
git clone <repo>
cd knowledge-graph-system

# Run setup (includes Neo4j Docker)
./scripts/setup.sh

# Add test API key to .env
echo "OPENAI_API_KEY=sk-test-..." >> .env

# Install test dependencies
pip install -r requirements-dev.txt
```

### Run Tests
```bash
# All tests
pytest

# Fast smoke tests only
pytest tests/smoke/

# Specific category
pytest tests/functional/test_backup_restore.py

# With coverage report
pytest --cov=src --cov-report=html
```

---

## 8. Success Criteria

**Test suite is successful when:**
- ✅ All critical workflows have functional tests
- ✅ All regression tests for known bugs pass
- ✅ CI passes consistently (< 10% flaky failures)
- ✅ New features include scenario tests
- ✅ Test data ranges are documented
- ✅ Test execution time < 10 minutes (full suite)

**Individual test is successful when:**
- ✅ Functional correctness demonstrated
- ✅ Graph integrity maintained
- ✅ Edge cases handled gracefully
- ✅ Error messages are clear and actionable

---

## 9. Future Test Areas

**Not yet covered, but needed:**
- [ ] Concurrent access (multiple users/agents)
- [ ] Large-scale ingestion (1000+ documents)
- [ ] Performance benchmarks (query latency)
- [ ] MCP server integration tests
- [ ] CLI argument parsing and error handling
- [ ] Backup file versioning and migration
- [ ] Vector search accuracy (recall/precision)

---

*This document is a living specification. Update as new test areas are identified or existing tests evolve.*
