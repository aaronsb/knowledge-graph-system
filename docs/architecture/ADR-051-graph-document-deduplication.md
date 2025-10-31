# ADR-051: Graph-Based Provenance Tracking

**Status:** Proposed
**Date:** 2025-10-31
**Author:** System Architecture
**Related:** ADR-014 (Job Approval Workflow), ADR-044 (Probabilistic Truth Convergence), ADR-037 (Human-Guided Graph Editing)

---

## Context

ADR-014 implemented document-level deduplication using SHA-256 hashes stored in the jobs table. This prevents users from re-ingesting the same file by checking if a completed job exists with matching content hash and ontology.

**This ADR addresses two related concerns:**
1. **Document deduplication** - Job deletion breaks deduplication (primary problem)
2. **Relationship provenance** - No audit trail for who/when/how relationships were created (secondary enhancement)

### The Problem: Job Deletion Breaks Deduplication

**Real-world scenario:**

```
Timeline:
1. User ingested 50 docs successfully (months ago)
   → 50 completed jobs in jobs table
   → 50 documents worth of content in graph

2. User adds 50 new docs to same directory

3. User ingests entire directory (100 files)
   → API key invalid → all 100 jobs fail

4. User fixes API key, tries to re-ingest
   → Blocked by failed job hashes

5. User deletes failed jobs to "clear the way"
   → Removes 100 job records (including 50 old successful ones)

6. User re-ingests directory
   → ALL 100 files process (no job records to check against)
   → 50 documents DUPLICATED in graph
```

**Root cause:** Deduplication checks ephemeral jobs table instead of persistent graph state.

### Additional Issues

**Issue 1: Job retention policies**
Organizations may want to purge old job records (compliance, storage) without breaking deduplication.

**Issue 2: Cross-ontology source tracking**
Cannot query "which documents exist in the graph?" without scanning job history.

**Issue 3: Incomplete audit trail**
Jobs table doesn't track source provenance (file path, hostname, ingestion method).

**Issue 4: No relationship provenance**
Cannot trace which job/user created relationships, making debugging and auditing difficult.

---

## Decision

Implement **graph-based provenance tracking** for both nodes and edges:

1. **`:DocumentMeta` nodes** - Track successfully ingested documents (solves deduplication problem)
2. **Edge metadata** - Track who/when/how relationships were created (audit trail + future ADR-037 support)

Deduplication checks the graph (source of truth), not the jobs table (ephemeral log).

### Core Principles

1. **Graph is source of truth** - Jobs table is operational log, graph is persistent state
2. **Source-aware metadata** - Track ingestion method (file, stdin, MCP, API) with best-effort provenance
3. **MCP silent enrichment** - MCP server adds metadata but doesn't expose it to AI (ADR-044 compliance)
4. **Job deletion safe** - Deleting jobs never breaks deduplication
5. **Relationship provenance** - All edges track creation metadata (audit trail, debugging, human curation)

---

## DocumentMeta Node Schema

```cypher
(:DocumentMeta {
  // Identification (required)
  document_id: "sha256:abc123...",           // Same as content_hash (unique ID)
  content_hash: "sha256:abc123...",          // SHA-256 for deduplication
  ontology: "My Docs",                       // Target ontology
  source_count: 15,                          // Number of Source nodes created

  // Provenance metadata (best-effort, varies by source type)
  filename: "chapter1.txt",                  // Display name or session ID
  source_type: "file",                       // "file" | "stdin" | "mcp" | "api"
  file_path: "/home/user/docs/chapter1.txt", // Full path (file ingestion only)
  hostname: "workstation-01",                // Hostname (CLI only, not MCP)
  ingested_at: "2025-10-31T12:34:56Z",      // Timestamp (always present)

  // Audit (required)
  ingested_by: "user_123",                   // User ID who submitted
  job_id: "job_xyz"                          // Link to original job (audit trail)
})

// Relationships
(:DocumentMeta)-[:HAS_SOURCE]->(:Source)
```

### Source Type Matrix

| Source Type | `filename` | `file_path` | `hostname` | `ingested_at` | Example |
|-------------|------------|-------------|------------|---------------|---------|
| **`file`** | ✅ basename | ✅ absolute path | ✅ hostname | ✅ file mtime or now() | `chapter1.txt` |
| **`stdin`** | ✅ "stdin" | ❌ null | ✅ hostname | ✅ now() | Piped content |
| **`mcp`** | ✅ session ID | ❌ null | ❌ null | ✅ now() (silent) | `mcp_session_1730...` |
| **`api`** | ⚠️ client-provided | ❌ null | ❌ null | ✅ now() | Direct API POST |

---

## Edge Metadata Schema

All relationships in the graph track provenance metadata for audit trails and debugging. This metadata is **stored but not exposed to AI** (ADR-044 compliance).

### Relationship Types with Metadata

```cypher
// LLM-extracted concept relationships (from ingestion)
(:Concept)-[:IMPLIES {
  created_at: "2025-10-31T12:34:56Z",
  created_by: "user_123",           // User who submitted the job
  source: "llm_extraction",         // How relationship was created
  job_id: "job_xyz",                // Which ingestion job
  document_id: "sha256:abc..."      // Links back to DocumentMeta
}]->(:Concept)

(:Concept)-[:SUPPORTS {
  created_at: "2025-10-31T12:34:56Z",
  created_by: "user_123",
  source: "llm_extraction",
  job_id: "job_xyz",
  document_id: "sha256:abc..."
}]->(:Concept)

(:Concept)-[:CONTRADICTS {
  created_at: "2025-10-31T12:34:56Z",
  created_by: "user_123",
  source: "llm_extraction",
  job_id: "job_xyz",
  document_id: "sha256:abc..."
}]->(:Concept)

// Evidence relationships (structural)
(:Concept)-[:EVIDENCED_BY {
  created_at: "2025-10-31T12:34:56Z",
  job_id: "job_xyz",
  document_id: "sha256:abc..."
}]->(:Instance)

(:Instance)-[:FROM_SOURCE {
  created_at: "2025-10-31T12:34:56Z",
  job_id: "job_xyz"
}]->(:Source)

(:Concept)-[:APPEARS_IN {
  created_at: "2025-10-31T12:34:56Z",
  job_id: "job_xyz",
  document_id: "sha256:abc..."
}]->(:Source)

// Document structure
(:DocumentMeta)-[:HAS_SOURCE {
  created_at: "2025-10-31T12:34:56Z"
}]->(:Source)

// Future: Human-curated relationships (ADR-037)
(:Concept)-[:IMPLIES {
  created_at: "2025-11-01T10:22:33Z",
  created_by: "user_456",
  source: "human_curation",         // Distinguished from LLM
  justification: "Explicit statement in document",  // Human reasoning
  document_id: null,                // Not from a document ingestion
  invalidates: ["rel_id_123"]       // Optional: IDs of relationships this replaces
}]->(:Concept)
```

### Edge Metadata Fields

| Field | Required | Description | Example |
|-------|----------|-------------|---------|
| `created_at` | ✅ Yes | Timestamp when relationship created | `"2025-10-31T12:34:56Z"` |
| `created_by` | ✅ Yes | User ID who created it | `"user_123"` |
| `source` | ✅ Yes | Creation method | `"llm_extraction"` or `"human_curation"` |
| `job_id` | ⚠️ LLM only | Job that extracted this relationship | `"job_xyz"` |
| `document_id` | ⚠️ LLM only | Document this came from (links to DocumentMeta) | `"sha256:abc..."` |
| `justification` | ⚠️ Human only | Human explanation for why relationship exists | `"Explicit statement..."` |
| `invalidates` | ❌ Optional | List of relationship IDs this replaces/corrects | `["rel_id_123"]` |

### Benefits of Edge Metadata

1. **Audit trail**: "Which job created this relationship?"
   ```cypher
   MATCH ()-[r {job_id: "job_xyz"}]->()
   RETURN type(r), count(*) as rel_count
   ```

2. **Human vs LLM distinction**: Weight human-curated relationships differently (future ADR-044 enhancement)
   ```cypher
   MATCH (c)-[r:SUPPORTS {source: "human_curation"}]->(c2)
   RETURN c.label, c2.label, r.justification
   ```

3. **Cascade delete by document**: Delete all relationships from a document
   ```cypher
   MATCH ()-[r {document_id: $doc_id}]->()
   DELETE r
   ```

4. **Debugging**: Trace relationship origin
   ```cypher
   MATCH (c1:Concept)-[r]->(c2:Concept)
   WHERE c1.label =~ '.*Linear Thinking.*'
   RETURN c1.label, type(r), c2.label, r.created_at, r.source
   ```

5. **MCP silent storage**: Metadata stored but NOT exposed to Claude in query results

### MCP Server: Silent Edge Metadata

**When Claude queries relationships:**

```typescript
// MCP tool: get_concept_details
case "get_concept_details": {
    const concept = await apiClient.getConceptDetails(concept_id);

    // API returns full relationship data including metadata
    // MCP server STRIPS metadata before showing to Claude

    const relationships = concept.relationships.map(r => ({
        type: r.type,
        target_concept: r.target_id,
        target_label: r.target_label
        // OMIT: created_at, created_by, source, job_id, document_id, justification
    }));

    return {
        content: [{
            type: "text",
            text: formatConceptWithRelationships(concept, relationships)
            // Metadata exists in graph but NOT shown to Claude
        }]
    };
}
```

**Why this matters (ADR-044 compliance):**
- Timestamps stored for audit, NOT for truth evaluation
- Claude never sees "when" relationships were created
- Prevents false "newer relationships = better" reasoning
- Humans can query metadata via CLI for legitimate operational tasks

---

## Implementation

### 1. Jobs Table Migration

Add optional source metadata columns:

```sql
-- Migration: 021_graph_document_deduplication.sql

ALTER TABLE kg_api.jobs
ADD COLUMN source_filename TEXT,
ADD COLUMN source_type TEXT,      -- "file" | "stdin" | "mcp" | "api"
ADD COLUMN source_path TEXT,
ADD COLUMN source_hostname TEXT;

CREATE INDEX idx_jobs_source_type ON kg_api.jobs(source_type);

COMMENT ON COLUMN kg_api.jobs.source_filename IS 'Display name: filename, "stdin", or MCP session ID';
COMMENT ON COLUMN kg_api.jobs.source_type IS 'Ingestion method for audit tracking';
COMMENT ON COLUMN kg_api.jobs.source_path IS 'Full filesystem path (file ingestion only, null otherwise)';
COMMENT ON COLUMN kg_api.jobs.source_hostname IS 'Hostname where ingestion initiated (CLI only, null for MCP)';
```

### 2. Deduplication Check (Graph-Based)

**Old approach (ADR-014):**
```python
# Check jobs table (ephemeral)
existing_job = job_queue.check_duplicate(content_hash, ontology)
if existing_job and existing_job['status'] == 'completed':
    raise HTTPException(409, "Document already ingested")
```

**New approach (ADR-051):**
```python
# Check graph (persistent)
existing_doc = age_client.get_document_meta(content_hash, ontology)
if existing_doc:
    raise HTTPException(409, {
        "error": "Document already ingested",
        "document_id": existing_doc['document_id'],
        "filename": existing_doc['filename'],
        "ingested_at": existing_doc['ingested_at'],
        "source_count": existing_doc['source_count']
    })
```

**AGEClient method:**
```python
def get_document_meta(self, content_hash: str, ontology: str) -> Optional[Dict]:
    """Check if document already exists in graph"""
    query = """
    SELECT * FROM cypher('knowledge_graph', $$
        MATCH (d:DocumentMeta {content_hash: $hash, ontology: $ontology})
        RETURN d
    $$) as (doc agtype);
    """
    result = self._execute_cypher(query, {"hash": content_hash, "ontology": ontology})
    return result[0]['doc'] if result else None
```

### 3. Create DocumentMeta After Successful Ingestion

**In `ingestion_worker.py`:**
```python
def run_ingestion_worker(job_data: Dict[str, Any], job_id: str, job_queue) -> Dict[str, Any]:
    """Execute ingestion and create DocumentMeta node"""

    # ... existing ingestion logic (chunk, extract, create sources) ...

    # After successful ingestion: Create DocumentMeta node
    content_hash = job_data.get("content_hash")
    ontology = job_data["ontology"]

    # Build DocumentMeta properties
    doc_meta = {
        "document_id": content_hash,
        "content_hash": content_hash,
        "ontology": ontology,
        "source_count": stats.sources_created,
        "ingested_by": job_data.get("user_id"),
        "job_id": job_id,
        "ingested_at": datetime.now(timezone.utc).isoformat()
    }

    # Add optional provenance (best effort)
    if job_data.get("source_filename"):
        doc_meta["filename"] = job_data["source_filename"]
    if job_data.get("source_type"):
        doc_meta["source_type"] = job_data["source_type"]
    if job_data.get("source_path"):
        doc_meta["file_path"] = job_data["source_path"]
    if job_data.get("source_hostname"):
        doc_meta["hostname"] = job_data["source_hostname"]

    # Create DocumentMeta node and link to Source nodes
    age_client.create_document_meta(doc_meta, source_ids)

    logger.info(f"✓ Created DocumentMeta node: {content_hash[:16]}... ({stats.sources_created} sources)")
```

**AGEClient method:**
```python
def create_document_meta(self, doc_meta: Dict, source_ids: List[str]):
    """Create DocumentMeta node and link to Source nodes"""

    # Create DocumentMeta node
    create_query = """
    SELECT * FROM cypher('knowledge_graph', $$
        CREATE (d:DocumentMeta $props)
        RETURN d
    $$, $params) as (doc agtype);
    """
    self._execute_cypher(create_query, {"props": doc_meta})

    # Link to all Source nodes created in this ingestion
    link_query = """
    SELECT * FROM cypher('knowledge_graph', $$
        MATCH (d:DocumentMeta {document_id: $doc_id})
        MATCH (s:Source)
        WHERE s.source_id IN $source_ids
        CREATE (d)-[:HAS_SOURCE]->(s)
    $$, $params) as (result agtype);
    """
    self._execute_cypher(link_query, {
        "doc_id": doc_meta["document_id"],
        "source_ids": source_ids
    })
```

### 4. Client Metadata Enrichment

**kg CLI (file ingestion):**
```typescript
// client/src/cli/ingest.ts
import os from 'os';
import path from 'path';

async function ingestFile(filePath: string, ontology: string) {
    const absolutePath = path.resolve(filePath);
    const filename = path.basename(filePath);
    const hostname = os.hostname();

    const response = await apiClient.ingestFile({
        content: fileContent,
        ontology: ontology,
        source_metadata: {
            filename: filename,
            source_type: "file",
            file_path: absolutePath,
            hostname: hostname
        }
    });
}
```

**kg CLI (stdin pipe):**
```typescript
// cat document.txt | kg ingest -o "My Docs"
async function ingestStdin(ontology: string) {
    const content = await readStdin();
    const hostname = os.hostname();

    const response = await apiClient.ingestText({
        content: content,
        ontology: ontology,
        source_metadata: {
            filename: "stdin",
            source_type: "stdin",
            file_path: null,
            hostname: hostname
        }
    });
}
```

**MCP Server (silent enrichment):**
```typescript
// client/src/mcp-server.ts
case "ingest_text": {
    const { text, ontology, auto_approve } = args;

    // Silently enrich with MCP-specific metadata
    const response = await apiClient.ingestText({
        content: text,
        ontology: ontology,
        auto_approve: auto_approve,
        source_metadata: {
            filename: `mcp_session_${Date.now()}`,
            source_type: "mcp",
            file_path: null,
            hostname: null
            // ingested_at added by server
        }
    });

    // Return to Claude WITHOUT mentioning timestamp or metadata
    return {
        content: [{
            type: "text",
            text: `✓ Text ingested into ontology "${ontology}"\n` +
                  `Job ID: ${response.job_id}\n` +
                  `Status: ${response.status}`
            // NO mention of timestamp, source type, or provenance
        }]
    };
}
```

### 5. Cascade Deletion

**When ontology is deleted:**
```python
# In routes/ontology.py
def delete_ontology(ontology_name: str, force: bool = False):
    """Delete ontology and all associated data"""

    # ... existing deletion logic (instances, sources, concepts) ...

    # Delete DocumentMeta nodes
    doc_meta_deleted = client._execute_cypher("""
        SELECT * FROM cypher('knowledge_graph', $$
            MATCH (d:DocumentMeta {ontology: $ontology})
            DETACH DELETE d
            RETURN count(d) as deleted
        $$, $params) as (count agtype);
    """, {"ontology": ontology_name})

    logger.info(f"Deleted {doc_meta_deleted} DocumentMeta nodes for ontology '{ontology_name}'")
```

### 6. Edge Metadata Creation

**No schema migration required!** Apache AGE natively supports edge properties.

**In `ingestion.py` (concept relationship creation):**

```python
def create_concept_relationship(
    age_client: AGEClient,
    from_concept_id: str,
    to_concept_id: str,
    rel_type: str,
    job_id: str,
    user_id: str,
    document_id: str
):
    """Create relationship with provenance metadata (ADR-051)"""

    query = """
    SELECT * FROM cypher('knowledge_graph', $$
        MATCH (c1:Concept {concept_id: $from_id})
        MATCH (c2:Concept {concept_id: $to_id})
        CREATE (c1)-[r:$rel_type {
            created_at: datetime(),
            created_by: $user_id,
            source: 'llm_extraction',
            job_id: $job_id,
            document_id: $document_id
        }]->(c2)
        RETURN r
    $$, $params) as (rel agtype);
    """

    age_client._execute_cypher(query, {
        "from_id": from_concept_id,
        "to_id": to_concept_id,
        "rel_type": rel_type,
        "user_id": user_id,
        "job_id": job_id,
        "document_id": document_id
    })
```

**In `ingestion_worker.py` (update all relationship creation calls):**

```python
# Pass metadata when creating relationships
create_concept_relationship(
    age_client=age_client,
    from_concept_id=concept1_id,
    to_concept_id=concept2_id,
    rel_type="IMPLIES",
    job_id=job_id,
    user_id=job_data.get("user_id"),
    document_id=job_data.get("content_hash")  # Links to DocumentMeta
)
```

**Update ALL relationship types:**
- `IMPLIES`, `SUPPORTS`, `CONTRADICTS` (concept relationships)
- `EVIDENCED_BY` (concept → instance)
- `FROM_SOURCE` (instance → source)
- `APPEARS_IN` (concept → source)
- `HAS_SOURCE` (DocumentMeta → source)

---

## ADR-044 Compliance: Timestamp Storage vs. Visibility

### The Challenge

ADR-044 (Probabilistic Truth Convergence) states that truth emerges from SUPPORTS/CONTRADICTS relationships, not document age. Timestamps must not create false "newer = better" biases.

### Solution: Silent Storage, Selective Visibility

**All sources store timestamps** (operational audit trail):
- ✅ CLI file ingestion: Stores timestamp (user-visible in `kg ontology info`)
- ✅ CLI stdin: Stores timestamp (user-visible)
- ✅ MCP ingestion: Stores timestamp (AI-invisible, silently added by server)

**AI visibility constraints:**
- ✅ MCP tool responses: NO timestamp, NO source metadata exposed
- ✅ Graph queries by AI: Can see DocumentMeta nodes, but shouldn't reason about age
- ✅ Human CLI output: Full metadata visible (humans understand context)

### Example: MCP Tool Response

**What the MCP server returns to Claude:**
```json
{
  "content": [{
    "type": "text",
    "text": "✓ Text ingested into ontology \"My Docs\"\nJob ID: job_abc123\nStatus: awaiting_approval"
  }]
}
```

**What's stored in the graph (silently):**
```cypher
(:DocumentMeta {
  document_id: "sha256:abc123...",
  filename: "mcp_session_1730395234",
  source_type: "mcp",
  ingested_at: "2025-10-31T12:34:56Z",  // ← Silent timestamp
  ingested_by: "user_123"
})
```

**Why this works:**
- Timestamp exists for audit purposes (operational queries, compliance)
- AI never sees timestamp in tool responses → no recency bias
- Humans can use timestamps for legitimate operational tasks

---

## User Experience

### Before (ADR-014 only)

```bash
# Scenario: 50 old docs + 50 new docs, all jobs failed due to bad API key
$ kg ingest directory/ -o "My Docs"
❌ Error: 100 documents already submitted (failed jobs exist)

# User deletes failed jobs to "clear the way"
$ kg job delete --status=failed --ontology="My Docs"
✓ Deleted 100 failed jobs

# Re-ingest now processes ALL files (including 50 duplicates)
$ kg ingest directory/ -o "My Docs"
✓ Processing 100 documents...
✓ Completed: 850 concepts, 1500 sources  # ⚠️ 50 documents duplicated!
```

### After (ADR-051)

```bash
# Scenario: 50 old docs + 50 new docs, all jobs failed due to bad API key
$ kg ingest directory/ -o "My Docs"
✓ Analyzing directory...
  - 50 documents already in graph (skipped)
  - 50 new documents (will process)
✓ Job queued: job_abc123

# User can safely delete failed jobs (graph is source of truth)
$ kg job delete --status=failed --ontology="My Docs"
✓ Deleted 100 failed jobs

# Re-ingest only processes new files (deduplication works)
$ kg ingest directory/ -o "My Docs"
✓ Analyzing directory...
  - 50 documents already in graph (skipped)
  - 50 new documents (will process)
✓ Processing 50 new documents...
✓ Completed: 425 concepts, 750 sources  # ✓ Only new documents processed
```

### Query Examples

**Show all documents in ontology:**
```bash
$ kg ontology info "My Docs"

Documents in ontology:
┌──────────────────────┬────────────┬──────────────────────┬──────────────┬──────────┐
│ Filename             │ Source     │ Ingested             │ By           │ Sources  │
├──────────────────────┼────────────┼──────────────────────┼──────────────┼──────────┤
│ chapter1.txt         │ file       │ 2025-10-31 12:34:56  │ user_123     │ 15       │
│ chapter2.txt         │ file       │ 2025-10-30 14:22:11  │ user_123     │ 12       │
│ stdin                │ stdin      │ 2025-10-29 09:15:33  │ user_456     │ 8        │
│ mcp_session_173039...│ mcp        │ 2025-10-28 16:44:02  │ claude_mcp   │ 5        │
└──────────────────────┴────────────┴──────────────────────┴──────────────┴──────────┘

Total: 4 documents, 40 source nodes
```

**Show documents by source type:**
```cypher
MATCH (d:DocumentMeta {ontology: "My Docs"})
RETURN d.source_type, count(*) as doc_count
ORDER BY doc_count DESC

// Output:
// source_type | doc_count
// ------------|----------
// file        | 47
// mcp         | 12
// stdin       | 3
```

**Force re-ingestion:**
```bash
$ kg ingest chapter1.txt -o "My Docs" --force
⚠️  Document already exists in graph:
  - Filename: chapter1.txt
  - Ingested: 2025-10-31 12:34:56
  - Sources: 15

✓ Deleting existing DocumentMeta and sources...
✓ Re-ingesting document...
✓ Completed: 15 concepts, 15 sources
```

---

## Consequences

### Positive

✅ **Job deletion safe** - Deleting jobs never breaks deduplication
✅ **Graph is self-documenting** - Query "what documents are in this ontology?" directly
✅ **Complete audit trail** - Track when, where, how, and by whom documents were ingested
✅ **Source-aware operations** - Can delete/re-ingest specific documents by type
✅ **ADR-044 compliant** - Timestamp storage doesn't create AI reasoning bias
✅ **Ontology cleanup** - DocumentMeta deleted when ontology deleted
✅ **Directory re-ingestion** - Only processes new files, skips existing
✅ **Minimal performance impact** - One additional graph query per ingestion

### Negative

⚠️ **Additional graph node type** - One more node type to maintain
⚠️ **Schema migration required** - Jobs table needs new columns
⚠️ **Storage overhead** - One DocumentMeta node per document (~1KB each)
⚠️ **Implementation complexity** - More code paths for metadata enrichment

### Neutral

🔵 **Backward compatibility** - Existing ingestions won't have DocumentMeta (can backfill or ignore)
🔵 **Jobs table still useful** - Job history remains valuable for operational queries
🔵 **--force flag required** - Users must explicitly force re-ingestion of existing documents

---

## Implementation Plan

### Phase 1: Core Functionality (Required for MVP)

- [ ] Create migration `021_graph_document_deduplication.sql` (jobs table columns)
- [ ] Add `create_document_meta()` method to AGEClient
- [ ] Add `get_document_meta()` deduplication check to AGEClient
- [ ] Update `ingestion_worker.py` to create DocumentMeta after success
- [ ] Update deduplication check to use graph instead of jobs table
- [ ] Update `delete_ontology()` to delete DocumentMeta nodes
- [ ] Update API ingest endpoint to accept `source_metadata`

### Phase 2: Client Enrichment (Required for Full Audit Trail)

- [ ] Update kg CLI file ingestion to send `source_metadata` (file path, hostname)
- [ ] Update kg CLI stdin ingestion to send `source_metadata` (stdin marker)
- [ ] Update MCP server to silently add `source_metadata` (session ID, mcp type)
- [ ] Add `kg ontology info` command to display DocumentMeta table

### Phase 3: Advanced Features (Optional Enhancements)

- [ ] Add `--force` flag support (delete old DocumentMeta, re-ingest)
- [ ] Add bulk directory ingestion with smart skip (check all files upfront)
- [ ] Add document-level delete command (`kg document delete <hash>`)
- [ ] Add backfill script for existing ingestions (create DocumentMeta retroactively)

---

## Alternatives Considered

### Alternative 1: Keep Jobs Table as Source of Truth

**Approach:** Fix the race condition bug, add retention policies, but keep jobs table as deduplication source.

**Rejected:**
- ❌ Jobs are operational logs, not persistent state
- ❌ Job retention policies break deduplication
- ❌ Cross-ontology queries are awkward (SQL joins instead of graph traversals)
- ❌ Cannot query "what documents are in the graph?" without job history

### Alternative 2: Source Nodes Track Deduplication

**Approach:** Add `document_hash` property to existing `:Source` nodes, check all sources in ontology.

**Rejected:**
- ❌ Requires full graph scan of Source nodes (O(N) instead of O(1))
- ❌ No document-level metadata (can't track file path, ingestion time, etc.)
- ❌ Mixing concerns (Source nodes are evidence chunks, not document metadata)

### Alternative 3: Separate PostgreSQL Table (No Graph Nodes)

**Approach:** Create `kg_api.document_registry` table instead of graph nodes.

**Rejected:**
- ❌ Splits state between SQL (documents) and graph (content)
- ❌ Cannot traverse relationships (which sources belong to which documents?)
- ❌ Doesn't leverage graph query capabilities
- ✅ Slightly faster lookups (but graph lookups are already fast enough)

---

## Related Decisions

- **ADR-014: Job Approval Workflow** - Keeps document-level SHA-256 hashing, adds persistent graph tracking
- **ADR-044: Probabilistic Truth Convergence** - Timestamp storage vs. visibility constraints
- **ADR-024: Multi-Schema PostgreSQL Architecture** - Jobs table lives in `kg_api` schema
- **ADR-016: Apache AGE Migration** - Graph storage and query patterns

---

## Open Questions

1. **Should we backfill DocumentMeta for existing ingestions?**
   - Pro: Complete audit trail, all documents tracked
   - Con: Requires scanning all Source nodes, inferring metadata from job history
   - **Decision:** Optional backfill script, not required for new system to work

2. **Should DocumentMeta track concept count?**
   - Pro: Quick stats without graph traversal
   - Con: Adds complexity (update on concept merges?)
   - **Decision:** Track `source_count` only (immutable after ingestion)

3. **Should we support document-level updates (re-ingest same file)?**
   - Pro: Users can update documentation and refresh graph
   - Con: How to handle existing concepts/sources? (merge vs replace)
   - **Decision:** `--force` flag deletes old DocumentMeta + sources, then re-ingests (destructive)

4. **Should MCP server expose any metadata to Claude in query results?**
   - Pro: Claude could help users understand provenance
   - Con: Timestamp visibility risks recency bias (ADR-044)
   - **Decision:** TBD - Consider exposing `source_type` but NOT `ingested_at`

---

## Validation Status

- [ ] Schema migration tested on development database
- [ ] DocumentMeta creation tested with all source types (file, stdin, mcp, api)
- [ ] Deduplication tested: duplicate rejection works
- [ ] Job deletion tested: deduplication still works after job cleanup
- [ ] Cascade deletion tested: ontology delete removes DocumentMeta
- [ ] MCP integration tested: metadata added silently, not exposed to AI
- [ ] CLI display tested: `kg ontology info` shows document table
- [ ] Performance tested: deduplication adds <10ms per ingestion

---

**Next Steps:**
1. Review ADR with team
2. Implement Phase 1 (core functionality)
3. Test with real-world directory re-ingestion scenario
4. Gather user feedback on metadata visibility
5. Implement Phase 2 (client enrichment)
