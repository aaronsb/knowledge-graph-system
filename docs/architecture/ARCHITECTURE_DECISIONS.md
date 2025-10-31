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
| [ADR-015](ADR-015-backup-restore-streaming.md) | Backup/Restore Streaming | Accepted | Streaming backup and restore for large graph databases |
| [ADR-016](ADR-016-apache-age-migration.md) | Apache AGE Migration | Accepted | Migration from Neo4j to Apache AGE (PostgreSQL graph extension) for open-source licensing |
| [ADR-017](ADR-017-sensitive-auth-verification.md) | Client-Initiated Token Revocation | Proposed | Time-bound elevated tokens with client-initiated revocation for destructive operations |
| [ADR-018](ADR-018-server-sent-events-streaming.md) | Server-Sent Events Streaming | Proposed | Real-time progress streaming via SSE for job status and future real-time features |
| [ADR-019](ADR-019-type-based-table-formatting.md) | Type-Based Table Formatting | Accepted | Semantic column types with centralized formatting for CLI table output |
| [ADR-020](ADR-020-admin-module-architecture.md) | Admin Module Architecture | Accepted | Modular Python admin operations replacing shell scripts |
| [ADR-021](ADR-021-live-man-switch-ai-safety.md) | Live Man Switch - AI Safety | Accepted | Physical confirmation (hold Enter) to prevent accidental AI execution of destructive operations |
| [ADR-022](ADR-022-semantic-relationship-taxonomy.md) | 30-Type Relationship Taxonomy | Accepted | Semantically sparse 30-type vocabulary with Porter stemmer-enhanced fuzzy matching |
| [ADR-023](ADR-023-markdown-structured-content-preprocessing.md) | Markdown Content Preprocessing | Proposed | AI translation of code blocks to prose before concept extraction |
| [ADR-024](ADR-024-multi-schema-postgresql-architecture.md) | Multi-Schema PostgreSQL | Proposed | Four-schema organization (ag_catalog, kg_api, kg_auth, kg_logs) for separation of concerns |
| [ADR-025](ADR-025-dynamic-relationship-vocabulary.md) | Dynamic Relationship Vocabulary | Proposed | Curator-driven vocabulary expansion with skipped relationships tracking |
| [ADR-026](ADR-026-autonomous-vocabulary-curation.md) | Autonomous Vocabulary Curation | Proposed | LLM-assisted vocabulary management with ontology versioning and analytics |
| [ADR-027](ADR-027-user-management-api.md) | User Management API | Accepted | Lightweight JWT authentication with bcrypt password hashing and API keys |
| [ADR-028](ADR-028-dynamic-rbac-system.md) | Dynamic RBAC System | Proposed | Three-tier RBAC with dynamic resource registration and scoped permissions |
| [ADR-029](ADR-029-cli-theory-of-operation.md) | CLI Theory of Operation | Proposed | Hybrid Unix/domain-specific design with verb shortcuts and universal JSON mode |
| [ADR-030](ADR-030-concept-deduplication-validation.md) | Concept Deduplication Validation | Accepted | Quality test suite for embedding-based concept matching |
| [ADR-031](ADR-031-encrypted-api-key-storage.md) | Encrypted API Key Storage | Accepted | Fernet encryption with container secrets and service token authorization |
| [ADR-032](ADR-032-automatic-edge-vocabulary-expansion.md) | Automatic Edge Vocabulary Expansion | Proposed | Auto-expand vocabulary on first use with intelligent pruning (naive/HITL/AITL modes) and sliding window (30-90 types) |
| [ADR-033](ADR-033-multimodal-ingestion-configurable-prompts.md) | Multimodal Image Ingestion with Configurable Prompts | Proposed | Vision AI describes images for concept extraction; database-stored prompts enable domain-specific extraction profiles |
| [ADR-034](ADR-034-graph-visualization-query-workbench.md) | Graph Visualization & Interactive Query Explorers | Proposed | React + TypeScript web application with modular explorer plugins (Force-Directed, Hierarchical, Sankey, Matrix, Timeline, Density) for interactive graph exploration |
| [ADR-035](ADR-035-explorer-methods-uses-capabilities.md) | Explorer Methods, Uses, and Capabilities | Proposed | Comprehensive documentation of 6 explorer types, 5 query workbenches, and 7 navigation enhancements including "You Are Here" persistent highlighting |
| [ADR-036](ADR-036-universal-visual-query-builder.md) | Universal Visual Query Builder | Proposed | Tri-mode query system (Smart Search, Visual Blocks, openCypher) that teaches Apache AGE syntax through "Rosetta Stone" learning pattern - blocks generate code users can view and learn from |
| [ADR-037](ADR-037-human-guided-graph-editing.md) | Human-Guided Graph Editing | Proposed | Human-in-the-loop system for connecting disconnected concepts and invalidating incorrect relationships - treats human justifications as first-class evidence fed through ingestion pipeline |
| [ADR-038](ADR-038-official-project-apparel.md) | Official Project Apparel Design Specifications | Proposed | Commemorative merchandise celebrating streaming entity resolution with O(n) full-scan cosine similarity - a genuinely unusual architectural choice backed by comprehensive scaling research |
| [ADR-039](ADR-039-local-embedding-service.md) | Local Embedding Service with Hybrid Client/Server Architecture | Proposed | Replace OpenAI embeddings with local models (nomic-embed-text, BGE) via single model-aware API endpoint; optional browser-side quantized search with two-pass reranking |
| [ADR-040](ADR-040-database-schema-migrations.md) | Database Schema Migration Management | Proposed | Simple bash-based migration system with schema_migrations tracking table and numbered migration files for safe schema evolution |
| [ADR-041](ADR-041-ai-extraction-config.md) | AI Extraction Provider Configuration | Proposed | Database-first configuration for LLM provider/model selection with hot-reload capability and unified management interface |
| [ADR-042](ADR-042-local-extraction-inference.md) | Local LLM Inference for Concept Extraction | Accepted | Ollama integration for local extraction with GPU acceleration, eliminating cloud API dependency and enabling air-gapped deployment |
| [ADR-043](ADR-043-single-node-resource-management.md) | Single-Node Resource Management for Local Inference | Accepted | Dynamic device selection with intelligent CPU fallback for embeddings when VRAM contention detected (~100ms penalty, prevents silent failures) |
| [ADR-044](ADR-044-probabilistic-truth-convergence.md) | Probabilistic Truth Convergence | Proposed | Embedding-based grounding strength calculation using semantic similarity to prototypical edge types (SUPPORTS/CONTRADICTS) - no hard-coded polarity, scales with vocabulary expansion. **Requires ADR-045** |
| [ADR-045](ADR-045-unified-embedding-generation.md) | Unified Embedding Generation System | Proposed | Centralized EmbeddingWorker for all embedding generation (concepts, vocabulary, cold start, model migration) - enables ADR-044 grounding and supports ADR-032 vocabulary expansion |
| [ADR-046](ADR-046-grounding-aware-vocabulary-management.md) | Grounding-Aware Vocabulary Management | Proposed | Enhanced VocabularyScorer with grounding contribution metrics; embedding-based synonym detection; dynamic LLM prompt curation (40-50 types instead of 200); sliding window lifecycle management |
| [ADR-047](ADR-047-probabilistic-vocabulary-categorization.md) | Probabilistic Vocabulary Categorization | Proposed | Embedding-based category assignment for LLM-generated relationship types using semantic similarity to 30 seed types - no manual classification, categories emerge from similarity scores |
| [ADR-048](ADR-048-vocabulary-metadata-as-graph.md) | Vocabulary Metadata as First-Class Graph | In Progress (Phase 3.1 ✅) | Move vocabulary metadata from SQL tables to Apache AGE graph nodes with namespace safety layer (GraphQueryFacade) - vocabulary becomes part of timeless graph, operations become graph-native traversals |
| [ADR-049](ADR-049-rate-limiting-and-concurrency.md) | Rate Limiting and Per-Provider Concurrency | Accepted | Exponential backoff retry (8 attempts) + per-provider semaphores (OpenAI=8, Anthropic=4, Ollama=1) with database-first configuration to eliminate 429 errors across concurrent workers |
| [ADR-050](ADR-050-scheduled-jobs-system.md) | Scheduled Jobs System | Proposed | Simple scheduler loop + launcher pattern extends existing job queue for automated maintenance tasks (category refresh, vocab consolidation) with ownership permissions and polling-based condition checks |
| [ADR-051](ADR-051-graph-document-deduplication.md) | Graph-Based Provenance Tracking | Proposed | DocumentMeta nodes + edge metadata for complete audit trail (enhances ADR-014) - prevents job deletion from breaking deduplication, tracks source provenance (file/stdin/mcp/api) and relationship origin (who/when/how), MCP silent enrichment maintains ADR-044 compliance |
| [ADR-052](ADR-052-vocabulary-expansion-consolidation-cycle.md) | Vocabulary Expansion-Consolidation Cycle | Accepted | Optimistic vocabulary generation + selective pruning mirrors biological memory consolidation - vocabulary must exist before knowledge can be expressed (general methods > prediction, per Sutton's Bitter Lesson) |

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

**Last Updated:** 2025-10-31

**Note:** When creating a new ADR file, remember to add it to this index table with its title, status, and a brief summary.
