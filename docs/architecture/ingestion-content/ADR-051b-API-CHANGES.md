# ADR-051: API Changes for Graph-Based Document Deduplication

**Date:** 2025-10-31
**Related:** ADR-051 (Graph-Based Document Deduplication)

## Overview

ADR-051a introduced a fundamental architectural change: moving document deduplication from the ephemeral jobs table to permanent DocumentMeta nodes in the graph. But that decision requires actual API and database changes to implement. This document specifies exactly what needs to change and how to do it while maintaining backward compatibility with existing clients.

The core change is adding optional source metadata fields to the ingestion endpoints. When you upload a file through the CLI, the client can now send extra information like the full file path, hostname where you're running, and what type of source it is (file upload, piped stdin, API call, etc.). This metadata gets stored in both the jobs table and the DocumentMeta node, creating a complete audit trail of where documents came from.

The beauty is that all these new parameters are optional—existing API clients continue to work without any modifications. The kg CLI gets smarter by sending this metadata, but direct API users can keep doing what they're doing. The deduplication logic changes to check the graph first (persistent state) and only fall back to the jobs table for in-progress jobs, so you can safely delete old job records without breaking deduplication.

New API endpoints let you query which documents are in an ontology, get details about a specific document, and even delete individual documents with all their sources. The graph becomes queryable in new ways: "show me all documents ingested via MCP," "which documents came from this machine," or "delete everything ingested on this date." The system gains transparency while maintaining complete backward compatibility.

---

## Current API (Before ADR-051)

This document specifies the exact API changes needed to implement ADR-051. These changes are **backward compatible** - existing clients continue to work without modification.

---

## Current API (Before ADR-051)

### POST /ingest (File Upload)

**Parameters:**
```python
file: UploadFile           # Document file
ontology: str              # Ontology name
filename: Optional[str]    # Override filename
force: bool               # Force re-ingestion
auto_approve: bool        # Skip approval
processing_mode: str      # serial | parallel
target_words: int         # Chunking params
overlap_words: int        # Chunking params
```

**Job Data Stored:**
```python
job_data = {
    "content": base64_encoded_content,
    "content_hash": "sha256:...",
    "ontology": "My Docs",
    "filename": "chapter1.txt",
    "user_id": "user_123",
    "processing_mode": "serial",
    "options": {...}
}
```

### POST /ingest/text (Text Ingestion)

**Parameters:**
```python
text: str                  # Text content
ontology: str              # Ontology name
filename: Optional[str]    # Source name
force: bool               # Force re-ingestion
auto_approve: bool        # Skip approval
processing_mode: str      # serial | parallel
target_words: int         # Chunking params
overlap_words: int        # Chunking params
```

**Job Data Stored:** (Same structure as file upload)

---

## Proposed API Changes (ADR-051)

### 1. Add Optional Source Metadata to Both Endpoints

**New optional parameters (backward compatible):**

```python
# POST /ingest and POST /ingest/text
source_path: Optional[str] = Form(None)      # Full filesystem path (CLI file ingestion only)
source_hostname: Optional[str] = Form(None)  # Hostname where ingested (CLI only)
source_type: Optional[str] = Form(None)      # "file" | "stdin" | "mcp" | "api"
```

**Backward Compatibility:**
- All three parameters are **optional**
- Existing clients work without changes
- If not provided, defaults to `None` (best-effort metadata)

**Jobs Table Schema (Migration Required):**
```sql
ALTER TABLE kg_api.jobs
ADD COLUMN source_filename TEXT,     -- Already have "filename" field
ADD COLUMN source_type TEXT,         -- NEW: "file" | "stdin" | "mcp" | "api"
ADD COLUMN source_path TEXT,         -- NEW: full filesystem path
ADD COLUMN source_hostname TEXT;     -- NEW: hostname where ingested
```

**Updated Job Data Structure:**
```python
job_data = {
    # Existing fields (unchanged)
    "content": base64_encoded_content,
    "content_hash": "sha256:...",
    "ontology": "My Docs",
    "filename": "chapter1.txt",          # Display name
    "user_id": "user_123",
    "processing_mode": "serial",
    "options": {...},

    # NEW: Source metadata (optional)
    "source_type": "file",               # or "stdin", "mcp", "api"
    "source_path": "/home/user/docs/chapter1.txt",  # null for non-file sources
    "source_hostname": "workstation-01"  # null for MCP/API
}
```

---

## Client Implementations

### kg CLI (File Ingestion)

**Client enrichment (TypeScript):**

```typescript
// client/src/cli/ingest.ts
import os from 'os';
import path from 'path';

async function ingestFile(filePath: string, ontology: string) {
    const absolutePath = path.resolve(filePath);
    const filename = path.basename(filePath);
    const hostname = os.hostname();

    // Prepare form data
    const formData = new FormData();
    formData.append('file', fs.createReadStream(filePath));
    formData.append('ontology', ontology);

    // NEW: Add source metadata
    formData.append('source_type', 'file');
    formData.append('source_path', absolutePath);
    formData.append('source_hostname', hostname);

    const response = await apiClient.post('/ingest', formData);
}
```

### kg CLI (Stdin Ingestion)

```typescript
// cat document.txt | kg ingest -o "My Docs"
async function ingestStdin(ontology: string) {
    const content = await readStdin();
    const hostname = os.hostname();

    const formData = new FormData();
    formData.append('text', content);
    formData.append('ontology', ontology);
    formData.append('filename', 'stdin');  // Existing field

    // NEW: Add source metadata
    formData.append('source_type', 'stdin');
    formData.append('source_hostname', hostname);
    // source_path = null (not provided)

    const response = await apiClient.post('/ingest/text', formData);
}
```

### MCP Server (Silent Enrichment)

```typescript
// client/src/mcp-server.ts
case "ingest_text": {
    const { text, ontology, auto_approve } = args;

    const formData = new FormData();
    formData.append('text', text);
    formData.append('ontology', ontology);
    formData.append('auto_approve', String(auto_approve));

    // NEW: Silently enrich with MCP metadata
    formData.append('filename', `mcp_session_${Date.now()}`);
    formData.append('source_type', 'mcp');
    // source_path = null (not provided)
    // source_hostname = null (not provided)

    const response = await apiClient.post('/ingest/text', formData);

    // Return to Claude WITHOUT mentioning metadata
    return {
        content: [{
            type: "text",
            text: `✓ Text ingested into ontology "${ontology}"\n` +
                  `Job ID: ${response.job_id}\n` +
                  `Status: ${response.status}`
            // NO mention of timestamp, source type, or metadata
        }]
    };
}
```

### Direct API Usage (Python Example)

```python
# Example: Direct API call from Python script
import requests

# Minimal call (backward compatible)
response = requests.post(
    "http://localhost:8000/ingest/text",
    data={
        "text": "Some content...",
        "ontology": "My Docs",
        "auto_approve": "true"
    },
    headers={"Authorization": f"Bearer {token}"}
)

# Full call with source metadata (ADR-051)
response = requests.post(
    "http://localhost:8000/ingest/text",
    data={
        "text": "Some content...",
        "ontology": "My Docs",
        "auto_approve": "true",
        "source_type": "api",          # NEW
        "filename": "automated_report" # NEW (was optional before)
    },
    headers={"Authorization": f"Bearer {token}"}
)
```

---

## New API Endpoints (Query DocumentMeta)

### GET /ontology/{ontology_name}/documents

**Purpose:** List all documents in an ontology (query DocumentMeta nodes)

**Response:**
```json
{
  "ontology": "My Docs",
  "document_count": 4,
  "source_count": 40,
  "documents": [
    {
      "document_id": "sha256:abc123...",
      "filename": "chapter1.txt",
      "source_type": "file",
      "file_path": "/home/user/docs/chapter1.txt",
      "hostname": "workstation-01",
      "ingested_at": "2025-10-31T12:34:56Z",
      "ingested_by": "user_123",
      "source_count": 15
    },
    {
      "document_id": "sha256:def456...",
      "filename": "mcp_session_1730395234",
      "source_type": "mcp",
      "file_path": null,
      "hostname": null,
      "ingested_at": "2025-10-28T16:44:02Z",
      "ingested_by": "claude_mcp",
      "source_count": 5
    }
  ]
}
```

**Implementation:**
```python
# src/api/routes/ontology.py

@router.get("/{ontology_name}/documents")
async def list_ontology_documents(
    ontology_name: str,
    current_user: dict = Depends(get_current_user)
):
    """List all documents in an ontology"""
    client = get_age_client()

    query = """
    SELECT * FROM cypher('knowledge_graph', $$
        MATCH (d:DocumentMeta {ontology: $ontology})
        RETURN d
        ORDER BY d.ingested_at DESC NULLS LAST
    $$, $params) as (doc agtype);
    """

    results = client._execute_cypher(query, {"ontology": ontology_name})

    documents = [row['doc'] for row in results]
    source_count = sum(doc.get('source_count', 0) for doc in documents)

    return {
        "ontology": ontology_name,
        "document_count": len(documents),
        "source_count": source_count,
        "documents": documents
    }
```

### GET /documents/{document_id}

**Purpose:** Get details about a specific document

**Response:**
```json
{
  "document_id": "sha256:abc123...",
  "content_hash": "sha256:abc123...",
  "ontology": "My Docs",
  "filename": "chapter1.txt",
  "source_type": "file",
  "file_path": "/home/user/docs/chapter1.txt",
  "hostname": "workstation-01",
  "ingested_at": "2025-10-31T12:34:56Z",
  "ingested_by": "user_123",
  "job_id": "job_xyz",
  "source_count": 15,
  "sources": [
    {"source_id": "chapter1_txt_chunk1", "paragraph": 1},
    {"source_id": "chapter1_txt_chunk2", "paragraph": 2},
    // ... up to 15 sources
  ]
}
```

**Implementation:**
```python
@router.get("/documents/{document_id}")
async def get_document_details(
    document_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Get document details including all linked sources"""
    client = get_age_client()

    query = """
    SELECT * FROM cypher('knowledge_graph', $$
        MATCH (d:DocumentMeta {document_id: $doc_id})
        OPTIONAL MATCH (d)-[:HAS_SOURCE]->(s:Source)
        RETURN d, collect({source_id: s.source_id, paragraph: s.paragraph}) as sources
    $$, $params) as (doc agtype, sources agtype);
    """

    result = client._execute_cypher(query, {"doc_id": document_id})

    if not result:
        raise HTTPException(404, "Document not found")

    return {
        **result[0]['doc'],
        "sources": result[0]['sources']
    }
```

### DELETE /documents/{document_id}

**Purpose:** Delete a specific document and all its sources/instances

**Response:**
```json
{
  "document_id": "sha256:abc123...",
  "deleted": true,
  "sources_deleted": 15,
  "instances_deleted": 47,
  "orphaned_concepts_deleted": 3
}
```

**Implementation:**
```python
@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    force: bool = Query(False),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a specific document and all its sources.

    Similar to ontology deletion but scoped to a single document.
    """
    if not force:
        raise HTTPException(400, "Must set force=true to delete document")

    client = get_age_client()

    # Get DocumentMeta
    doc = client.get_document_meta(document_id)
    if not doc:
        raise HTTPException(404, "Document not found")

    # Delete instances linked to this document's sources
    instances_deleted = client._execute_cypher("""
        SELECT * FROM cypher('knowledge_graph', $$
            MATCH (d:DocumentMeta {document_id: $doc_id})-[:HAS_SOURCE]->(s:Source)
            MATCH (s)<-[:FROM_SOURCE]-(i:Instance)
            DETACH DELETE i
            RETURN count(i) as deleted
        $$, $params) as (count agtype);
    """, {"doc_id": document_id})

    # Delete sources
    sources_deleted = client._execute_cypher("""
        SELECT * FROM cypher('knowledge_graph', $$
            MATCH (d:DocumentMeta {document_id: $doc_id})-[:HAS_SOURCE]->(s:Source)
            DETACH DELETE s
            RETURN count(s) as deleted
        $$, $params) as (count agtype);
    """, {"doc_id": document_id})

    # Delete orphaned concepts
    orphaned = client._execute_cypher("""
        SELECT * FROM cypher('knowledge_graph', $$
            MATCH (c:Concept)
            WHERE NOT (c)-[:APPEARS_IN]->(:Source)
            DETACH DELETE c
            RETURN count(c) as deleted
        $$) as (count agtype);
    """)

    # Delete DocumentMeta
    client._execute_cypher("""
        SELECT * FROM cypher('knowledge_graph', $$
            MATCH (d:DocumentMeta {document_id: $doc_id})
            DELETE d
        $$, $params) as (result agtype);
    """, {"doc_id": document_id})

    return {
        "document_id": document_id,
        "deleted": True,
        "sources_deleted": sources_deleted[0]['count'],
        "instances_deleted": instances_deleted[0]['count'],
        "orphaned_concepts_deleted": orphaned[0]['count']
    }
```

---

## Deduplication Check Changes

### Before (ADR-014 - Jobs Table)

**Location:** `src/api/services/content_hasher.py`

```python
def check_duplicate(self, content_hash: str, ontology: str) -> Optional[Dict]:
    """Check jobs table for duplicate"""
    return self.job_queue.check_duplicate(content_hash, ontology)
```

**Query:** (In `job_queue.py`)
```sql
SELECT * FROM kg_api.jobs
WHERE content_hash = :hash
  AND ontology = :ontology
  AND status IN ('completed', 'running', 'queued', 'awaiting_approval')
ORDER BY created_at DESC
LIMIT 1
```

### After (ADR-051 - Graph)

**Location:** `src/api/services/content_hasher.py`

```python
def check_duplicate(self, content_hash: str, ontology: str) -> Optional[Dict]:
    """Check graph for duplicate (ADR-051)"""
    from ..lib.age_client import get_age_client

    client = get_age_client()
    doc_meta = client.get_document_meta(content_hash, ontology)

    if doc_meta:
        # Document exists in graph - return structured info
        return {
            "duplicate": True,
            "document_id": doc_meta["document_id"],
            "filename": doc_meta.get("filename"),
            "ingested_at": doc_meta.get("ingested_at"),
            "source_count": doc_meta.get("source_count"),
            "source_type": doc_meta.get("source_type")
        }

    return None
```

**Query:** (In `age_client.py`)
```python
def get_document_meta(self, content_hash: str, ontology: str) -> Optional[Dict]:
    """Check if document exists in graph (ADR-051)"""
    query = """
    SELECT * FROM cypher('knowledge_graph', $$
        MATCH (d:DocumentMeta {content_hash: $hash, ontology: $ontology})
        RETURN d
    $$, $params) as (doc agtype);
    """

    result = self._execute_cypher(query, {
        "hash": content_hash,
        "ontology": ontology
    })

    return result[0]['doc'] if result else None
```

**Important:** Jobs table check becomes **fallback only** (for jobs in progress):
```python
def check_duplicate(self, content_hash: str, ontology: str) -> Optional[Dict]:
    """Check graph first, jobs table second (ADR-051)"""

    # Primary check: Graph (persistent state)
    doc_meta = client.get_document_meta(content_hash, ontology)
    if doc_meta:
        return {"duplicate": True, "source": "graph", ...}

    # Fallback check: Jobs table (in-progress jobs)
    active_job = self.job_queue.check_duplicate(content_hash, ontology)
    if active_job and active_job['status'] in ['running', 'queued', 'awaiting_approval']:
        return {"duplicate": True, "source": "job_queue", ...}

    return None
```

---

## Migration Strategy

### Phase 1: Backward Compatible Deployment

1. **Deploy API changes** (optional parameters don't break existing clients)
2. **Jobs table migration** (add new columns with `NULL` defaults)
3. **Keep old deduplication** (jobs table check still works)
4. **New ingestions** create DocumentMeta nodes
5. **Old ingestions** still work (no DocumentMeta, uses jobs table)

### Phase 2: Client Updates

1. **Update kg CLI** to send source metadata
2. **Update MCP server** to silently enrich metadata
3. **Test** both old and new clients work

### Phase 3: Full Cutover

1. **Switch deduplication** to check graph first (jobs table fallback)
2. **Verify** no regressions
3. **(Optional) Backfill** DocumentMeta for old ingestions

---

## Summary of Changes

### Required API Changes

✅ **POST /ingest** - Add 3 optional parameters (`source_type`, `source_path`, `source_hostname`)
✅ **POST /ingest/text** - Add same 3 optional parameters
✅ **Jobs table migration** - Add 3 new columns
✅ **Deduplication logic** - Check graph first, jobs table second

### New API Endpoints

✅ **GET /ontology/{name}/documents** - List documents in ontology
✅ **GET /documents/{id}** - Get document details
✅ **DELETE /documents/{id}** - Delete specific document

### Client Changes

✅ **kg CLI** - Send source metadata (file path, hostname, type)
✅ **MCP server** - Silently enrich with session ID and type

### Backward Compatibility

✅ **All changes are optional** - Existing clients work without modification
✅ **Graceful degradation** - Missing metadata defaults to `null`
✅ **Dual deduplication** - Graph primary, jobs table fallback

---

## Testing Checklist

- [ ] API accepts new optional parameters (no errors when omitted)
- [ ] Jobs table migration applied successfully
- [ ] Old clients work without changes (backward compatibility)
- [ ] kg CLI sends file path and hostname for file ingestion
- [ ] kg CLI sends "stdin" marker for piped input
- [ ] MCP server adds "mcp" source type (silently)
- [ ] MCP server doesn't expose metadata to Claude
- [ ] Deduplication checks graph before jobs table
- [ ] DocumentMeta created after successful ingestion
- [ ] Ontology deletion removes DocumentMeta nodes
- [ ] New document list endpoints return correct data
- [ ] Force re-ingestion deletes old DocumentMeta

---

**Next Steps:**
1. Review API changes with team
2. Create migration script `021_graph_document_deduplication.sql`
3. Implement API parameter additions (backward compatible)
4. Implement DocumentMeta creation in ingestion worker
5. Update deduplication check to prioritize graph
6. Update clients (kg CLI, MCP server)
7. Add new query endpoints
8. Test full workflow
