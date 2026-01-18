# ADR-076B: Pathfinding Performance Baseline

**Status:** Reference Data
**Date:** 2025-12-10
**Related:** ADR-076 (Pathfinding Optimization)

## Purpose

This document records baseline performance measurements for the current exhaustive pathfinding implementation. These measurements establish the "before" state against which the Bidirectional BFS optimization (ADR-076) will be compared.

## Test Environment

- **Graph Size:** 833 concepts, 4856 relationships
- **Database:** Apache AGE on PostgreSQL 16
- **Hardware:** Development workstation (specifics vary)
- **Date:** December 10, 2025
- **Ontologies:** AI_Semantics, Watts-Zen, Watts-Tao

### Graph Characteristics

| Metric | Value |
|--------|-------|
| Concepts | 833 |
| Relationships | 4,856 |
| Sources | 221 |
| Instances | 1,163 |
| Avg relationships/concept | ~5.8 |

## Baseline Measurements

### Test Case 1: Connected Path (Buddhism → Nirvana)

Query: `kg search connect "buddhism meditation" "nirvana" --min-similarity 0.8`

Semantic matches:
- From: "Meditation in Buddhism" (87.1% match)
- To: "Nirvana" (84.8% match)
- Shortest path exists: 2 hops

| Max Hops | Time (s) | Paths Found | Notes |
|----------|----------|-------------|-------|
| 4 | 1.54 | 5 | Acceptable |
| 5 | 1.86 | 5 | Acceptable |
| 6 | 4.68 | 5 | Noticeable delay |
| 7 | 33.35 | 5 | Significant slowdown |

**Growth pattern:** ~2.5x per hop increase (exponential)

### Test Case 2: Cross-Ontology (Conscious Ego → Illusion of Self)

Query: `kg search connect "conscious ego" "illusion of self" --max-hops 6 --min-similarity 0.75`

Semantic matches:
- From: "Conscious Ego" (matched)
- To: "Illusion of Self" (matched)
- No direct path exists

| Max Hops | Time (s) | Paths Found | Notes |
|----------|----------|-------------|-------|
| 6 | 14.33 | 0 | Full exhaustive search |

**Observation:** Even failed searches take significant time because the algorithm must enumerate all possible paths before determining no connection exists.

### Test Case 3: New Bridge Path (Borrowed Ego → Illusion of Self)

After ingesting reflective content that created an explicit bridge:

Query: Direct concept ID connection test

| Max Hops | Time (s) | Paths Found | Path |
|----------|----------|-------------|------|
| 5 | <2 | 1 | Borrowed Ego → Human ego → Spotlight Consciousness → Illusion of Self |

**Path details:**
```
Borrowed Ego
    ↓ REQUIRES
Human ego
    ↓ DEFINED_AS
Spotlight and Floodlight Consciousness
    ↓ CONTRASTS_WITH
Spotlight Consciousness
    ↓ ENABLES
Illusion of Self
```

## Path Structure Analysis

### Buddhism → Nirvana (5 paths found)

**Path 1 (2 hops):**
```
Meditation in Buddhism → UTILIZES → Zen Buddhism → RESULTS_FROM → Nirvana
```

**Path 2 (3 hops):**
```
Meditation in Buddhism → DEFINED_AS → Meditation in Buddhism → UTILIZES → Zen Buddhism → RESULTS_FROM → Nirvana
```

**Path 3 (3 hops):**
```
Meditation in Buddhism → UTILIZES → Zen Buddhism → SUPPORTS → Middle Way → ENABLES → Nirvana
```

**Path 4 (4 hops):**
```
Meditation in Buddhism → UTILIZES → Zen Buddhism → ASSOCIATED_WITH → Karlfried Graf Dürckheim → PRACTITIONER_OF → Zen Buddhism → RESULTS_FROM → Nirvana
```

**Path 5 (4 hops):**
```
Meditation in Buddhism → UTILIZES → Zen Buddhism → PRACTITIONER_OF → Karlfried Graf Dürckheim → ASSOCIATED_WITH → Zen Buddhism → RESULTS_FROM → Nirvana
```

**Observation:** Paths 4 and 5 are essentially the same path traversed in different directions through the Dürckheim node. The exhaustive search finds both.

## Extrapolated Performance

Based on observed exponential growth (~2.5-7x per hop):

| Max Hops | Estimated Time | Usability |
|----------|----------------|-----------|
| 4 | ~1.5s | Good |
| 5 | ~2s | Good |
| 6 | ~5s | Marginal |
| 7 | ~33s | Poor |
| 8 | ~2-4 min | Unusable |
| 10 | Hours | Timeout |

## Comparison with AGE Issue #195

From GitHub Issue #195 (1.5M nodes, 1.2M edges):

| Max Hops | Issue #195 Time | Our Time |
|----------|-----------------|----------|
| 4 | 7s | 1.5s |
| 5 | 3.5 min | 1.9s |
| 6 | ~7 min | 4.7s |
| 7 | - | 33s |

Our graph is much smaller (~800 vs 1.5M nodes) which explains faster times, but the exponential growth pattern is consistent.

## Conclusions

1. **Exponential degradation confirmed:** Each additional hop multiplies query time by 2.5-7x

2. **Practical limit:** Max 5-6 hops before UX degrades significantly

3. **Failed searches are expensive:** Full exhaustive enumeration even when no path exists

4. **Current implementation scales poorly:** With graph growth to 10K+ concepts, even 4-hop queries will become problematic

5. **Bidirectional BFS justified:** The O(b^d) → O(b^(d/2)) improvement from ADR-076 is necessary for production use

## Post-Optimization Targets

After implementing Bidirectional BFS, target performance:

| Max Hops | Target Time | Improvement |
|----------|-------------|-------------|
| 6 | <1s | 5x |
| 7 | <2s | 15x |
| 10 | <5s | Orders of magnitude |

## Test Commands

To reproduce these measurements:

```bash
# Basic timing test
time kg search connect "buddhism meditation" "nirvana" --max-hops 5 --min-similarity 0.8 --no-evidence

# Full JSON output for analysis
kg search connect "buddhism meditation" "nirvana" --max-hops 5 --min-similarity 0.8 --no-evidence --json | jq '.'

# Cross-ontology test
time kg search connect "conscious ego" "illusion of self" --max-hops 6 --min-similarity 0.75 --no-evidence
```

## References

- ADR-076: Pathfinding Optimization for Apache AGE
- [GitHub Issue #195](https://github.com/apache/age/issues/195) - Variable-length path performance
- Graph state captured during Watts + AI_Semantics ingestion session
