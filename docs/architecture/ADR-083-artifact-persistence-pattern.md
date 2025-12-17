# ADR-083: Artifact Persistence Pattern

**Status:** Accepted
**Date:** 2025-12-17
**Deciders:** @aaronsb, @claude
**Related ADRs:** ADR-079 (Projection Storage), ADR-082 (User Scoping), ADR-014 (Job Queue)

## Context

The knowledge graph system produces various computed artifacts:
- Polarity axis analyses (expensive: ~189 seconds observed)
- t-SNE/UMAP projections (expensive: 1-30 seconds)
- Graph query results (variable cost)
- Vocabulary analyses (moderate cost)
- Search results, connection paths, reports

Currently:
- Some artifacts are ephemeral (lost on page refresh)
- Some use Zustand stores (browser session only)
- Projections use Garage storage (ADR-079) but ad-hoc
- No unified pattern for persistence, ownership, or recall

### Problems

1. **Expensive re-computation** - 189-second polarity analysis lost on refresh
2. **No sharing** - Users can't share saved analyses
3. **No AI recall** - MCP agents can't retrieve previous work
4. **Inconsistent** - Each feature handles persistence differently
5. **Web timeouts** - Long computations exceed 30-second HTTP timeout

### Goals

1. **Unified pattern** for all artifact types
2. **Multi-tier storage** optimized for different data sizes
3. **Ownership model** integrated with ADR-082
4. **Freshness tracking** via graph epoch
5. **Lazy loading** to avoid memory bloat
6. **Resilient** with fallback paths

## Decision

### 1. Multi-Tier Storage Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Persistence Hierarchy                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Tier 0: PostgreSQL (Source of Truth)                          │
│    • Artifact metadata, definitions, ownership                  │
│    • Small payloads inline (JSONB, <10KB)                       │
│    • Pointers to Garage for large payloads                      │
│                                                                 │
│  Tier 1: Zustand (Working State)                                │
│    • Artifact pointers (metadata only)                          │
│    • Small fully-loaded data (themes, preferences, diagrams)    │
│    • Active session state                                       │
│                                                                 │
│  Tier 2: LocalStorage (Client Cache)                            │
│    • Recent large payloads (LRU eviction)                       │
│    • Quick reload without API round-trip                        │
│    • Validated against graph_epoch                              │
│                                                                 │
│  Tier 3: Garage S3 (Blob Archive)                               │
│    • Large payloads (>10KB)                                     │
│    • Historical artifacts                                       │
│    • Shared/public data                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Data Classification

| Data Type | Size | Tier 0 (DB) | Tier 1 (Zustand) | Tier 2 (Local) | Tier 3 (Garage) |
|-----------|------|:-----------:|:----------------:|:--------------:|:---------------:|
| Artifact metadata | Small | ✓ Source | ✓ Hydrate | - | - |
| User preferences | Small | ✓ Source | ✓ Hydrate | - | - |
| Color themes | Small | ✓ Source | ✓ Hydrate | - | - |
| Query definitions | Small | ✓ Source | ✓ Hydrate | - | - |
| Small results (<10KB) | Small | ✓ Inline | - | ✓ Cache | - |
| Large results (>10KB) | Large | Pointer | - | ✓ Cache | ✓ Source |
| Recent graph state | Variable | Pointer | Pointer | ✓ Cache | Optional |
| Session state | Ephemeral | - | ✓ | - | - |

### 3. Artifact Types and Representations

**Artifact Types** (what's computed):

| Type | Typical Size | Storage | Async Job? |
|------|--------------|---------|------------|
| `polarity_analysis` | 10-500KB | Garage | Yes (>30s) |
| `projection` | 50-500KB | Garage | Yes (>500 concepts) |
| `query_result` | Variable | Garage if large | Optional |
| `graph_subgraph` | Variable | Garage if large | No |
| `vocabulary_analysis` | 5-50KB | Inline or Garage | No |
| `epistemic_measurement` | 10-100KB | Garage | Yes |
| `consolidation_result` | 5-50KB | Garage | Yes (LLM) |
| `search_result` | 1-20KB | Inline | No |
| `connection_path` | 1-10KB | Inline | No |
| `report` | Variable | Garage | No |
| `stats_snapshot` | 1-5KB | Inline | No |

**Representations** (where it came from):

| Representation | Description |
|----------------|-------------|
| `polarity_explorer` | Web: Polarity axis workspace |
| `embedding_landscape` | Web: t-SNE/UMAP projection |
| `block_builder` | Web: Visual query builder |
| `edge_explorer` | Web: System vocabulary visualization |
| `vocabulary_chord` | Web: Subgraph vocabulary analysis |
| `force_graph_2d` | Web: 2D graph explorer |
| `force_graph_3d` | Web: 3D graph explorer |
| `report_workspace` | Web: Aggregated reports |
| `cli` | Command-line interface |
| `mcp_server` | Claude Desktop / AI agents |
| `api_direct` | Programmatic API access |

### 4. SQL Schema

```sql
-- Query/Report Definitions (the "recipe" that can be re-run)
CREATE TABLE kg_api.query_definitions (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    definition_type VARCHAR(50) NOT NULL,
    definition JSONB NOT NULL,
    owner_id INTEGER REFERENCES kg_auth.users(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_definition_type CHECK (definition_type IN (
        'block_diagram', 'cypher', 'search', 'polarity', 'connection'
    ))
);

CREATE INDEX idx_query_def_owner ON kg_api.query_definitions(owner_id);
CREATE INDEX idx_query_def_type ON kg_api.query_definitions(definition_type);

-- Computed Artifacts (results, analyses, snapshots)
CREATE TABLE kg_api.artifacts (
    id SERIAL PRIMARY KEY,

    -- Classification
    artifact_type VARCHAR(50) NOT NULL,
    representation VARCHAR(50) NOT NULL,
    name VARCHAR(200),

    -- Ownership (NULL = system-owned, integrates with ADR-082)
    owner_id INTEGER REFERENCES kg_auth.users(id),

    -- Freshness tracking
    graph_epoch INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,

    -- Content (either inline or pointer to Garage)
    parameters JSONB NOT NULL,
    metadata JSONB,
    inline_result JSONB,
    garage_key VARCHAR(200),

    -- Relationships
    query_definition_id INTEGER REFERENCES kg_api.query_definitions(id),
    ontology VARCHAR(200),
    concept_ids TEXT[],

    CONSTRAINT valid_artifact_type CHECK (artifact_type IN (
        'polarity_analysis', 'projection', 'query_result', 'graph_subgraph',
        'vocabulary_analysis', 'epistemic_measurement', 'consolidation_result',
        'search_result', 'connection_path', 'report', 'stats_snapshot'
    )),
    CONSTRAINT valid_representation CHECK (representation IN (
        'polarity_explorer', 'embedding_landscape', 'block_builder',
        'edge_explorer', 'vocabulary_chord', 'force_graph_2d', 'force_graph_3d',
        'report_workspace', 'cli', 'mcp_server', 'api_direct'
    )),
    CONSTRAINT has_content CHECK (
        inline_result IS NOT NULL OR garage_key IS NOT NULL
    )
);

CREATE INDEX idx_artifacts_owner ON kg_api.artifacts(owner_id);
CREATE INDEX idx_artifacts_type ON kg_api.artifacts(artifact_type);
CREATE INDEX idx_artifacts_representation ON kg_api.artifacts(representation);
CREATE INDEX idx_artifacts_ontology ON kg_api.artifacts(ontology);
CREATE INDEX idx_artifacts_epoch ON kg_api.artifacts(graph_epoch);
CREATE INDEX idx_artifacts_created ON kg_api.artifacts(created_at DESC);
CREATE INDEX idx_artifacts_query_def ON kg_api.artifacts(query_definition_id);
```

### 5. Validation Chain

```
Scenario 1: LocalStorage hit (fastest)
  DB(✓) → Zustand(✓) → LocalStorage(✓, epoch matches)
  → Use cached payload immediately

Scenario 2: LocalStorage miss, Garage hit
  DB(✓) → Zustand(✓) → LocalStorage(✗) → Garage(✓)
  → Fetch from Garage via API
  → Cache in LocalStorage for next time

Scenario 3: Stale data (graph changed)
  DB(✓, epoch=100) → Zustand(✓) → LocalStorage(✓, epoch=90)
  → Warn: "Data is stale (graph changed). Regenerate?"
  → User chooses: Use anyway | Regenerate | Cancel

Scenario 4: Garage blob missing
  DB(✓) → Zustand(✓) → Garage(✗)
  → Error: "Artifact data unavailable"
  → User chooses: Delete artifact | Regenerate | Cancel

Scenario 5: Inline result (small artifacts)
  DB(✓, inline_result) → API
  → Return inline data directly, no Garage fetch
```

### 6. API Endpoints

```python
# List artifacts (metadata only - fast)
GET /artifacts
Query: owner=me|all, type=?, representation=?, ontology=?
Response: [{ id, name, type, representation, graph_epoch, is_fresh, created_at }]

# Get artifact metadata
GET /artifacts/{id}
Response: { id, name, parameters, graph_epoch, is_fresh, has_inline, garage_key }

# Get artifact payload (handles inline vs Garage)
GET /artifacts/{id}/payload
Response: The actual data (from inline_result or Garage)
Errors: 404 if Garage blob missing

# Create artifact (persist from client)
POST /artifacts
Body: { artifact_type, representation, name?, parameters, payload }
Response: { id, garage_key? }

# Regenerate artifact (re-run the computation)
POST /artifacts/{id}/regenerate
Response: { job_id } (async) or { id, payload } (sync if fast)

# Delete artifact
DELETE /artifacts/{id}
Effect: Removes DB record and Garage blob

# Save query definition
POST /query-definitions
Body: { name, definition_type, definition }
Response: { id }

# List query definitions
GET /query-definitions
Query: owner=me, type=?
Response: [{ id, name, definition_type, updated_at }]

# Execute query definition (creates artifact)
POST /query-definitions/{id}/execute
Response: { artifact_id, job_id? }
```

### 7. Async Job Integration

For expensive computations (>30 seconds), integrate with ADR-014 job queue:

```python
POST /artifacts
Body: { artifact_type: "polarity_analysis", parameters: {...}, async: true }

Response (if async):
{
  "status": "queued",
  "job_id": "job_abc123",
  "artifact_id": 42  # Reserved, will be populated when complete
}

# Poll for completion
GET /jobs/{job_id}
Response: { status: "running", progress: { percent: 45, message: "..." } }

# When complete, artifact is ready
GET /artifacts/42/payload
```

### 8. Client-Side Implementation

**Zustand Store (lightweight pointers):**

```typescript
interface ArtifactStore {
  // Metadata only - no large payloads
  artifacts: ArtifactMeta[];
  queryDefinitions: QueryDefinition[];

  // Actions
  loadArtifacts: () => Promise<void>;
  loadQueryDefinitions: () => Promise<void>;
  persistArtifact: (type: string, params: any, payload: any) => Promise<string>;
  deleteArtifact: (id: string) => Promise<void>;
}

interface ArtifactMeta {
  id: string;
  name: string;
  artifact_type: string;
  representation: string;
  graph_epoch: number;
  is_fresh: boolean;
  created_at: string;
  has_inline: boolean;
}
```

**Payload Fetching (component-level, with LocalStorage cache):**

```typescript
async function fetchArtifactPayload(artifactId: string, meta: ArtifactMeta) {
  const cacheKey = `artifact:${artifactId}`;

  // Check LocalStorage cache
  const cached = localStorage.getItem(cacheKey);
  if (cached) {
    const { epoch, payload } = JSON.parse(cached);
    if (epoch === meta.graph_epoch) {
      return { status: 'cached', payload };
    }
    // Stale - will fetch fresh but warn user
  }

  // Fetch from API (inline or Garage)
  try {
    const payload = await api.getArtifactPayload(artifactId);

    // Cache in LocalStorage (with LRU eviction if needed)
    cachePayload(cacheKey, meta.graph_epoch, payload);

    return {
      status: cached ? 'stale_refreshed' : 'fetched',
      payload,
      was_stale: !!cached
    };
  } catch (e) {
    if (e.status === 404) {
      return { status: 'missing', canRegenerate: true };
    }
    throw e;
  }
}

// LRU cache management
function cachePayload(key: string, epoch: number, payload: any) {
  const MAX_CACHE_SIZE = 50 * 1024 * 1024; // 50MB
  const data = JSON.stringify({ epoch, payload });

  // Evict old entries if needed
  while (getLocalStorageSize() + data.length > MAX_CACHE_SIZE) {
    evictOldestArtifactCache();
  }

  localStorage.setItem(key, data);
  localStorage.setItem(`${key}:accessed`, Date.now().toString());
}
```

**Component Pattern:**

```tsx
function ArtifactViewer({ artifactId }: Props) {
  const meta = useArtifactStore(s => s.artifacts.find(a => a.id === artifactId));
  const [state, setState] = useState<'loading'|'ready'|'stale'|'missing'>('loading');
  const [payload, setPayload] = useState<any>(null);

  useEffect(() => {
    if (!meta) return;

    fetchArtifactPayload(artifactId, meta).then(result => {
      switch (result.status) {
        case 'cached':
        case 'fetched':
          setPayload(result.payload);
          setState('ready');
          break;
        case 'stale_refreshed':
          setPayload(result.payload);
          setState('ready'); // Fresh data fetched
          break;
        case 'missing':
          setState('missing');
          break;
      }
    });

    // Cleanup on unmount - release memory
    return () => setPayload(null);
  }, [artifactId, meta?.graph_epoch]);

  if (!meta) return <NotFound />;
  if (state === 'loading') return <Loading />;
  if (state === 'missing') return <MissingArtifact onRegenerate={...} onDelete={...} />;
  if (!meta.is_fresh) return <StaleWarning onContinue={() => {}} onRegenerate={...} />;

  return <ArtifactRenderer type={meta.artifact_type} payload={payload} />;
}
```

### 9. Garage Storage Structure

```
artifacts/
├── polarity/
│   ├── {artifact_id}.json
│   └── {artifact_id}.json
├── projection/
│   ├── {ontology}/
│   │   ├── latest.json
│   │   └── {timestamp}.json
├── query_result/
│   └── {artifact_id}.json
├── report/
│   └── {artifact_id}.json
└── ...
```

### 10. Migration from ADR-079

ADR-079 established projection storage in Garage. This ADR generalizes that pattern:

- Existing projection storage continues to work
- Add `kg_api.artifacts` records for existing projections
- New projections create artifacts automatically
- Unified API for all artifact types

## Consequences

### Positive

1. **Unified pattern** - All artifacts follow same persistence model
2. **No lost work** - Expensive computations survive page refresh
3. **Shareable** - Artifacts can be shared via grants (ADR-082)
4. **AI-friendly** - MCP agents can list and recall artifacts
5. **Memory efficient** - Large data stays out of Zustand
6. **Fast reload** - LocalStorage caching for recent artifacts
7. **Resilient** - Multiple fallback paths, clear error states
8. **Async support** - Long computations don't timeout

### Negative

1. **Complexity** - Multi-tier storage requires careful implementation
2. **Storage costs** - Garage usage increases
3. **Cache invalidation** - LocalStorage cache must track freshness
4. **Migration** - Existing Zustand stores need refactoring

### Neutral

1. **Zustand remains** - Still used for working state, just lighter
2. **LocalStorage optional** - Cache improves UX but not required
3. **Inline vs Garage** - Small artifacts stay in DB, large go to Garage

## Implementation Plan

### Phase 1: Schema and API
1. Create migration for `query_definitions` and `artifacts` tables
2. Implement artifact CRUD endpoints
3. Implement payload storage (inline vs Garage routing)

### Phase 2: Async Integration
1. Add artifact job type to job queue
2. Implement workers for expensive artifact types
3. Connect job completion to artifact finalization

### Phase 3: Web Client
1. Create `useArtifactStore` Zustand store
2. Implement `fetchArtifactPayload` with LocalStorage caching
3. Refactor existing stores to use artifact pattern:
   - `polarityState` → artifacts
   - `blockDiagramStore` → query_definitions
   - `reportStore` → artifacts

### Phase 4: CLI/MCP
1. Add `artifact list`, `artifact show`, `artifact delete` commands
2. Update MCP tools to support artifact recall
3. Add artifact creation from CLI results

## References

- ADR-014: Job Queue (async processing)
- ADR-079: Projection Artifact Storage (Garage pattern, superseded/generalized)
- ADR-082: User Scoping and Artifact Ownership
