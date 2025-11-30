# Polarity Axis Analysis - Production Implementation Plan

**Status:** Planning
**Date:** 2025-11-29
**Target:** Production deployment following ADR-070
**Branch:** `feature/adr-070-polarity-axis-analysis`

## Overview

Implement polarity axis analysis as a production feature, enabling users to:
- Discover implicit semantic dimensions in their knowledge graph
- Position concepts along bidirectional spectrums (Modern ↔ Traditional)
- Find connection paths between opposing concepts
- Validate positioning with source evidence
- Identify bridge/synthesis concepts

**Foundation:** Builds on experimental validation (branch `experiment/semantic-path-gradients`) and integrates with existing capabilities (ADR-068 source search, `/query/connect` path finding).

---

## Architecture Overview

```
User Interface Layer
  ├─ CLI: kg polarity {analyze|discover|project}
  ├─ MCP: analyze_polarity_axis, discover_polarity_axes
  └─ Web: Polarity Axis Explorer (new panel)
         ↓
API Layer (FastAPI)
  ├─ POST /queries/polarity-axis (analyze)
  ├─ POST /queries/discover-polarity-axes (auto-discover)
  └─ GET /queries/polarity-axis/{axis_id}/project/{concept_id}
         ↓
Worker Layer (Background Jobs)
  └─ PolarityAxisWorker
      ├─ Analyze axis between poles
      ├─ Project concepts onto axis
      ├─ Calculate grounding correlation
      └─ Optional: Find paths + source evidence
         ↓
Data Layer
  ├─ Apache AGE (concept embeddings, grounding)
  ├─ PostgreSQL (source embeddings - ADR-068)
  └─ Job Queue (async processing)
```

---

## Integration with Existing Systems

### 1. ADR-068 Source Search
**Purpose:** Validate why concepts sit where they do on the axis

```python
# After projecting concept onto axis:
if concept.position > 0.7:  # Strongly toward positive pole
    # Find evidence in source passages
    sources = client.search_sources(
        query=f"{concept.label} {positive_pole.label}",
        limit=5
    )
    # Returns passages explaining the positioning
```

### 2. /query/connect Path Finding
**Purpose:** Discover semantic paths between opposing poles

```python
# Find paths connecting poles
paths = client.find_connection(
    from_id=negative_pole_id,
    to_id=positive_pole_id,
    max_hops=5
)

# Analyze path coherence on axis
for path in paths:
    positions = [axis.project(concept).position for concept in path.concepts]
    coherence = calculate_progression_smoothness(positions)
    # Smooth progression = semantically coherent path
```

### 3. Grounding Calculation (ADR-058)
**Purpose:** Correlate axis position with concept reliability

```python
# Grounding correlation reveals value polarity
positions = [proj.position for proj in projections]
groundings = [proj.grounding for proj in projections]
correlation = pearsonr(positions, groundings)

# Strong correlation (r > 0.7) = value-laden axis
# Weak correlation (r < 0.3) = descriptive axis
```

---

## Phase 1: Worker Service

**Location:** `api/api/workers/polarity_axis_worker.py`

### Job Input Schema

```python
{
    "job_type": "polarity_axis_analysis",
    "job_data": {
        "positive_pole_id": "sha256:...",      # Required
        "negative_pole_id": "sha256:...",      # Required
        "analysis_mode": "basic|full",         # Default: basic
        "candidate_discovery": {
            "enabled": true,                   # Auto-discover candidates
            "max_candidates": 20,
            "relationship_types": ["SUPPORTS", "ENABLES", "PREVENTS"],
            "max_hops": 2
        },
        "path_analysis": {
            "enabled": false,                  # Find paths between poles
            "max_paths": 5,
            "max_hops": 5
        },
        "source_grounding": {
            "enabled": false,                  # Find source evidence
            "per_concept_limit": 3
        }
    }
}
```

### Job Output Schema

```python
{
    "axis": {
        "positive_pole": {
            "concept_id": "...",
            "label": "Digital Transformation",
            "grounding": -0.022,
            "embedding_dimension": 768
        },
        "negative_pole": {
            "concept_id": "...",
            "label": "Legacy Systems",
            "grounding": -0.075,
            "embedding_dimension": 768
        },
        "magnitude": 1.0714,                   # Semantic distance
        "axis_quality": "strong"               # Based on magnitude thresholds
    },
    "projections": [
        {
            "concept_id": "...",
            "label": "Agile",
            "position": 0.194,                 # -1 to +1 scale
            "axis_distance": 1.0008,           # Orthogonal distance
            "direction": "positive",           # positive|negative|neutral
            "grounding": 0.227,
            "alignment": {
                "positive_pole_similarity": 0.845,
                "negative_pole_similarity": 0.621
            },
            "source_evidence": [               # If source_grounding enabled
                {
                    "source_id": "...",
                    "document": "ADR-068",
                    "matched_chunk": "Agile methodologies emphasize...",
                    "similarity": 0.82
                }
            ]
        }
    ],
    "statistics": {
        "total_concepts": 4,
        "position_range": [-0.124, 0.194],
        "mean_position": 0.043,
        "std_deviation": 0.140,
        "mean_axis_distance": 0.947,
        "direction_distribution": {
            "positive": 0,
            "negative": 0,
            "neutral": 4
        }
    },
    "grounding_correlation": {
        "pearson_r": 0.847,
        "p_value": 0.023,
        "interpretation": "Strong positive correlation: value-laden axis"
    },
    "paths": [                                 # If path_analysis enabled
        {
            "path_id": 1,
            "length": 3,
            "concepts": ["...", "...", "..."],
            "positions_on_axis": [-0.8, -0.2, 0.6],
            "coherence_score": 0.92,           # Smoothness of progression
            "mean_curvature": 1.2              # From gradient analysis
        }
    ]
}
```

### Worker Implementation

**Refactor from:** `docs/features/polarity-axis-analysis/experimental_code/polarity_axis_analysis.py`

**Key Classes:**
```python
class PolarityAxisWorker:
    """Background worker for polarity axis analysis"""

    def run(self, job_data: Dict, job_id: str) -> Dict:
        """Execute polarity axis analysis job"""
        # 1. Fetch pole embeddings
        # 2. Calculate axis vector
        # 3. Discover or use provided candidates
        # 4. Project candidates onto axis
        # 5. Calculate grounding correlation
        # 6. Optional: Find paths between poles
        # 7. Optional: Find source evidence
        # 8. Return structured results

class PolarityAxis:
    """Core axis calculation logic"""
    positive_pole: Concept
    negative_pole: Concept
    axis_vector: np.ndarray
    axis_magnitude: float

    def project_concept(self, concept: Concept) -> Dict:
        """Project concept onto axis, return position/distance/direction"""

class PathCoherenceAnalyzer:
    """Analyze how smoothly paths transition along axis"""

    def analyze_path(self, path: List[Concept], axis: PolarityAxis) -> Dict:
        """Calculate coherence metrics for path on axis"""
```

### Dependencies
- `api/api/lib/age_client.py` - Grounding calculation
- `api/api/routes/queries.py` - Concept connection (reuse `/query/connect` logic)
- `api/api/lib/similarity_calculator.py` - Cosine similarity
- NumPy for vector operations
- SciPy for correlation calculations

---

## Phase 2: API Endpoints

**Location:** `api/api/routes/queries.py`

### Endpoint 1: Analyze Polarity Axis

```python
@router.post("/polarity-axis", response_model=PolarityAxisJobResponse)
async def analyze_polarity_axis(
    current_user: CurrentUser,
    request: AnalyzePolarityAxisRequest
):
    """
    Analyze bidirectional semantic spectrum between two opposing concepts.

    Submits background job for axis analysis. Returns job ID for status polling.

    **Authentication:** Requires valid OAuth token

    **Parameters:**
    - positive_pole_id: Concept ID for positive pole (e.g., "Modern")
    - negative_pole_id: Concept ID for negative pole (e.g., "Traditional")
    - candidate_ids: Optional list of concepts to project (auto-discovered if not provided)
    - include_path_analysis: Find connection paths between poles
    - include_source_evidence: Find source passages supporting positions

    **Returns:** Job ID with estimated completion time

    **Example:**
    ```json
    {
      "positive_pole_id": "sha256:2af75_chunk1_78594e1b",
      "negative_pole_id": "sha256:0f72d_chunk1_9a13bb20",
      "candidate_discovery": {
        "enabled": true,
        "max_candidates": 20
      },
      "include_path_analysis": true
    }
    ```
    """
```

### Endpoint 2: Discover Polarity Axes

```python
@router.post("/discover-polarity-axes", response_model=DiscoverPolarityAxesResponse)
async def discover_polarity_axes(
    current_user: CurrentUser,
    request: DiscoverPolarityAxesRequest
):
    """
    Auto-discover potential polarity axes from oppositional relationships.

    **Authentication:** Requires valid OAuth token

    Scans for PREVENTS, CONTRADICTS relationships to identify natural semantic
    oppositions. Returns candidate axes ranked by semantic magnitude and grounding
    differential.

    **Parameters:**
    - relationship_types: List of oppositional relationship types to scan
    - min_magnitude: Minimum semantic distance to qualify as axis
    - max_results: Maximum number of axes to return
    - ontology: Optional filter to specific ontology

    **Returns:** List of discovered axes with metadata

    **Example:**
    ```json
    {
      "relationship_types": ["PREVENTS", "CONTRADICTS"],
      "min_magnitude": 0.5,
      "max_results": 10
    }
    ```

    **Response:**
    ```json
    {
      "axes": [
        {
          "positive_pole": {
            "concept_id": "...",
            "label": "Digital Transformation"
          },
          "negative_pole": {
            "concept_id": "...",
            "label": "Legacy Systems"
          },
          "relationship_type": "PREVENTS",
          "magnitude": 1.0714,
          "grounding_differential": 0.053
        }
      ]
    }
    ```
    """
```

### Endpoint 3: Project Concept

```python
@router.get("/polarity-axis/{axis_id}/project/{concept_id}", response_model=ProjectConceptResponse)
async def project_concept_on_axis(
    current_user: CurrentUser,
    axis_id: str,
    concept_id: str
):
    """
    Project a single concept onto a previously analyzed axis.

    **Authentication:** Requires valid OAuth token

    Quick projection without re-analyzing entire axis. Useful for:
    - Adding new concepts to existing axis view
    - Interactive exploration in web UI
    - Incremental analysis

    **Note:** Requires axis to be cached from previous analysis job

    **Returns:** Position, direction, axis distance for the concept
    """
```

### Request/Response Models

```python
class AnalyzePolarityAxisRequest(BaseModel):
    positive_pole_id: str
    negative_pole_id: str
    candidate_ids: Optional[List[str]] = None
    candidate_discovery: Optional[CandidateDiscoveryConfig] = None
    include_path_analysis: bool = False
    include_source_evidence: bool = False

class PolarityAxisJobResponse(BaseModel):
    job_id: str
    status: str
    estimated_duration_seconds: int
    message: str

class DiscoverPolarityAxesRequest(BaseModel):
    relationship_types: List[str] = ["PREVENTS", "CONTRADICTS"]
    min_magnitude: float = 0.5
    max_results: int = 10
    ontology: Optional[str] = None
```

---

## Phase 3: CLI Integration

**Location:** `client/src/cli/polarity.ts`

### Command Structure

```bash
kg polarity <subcommand> [options]

Subcommands:
  analyze <positive> <negative>  # Analyze specific polarity axis
  discover [options]             # Auto-discover axes from relationships
  project <axis-id> <concept>    # Project concept onto known axis

Options:
  --candidates <id1> <id2> ...   # Specify concepts to project
  --auto-discover                # Auto-discover related concepts
  --include-paths                # Find connection paths between poles
  --include-sources              # Include source evidence
  --ontology <name>              # Filter to specific ontology
  --json                         # Output as JSON
```

### Example Commands

```bash
# Analyze Modern vs Traditional axis
kg polarity analyze "Modern Operating Model" "Traditional Operating Models"

# Auto-discover axes from PREVENTS relationships
kg polarity discover --type PREVENTS --limit 10

# Project specific concept onto axis
kg polarity project axis-uuid-123 "Agile Methodology"

# Full analysis with paths and sources
kg polarity analyze "Centralized" "Decentralized" \
  --auto-discover \
  --include-paths \
  --include-sources
```

### Output Format

**Table Mode (Default):**
```
Polarity Axis Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Positive Pole: Digital Transformation (grounding: -0.022)
Negative Pole: Legacy Systems (grounding: -0.075)
Semantic Distance: 1.071
Grounding Correlation: r=0.85, p=0.023 ✓ Strong

Projected Concepts (4 total)
┌────────────────────────────────┬──────────┬──────────┬───────────┐
│ Concept                        │ Position │ Direction│ Grounding │
├────────────────────────────────┼──────────┼──────────┼───────────┤
│ Agile                          │ +0.194   │ Positive │ +0.227    │
│ Modern Operating Model         │ +0.089   │ Neutral  │ +0.133    │
│ Tech Debt                      │ -0.049   │ Neutral  │ 0.000     │
│ Traditional Operating Models   │ -0.124   │ Negative │ -0.040    │
└────────────────────────────────┴──────────┴──────────┴───────────┘

Visual Spectrum:
Legacy Systems ●────────────┼────────────● Digital Transformation
                  ^         ^         ^
               -0.124    -0.049    +0.194

Connection Paths (2 found):
  Path 1: Legacy → Modernization → Digital (coherence: 0.94)
  Path 2: Legacy → Integration → Agile → Digital (coherence: 0.87)
```

---

## Phase 4: MCP Server Integration

**Location:** `client/src/mcp-server.ts`

### MCP Tool: analyze_polarity_axis

```typescript
{
  name: "analyze_polarity_axis",
  description: "Analyze bidirectional semantic spectrum between two opposing concepts. Projects concepts onto the axis to reveal their position on the spectrum. Optionally includes connection paths and source evidence.",
  inputSchema: {
    type: "object",
    properties: {
      positive_pole_query: {
        type: "string",
        description: "Search query for positive pole concept (e.g., 'Modern Operating Model')"
      },
      negative_pole_query: {
        type: "string",
        description: "Search query for negative pole concept (e.g., 'Traditional Operating Models')"
      },
      auto_discover_candidates: {
        type: "boolean",
        default: true,
        description: "Auto-discover related concepts to project onto axis"
      },
      include_paths: {
        type: "boolean",
        default: false,
        description: "Find connection paths between poles"
      },
      include_source_evidence: {
        type: "boolean",
        default: false,
        description: "Include source passages supporting positions"
      }
    },
    required: ["positive_pole_query", "negative_pole_query"]
  }
}
```

### MCP Tool: discover_polarity_axes

```typescript
{
  name: "discover_polarity_axes",
  description: "Auto-discover polarity axes from oppositional relationships (PREVENTS, CONTRADICTS). Reveals implicit semantic dimensions in the knowledge graph.",
  inputSchema: {
    type: "object",
    properties: {
      relationship_types: {
        type: "array",
        items: { type: "string" },
        default: ["PREVENTS", "CONTRADICTS"],
        description: "Oppositional relationship types to scan"
      },
      max_results: {
        type: "number",
        default: 10,
        description: "Maximum number of axes to return"
      },
      ontology: {
        type: "string",
        description: "Optional: filter to specific ontology"
      }
    }
  }
}
```

### Response Formatter

**Location:** `client/src/mcp/formatters.ts`

```typescript
export function formatPolarityAxisResults(result: PolarityAxisResponse): string {
  let output = `# Polarity Axis: ${result.axis.negative_pole.label} ↔ ${result.axis.positive_pole.label}\n\n`;

  output += `**Semantic Distance:** ${result.axis.magnitude.toFixed(3)}\n`;
  output += `**Grounding Correlation:** r=${result.grounding_correlation.pearson_r.toFixed(2)} `;

  if (Math.abs(result.grounding_correlation.pearson_r) > 0.7) {
    output += `🟢 Strong\n`;
  } else if (Math.abs(result.grounding_correlation.pearson_r) > 0.4) {
    output += `🟡 Moderate\n`;
  } else {
    output += `⚪ Weak\n`;
  }

  output += `\n## Projected Concepts\n\n`;

  // Group by direction
  const positive = result.projections.filter(p => p.direction === 'positive');
  const neutral = result.projections.filter(p => p.direction === 'neutral');
  const negative = result.projections.filter(p => p.direction === 'negative');

  if (positive.length > 0) {
    output += `### ➕ Toward ${result.axis.positive_pole.label}\n`;
    positive.forEach(p => {
      output += `- **${p.label}** (${p.position > 0 ? '+' : ''}${p.position.toFixed(3)}) - grounding: ${p.grounding.toFixed(3)}\n`;
      if (p.source_evidence) {
        output += `  📄 Evidence: "${p.source_evidence[0].matched_chunk.substring(0, 100)}..."\n`;
      }
    });
    output += '\n';
  }

  // ... similar for neutral and negative

  if (result.paths && result.paths.length > 0) {
    output += `## Connection Paths\n\n`;
    result.paths.forEach((path, i) => {
      output += `**Path ${i + 1}** (coherence: ${path.coherence_score.toFixed(2)})\n`;
      output += `${path.concepts.join(' → ')}\n`;
      output += `Positions: ${path.positions_on_axis.map(p => p.toFixed(2)).join(' → ')}\n\n`;
    });
  }

  return output;
}
```

---

## Phase 5: Web UI - Polarity Axis Explorer

**Location:** `web/src/components/explorer/PolarityAxisExplorer.tsx`

### Panel Design

**New Explorer Category** (not a Block Builder block)

```
Navigation:
  Explorer
    ├─ Search
    ├─ Graph
    ├─ Evidence
    └─ Polarity Axes  ← NEW
```

### UI Components

#### 1. Discovery Panel

```tsx
<PolarityAxisDiscovery>
  <RelationshipTypeSelector types={["PREVENTS", "CONTRADICTS"]} />
  <OntologyFilter optional />
  <ResultsTable
    columns={["Axis", "Magnitude", "Correlation", "Action"]}
    onExplore={(axis) => openAxisAnalysis(axis)}
  />
</PolarityAxisDiscovery>
```

#### 2. Axis Analysis View

```tsx
<PolarityAxisAnalysis axis={selectedAxis}>
  <AxisHeader
    positiveP pole={axis.positive_pole}
    negativePole={axis.negative_pole}
    stats={axis.statistics}
  />

  <SpectrumVisualization>
    {/* Interactive slider showing concept positions */}
    <AxisLine from={-1} to={1} />
    {projections.map(proj => (
      <ConceptBubble
        position={proj.position}
        label={proj.label}
        grounding={proj.grounding}
        onClick={() => showConceptDetails(proj)}
      />
    ))}
  </SpectrumVisualization>

  <ConceptTable
    projections={projections}
    sortable
    filterable
  />

  {paths && (
    <PathsPanel>
      {paths.map(path => (
        <PathVisualization
          concepts={path.concepts}
          positions={path.positions_on_axis}
          coherence={path.coherence_score}
        />
      ))}
    </PathsPanel>
  )}

  <SourceEvidencePanel
    projections={projections}
    expandable
  />
</PolarityAxisAnalysis>
```

#### 3. Custom Axis Creator

```tsx
<CustomAxisCreator>
  <ConceptSearch
    label="Positive Pole"
    onSelect={(concept) => setPositivePole(concept)}
  />
  <ConceptSearch
    label="Negative Pole"
    onSelect={(concept) => setNegativePole(concept)}
  />

  <AnalysisOptions>
    <Toggle label="Auto-discover candidates" />
    <Toggle label="Find connection paths" />
    <Toggle label="Include source evidence" />
  </AnalysisOptions>

  <Button onClick={analyzeAxis}>Analyze Axis →</Button>
</CustomAxisCreator>
```

### Visual Design

**Color Scheme:**
- Negative pole: Red gradient (#ef4444 → #fca5a5)
- Midpoint: Neutral gray (#6b7280)
- Positive pole: Green gradient (#a5f3a5 → #22c55e)

**Interactive Elements:**
- Hover over concept bubble → show stats tooltip
- Click concept → navigate to concept details
- Drag concept → see how adding/removing affects statistics
- Export as PNG/SVG for documentation

---

## Implementation Phases

### Phase 1: Backend Foundation
- [x] Experimental validation complete
- [ ] Create `PolarityAxisWorker` class
- [ ] Refactor experimental code into production worker
- [ ] Add job type to worker registry
- [ ] Unit tests for projection algorithm
- [ ] Integration tests with real embeddings

### Phase 2: API Endpoints
- [ ] Implement `/queries/polarity-axis` endpoint
- [ ] Implement `/queries/discover-polarity-axes` endpoint
- [ ] Implement `/queries/polarity-axis/{axis_id}/project/{concept_id}` endpoint
- [ ] Pydantic request/response models
- [ ] OpenAPI documentation
- [ ] Integration with job queue
- [ ] API tests

### Phase 3: CLI Integration
- [ ] Implement `kg polarity analyze` command
- [ ] Implement `kg polarity discover` command
- [ ] Implement `kg polarity project` command
- [ ] Table, visual, and JSON output modes
- [ ] CLI tests
- [ ] Update kg CLI documentation

### Phase 4: MCP Server
- [ ] Add `analyze_polarity_axis` tool
- [ ] Add `discover_polarity_axes` tool
- [ ] Implement formatters for polarity results
- [ ] Update MCP server documentation
- [ ] Test with Claude Desktop

### Phase 5: Web UI Explorer
- [ ] Create `PolarityAxisExplorer` component
- [ ] Discovery panel with relationship type filters
- [ ] Axis analysis view with spectrum visualization
- [ ] Custom axis creator
- [ ] Path visualization (if paths included)
- [ ] Source evidence integration
- [ ] Export functionality (PNG/SVG/JSON)
- [ ] Web UI tests

### Phase 6: Documentation
- [ ] Update ADR-070 status to "Implemented"
- [ ] Update API documentation
- [ ] Add examples to guides

---

## Success Criteria

### Functional
- ✅ Polarity axis calculation produces stable results (±0.05 across runs)
- ✅ Grounding correlation r > 0.7 for PREVENTS/CONTRADICTS axes
- ✅ Direction classification accuracy >90% (spot check)
- ✅ Graceful handling of edge cases (single concept, no candidates, invalid IDs)

### Performance
- ✅ Axis calculation <5s for 20 candidates (without caching)
- ✅ Auto-discovery <10s for 50 relationships
- ✅ Background worker prevents API blocking
- ✅ No performance regression on existing endpoints

### Integration
- ✅ Source evidence integration working (ADR-068)
- ✅ Path finding integration working (/query/connect)
- ✅ Grounding calculation integration working (ADR-058)
- ✅ All interfaces operational (CLI, MCP, Web)

### Implementation
- ✅ Zero critical bugs
- ✅ All tests passing
- ✅ Documentation complete

---

## Testing Strategy

### Unit Tests
```python
# api/api/tests/test_polarity_axis_worker.py
def test_axis_calculation()
def test_projection_algorithm()
def test_direction_classification()
def test_grounding_correlation()

# api/api/tests/test_polarity_endpoints.py
def test_analyze_axis_endpoint()
def test_discover_axes_endpoint()
def test_project_concept_endpoint()
```

### Integration Tests
```python
# api/api/tests/integration/test_polarity_integration.py
def test_with_real_embeddings()
def test_path_finding_integration()
def test_source_evidence_integration()
def test_job_queue_processing()
```

### CLI Tests
```bash
# client/src/cli/polarity.test.ts
test('kg polarity analyze with concept IDs')
test('kg polarity discover with filters')
test('kg polarity project single concept')
```

### Web UI Tests
```typescript
// web/src/components/explorer/__tests__/PolarityAxisExplorer.test.tsx
test('renders discovery panel')
test('creates custom axis')
test('displays spectrum visualization')
test('exports axis as PNG')
```

---

## Rollout Plan

### Stage 1: Backend
1. Merge experimental code to feature branch
2. Implement worker and API endpoints
3. Run integration tests

### Stage 2: Interfaces
1. Implement CLI commands
2. Implement MCP tools
3. Test with Claude Desktop

### Stage 3: Web UI & Docs
1. Implement Polarity Explorer
2. Update documentation
3. Merge to main

---

## Open Questions

1. **Should we cache analyzed axes?**
   - Pro: Faster retrieval, can query "which axes use this concept?"
   - Con: Invalidation complexity when embeddings regenerate
   - **Decision:** Start without caching, add if usage patterns reveal value

2. **How to handle multi-dimensional axes?**
   - Current: 1D projection (positive ↔ negative)
   - Future: 2D projection (Modern/Traditional × Centralized/Decentralized)
   - **Decision:** Implement 1D first, design for future extension

3. **Should polarity analysis be a Smart Block in Block Builder?**
   - Pro: Integrates with query construction workflow
   - Con: Explorer provides richer interaction (discovery, paths, evidence)
   - **Decision:** Dedicated Explorer for now, Block integration if requested

4. **Performance optimization strategy?**
   - Current: On-demand calculation, no caching
   - Future: Global embedding query cache (benefits all embedding-dependent queries)
   - **Decision:** Implement core capability first, optimize holistically later

---

## Dependencies

### Existing Systems
- ✅ ADR-068: Source text embeddings and search
- ✅ ADR-058: Grounding calculation with polarity axis triangulation
- ✅ `/query/connect`: Concept path finding
- ✅ Job queue system for background processing
- ✅ Apache AGE for graph traversal
- ✅ PostgreSQL for embeddings storage

### New Dependencies
- NumPy (vector operations)
- SciPy (correlation calculations)
- React Flow (web UI spectrum visualization)

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Expensive computation affects UX | High | Background workers, job queue, progress tracking |
| Results unintuitive to users | Medium | Clear docs, examples, visual aids, tooltips |
| Grounding correlation weak for some axes | Medium | Document correlation strength, provide interpretation guide |
| Users discover nonsensical axes | Low | Show correlation metrics, filter by strength |

---

## Next Steps

1. ✅ Review this production plan with team
2. ⏳ Create feature branch: `feature/adr-070-polarity-axis-analysis`
3. ⏳ Implement Phase 1 (worker service)
4. ⏳ Add comprehensive tests
5. ⏳ Deploy to staging
6. ⏳ Iterate based on feedback

---

**Questions? Concerns? Ready to begin implementation?**
