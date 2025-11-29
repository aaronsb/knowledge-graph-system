# Polarity Axis Analysis

**Status:** Planned
**ADR:** [ADR-070: Polarity Axis Analysis for Bidirectional Semantic Dimensions](../../architecture/ADR-070-polarity-axis-analysis.md)
**Branch:** `feature/polarity-axis-analysis`

## Overview

Polarity axis analysis enables exploration of bidirectional semantic dimensions in the knowledge graph. By projecting concept embeddings onto axes formed by opposing concepts (e.g., Modern ↔ Traditional), users can discover where concepts fall on semantic spectrums and identify synthesis concepts that balance both poles.

This complements ADR-058's grounding calculation (which projects relationship edges onto polarity axes for reliability scoring) by applying the same mathematical technique to concept exploration.

## Key Capabilities

- **Semantic Positioning:** Determine where concepts fall on conceptual spectrums
- **Axis Discovery:** Auto-discover implicit dimensions from PREVENTS/CONTRADICTS relationships
- **Synthesis Detection:** Identify "middle ground" concepts that integrate opposing poles
- **Grounding Correlation:** Validate axes by measuring correlation with grounding strength

## Feature Documentation

- **[IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)** - Complete implementation roadmap with API endpoints, worker architecture, and interface specifications
- **[FINDINGS.md](./FINDINGS.md)** - Experimental validation results from prototype testing
- **[SESSION_SUMMARY.md](./SESSION_SUMMARY.md)** - Development session notes including grounding integration fix and production planning

## Experimental Code

The [experimental_code/](./experimental_code/) directory contains the validated prototype implementations:

- **`polarity_axis_analysis.py`** - Core polarity axis library with grounding integration
- **`analyze_prevents_polarity.py`** - PREVENTS relationship polarity analysis
- **`path_analysis.py`** - Semantic path analysis utilities
- **`run_polarity_enhanced.py`** - Enhanced runner with better exemplars
- **`analyze_mcp_path.py`** - Real graph analysis using database embeddings

These scripts demonstrate the approach and can be referenced during production implementation.

## Example Use Case

**Question:** Where does "Agile" fall on the Modern ↔ Traditional spectrum?

**Analysis:**
```
Traditional ●────────────────────────────────● Modern
      │                                        │
 Grounding: -0.040                       Grounding: +0.133

Projected Concepts:
  Agile                  (+0.194) - Toward Modern pole
  Legacy Systems         (-0.114) - Toward Traditional pole
  Modern Ways of Working (+0.803) - Strongly Modern
```

**Insight:** Agile's position (+0.194) aligns with positive grounding (+0.227), validating it as a modern/beneficial practice. The strong correlation (r=0.85) confirms this axis represents a value dimension.

## Implementation Status

**Phase 1: Core Worker** - Not started
- Refactor experimental code into `PolarityAxisWorker`
- Add to worker registry
- Unit tests for projection algorithm

**Phase 2: API Endpoints** - Not started
- `POST /queries/polarity-axis` (analyze axis)
- `POST /queries/discover-polarity-axes` (auto-discover)
- `GET /queries/polarity-axis/{axis_id}/project/{concept_id}` (project concept)

**Phase 3: Documentation** - In Progress
- ✅ ADR-070 drafted
- ✅ Feature documentation organized
- ⏳ API documentation (OpenAPI)
- ⏳ User guides

**Phase 4: Interface Integration** - Not started
- MCP server tools
- CLI commands (`kg polarity ...`)
- Web workstation "Polarity Axis Explorer" panel

## Research Foundation

- **Large Concept Models** (Meta, Dec 2024) - Validates operating in sentence-embedding space
- **Experimental Results:**
  - Coherence: 0.9929 on real graph paths
  - Grounding correlation: r > 0.8 for PREVENTS relationships
  - Axis magnitude: 0.9-1.1 for strong oppositional pairs

## Related Work

- **ADR-058:** Polarity Axis Triangulation for Grounding - Uses same technique for reliability calculation
- **ADR-044:** Probabilistic Truth Convergence - Grounding strength foundation
- **ADR-045:** Unified Embedding Generation - Provides embeddings for analysis
- **ADR-068:** Unified Embedding Regeneration - Handles embedding updates

## See Also

- [Implementation Plan](./IMPLEMENTATION_PLAN.md) for detailed technical design
- [Findings](./FINDINGS.md) for experimental validation results
- [ADR-070](../../architecture/ADR-070-polarity-axis-analysis.md) for architectural decision rationale
