# ADR-200 Phase 3a: Annealing Controls Exercise Report

**Date:** 2026-01-30
**Epoch range:** 0 → 13
**Ontologies tested:** distributed-systems, database-architecture, consensus-theory (created and dissolved)

## Setup

Two ontologies created with intentional thematic overlap:

- **distributed-systems** — consensus protocols, fault tolerance, distributed storage, eventual consistency, service discovery, network partitions, plus ADRs (072, 014, 200)
- **database-architecture** — storage engines, query optimization, replication/transactions, indexing, vacuum/bloat, distributed databases, plus ADRs (016, 024, 040)

Bridging concepts expected: replication, consistency, WAL, LSM-trees, CockroachDB, Raft consensus.

## Operations Log (Chronological)

1. Created ontologies: `distributed-systems`, `database-architecture` via `kg ontology create`
2. Ingested 3 seed documents into each ontology (consensus protocols, fault tolerance, distributed storage / storage engines, query optimization, replication) via MCP `ingest` tool with `action="text"` (MCP file allowlist not yet configured)
3. Scored both ontologies → **Round 1 at epoch 0** (3 docs each, ~21 concepts each)
4. Ingested 4 more documents into distributed-systems (eventual consistency, service discovery, network partitions, vector clocks) and 3 into database-architecture (indexing, vacuum/bloat, distributed databases)
5. Scored both → **Round 2 at epoch 7** (7/6 docs, ~44/40 concepts)
6. Discovered epoch counter bug: `document_ingestion_counter` never incremented by ingestion worker. Fixed by adding `increment_counter('document_ingestion_counter')` call at job completion in `ingestion_worker.py`
7. Ingested 3 ADR documents into each ontology (ADR-072, ADR-014, ADR-200 into distributed-systems; ADR-016, ADR-024, ADR-040 into database-architecture) — again via `action="text"` workaround
8. Scored both → **Round 3 at epoch 13** (10/9 docs, ~64/63 concepts)
9. Configured MCP file allowlist: `kg mcp-config init-allowlist` + `kg mcp-config allow-dir` for project directory
10. **Reassign:** moved 3 ADR sources (ADR-072, ADR-014, ADR-200) from distributed-systems → database-architecture. Required raw SQL to discover source IDs (gap #245). Re-scored both.
11. **Split:** created `consensus-theory` ontology, reassigned 2 consensus-related sources from distributed-systems. Scored the new ontology.
12. **Dissolve:** dissolved `consensus-theory` back into distributed-systems. Verified scores returned to pre-split values.
13. Checked cross-ontology affinity at each round (3 → 4 → 5 shared concepts)

## Scoring Progression

### distributed-systems

| Metric | Round 1 (ep 0, 3 docs) | Round 2 (ep 7, 7 docs) | Round 3 (ep 13, 10 docs) | Post-reassign (ep 13, 7 docs) |
|--------|------------------------|------------------------|--------------------------|-------------------------------|
| Concepts | 21 | 44 | 64 | 44 |
| Mass | 0.322 | 0.501 | 0.583 | 0.501 |
| Coherence | 0.604 | 0.590 | 0.565 | 0.590 |
| Exposure | 0.000 | 0.123 | 0.206 | 0.206 |
| Protection | 0.228 | 0.231 | 0.208 | 0.179 |

### database-architecture

| Metric | Round 1 (ep 0, 3 docs) | Round 2 (ep 7, 6 docs) | Round 3 (ep 13, 9 docs) | Post-reassign (ep 13, 12 docs) |
|--------|------------------------|------------------------|--------------------------|--------------------------------|
| Concepts | 21 | 40 | 63 | 63+ |
| Mass | 0.327 | 0.495 | 0.611 | 0.662 |
| Coherence | 0.602 | 0.588 | 0.577 | 0.564 |
| Exposure | 0.000 | 0.123 | 0.206 | 0.206 |
| Protection | 0.229 | 0.226 | 0.227 | 0.248 |

## Observations

### Mass (Michaelis-Menten saturation)

Working as designed. Mass climbs steeply in the early phase (0.32 → 0.50 on doubling content), then begins to saturate (0.50 → 0.58 on another ~50% increase). The curve flattens as ontologies grow, which is the intended behavior — raw size matters less as substance accumulates.

### Coherence (mean pairwise cosine similarity)

Gradual decline with growth: 0.604 → 0.590 → 0.565. This correctly reflects that broader topic coverage dilutes semantic focus. An ontology covering "consensus protocols" alone is tighter than one also covering "network partitions" and "service discovery." The decline is gentle, not catastrophic — the topics are related enough to maintain reasonable coherence.

Notably, the small consensus-theory ontology (2 sources, split off then dissolved) scored 0.663 coherence — the highest observed. Small + focused = high coherence. This is the signal a annealing worker would use to identify "nuclei" vs "crossroads."

### Exposure (epoch-based pressure)

Appeared once the epoch counter started incrementing (fixed during this session — ingestion worker wasn't calling `increment_counter`). At epoch 13, both ontologies show ~0.21 raw exposure. With a half-life of 50 epochs, this is still in the gentle ramp-up phase. The formula is working but needs more epoch depth to see meaningful pressure differentiation.

### Protection (composite score)

Protection stayed relatively flat across all rounds (0.228 → 0.231 → 0.208 → 0.179 for distributed-systems). Mass gains are being offset by exposure pressure. This is arithmetically correct per the formula, but raises a question: should young ontologies with rapidly growing mass feel this much exposure pressure?

At epoch 13 with mass 0.50, a protection score of 0.18 feels low. The ontology is healthy and growing. A possible tuning: reduce exposure weight for ontologies below a mass threshold, or adjust the sigmoid steepness in the protection formula so that mass gains have more impact in the 0.3–0.6 range.

Not actionable yet — we need to see how the curve behaves at epoch 50+ with mature ontologies. Logging this observation for Phase 3b tuning.

### Cross-Ontology Affinity

Affinity tracked shared concepts accurately:

| Round | Shared Concepts | Total | Affinity % |
|-------|----------------|-------|-----------|
| Round 1 | 3 | 23 | 13.0% |
| Round 2 | 4 | 44 | 9.1% |
| Round 3 | 5 | 64 | 7.8% |

Absolute overlap grew (3 → 5 shared concepts), but proportional affinity declined as ontologies accumulated more distinct content. This is the expected behavior — casual overlap becomes proportionally smaller relative to domain-specific content.

The AnnealingTest ontologies from earlier testing also appeared at 1.6% affinity after ADR-200 was ingested — the annealing ontologies ADR created a tiny bridge.

## Operations Exercised

### Reassign (sources between ontologies)

Moved 3 ADR sources from distributed-systems to database-architecture. Results:

- **Donor** (distributed-systems): mass dropped 0.583 → 0.501, coherence rose 0.565 → 0.590
- **Recipient** (database-architecture): mass rose 0.611 → 0.662, coherence dropped 0.577 → 0.564

Mass follows source count. Coherence inversely reflects breadth — losing broad content tightens focus, gaining it dilutes. Both responses are correct and expected.

### Split (create + reassign)

Created `consensus-theory`, moved 2 consensus-related sources into it:

- **consensus-theory**: mass 0.225, coherence 0.663, protection 0.188
- Highest coherence observed — small + focused ontologies are semantically tight

This is exactly the signal Phase 3b's annealing worker would look for: high coherence suggests a natural cluster, but low mass and protection make it a demotion candidate unless it grows.

### Dissolve (non-destructive absorption)

Dissolved consensus-theory back into distributed-systems. Scores returned to pre-split values exactly. The round-trip is clean — no data lost, no score artifacts.

## Bugs Found and Fixed

1. **Epoch counter not incrementing** — `document_ingestion_counter` in `graph_metrics` was never incremented by the ingestion worker. Added `increment_counter('document_ingestion_counter')` call at job completion. Fixed in this session.

2. **MCP file allowlist not configured** — MCP ingest with `action="file"` failed silently because `~/.config/kg/mcp-allowed-paths.json` didn't exist. Fixed by running `kg mcp-config init-allowlist` and `kg mcp-config allow-dir`.

## Gaps Identified

1. **Source ID discoverability** ([#245](https://github.com/aaronsb/knowledge-graph-system/issues/245)) — The files endpoint, documents endpoint, and CLI don't expose source IDs needed for reassignment. Had to use raw SQL to find them. The reassign workflow needs a self-contained path from "show me what's in this ontology" to "here are the IDs to move."

2. **Epoch tagging on concepts** — Concepts don't carry a `created_at_epoch` property. This would provide a causal timeline of graph growth and enable questions like "what appeared after epoch N?" and "is this ontology's concept-per-epoch ratio declining?" The data for a derived ratio already exists (`concept_creation_counter / document_ingestion_counter`), but per-concept tagging would be more granular.

3. **Protection sensitivity** — Protection stays flat as mass grows because exposure pressure offsets gains. Needs observation at higher epoch depth before tuning.

## Conclusions

The Phase 3a annealing controls work as designed. Scoring responds to real structural changes. Reassignment and dissolution are clean operations with predictable score impacts. The tools are ready for Phase 3b automation — the manual controls prove the primitives are sound.

Key validation: the system correctly distinguishes focused clusters (high coherence, low mass) from broad collections (lower coherence, high mass). This is the foundation for automated promotion/demotion decisions.
