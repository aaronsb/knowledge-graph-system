# ADR-079: Projection Artifact Storage in Garage

**Status:** Proposed
**Date:** 2025-12-13
**Deciders:** @aaronsb, @claude
**Related ADRs:** ADR-057 (Multimodal Image Ingestion - Garage setup), ADR-078 (Embedding Landscape Explorer)

## Context

The Embedding Landscape Explorer (ADR-078) computes t-SNE/UMAP projections of concept embeddings into 3D space. These projections:

- Take 1-30 seconds to compute depending on ontology size
- Are deterministic given the same parameters and graph state
- Are expensive to recompute on every page load
- Could enable interesting time-series analysis if we kept historical versions

Currently, projections are computed on-demand and discarded after the session. The `/tmp/kg_projections/` cache is ephemeral and lost on container restart.

### Rejected Approach: Graph Node Properties

Our initial ADR draft proposed caching computed values (grounding_strength, diversity_score, projection coordinates) as properties on Concept nodes. This was rejected because:

1. **ADR-044 Contradiction**: Grounding strength must be calculated fresh per ADR-044's "always current" philosophy
2. **Graph Pollution**: Computed artifacts don't belong in the source-of-truth graph
3. **Invalidation Complexity**: Node properties require cache invalidation logic
4. **Separation of Concerns**: Projections are derived views, not graph data

### Better Approach: Object Storage

We already have Garage (S3-compatible storage) set up for image ingestion (ADR-057). Projection artifacts are a natural fit:

- **Versioned files**: Keep historical projections
- **Parameter-keyed**: Different parameters = different files
- **Lazy loading**: Fetch from storage, compute only if missing
- **Time-series capability**: Load multiple versions for playback

### Note on Garage Versioning

Garage does **not** have native S3 object versioning ([open feature request](https://git.deuxfleurs.fr/Deuxfleurs/garage/issues/166)). We implement our own versioning via manifest files that track snapshot history.

## Decision

Store projection artifacts in Garage as versioned JSON files, enabling:

1. **Efficient retrieval**: Skip recomputation when cached projection matches requested parameters
2. **Historical playback**: Animate how the concept landscape evolves over time
3. **Clean graph**: No computed properties pollute the graph schema

### Global Parameter Defaults

To enable meaningful time-series comparison, we establish **global defaults**:

| Algorithm | Parameter | Default | Rationale |
|-----------|-----------|---------|-----------|
| t-SNE | `perplexity` | **30** | Balance between local/global structure |
| t-SNE | `metric` | `cosine` | Angular similarity for embeddings |
| UMAP | `n_neighbors` | **15** | Local neighborhood size |
| UMAP | `min_dist` | **0.1** | Cluster tightness |

### Primary vs Outlier Projections

Projections are categorized as **primary** or **outlier**:

**Primary Projections** (tracked in timeline):
- Use global default parameters
- Form the historical timeline for playback
- Retained according to retention policy
- Default view when loading the landscape explorer

**Outlier Projections** (exploratory analysis):
- Use non-default parameters (e.g., `perplexity=50`)
- Stored separately, not part of timeline
- Useful for alternate analysis/comparison
- More aggressive cleanup (shorter retention)

This separation ensures:
1. Time-series playback compares apples-to-apples (same parameters)
2. Custom analysis is preserved but doesn't clutter the timeline
3. Simple mental model: "default view" vs "custom exploration"

### Storage Structure

```
kg-projections/
├── {ontology}/
│   ├── manifest.json              # Index of primary projections (timeline)
│   ├── latest.json.gz             # Most recent primary projection
│   ├── primary/                   # Default parameters (perplexity=30)
│   │   ├── {timestamp}_{changelist}.json.gz
│   │   └── {timestamp}_{changelist}.json.gz
│   └── outliers/                  # Non-default parameters
│       ├── perplexity_50/
│       │   └── {timestamp}_{changelist}.json.gz
│       └── perplexity_10/
│           └── {timestamp}_{changelist}.json.gz
```

### Manifest Schema

```json
{
  "ontology": "Philosophy",
  "global_defaults": {
    "algorithm": "tsne",
    "perplexity": 30,
    "metric": "cosine",
    "n_components": 3
  },
  "primary": {
    "latest": "2025-12-13T14:30:00Z_c1847",
    "snapshots": [
      {
        "id": "2025-12-13T14:30:00Z_c1847",
        "timestamp": "2025-12-13T14:30:00Z",
        "changelist_id": "c1847",
        "statistics": {
          "concept_count": 412,
          "computation_time_ms": 1847,
          "embedding_dims": 768
        },
        "file_key": "Philosophy/primary/2025-12-13T14:30:00Z_c1847.json.gz",
        "file_size_bytes": 45230
      }
    ]
  },
  "outliers": [
    {
      "parameter_key": "perplexity_50",
      "parameters": { "perplexity": 50 },
      "latest": "2025-12-12T10:15:00Z_c1800",
      "file_key": "Philosophy/outliers/perplexity_50/2025-12-12T10:15:00Z_c1800.json.gz"
    }
  ]
}
```

### Projection File Schema

```json
{
  "ontology": "Philosophy",
  "snapshot_id": "2025-12-13T14:30:00Z_c1847",
  "computed_at": "2025-12-13T14:30:00Z",
  "changelist_id": "c1847",

  "algorithm": "tsne",
  "parameters": {
    "n_components": 3,
    "perplexity": 30,
    "metric": "cosine",
    "normalize_l2": true
  },

  "statistics": {
    "concept_count": 412,
    "computation_time_ms": 1847,
    "embedding_dims": 768,
    "grounding_range": [-0.85, 0.92],
    "diversity_range": [0.12, 0.67]
  },

  "concepts": [
    {
      "concept_id": "c-abc123",
      "label": "recursive self-reference",
      "x": 45.23,
      "y": -12.87,
      "z": 8.41,
      "grounding_strength": 0.72,
      "diversity_score": 0.34,
      "item_type": "concept"
    }
  ]
}
```

### Efficient Storage Format

For large projections (1000+ concepts), use compressed binary format:

| Format | Size (1000 concepts) | Parse Time | Use Case |
|--------|---------------------|------------|----------|
| JSON | ~150KB | ~50ms | Default, readable |
| Gzip JSON | ~25KB | ~60ms | Storage efficiency |
| MessagePack | ~80KB | ~20ms | Fast parsing |
| Gzip MessagePack | ~20KB | ~30ms | Optimal balance |

**Recommendation**: Store as gzip-compressed JSON (`.json.gz`) for:
- 6x size reduction
- Human-readable when decompressed
- Standard tooling support
- Negligible decompression overhead

### Changelist-Based Cache Validation

The worker automatically determines freshness by comparing the current graph increment against what's stored. Clients simply request projections; the worker handles staleness detection.

```
┌─────────────────────────────────────────────────────────────────┐
│  Client Request Flow                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Web/CLI ──► API ──► Worker                                     │
│                        │                                        │
│                        ▼                                        │
│              ┌─────────────────────┐                            │
│              │ Get current graph   │                            │
│              │ increment (c1900)   │                            │
│              └──────────┬──────────┘                            │
│                         │                                       │
│                         ▼                                       │
│              ┌─────────────────────┐                            │
│              │ Get stored manifest │                            │
│              │ changelist (c1847)  │                            │
│              └──────────┬──────────┘                            │
│                         │                                       │
│            ┌────────────┴────────────┐                          │
│            │                         │                          │
│            ▼                         ▼                          │
│   c1900 > c1847?              c1900 == c1847?                   │
│   ┌───────────┐               ┌───────────┐                     │
│   │ STALE     │               │ FRESH     │                     │
│   │ Compute   │               │ Retrieve  │                     │
│   │ Store     │               │ from      │                     │
│   │ Return    │               │ Garage    │                     │
│   └───────────┘               └───────────┘                     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Cache Hit Logic

```python
# Global defaults (configurable via system settings)
GLOBAL_DEFAULTS = {
    'tsne': {
        'perplexity': 30,
        'metric': 'cosine',
        'n_components': 3,
    },
    'umap': {
        'n_neighbors': 15,
        'min_dist': 0.1,
        'metric': 'cosine',
        'n_components': 3,
    }
}


async def get_current_changelist() -> int:
    """
    Get current graph state as integer increment.

    Uses concept_creation_counter from graph_metrics table.
    This counter increments on every concept/relationship addition.
    """
    result = await db.execute("""
        SELECT concept_creation_counter + relationship_creation_counter
        FROM kg_api.graph_metrics
        WHERE id = 1
    """)
    return result.scalar() or 0


def is_primary_projection(algorithm: str, params: ProjectionParams) -> bool:
    """Check if parameters match global defaults (primary) or are outliers."""
    defaults = GLOBAL_DEFAULTS.get(algorithm, {})

    if algorithm == 'tsne':
        return params.perplexity == defaults.get('perplexity', 30)
    elif algorithm == 'umap':
        return (
            params.n_neighbors == defaults.get('n_neighbors', 15) and
            params.min_dist == defaults.get('min_dist', 0.1)
        )
    return True


async def get_or_compute_projection(
    ontology: str,
    algorithm: str = 'tsne',
    params: ProjectionParams = None,
    force_refresh: bool = False  # Admin override - bypass changelist check
) -> ProjectionData:
    """
    Retrieve cached projection or compute fresh based on graph changelist.

    If params is None, uses global defaults (primary projection).

    Freshness is automatic:
    - Worker compares current graph increment vs stored changelist
    - If graph changed → compute fresh, store, return
    - If graph unchanged → retrieve from storage

    force_refresh (admin): Bypass changelist check and always recompute.
    Useful for debugging or forcing regeneration after algorithm changes.
    """
    # Default to global parameters if not specified
    if params is None:
        params = ProjectionParams(**GLOBAL_DEFAULTS[algorithm])

    is_primary = is_primary_projection(algorithm, params)

    # Get current graph state
    current_changelist = await get_current_changelist()

    # Check stored manifest (unless force_refresh)
    if not force_refresh:
        manifest = await garage.get_manifest(ontology)

        if manifest:
            if is_primary:
                stored_changelist = get_stored_changelist(manifest.primary)
                if stored_changelist == current_changelist:
                    # Graph unchanged - retrieve from storage
                    cached = manifest.primary.snapshots[-1]
                    return await garage.get_projection(cached.file_key)
            else:
                # Outlier: check if we have this parameter set at current changelist
                cached = find_fresh_outlier(manifest, params, current_changelist)
                if cached:
                    return await garage.get_projection(cached.file_key)

    # Graph changed, no cache, or force_refresh - compute fresh
    projection = await compute_projection(ontology, algorithm, params)

    # Store in Garage with current changelist
    await store_projection(
        projection,
        changelist=current_changelist,
        is_primary=is_primary
    )

    return projection


def get_stored_changelist(primary: PrimarySection) -> int:
    """Extract changelist number from latest primary snapshot."""
    if not primary.snapshots:
        return -1

    latest = primary.snapshots[-1]
    # Parse "c1847" → 1847
    changelist_str = latest.changelist_id
    if changelist_str.startswith('c'):
        return int(changelist_str[1:])
    return int(changelist_str)


def find_fresh_outlier(
    manifest: Manifest,
    params: ProjectionParams,
    current_changelist: int
) -> Snapshot | None:
    """Find outlier snapshot matching parameters AND current changelist."""
    param_key = get_parameter_key(params)

    for outlier in manifest.outliers:
        if outlier.parameter_key != param_key:
            continue

        # Check if outlier is fresh
        stored = get_stored_changelist_from_id(outlier.latest)
        if stored == current_changelist:
            return outlier

    return None


def get_parameter_key(params: ProjectionParams) -> str:
    """Generate unique key for outlier parameters."""
    parts = []
    if params.perplexity and params.perplexity != 30:
        parts.append(f"perplexity_{params.perplexity}")
    if params.n_neighbors and params.n_neighbors != 15:
        parts.append(f"neighbors_{params.n_neighbors}")
    if params.min_dist and params.min_dist != 0.1:
        parts.append(f"mindist_{params.min_dist}")
    return "_".join(parts) or "custom"
```

### Time-Series Playback

The manifest tracks all historical snapshots, enabling playback:

```typescript
// Frontend: Load projection history for animation
async function loadProjectionTimeline(ontology: string): Promise<ProjectionSnapshot[]> {
  const manifest = await api.getProjectionManifest(ontology);

  // Load all snapshots (or subset for performance)
  const snapshots = await Promise.all(
    manifest.snapshots
      .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
      .slice(-10)  // Last 10 snapshots
      .map(s => api.getProjection(s.file_key))
  );

  return snapshots;
}

// Animate between snapshots
function animateLandscapeEvolution(snapshots: ProjectionSnapshot[]) {
  let currentIndex = 0;

  const animate = () => {
    if (currentIndex >= snapshots.length) {
      currentIndex = 0;  // Loop
    }

    updateVisualization(snapshots[currentIndex]);
    currentIndex++;

    setTimeout(animate, 1000);  // 1 second per frame
  };

  animate();
}
```

### Changelist Tracking

The `graph_change_counter` tracks ALL graph modifications via database triggers (Migration 033).

**Trigger-based tracking (reliable):**
- Triggers on ALL vertex tables (Concept, VocabType, Source, Instance, etc.)
- Triggers on ALL edge tables (108+ relationship types)
- Increments `graph_change_counter` on every INSERT/UPDATE/DELETE
- No application code required - database handles it automatically

```python
async def get_current_changelist() -> int:
    """
    Get current graph state as integer.

    Uses the unified graph_change_counter from graph_metrics table.
    This counter is incremented by database triggers on ALL graph modifications.
    """
    result = await db.execute("""
        SELECT counter
        FROM public.graph_metrics
        WHERE metric_name = 'graph_change_counter'
    """)
    return result.scalar() or 0
```

**Related counters (also trigger-based):**
- `concept_creation_counter` / `concept_deletion_counter`
- `relationship_creation_counter` / `relationship_deletion_counter`
- `vocabulary_change_counter`

**Maintenance function for new edge types:**
```sql
-- Call after ingestion if new relationship types were created
SELECT * FROM knowledge_graph.sync_edge_triggers();
```

This enables:
- Knowing exactly how stale a cached projection is
- Comparing projections across graph changes
- Automatic cache invalidation without application code

### API Endpoints

```python
# Get projection (automatically fresh based on changelist)
GET /api/projections/{ontology}
Query params:
  - algorithm: "tsne" | "umap" (default: tsne)
  - perplexity: int (t-SNE, default: 30)
  - n_neighbors: int (UMAP, default: 15)
  - min_dist: float (UMAP, default: 0.1)
  - metric: "cosine" | "euclidean" (default: cosine)
  - force_refresh: bool (optional, admin - bypass changelist check)

Response: ProjectionData
# Worker automatically computes if graph changelist > stored changelist
# force_refresh bypasses check and always recomputes (admin use only)

# Get manifest (list available snapshots + current changelist)
GET /api/projections/{ontology}/manifest
Response: {
  manifest: Manifest,
  current_changelist: int,
  is_stale: bool  # True if graph changed since last projection
}

# Get specific historical snapshot (for playback)
GET /api/projections/{ontology}/snapshots/{snapshot_id}
Response: ProjectionData

# Delete old snapshots (cleanup)
DELETE /api/projections/{ontology}/snapshots
Query params:
  - keep_last: int (default: 10)
```

### Retention Policy

Different retention for primary (timeline) vs outlier (exploratory) projections:

```python
async def cleanup_old_projections(
    ontology: str,
    primary_keep_last: int = 10,
    primary_max_age_days: int = 90,
    outlier_keep_last: int = 1,      # Only keep latest per parameter set
    outlier_max_age_days: int = 7    # More aggressive cleanup
):
    """
    Remove old projection snapshots.

    Primary projections (timeline):
    - Keep most recent N snapshots (primary_keep_last)
    - Keep anything younger than primary_max_age_days
    - Enable historical playback

    Outlier projections (exploratory):
    - Keep only most recent per parameter set (outlier_keep_last)
    - Delete after outlier_max_age_days
    - These are for ad-hoc analysis, not history
    """
    manifest = await garage.get_manifest(ontology)

    # Clean primary snapshots
    primary_to_keep = set()
    sorted_primary = sorted(
        manifest.primary.snapshots,
        key=lambda s: s.timestamp,
        reverse=True
    )

    for snapshot in sorted_primary[:primary_keep_last]:
        primary_to_keep.add(snapshot.id)

    cutoff = datetime.utcnow() - timedelta(days=primary_max_age_days)
    for snapshot in manifest.primary.snapshots:
        if datetime.fromisoformat(snapshot.timestamp) > cutoff:
            primary_to_keep.add(snapshot.id)

    # Delete old primary snapshots
    for snapshot in manifest.primary.snapshots:
        if snapshot.id not in primary_to_keep:
            await garage.delete(snapshot.file_key)

    manifest.primary.snapshots = [
        s for s in manifest.primary.snapshots
        if s.id in primary_to_keep
    ]

    # Clean outlier snapshots (more aggressive)
    outlier_cutoff = datetime.utcnow() - timedelta(days=outlier_max_age_days)
    manifest.outliers = [
        o for o in manifest.outliers
        if datetime.fromisoformat(o.latest.split('_')[0]) > outlier_cutoff
    ]

    # Delete orphaned outlier files
    for outlier in manifest.outliers:
        if datetime.fromisoformat(outlier.latest.split('_')[0]) <= outlier_cutoff:
            await garage.delete(outlier.file_key)

    await garage.put_manifest(ontology, manifest)
```

## Consequences

### Positive

1. **No ADR-044 Conflict**: Grounding/diversity still calculated fresh at query time
2. **Clean Graph Schema**: No computed properties pollute Concept nodes
3. **Efficient Caching**: Skip expensive t-SNE/UMAP when parameters match
4. **Historical Analysis**: Track how concept landscape evolves
5. **Playback Capability**: Animate landscape changes over time
6. **Leverages Existing Infrastructure**: Reuses Garage from ADR-057
7. **Standard Storage**: JSON files are debuggable and portable

### Negative

1. **Additional Storage**: Projection files consume Garage space (~25-150KB each)
2. **Network Latency**: Fetching from Garage adds ~10-50ms vs in-memory
3. **Manifest Maintenance**: Need to keep manifest in sync with files
4. **Cleanup Required**: Old snapshots accumulate without retention policy

### Neutral

1. **Primary/Outlier Split**: Default parameters form timeline; custom analysis stored separately
2. **Freshness Is Caller's Choice**: API doesn't auto-refresh; caller decides
3. **Grounding Included**: Each snapshot includes grounding values computed at that time
4. **Global Defaults**: Perplexity=30 is the canonical view; other values are exploratory

## What This ADR Does NOT Do

To be explicit about scope:

1. **Does NOT cache grounding_strength on Concept nodes** - Always calculated fresh per ADR-044
2. **Does NOT cache diversity_score on Concept nodes** - Always calculated fresh per ADR-063
3. **Does NOT implement cache invalidation** - Caller explicitly requests refresh
4. **Does NOT change runtime calculation behavior** - Only stores results

The projection snapshots include grounding/diversity values, but these are:
- Computed fresh when the projection is generated
- Stored as part of the snapshot (point-in-time values)
- NOT used as cache for future queries (always recalculate on next projection)

## Implementation Plan

### Phase 1: Core Storage

1. Create Garage bucket: `kg-projections`
2. Implement manifest read/write
3. Implement projection file read/write (gzip JSON)
4. Update projection service to check cache before compute

### Phase 2: API Integration

1. Add `force_refresh` parameter to projection endpoint
2. Implement manifest endpoint
3. Implement historical snapshot endpoint
4. Add cleanup endpoint

### Phase 3: Frontend Playback

1. Load projection timeline from manifest
2. Implement snapshot selector UI
3. Implement playback animation controls
4. Show changelist/timestamp metadata

## Migration

```sql
-- No database migration needed.
-- Garage bucket created via operator:

-- In operator/admin/init_projection_storage.py:
async def init_projection_storage():
    """Initialize Garage bucket for projection storage."""
    await garage.create_bucket_if_not_exists('kg-projections')

    # Set bucket policy (private, API-mediated access)
    await garage.set_bucket_policy('kg-projections', {
        'Version': '2012-10-17',
        'Statement': [{
            'Effect': 'Allow',
            'Principal': {'AWS': ['kg-api-key']},
            'Action': ['s3:GetObject', 's3:PutObject', 's3:DeleteObject'],
            'Resource': ['arn:aws:s3:::kg-projections/*']
        }]
    })
```

## References

- ADR-057: Multimodal Image Ingestion (Garage infrastructure)
- ADR-078: Embedding Landscape Explorer (projection computation)
- ADR-044: Probabilistic Truth Convergence (grounding calculation philosophy)
- ADR-063: Semantic Diversity (diversity calculation philosophy)
- Migration 033: Graph Change Triggers (counter wiring)
