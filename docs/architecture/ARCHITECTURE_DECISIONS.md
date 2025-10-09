# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records (ADRs) for the Knowledge Graph System. Each ADR documents a significant architectural decision, the context that led to it, and the consequences of the decision.

## ADR Format

All ADRs follow a consistent format:
- **Status:** Proposed / Accepted / Deprecated / Superseded
- **Date:** When the decision was made
- **Context:** The problem or situation requiring a decision
- **Decision:** The architectural choice made
- **Consequences:** Benefits (positive), drawbacks (negative), and other impacts (neutral)
- **Alternatives Considered:** Other options evaluated
- **Related ADRs:** Links to related decisions

## ADR Index

| ADR | Title | Status | Summary |
|-----|-------|--------|---------|
| [ADR-001](ADR-001-multi-tier-agent-access.md) | Multi-Tier Agent Access Model | Proposed | Tiered access control via Neo4j roles (reader, contributor, librarian, curator) with database-level security enforcement |
| [ADR-002](ADR-002-node-fitness-scoring.md) | Node Fitness Scoring System | Proposed | Automatic fitness scoring based on query patterns with curator override, enabling evolutionary knowledge promotion |
| [ADR-003](ADR-003-semantic-tool-hints.md) | Semantic Tool Hint Networks | Proposed | "Text adventure" style workflow hints in MCP server that guide without enforcing, allowing informed agent overrides |
| [ADR-004](ADR-004-pure-graph-design.md) | Pure Graph Design (Library Metaphor) | Proposed | Graph stores only knowledge, not business logic - access control and workflow live in application layer |
| [ADR-005](ADR-005-source-text-tracking.md) | Source Text Tracking and Retrieval | Proposed | Markdown as canonical format with graph storing references, not full text - flexible retrieval modes |
| [ADR-006](ADR-006-staging-migration-workflows.md) | Staging and Migration Workflows | Proposed | Separate Neo4j databases for staging/production/archive with selective promotion and rollback capability |
| [ADR-007](#adr-007-edge-fitness-scoring-future) | Edge Fitness Scoring | Future | Track relationship traversal usefulness for query optimization |
| [ADR-008](#adr-008-multi-agent-coordination-future) | Multi-Agent Coordination | Future | Event streaming and conflict resolution for concurrent agent edits |
| [ADR-009](#adr-009-cross-graph-querying-future) | Cross-Graph Querying | Future | Federated queries and virtual graph views across staging/production/archive |
| [ADR-010](#adr-010-llm-assisted-curation-future) | LLM-Assisted Curation | Future | AI-powered merge suggestions, summaries, and semantic consistency checking |
| [ADR-011](ADR-011-cli-admin-separation.md) | CLI and Admin Tooling Separation | Accepted | Restructure into shared libraries, CLI tools (query), and admin tools (database ops) |
| [ADR-012](ADR-012-api-server-architecture.md) | API Server Architecture | Accepted | FastAPI intermediary layer for scalable Neo4j access with job queue and deduplication |
| [ADR-013](ADR-013-unified-typescript-client.md) | Unified TypeScript Client | Accepted | Single TypeScript client serves as both CLI and MCP server with shared codebase |
| [ADR-014](ADR-014-job-approval-workflow.md) | Job Approval Workflow | Accepted | Pre-ingestion analysis with cost/time estimates requiring user approval before processing |
| [ADR-015](ADR-015-smart-chunking-strategy.md) | Smart Chunking Strategy | Accepted | Semantic boundary detection for optimal chunk sizes, preserving context integrity |
| [ADR-016](ADR-016-apache-age-migration.md) | Apache AGE Migration | Accepted | Migration from Neo4j to Apache AGE (PostgreSQL graph extension) for open-source licensing |

## How to Use This Index

- **Implemented decisions** (Status: Accepted) reflect the current system architecture
- **Proposed decisions** represent planned architectural directions
- **Future considerations** are placeholders for potential enhancements

When making architectural changes, update or create ADRs following the established format. Link related ADRs to maintain decision traceability.

---

## Future Considerations

### ADR-007: Edge Fitness Scoring (Future)

Track which relationship types are most useful for traversal:

```cypher
(:Concept)-[:IMPLIES {
  traversal_count: 423,
  useful_count: 387,      // Led to relevant results
  fitness: 0.915          // useful_count / traversal_count
}]->(:Concept)
```

**Rationale:** Enables query optimization by preferring relationship types that historically lead to useful results.

---

### ADR-008: Multi-Agent Coordination (Future)

Proposed capabilities:
- Event streaming for graph changes
- Agent-to-agent communication via graph annotations
- Conflict resolution strategies for concurrent edits
- Optimistic locking for critical operations

**Rationale:** Enable multiple agents to collaborate effectively without stepping on each other's work.

---

### ADR-009: Cross-Graph Querying (Future)

Proposed capabilities:
- Federated queries across staging/production/archive
- Virtual graph views (merge multiple graphs at query time)
- Transparent graph routing based on query patterns

**Rationale:** Allow querying across environments without manual migration, useful for comparisons and validation.

---

### ADR-010: LLM-Assisted Curation (Future)

Proposed capabilities:
- LLM-powered merge suggestions based on semantic similarity
- Auto-generate concept descriptions from evidence instances
- Semantic consistency checking across relationship networks
- Quality assessment with natural language explanations

**Rationale:** Leverage LLMs not just for extraction, but for ongoing graph maintenance and quality improvement.

---

## ADR Lifecycle

1. **Proposed:** Initial draft of architectural decision
2. **Accepted:** Decision implemented in codebase
3. **Deprecated:** Decision replaced but code may still exist
4. **Superseded:** Decision replaced by specific ADR (noted in "Related" section)

---

**Last Updated:** 2025-10-08
