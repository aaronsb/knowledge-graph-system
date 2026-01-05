# Document Explorer Design Notes

**Date:** 2026-01-04
**Context:** B4 of ADR-084 (Document Search) - Web Explorer Integration

## Gemini Discussion Summary

User had a discussion with Gemini about visualizing document→concept relationships. Key concepts proposed:

### 1. "Epistemic Ray Tracing" Metaphor
- Treat documents as **light sources** emitting "truth particles" (concepts)
- Light propagates along edges and **decays** with distance
- **Occlusion** when contradictions are found
- Vector similarity acts as "refraction index" controlling decay

### 2. Claimed Precedents
- **Spreading Activation** (Cognitive Science) - energy propagates through semantic networks with decay
- **TrustRank** (Google/Yahoo) - trust flows from seed nodes, decays with hops
- **Impact Analysis** (Systems Engineering) - trace downstream effects of changes
- **GraphRAG Flow** (2024-2025 research) - flow-based retrieval vs k-NN

### 3. Claimed Architecture References
- **ADR-044**: "Probabilistic Truth Convergence" with 2-hop satisficing
- **EpistemicStatusService**: Implements bounded locality
- **PathfindingFacade**: Vector similarity for path analysis

## Questions to Validate

1. **Does ADR-044 exist?** What does it actually say about bounded locality/satisficing?
2. **What does EpistemicStatusService actually do?** Is it k-hop based?
3. **How do existing explorers work?** What patterns should we follow?
4. **Is "ray tracing" the right metaphor?** Or is it over-engineering?

## Existing System Capabilities (to research)

- [ ] What explorers exist in web/src/?
- [ ] How does grounding calculation actually work?
- [ ] What's the relationship between DocumentMeta → Source → Concept?
- [ ] Do we already have document→concept traversal in the API?

## Design Considerations

### Simple First Approach
Start with a 2D explorer similar to concept explorer:
- Center: Selected document
- Radiating: Concepts extracted from that document
- Edge weight: Could be instance count or grounding contribution

### Data We Already Have (from ADR-084)
- `GET /documents` - list documents
- `GET /documents/{id}/concepts` - concepts for a document
- `POST /query/documents/search` - semantic search

### What We DON'T Have Yet
- Concept→concept relationships originating from a specific document
- "Light decay" or distance-based scoring from document
- Contradiction detection per document

## Next Steps

1. Research existing explorers to understand patterns
2. Validate what EpistemicStatusService actually does
3. Start simple: Document-centric concept graph
4. Add sophistication later (decay, grounding visualization)

---

## Research Findings

### 1. ADR-044 EXISTS ✅ (Gemini was right)

**Location:** `docs/architecture/ai-embeddings/ADR-044-probabilistic-truth-convergence.md`

**Key concepts (lines 358-671):**
- **Bounded Rationality** - Herbert Simon's concept applied to graph traversal
- **Satisficing** - "good enough" rather than perfect consistency
- **Depth=1 is the pragmatic optimum** for grounding calculations
- **Maximum 3 hops** for path queries
- Recursive depth causes exponential explosion O(E^depth)

**What it actually does:**
- Calculates `grounding_strength` from SUPPORTS/CONTRADICTS edge weights
- Query-time calculation, not stored
- Uses cosine similarity to SUPPORTS/CONTRADICTS prototypes
- Default threshold 0.20 (20% support minimum)

**Gemini's claim accuracy:** ~80% correct. The concepts exist, but it's about grounding strength calculation, not "ray tracing" per se.

### 2. EpistemicStatusService - Different Purpose ⚠️

**Location:** `api/api/services/epistemic_status_service.py`

**What Gemini claimed:** Implements bounded locality for k-hop traversal from documents

**What it actually does:**
- Measures epistemic status for **vocabulary types** (relationship types)
- Samples edges and calculates grounding dynamically
- Classifies as: WELL_GROUNDED, MIXED_GROUNDING, WEAK_GROUNDING, etc.
- NOT for document→concept traversal

**Conclusion:** Gemini conflated two different systems.

### 3. PathfindingFacade - Correct but Misapplied ⚠️

**Location:** `api/api/lib/pathfinding_facade.py`

**What it does:**
- Bidirectional BFS for shortest path between concepts
- Part of ADR-076 (Pathfinding Optimization)
- O(b^(d/2)) instead of O(b^d)

**What Gemini claimed:** Vector similarity for path analysis

**Reality:** Pure graph traversal, no vector similarity decay. Just finds paths efficiently.

### 4. Existing Web Explorers Pattern ✅

**Location:** `web/src/explorers/ForceGraph2D/ForceGraph2D.tsx` (~1800 lines)

**Key patterns to follow:**
- Uses `ExplorerProps<ForceGraph2DData, ForceGraph2DSettings>` interface
- D3.js force simulation
- Settings panels (visual, physics, interaction)
- Node/edge info boxes on click
- Context menus (right-click)
- Legend component
- Follows **ADR-034 Explorer Plugin Interface**

**Components available:**
- `NodeInfoBox`, `EdgeInfoBox` - info popups
- `StatsPanel` - node/edge counts
- `GraphSettingsPanel` - settings UI
- `Legend` - color legend
- `PanelStack` - layout management
- `ContextMenu` - right-click menus

### 5. What We Actually Need for Document Explorer

**Simple approach (recommended):**
1. Document as center node (like concept explorer)
2. Concepts radiating outward
3. Edge weight = instance count or grounding contribution
4. Reuse existing explorer components

**API endpoints already exist (ADR-084):**
- `GET /documents` - list documents
- `GET /documents/{id}/concepts` - concepts for a document
- `POST /query/documents/search` - semantic search

**What we DON'T need:**
- Complex "ray tracing" algorithms
- Vector similarity decay calculations
- Custom EpistemicRayTracer service

### 6. Verdict on Gemini's Proposal

| Claim | Accuracy | Notes |
|-------|----------|-------|
| ADR-044 exists | ✅ Correct | In ai-embeddings/, not adr/ |
| Bounded locality/satisficing | ✅ Correct | Depth=1 default, max 3 hops |
| EpistemicStatusService does k-hop | ❌ Wrong | Does vocabulary classification |
| PathfindingFacade has vector decay | ❌ Wrong | Pure graph BFS |
| "Ray tracing" metaphor useful | 🤷 Maybe | Over-engineering for MVP |

**Recommendation:** Start simple with existing explorer pattern. Add sophistication later if needed.
