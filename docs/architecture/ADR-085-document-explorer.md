# ADR-085: Document Explorer with Radial Concept Visualization

**Status:** Proposed
**Date:** 2026-01-04
**Deciders:** @aaronsb, @claude
**Related:** ADR-084 (Document Search), ADR-044 (Probabilistic Truth Convergence), ADR-034 (Explorer Plugin Interface)

## Context

ADR-084 introduced document-level search APIs. The next step is visualizing document→concept relationships in the web UI. Users need to understand:

1. What concepts were extracted from a document
2. How those concepts relate to other concepts in the graph
3. The "epistemic reach" of a document - how far its concepts influence the knowledge graph

### Prior Art: Spreading Activation

A design discussion proposed visualizing documents as origin nodes with activation spreading outward, intensity decaying over graph distance. This draws from:

- **Spreading Activation** (Cognitive Science) - energy propagates through semantic networks with decay
- **TrustRank** (Google/Yahoo) - trust flows from seed nodes, decays with hops
- **ADR-044** - bounded locality with depth=1 default, max 3 hops

### Recent Research: SA-RAG (December 2025)

The paper ["Leveraging Spreading Activation for Improved Document Retrieval in Knowledge-Graph-Based RAG Systems"](https://arxiv.org/abs/2512.15922) (arXiv:2512.15922) provides empirical validation:

- **Vector-weighted edges**: Edge weights = cosine similarity between query embedding and link embedding
- **Rescaling factor**: `w' = (w - c) / (1 - c)` where c=0.4 prevents overactivation
- **k-hop traversal**: k=3-10 hops depending on task complexity
- **Activation threshold**: τₐ=0.5 determines which nodes to retrieve
- **Results**: 25-39% improvement in answer correctness vs naive RAG

This validates our approach and suggests enhancements for Phase 2+.

### Existing Implementation

Our system already implements the computational foundations for spreading activation: `grounding_strength` uses cosine similarity against prototype embeddings (ADR-044/045), k-hop traversal exists via `concept related --max-depth N`, all vocabulary types have embeddings for edge weighting, and similarity thresholds filter weak connections. Spreading activation—propagating weights from a source node with decay over graph distance—describes what the system already does computationally. This ADR adds the **visualization layer** to make that latent structure visible.

No dedicated spreading activation service exists; EpistemicStatusService handles vocabulary classification, and PathfindingFacade provides pure BFS pathfinding. However, the visual effect can be achieved entirely in the presentation layer using existing API data.

## Decision

### 1. Radial Layout with Distance-Based Opacity

Visualize document→concept relationships as a radial graph:

```
                    ┌─────────────────┐
                    │   Hop 2 Nodes   │  ← Dim (opacity ~0.3)
                    │  (gray, small)  │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │   Hop 1 Nodes   │  ← Medium (opacity ~0.6)
                    │ (colored, med)  │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │   Hop 0 Nodes   │  ← Bright (opacity ~0.9)
                    │(colored, large) │
                    └────────┬────────┘
                             │
                    ┌────────┴────────┐
                    │    DOCUMENT     │  ← Center (gold, pulsing)
                    │ (origin node)   │
                    └─────────────────┘
```

### 2. Fixed Radial Positioning

Use deterministic fixed coordinates instead of force simulation to prevent wobble:

```typescript
// Pre-calculate fixed positions on graph load
const RING_RADIUS = 100;

nodes.forEach((node, i) => {
  if (node.type === 'document') {
    node.fx = 0;  // Document at origin
    node.fy = 0;
  } else {
    const nodesInRing = nodes.filter(n => n.hop === node.hop).length;
    const angleIndex = nodes.filter(n => n.hop === node.hop && n.id < node.id).length;
    const angle = (angleIndex / nodesInRing) * 2 * Math.PI;
    node.fx = Math.cos(angle) * (node.hop * RING_RADIUS);
    node.fy = Math.sin(angle) * (node.hop * RING_RADIUS);
  }
});
```

This creates stable "orbits" rather than physics-driven jitter.

### 3. Intensity Calculation (Presentation Layer)

Calculate intensity client-side from existing API data:

```typescript
interface ConceptNode {
  id: string;
  hop: number;                    // 0, 1, or 2
  grounding_strength: number;     // 0.0-1.0 from API
  edge_confidence: number;        // confidence of incoming edge
}

function calculateIntensity(node: ConceptNode): number {
  const decayFactor = 0.7;  // 30% decay per hop
  const hopDecay = Math.pow(decayFactor, node.hop);
  return hopDecay * node.grounding_strength;
}

// Visual mapping
node.opacity = 0.2 + (0.8 * calculateIntensity(node));  // 0.2-1.0 range
node.radius = 8 + (12 * calculateIntensity(node));      // 8-20px range
```

### 4. Data Flow

Use existing APIs - no new endpoints needed:

```
1. User selects document
   └── GET /documents/{id}  →  document metadata

2. Fetch direct concepts (Hop 0)
   └── GET /documents/{id}/concepts  →  concept list with grounding

3. Fetch related concepts (Hop 1-2)
   └── POST /query/concepts/related  →  neighbors with depth=2

4. Transform to D3 graph format
   └── Client-side: nodes[], links[], calculate intensities

5. Render with ForceGraph2D (radial mode)
   └── Reuse existing explorer components
```

### 5. Component Structure

Follow ADR-034 Explorer Plugin Interface:

```
web/src/explorers/DocumentExplorer/
├── DocumentExplorer.tsx        # Main component
├── types.ts                    # DocumentExplorerData, DocumentExplorerSettings
├── RadialLayout.ts             # Custom D3 force for radial positioning
└── IntensityCalculator.ts      # Decay/opacity calculations
```

Reuse from `explorers/common/`:
- `NodeInfoBox` - concept details on click
- `Legend` - grounding status colors
- `PanelStack` - layout management
- `GraphSettingsPanel` - hop depth, decay factor controls

### 6. Visual Encoding

| Property | Encodes | Range |
|----------|---------|-------|
| **Opacity** | Intensity (hop decay × grounding) | 0.2 - 1.0 |
| **Size** | Evidence count | 8 - 20px |
| **Color** | Grounding status | Green/Yellow/Gray/Red |
| **Ring** | Hop distance | Center=doc, rings=0,1,2 |
| **Edge thickness** | Relationship confidence | 1 - 4px |
| **Edge style** | Relationship type | Solid/dashed by category |

### 7. Re-centering Interaction

Clicking a concept re-centers the visualization on that concept:

```typescript
function handleNodeClick(node: ConceptNode) {
  if (node.type === 'concept') {
    // Animate transition: current view → node at center
    // Fetch documents that ground this concept
    // Rebuild graph with concept as origin
    setOriginNode(node.id);
    fetchGroundingDocuments(node.id);
  }
}
```

This enables traversal: Document → Concept → Other Documents → deeper exploration.

### 8. Settings Panel

```typescript
interface DocumentExplorerSettings {
  visual: {
    maxHops: 1 | 2 | 3;           // Default: 2
    decayFactor: number;          // Default: 0.7 (0.5-0.9 slider)
    minOpacity: number;           // Default: 0.2
    showLabels: boolean;          // Default: true
    colorBy: 'grounding' | 'ontology';
  };
  layout: {
    radialSpacing: number;        // Distance between rings
    nodeSpacing: number;          // Angular spread within ring
  };
}
```

## Consequences

### Positive

- **No new backend services** - uses existing APIs
- **Familiar patterns** - follows ADR-034 explorer interface
- **Reuses components** - NodeInfoBox, Legend, PanelStack
- **Intuitive metaphor** - "closer = more directly related"
- **Adjustable** - decay factor slider for user control
- **Performance** - client-side intensity calculation is O(n)

### Negative

- **Limited depth** - max 2-3 hops before visualization becomes cluttered
- **Simplified decay** - geometric decay per hop, not vector-similarity weighted per edge
- **Approximation** - intensity doesn't account for path quality, just distance

### Future Enhancements

1. **Vector-weighted decay (SA-RAG style)** - Replace fixed decay with cosine similarity:
   ```typescript
   // Current: fixed decay
   const decay = 0.7;

   // Future: vector-weighted (per arXiv:2512.15922)
   const edgeSimilarity = cosineSimilarity(documentEmbedding, edgeEmbedding);
   const rescaled = (edgeSimilarity - 0.4) / (1 - 0.4);  // c=0.4 prevents overactivation
   const decay = Math.max(0, rescaled);
   ```

2. **Activation threshold** - Prune nodes below τₐ=0.5 to prevent noise

3. **Contradiction highlighting** - Show "shadows" where CONTRADICTS edges exist (negative activation)

4. **Multi-document comparison** - Overlay multiple documents as activation sources, see where influence overlaps

5. **Animated traversal** - Show activation spreading as BFS animation on load

## Alternatives Considered

### 1. Build Dedicated Spreading Activation Service

**Rejected:** Over-engineering for MVP. The visual effect can be achieved with presentation-layer calculations. Can add backend optimization later if performance requires.

### 2. Use Existing ForceGraph2D Without Radial Layout

**Considered for v1:** Simpler implementation, but loses the "document at center" metaphor. May use as fallback if radial layout proves complex.

### 3. 3D Visualization with Depth as Z-Axis

**Deferred:** ForceGraph3D exists but adds complexity. Radial 2D is more intuitive for showing distance relationships.

## Implementation Plan

1. **Phase 1:** Basic DocumentExplorer with hop-0 concepts only
2. **Phase 2:** Add hop-1 expansion with decay visualization
3. **Phase 3:** Add hop-2 and settings panel
4. **Phase 4:** Polish (animations, multi-document support)

## References

- **SA-RAG Paper:** Kovač, M. et al. (2025). "Leveraging Spreading Activation for Improved Document Retrieval in Knowledge-Graph-Based RAG Systems." arXiv:2512.15922. https://arxiv.org/abs/2512.15922
- **GraphRAG Survey:** Pan, S. et al. (2024). "Retrieval-Augmented Generation with Graphs." arXiv:2501.00309. https://arxiv.org/abs/2501.00309
- **Spreading Activation (Original):** Collins, A. M., & Loftus, E. F. (1975). "A spreading-activation theory of semantic processing." Psychological Review.
- **ADR-044:** Probabilistic Truth Convergence - bounded locality, satisficing, grounding calculation
- **ADR-084:** Document-Level Search - APIs for document discovery
