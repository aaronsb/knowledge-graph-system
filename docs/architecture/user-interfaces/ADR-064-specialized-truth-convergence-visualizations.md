# ADR-064: Specialized Truth Convergence Visualizations

**Status:** Proposed
**Date:** 2025-11-13
**Deciders:** Development Team
**Related:** ADR-034 (Graph Visualization Architecture), ADR-035 (Explorer Methods), ADR-044 (Probabilistic Truth Convergence), ADR-051 (Graph Provenance Tracking), ADR-063 (Semantic Diversity)

## Context

The current web visualization (ADR-034, ADR-035) provides 2D and 3D force-directed graph explorers that excel at showing connectivity patterns and conceptual neighborhoods. However, the platform has unique capabilities that are not leveraged by traditional node-edge visualizations:

**Unique Platform Capabilities:**
- **Truth convergence:** Grounding strength (-1.0 to 1.0) measures reliability vs. contradiction (ADR-044, ADR-058)
- **Semantic diversity:** Measures conceptual richness via percentage of diverse connections (ADR-063)
- **Provenance tracking:** DocumentMeta nodes, relationship audit trails (ADR-051)
- **Relationship polarity:** Support vs. contradict indicators with authenticated diversity
- **Vocabulary lifecycle:** Dynamic relationship types with categorization (ADR-052, ADR-053)
- **Evidence-based relationships:** Quoted text from source documents with image indicators

**Limitations of Current Approach:**

While force graphs show "which concepts are connected," they don't effectively communicate:
1. **Confidence landscapes:** Where is knowledge well-grounded vs. contradictory?
2. **Provenance flows:** Which sources contribute most to key concepts?
3. **Temporal evolution:** How has understanding matured over time?
4. **Semantic clustering:** Are concepts authentically diverse or circularly dependent?
5. **Evidence balance:** What proportion of evidence supports vs. contradicts assertions?

**User Needs:**

**Analysts & Decision Makers:**
- Identify weak knowledge areas (low grounding strength)
- Validate data source contributions
- Assess readiness for decisions based on knowledge confidence
- Understand evidence quality across domains

**Knowledge Curators:**
- Detect suspicious low-diversity clusters (potential bias or circular reasoning)
- Track vocabulary consolidation lifecycle
- Identify high-value vs. low-value source documents

**Researchers:**
- Understand how concepts evolved during discovery
- Identify when grounding strength changed significantly
- Trace provenance chains from documents to assertions

## Decision

Expand the web visualization application with **specialized explorers** that leverage truth convergence, provenance, and temporal metadata beyond traditional node-edge graphs.

### Visualization Categories

**Category 1: Truth & Confidence Visualizations** (Leverage existing metadata)
1. **Confidence Heatmap** - 2D grid/3D terrain where concepts positioned by domain/category, colored/sized by grounding strength
2. **Polarity Spectrum** - Horizontal spectrum from CONTRADICTS ↔ SUPPORTS showing relationship polarity balance
3. **Evidence Balance Gauge** - Radial gauges showing % supporting vs. contradicting evidence for key concepts

**Category 2: Temporal & Evolution Visualizations** (Require new timestamps)
4. **Concept Lifecycle Timeline** - Horizontal timeline showing concept creation, grounding strength evolution, vocabulary consolidation
5. **Document Ingestion Waterfall** - Vertical cascade showing documents with branches for extracted concepts
6. **Grounding Strength Evolution** - Line chart showing how concept confidence changed over time

**Category 3: Semantic & Categorical Visualizations** (Leverage existing metadata)
7. **Semantic Diversity Sunburst** - Radial hierarchy: inner=vocabulary categories, outer=concepts, color=diversity score
8. **Concept Cluster Treemap** - Nested rectangles where area=relationship count, color=average grounding strength

**Category 4: Relationship & Impact Visualizations** (Leverage existing metadata)
9. **Provenance Sankey** - Flow diagram from source documents → concepts → derived assertions
10. **Concept Relationship Matrix** - Cross-ontology relationship patterns shown as adjacency matrix with strength heatmap

### Technical Architecture

All new explorers follow the **plugin pattern** established in ADR-034:

```typescript
// src/explorers/ConfidenceHeatmap/index.ts

import { HeatmapIcon } from 'lucide-react';
import { ConfidenceHeatmapViz } from './ConfidenceHeatmapViz';
import { ConfidenceSettingsPanel } from './SettingsPanel';

export const ConfidenceHeatmapExplorer: ExplorerPlugin = {
  config: {
    id: 'confidence-heatmap',
    type: 'confidence-heatmap',
    name: 'Confidence Heatmap',
    description: 'Visualize grounding strength across concept domains',
    icon: HeatmapIcon,
    requiredDataShape: 'aggregate', // Not 'graph' or 'tree'
  },

  component: ConfidenceHeatmapViz,
  settingsPanel: ConfidenceSettingsPanel,

  dataTransformer: (apiData) => {
    // Transform concepts into heatmap grid
    return buildConfidenceGrid(apiData);
  },

  defaultSettings: {
    colorScale: 'diverging', // red (low) → yellow → green (high)
    aggregation: 'category', // 'category' | 'ontology' | 'time_bucket'
    showLabels: true,
  },
};
```

**Integration:** Register in `src/explorers/registry.ts` → automatically appears in sidebar.

### REST API Endpoints (New)

```python
# src/api/routes/visualization.py

@router.get("/viz/confidence/heatmap")
async def get_confidence_heatmap(
    ontology: Optional[str] = None,
    groupBy: Literal["category", "ontology", "vocabulary_type"] = "category"
) -> ConfidenceHeatmapResponse:
    """
    Return concepts grouped with aggregate grounding strength metrics.

    Response:
    {
      "cells": [
        {
          "group": "Infrastructure Concepts",
          "conceptCount": 45,
          "avgGroundingStrength": 0.73,
          "minGrounding": 0.12,
          "maxGrounding": 0.95,
          "semanticDiversity": 0.42
        },
        ...
      ]
    }
    """
    pass

@router.get("/viz/provenance/flow")
async def get_provenance_flow(
    target_concept_id: Optional[str] = None,
    ontology: Optional[str] = None
) -> ProvenanceFlowResponse:
    """
    Return Sankey diagram data showing DocumentMeta → Source → Concept flow.

    Response:
    {
      "nodes": [
        {"id": "doc_123", "name": "research_paper.pdf", "type": "document"},
        {"id": "src_456", "name": "Source paragraph", "type": "source"},
        {"id": "concept_789", "name": "Neural Networks", "type": "concept"}
      ],
      "links": [
        {"source": "doc_123", "target": "src_456", "value": 1},
        {"source": "src_456", "target": "concept_789", "value": 1}
      ]
    }
    """
    pass

@router.get("/viz/timeline/concept_lifecycle")
async def get_concept_lifecycle(
    concept_id: str
) -> ConceptLifecycleResponse:
    """
    Return temporal evolution of a concept's grounding strength.

    Requires: Concept.created_at timestamps + edge.created_at history

    Response:
    {
      "concept": {"id": "concept_123", "label": "Machine Learning Ethics"},
      "events": [
        {"timestamp": "2025-01-01T00:00:00Z", "type": "created", "grounding": 0.0},
        {"timestamp": "2025-01-15T12:00:00Z", "type": "edge_added", "grounding": 0.45, "evidence_count": 3},
        {"timestamp": "2025-02-10T08:30:00Z", "type": "contradicting_edge", "grounding": 0.12, "evidence_count": 5}
      ]
    }
    """
    pass

@router.get("/viz/semantic/diversity_sunburst")
async def get_diversity_sunburst(
    ontology: str,
    min_diversity: float = 0.0
) -> DiversitySunburstResponse:
    """
    Return hierarchical data: VocabCategory → VocabType → Concepts.

    Response:
    {
      "name": "root",
      "children": [
        {
          "name": "Causal Relationships",
          "children": [
            {
              "name": "CAUSES",
              "children": [
                {"name": "Climate Change", "value": 12, "diversity": 0.37},
                {"name": "Ocean Acidification", "value": 8, "diversity": 0.41}
              ]
            }
          ]
        }
      ]
    }
    """
    pass
```

### Data Requirements & Migration

**Existing Metadata (No Changes Needed):**
- ✅ Grounding strength (`grounding_strength` on relationships - ADR-044, ADR-058)
- ✅ Semantic diversity (calculated on-demand - ADR-063)
- ✅ Provenance tracking (`DocumentMeta` nodes, `source_type`, `ingested_by` - ADR-051)
- ✅ Relationship polarity (embedded in polarity axis projection - ADR-058)
- ✅ Vocabulary categories (`VocabType`, `VocabCategory` - ADR-047, ADR-053)

**New Metadata Required (Migration 025):**

```sql
-- Migration 025: Temporal Tracking for Visualization

-- Add created_at to Concept nodes (graph property)
-- NOTE: Apache AGE stores properties on nodes, no SQL schema changes needed
-- Application code will add 'created_at' property when creating concepts
-- Format: ISO 8601 timestamp string (e.g., "2025-01-13T10:30:00Z")

-- Example Cypher for creating concept with timestamp:
-- CREATE (c:Concept {
--   concept_id: 'abc123',
--   label: 'VM Sprawl',
--   created_at: '2025-11-13T10:30:00Z',
--   last_modified: '2025-11-13T10:30:00Z'
-- })

-- Add SQL table for grounding strength history (optional, for performance)
CREATE TABLE IF NOT EXISTS kg_api.grounding_strength_history (
    id BIGSERIAL PRIMARY KEY,
    concept_id TEXT NOT NULL,
    grounding_strength NUMERIC(5,4) NOT NULL, -- -1.0000 to 1.0000
    evidence_count INTEGER NOT NULL,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    triggered_by TEXT, -- 'edge_added' | 'edge_removed' | 'recalculation'
    job_id TEXT REFERENCES kg_api.jobs(job_id)
);

CREATE INDEX IF NOT EXISTS idx_grounding_history_concept
ON kg_api.grounding_strength_history(concept_id, calculated_at DESC);

CREATE INDEX IF NOT EXISTS idx_grounding_history_time
ON kg_api.grounding_strength_history(calculated_at DESC);

COMMENT ON TABLE kg_api.grounding_strength_history IS
'Tracks how concept grounding strength changes over time - enables lifecycle timeline visualization';

-- Add SQL table for vocabulary lifecycle tracking
CREATE TABLE IF NOT EXISTS kg_api.vocabulary_lifecycle_events (
    id BIGSERIAL PRIMARY KEY,
    vocab_type TEXT NOT NULL, -- Relationship type name
    event_type TEXT NOT NULL, -- 'created' | 'dream_mode' | 'consolidated' | 'deprecated'
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    triggered_by TEXT, -- User ID or 'system'
    metadata JSONB -- Additional event details
);

CREATE INDEX IF NOT EXISTS idx_vocab_lifecycle_type
ON kg_api.vocabulary_lifecycle_events(vocab_type, occurred_at DESC);

COMMENT ON TABLE kg_api.vocabulary_lifecycle_events IS
'Tracks vocabulary expansion-consolidation cycle (ADR-052) for timeline visualization';
```

**Why SQL Tables for History Instead of Graph Edges:**

1. **Performance:** Time-series queries are faster in PostgreSQL than graph traversals
2. **Retention:** Don't pollute graph with historical snapshots
3. **Aggregation:** SQL window functions ideal for trends/deltas
4. **Hybrid approach:** Graph stores current state, SQL stores history

### D3.js Implementation Examples

**1. Confidence Heatmap (2D)**

```typescript
// src/explorers/ConfidenceHeatmap/ConfidenceHeatmapViz.tsx

import * as d3 from 'd3';
import { useEffect, useRef } from 'react';

interface ConfidenceCell {
  group: string;
  conceptCount: number;
  avgGroundingStrength: number;
  semanticDiversity: number;
}

export const ConfidenceHeatmapViz: React.FC<{ data: ConfidenceCell[] }> = ({ data }) => {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const width = 800;
    const height = 600;
    const margin = { top: 40, right: 20, bottom: 60, left: 150 };

    // Diverging color scale: red (weak) → white (neutral) → green (strong)
    const colorScale = d3.scaleLinear<string>()
      .domain([-1, 0, 1])
      .range(['#d73027', '#ffffbf', '#1a9850']);

    // Position cells in grid
    const cellWidth = (width - margin.left - margin.right) / 5;
    const cellHeight = 60;

    const cells = svg.selectAll('rect')
      .data(data)
      .join('rect')
      .attr('x', (d, i) => margin.left + (i % 5) * cellWidth)
      .attr('y', (d, i) => margin.top + Math.floor(i / 5) * cellHeight)
      .attr('width', cellWidth - 2)
      .attr('height', cellHeight - 2)
      .attr('fill', d => colorScale(d.avgGroundingStrength))
      .attr('stroke', '#333')
      .attr('stroke-width', 1);

    // Add labels
    svg.selectAll('text')
      .data(data)
      .join('text')
      .attr('x', (d, i) => margin.left + (i % 5) * cellWidth + cellWidth / 2)
      .attr('y', (d, i) => margin.top + Math.floor(i / 5) * cellHeight + cellHeight / 2)
      .attr('text-anchor', 'middle')
      .attr('dominant-baseline', 'middle')
      .attr('fill', d => d.avgGroundingStrength > 0.5 ? '#000' : '#fff')
      .text(d => `${d.group}\n(${d.conceptCount})`)
      .style('font-size', '12px')
      .style('pointer-events', 'none');

    // Add tooltips
    cells.append('title')
      .text(d => `${d.group}\nConcepts: ${d.conceptCount}\nGrounding: ${d.avgGroundingStrength.toFixed(2)}\nDiversity: ${d.semanticDiversity.toFixed(2)}`);

  }, [data]);

  return <svg ref={svgRef} width={800} height={600} />;
};
```

**2. Provenance Sankey Diagram**

```typescript
// src/explorers/ProvenanceSankey/ProvenanceSankeyViz.tsx

import * as d3 from 'd3';
import { sankey, sankeyLinkHorizontal } from 'd3-sankey';

interface SankeyNode {
  id: string;
  name: string;
  type: 'document' | 'source' | 'concept';
}

interface SankeyLink {
  source: string;
  target: string;
  value: number; // Flow strength (number of concepts)
}

export const ProvenanceSankeyViz: React.FC<{ nodes: SankeyNode[]; links: SankeyLink[] }> = ({ nodes, links }) => {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const width = 1000;
    const height = 600;

    const sankeyGenerator = sankey<SankeyNode, SankeyLink>()
      .nodeWidth(15)
      .nodePadding(10)
      .extent([[1, 1], [width - 1, height - 6]]);

    const graph = sankeyGenerator({
      nodes: nodes.map(d => ({ ...d })),
      links: links.map(d => ({ ...d }))
    });

    // Draw links
    svg.selectAll('path.link')
      .data(graph.links)
      .join('path')
      .attr('class', 'link')
      .attr('d', sankeyLinkHorizontal())
      .attr('stroke', '#ccc')
      .attr('stroke-width', d => Math.max(1, d.width))
      .attr('fill', 'none')
      .attr('opacity', 0.5);

    // Draw nodes
    svg.selectAll('rect.node')
      .data(graph.nodes)
      .join('rect')
      .attr('class', 'node')
      .attr('x', d => d.x0)
      .attr('y', d => d.y0)
      .attr('height', d => d.y1 - d.y0)
      .attr('width', d => d.x1 - d.x0)
      .attr('fill', d => {
        if (d.type === 'document') return '#4A90E2';
        if (d.type === 'source') return '#50C878';
        return '#FFD700';
      });

    // Add labels
    svg.selectAll('text.node-label')
      .data(graph.nodes)
      .join('text')
      .attr('class', 'node-label')
      .attr('x', d => d.x0 < width / 2 ? d.x1 + 6 : d.x0 - 6)
      .attr('y', d => (d.y1 + d.y0) / 2)
      .attr('text-anchor', d => d.x0 < width / 2 ? 'start' : 'end')
      .text(d => d.name);

  }, [nodes, links]);

  return <svg ref={svgRef} width={1000} height={600} />;
};
```

**3. Concept Lifecycle Timeline**

```typescript
// src/explorers/ConceptLifecycle/ConceptLifecycleViz.tsx

import * as d3 from 'd3';

interface LifecycleEvent {
  timestamp: string;
  type: 'created' | 'edge_added' | 'contradicting_edge' | 'recalculated';
  grounding: number;
  evidenceCount: number;
}

export const ConceptLifecycleViz: React.FC<{ events: LifecycleEvent[] }> = ({ events }) => {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current) return;

    const svg = d3.select(svgRef.current);
    const width = 1000;
    const height = 400;
    const margin = { top: 20, right: 20, bottom: 50, left: 60 };

    // Parse timestamps
    const parseTime = d3.utcParse('%Y-%m-%dT%H:%M:%SZ');
    const data = events.map(e => ({
      ...e,
      date: parseTime(e.timestamp)!
    }));

    // Scales
    const xScale = d3.scaleTime()
      .domain(d3.extent(data, d => d.date) as [Date, Date])
      .range([margin.left, width - margin.right]);

    const yScale = d3.scaleLinear()
      .domain([-1, 1])
      .range([height - margin.bottom, margin.top]);

    // Line generator
    const line = d3.line<typeof data[0]>()
      .x(d => xScale(d.date))
      .y(d => yScale(d.grounding))
      .curve(d3.curveMonotoneX);

    // Draw line
    svg.append('path')
      .datum(data)
      .attr('fill', 'none')
      .attr('stroke', '#4A90E2')
      .attr('stroke-width', 2)
      .attr('d', line);

    // Draw points
    svg.selectAll('circle')
      .data(data)
      .join('circle')
      .attr('cx', d => xScale(d.date))
      .attr('cy', d => yScale(d.grounding))
      .attr('r', 4)
      .attr('fill', d => {
        if (d.type === 'contradicting_edge') return '#d73027';
        if (d.type === 'edge_added') return '#1a9850';
        return '#4A90E2';
      });

    // Add axes
    const xAxis = d3.axisBottom(xScale);
    const yAxis = d3.axisLeft(yScale);

    svg.append('g')
      .attr('transform', `translate(0,${height - margin.bottom})`)
      .call(xAxis);

    svg.append('g')
      .attr('transform', `translate(${margin.left},0)`)
      .call(yAxis);

    // Add labels
    svg.append('text')
      .attr('x', width / 2)
      .attr('y', height - 10)
      .attr('text-anchor', 'middle')
      .text('Time');

    svg.append('text')
      .attr('transform', 'rotate(-90)')
      .attr('x', -height / 2)
      .attr('y', 15)
      .attr('text-anchor', 'middle')
      .text('Grounding Strength');

  }, [events]);

  return <svg ref={svgRef} width={1000} height={400} />;
};
```

### 3D Visualizations (Three.js)

**3D Evidence Mountain:**

```typescript
// src/explorers/EvidenceMountain/EvidenceMountainViz.tsx

import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls';

interface ConceptPosition {
  x: number;
  y: number;
  grounding: number; // Z height
  label: string;
}

export const EvidenceMountainViz: React.FC<{ concepts: ConceptPosition[] }> = ({ concepts }) => {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mountRef.current) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, 800 / 600, 0.1, 1000);
    const renderer = new THREE.WebGLRenderer();
    renderer.setSize(800, 600);
    mountRef.current.appendChild(renderer.domElement);

    // Add orbit controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;

    // Create terrain surface
    concepts.forEach(c => {
      const geometry = new THREE.ConeGeometry(0.5, c.grounding * 5, 8);
      const material = new THREE.MeshPhongMaterial({
        color: c.grounding > 0.5 ? 0x1a9850 : 0xd73027
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(c.x * 10, c.grounding * 5, c.y * 10);
      scene.add(mesh);
    });

    // Add lighting
    const light = new THREE.DirectionalLight(0xffffff, 1);
    light.position.set(5, 10, 5);
    scene.add(light);
    scene.add(new THREE.AmbientLight(0x404040));

    // Position camera
    camera.position.set(15, 15, 15);
    camera.lookAt(0, 0, 0);

    // Animation loop
    const animate = () => {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    return () => {
      mountRef.current?.removeChild(renderer.domElement);
    };
  }, [concepts]);

  return <div ref={mountRef} />;
};
```

## Implementation Priority

### Tier 1: High Value, Low Complexity (Existing Data)
**Effort:** 2-3 weeks each
**Timeline:** Q4 2025 / Q1 2026

1. **Confidence Heatmap** (2D)
   - Uses: `grounding_strength`, `concept.label`, `vocab_type` (for grouping)
   - API: Aggregate query with GROUP BY
   - Value: Immediate visibility into weak knowledge areas

2. **Polarity Spectrum** (2D)
   - Uses: Relationship polarity from ADR-058 projection
   - API: Query all edges for a concept, compute balance
   - Value: Validate transformation readiness at-a-glance

3. **Concept Cluster Treemap** (2D)
   - Uses: Relationship counts, grounding strength
   - API: Aggregate query with graph traversal depth-1
   - Value: Identify dense vs sparse graph regions

### Tier 2: High Value, Medium Complexity (Needs Timestamps)
**Effort:** 3-4 weeks each
**Timeline:** Q1 2026
**Prerequisite:** Migration 025 (temporal metadata)

4. **Concept Lifecycle Timeline** (2D)
   - Requires: `grounding_strength_history` table
   - API: Time-series query with window functions
   - Value: Understand how confidence changed over time

5. **Document Ingestion Waterfall** (2D)
   - Uses: `DocumentMeta.ingested_at`, `Source` relationships
   - API: Chronological query with nested results
   - Value: Validate discovery sessions added unique value

6. **Grounding Evolution Chart** (2D)
   - Uses: `grounding_strength_history` table
   - API: Time-series query for multiple concepts
   - Value: Compare concept reliability trends

### Tier 3: High Value, High Complexity
**Effort:** 4-6 weeks each
**Timeline:** Q2 2026

7. **Provenance Sankey** (2D)
   - Uses: `DocumentMeta → Source → Concept` traversals
   - API: Complex graph traversal with flow calculation
   - Value: Understand source contributions

8. **3D Evidence Mountain** (3D)
   - Uses: Embedding 2D projection + grounding strength
   - API: Concept embeddings with t-SNE/UMAP projection
   - Value: Spatial intuition for confidence landscape

9. **Semantic Diversity Sunburst** (2D)
   - Uses: `VocabCategory → VocabType → Concept` hierarchy
   - API: Hierarchical query with diversity calculations
   - Value: Identify authentic vs synthetic knowledge

### Tier 4: Specialized Use Cases
**Effort:** 3-4 weeks each
**Timeline:** Q3 2026

10. **Concept Relationship Matrix** (2D)
    - Uses: Cross-ontology bipartite graph queries
    - API: Relationship strength between concept groups
    - Value: Identify patterns and gaps in knowledge connections

11. **Vocabulary Lifecycle Timeline** (2D)
    - Requires: `vocabulary_lifecycle_events` table
    - API: Event stream query
    - Value: Track expansion-consolidation cycle (ADR-052)

## Consequences

### Positive

1. **Better Decision Support:** Truth convergence and confidence visualizations directly inform transformation planning
2. **Quality Assurance:** Semantic diversity and provenance views detect suspicious patterns (circular reasoning, single-source bias)
3. **Temporal Understanding:** Lifecycle timelines show how knowledge matured, building confidence in the graph
4. **User Engagement:** Diverse visualization modes match different analysis tasks (research, curation, planning)
5. **Platform Differentiation:** Leverages unique capabilities (grounding, diversity, provenance) that competitors lack

### Negative

1. **Increased Complexity:** 11 new explorer types increases maintenance burden and testing surface
2. **API Expansion:** 6+ new endpoints with complex aggregation queries
3. **Migration Risk:** Requires schema changes (temporal metadata) that affect existing ingestion code
4. **Learning Curve:** Users must understand which visualization fits their question
5. **Performance Uncertainty:** Large-scale aggregations (heatmaps, Sankeys) may be slow on 10,000+ concept graphs

### Neutral

1. **Incremental Rollout:** Tier-based implementation spreads effort over 3-4 quarters
2. **Backward Compatibility:** Existing force graph explorers unchanged, new explorers additive
3. **Documentation Need:** Each explorer requires user guide explaining when to use it
4. **Testing Strategy:** Need synthetic datasets with known patterns (high/low grounding, diverse/circular clusters)

## Alternatives Considered

### Alternative 1: External Visualization Tools

**Option:** Export data to Gephi, Tableau, or Observable notebooks for specialized visualizations.

**Pros:**
- No development effort for visualization code
- Users can customize views extensively
- Leverage mature visualization ecosystems

**Cons:**
- Friction: Users must export data, switch tools, re-import
- No real-time updates from graph changes
- Loses platform integration (authentication, query history, provenance links)
- Cannot leverage platform-specific features (follow concept, context menus)

**Verdict:** Rejected. Platform integration and real-time updates are critical for iterative analysis.

### Alternative 2: Dashboarding Framework (Grafana, Metabase)

**Option:** Build dashboards using existing BI tools that connect to PostgreSQL.

**Pros:**
- Pre-built components for charts, tables, aggregations
- User-configurable dashboards
- Alert/notification systems

**Cons:**
- Optimized for metrics, not graph topology
- Limited support for graph-specific visualizations (Sankey, force graphs)
- Cannot render interactive node-edge exploration
- Awkward integration with openCypher queries (Apache AGE)

**Verdict:** Rejected. Graph-native visualizations require custom D3/Three.js implementations.

### Alternative 3: Minimal Approach (Heatmap Only)

**Option:** Implement only Confidence Heatmap as proof-of-concept, defer others.

**Pros:**
- Fastest path to value
- Validates user demand before investing in 11 explorers
- Lower maintenance burden

**Cons:**
- Limited utility (one view cannot serve all analysis needs)
- May not demonstrate platform's full potential
- Users may assume platform lacks visualization depth

**Verdict:** Considered. **Recommendation:** Start with Tier 1 (3 explorers) as MVP to validate approach, then proceed to Tier 2 based on user feedback.

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- Create database migration 025 (temporal metadata)
- Update `ingestion_worker.py` to record `created_at` on concepts
- Add `grounding_strength_history` tracking on relationship changes
- Create `/viz/` API endpoint namespace

### Phase 2: Tier 1 Explorers (Week 3-8)
- Implement ConfidenceHeatmap explorer + API endpoint
- Implement PolaritySpectrum explorer + API endpoint
- Implement ConceptClusterTreemap explorer + API endpoint
- User testing and feedback

### Phase 3: Tier 2 Explorers (Week 9-20)
- Implement ConceptLifecycle explorer + API endpoint
- Implement DocumentWaterfall explorer + API endpoint
- Implement GroundingEvolution explorer + API endpoint
- Performance testing with large graphs

### Phase 4: Advanced Explorers (Week 21-32)
- Implement ProvenanceSankey explorer
- Implement EvidenceMountain (3D) explorer
- Implement SemanticDiversitySunburst explorer
- Integration testing across all explorers

### Phase 5: Specialized Explorers (Week 33-44)
- Implement TransformationMatrix explorer
- Implement VocabularyLifecycle explorer
- Documentation and training materials
- Production deployment

## Success Metrics

**Adoption Metrics:**
- % of users trying non-force-graph explorers
- Avg explorers used per session
- Time spent in specialized views vs force graphs

**Discovery Metrics:**
- Number of weak-grounding concepts identified and improved
- Source provenance queries executed
- Transformation readiness assessments performed

**Quality Metrics:**
- Semantic diversity improvements after curator interventions
- Reduction in low-grounding concept clusters
- Increase in diverse evidence sources per concept

**Technical Metrics:**
- API response time for aggregation queries (<2s for p95)
- Visualization render time (<1s for 100-500 data points)
- Memory usage for large datasets

## Related ADRs

- **ADR-034:** Establishes web visualization architecture and force graph explorers
- **ADR-035:** Documents interaction patterns and "You Are Here" navigation
- **ADR-044:** Probabilistic truth convergence provides grounding strength metric
- **ADR-051:** Graph provenance tracking enables DocumentMeta → Concept flows
- **ADR-052:** Vocabulary expansion-consolidation cycle informs lifecycle visualization
- **ADR-058:** Polarity axis triangulation provides relationship polarity for spectrum view
- **ADR-063:** Semantic diversity as authenticity signal drives diversity visualizations

## References

- [D3.js Gallery](https://observablehq.com/@d3/gallery)
- [D3-Sankey Documentation](https://github.com/d3/d3-sankey)
- [D3-Hierarchy Sunburst](https://observablehq.com/@d3/sunburst)
- [Three.js Examples](https://threejs.org/examples/)
- [Deck.gl Hexagonal Binning](https://deck.gl/docs/api-reference/aggregation-layers/hexagon-layer)

## Approval & Sign-Off

- [ ] Development Team Review
- [ ] Database Migration Review (Migration 025)
- [ ] API Design Review (REST endpoint contracts)
- [ ] UX/UI Design Review (explorer wireframes)
- [ ] Performance Testing (large graph aggregations)
- [ ] Documentation Complete (per-explorer usage guides)
