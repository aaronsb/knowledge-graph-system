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
| [ADR-001](access-workflow/ADR-001-multi-tier-agent-access.md) | Multi-Tier Agent Access Model | Proposed | Tiered access control via Neo4j roles (reader, contributor, librarian, curator) with database-level security enforcement |
| [ADR-002](access-workflow/ADR-002-node-fitness-scoring.md) | Node Fitness Scoring System | Proposed | Automatic fitness scoring based on query patterns with curator override, enabling evolutionary knowledge promotion |
| [ADR-003](access-workflow/ADR-003-semantic-tool-hints.md) | Semantic Tool Hint Networks | Proposed | "Text adventure" style workflow hints in MCP server that guide without enforcing, allowing informed agent overrides |
| [ADR-004](access-workflow/ADR-004-pure-graph-design.md) | Pure Graph Design (Library Metaphor) | Proposed | Graph stores only knowledge, not business logic - access control and workflow live in application layer |
| [ADR-005](access-workflow/ADR-005-source-text-tracking.md) | Source Text Tracking and Retrieval | Proposed | Markdown as canonical format with graph storing references, not full text - flexible retrieval modes |
| [ADR-006](access-workflow/ADR-006-staging-migration-workflows.md) | Staging and Migration Workflows | Proposed | Separate Neo4j databases for staging/production/archive with selective promotion and rollback capability |
| [ADR-007](#adr-007-edge-fitness-scoring-future) | Edge Fitness Scoring | Future | Track relationship traversal usefulness for query optimization |
| [ADR-008](#adr-008-multi-agent-coordination-future) | Multi-Agent Coordination | Future | Event streaming and conflict resolution for concurrent agent edits |
| [ADR-009](#adr-009-cross-graph-querying-future) | Cross-Graph Querying | Future | Federated queries and virtual graph views across staging/production/archive |
| [ADR-010](#adr-010-llm-assisted-curation-future) | LLM-Assisted Curation | Future | AI-powered merge suggestions, summaries, and semantic consistency checking |
| [ADR-011](user-interfaces/ADR-011-cli-admin-separation.md) | CLI and Admin Tooling Separation | Accepted | Restructure into shared libraries, CLI tools (query), and admin tools (database ops) |
| [ADR-012](infrastructure/ADR-012-api-server-architecture.md) | API Server Architecture | Accepted | FastAPI intermediary layer for scalable Neo4j access with job queue and deduplication |
| [ADR-013](user-interfaces/ADR-013-unified-typescript-client.md) | Unified TypeScript Client | Accepted | Single TypeScript client serves as both CLI and MCP server with shared codebase |
| [ADR-014](ingestion-content/ADR-014-job-approval-workflow.md) | Job Approval Workflow | Accepted | Pre-ingestion analysis with cost/time estimates requiring user approval before processing |
| [ADR-015](infrastructure/ADR-015-backup-restore-streaming.md) | Backup/Restore Streaming | Accepted | Streaming backup and restore for large graph databases |
| [ADR-016](database-schema/ADR-016-apache-age-migration.md) | Apache AGE Migration | Accepted | Migration from Neo4j to Apache AGE (PostgreSQL graph extension) for open-source licensing |
| [ADR-017](authentication-security/ADR-017-sensitive-auth-verification.md) | Client-Initiated Token Revocation | Proposed | Time-bound elevated tokens with client-initiated revocation for destructive operations |
| [ADR-018](infrastructure/ADR-018-server-sent-events-streaming.md) | Server-Sent Events Streaming | Proposed | Real-time progress streaming via SSE for job status and future real-time features |
| [ADR-019](user-interfaces/ADR-019-type-based-table-formatting.md) | Type-Based Table Formatting | Accepted | Semantic column types with centralized formatting for CLI table output |
| [ADR-020](infrastructure/ADR-020-admin-module-architecture.md) | Admin Module Architecture | Accepted | Modular Python admin operations replacing shell scripts |
| [ADR-021](infrastructure/ADR-021-live-man-switch-ai-safety.md) | Live Man Switch - AI Safety | Accepted | Physical confirmation (hold Enter) to prevent accidental AI execution of destructive operations |
| [ADR-022](vocabulary-relationships/ADR-022-semantic-relationship-taxonomy.md) | 30-Type Relationship Taxonomy | Accepted | Semantically sparse 30-type vocabulary with Porter stemmer-enhanced fuzzy matching |
| [ADR-023](ingestion-content/ADR-023-markdown-structured-content-preprocessing.md) | Markdown Content Preprocessing | Proposed | AI translation of code blocks to prose before concept extraction |
| [ADR-024](database-schema/ADR-024-multi-schema-postgresql-architecture.md) | Multi-Schema PostgreSQL | Proposed | Four-schema organization (ag_catalog, kg_api, kg_auth, kg_logs) for separation of concerns |
| [ADR-025](vocabulary-relationships/ADR-025-dynamic-relationship-vocabulary.md) | Dynamic Relationship Vocabulary | Proposed | Curator-driven vocabulary expansion with skipped relationships tracking |
| [ADR-026](vocabulary-relationships/ADR-026-autonomous-vocabulary-curation.md) | Autonomous Vocabulary Curation | Proposed | LLM-assisted vocabulary management with ontology versioning and analytics |
| [ADR-027](authentication-security/ADR-027-user-management-api.md) | User Management API | Superseded by ADR-054 | Lightweight JWT authentication with bcrypt password hashing and API keys - replaced by OAuth 2.0 |
| [ADR-028](authentication-security/ADR-028-dynamic-rbac-system.md) | Dynamic RBAC System | Proposed | Three-tier RBAC with dynamic resource registration and scoped permissions |
| [ADR-029](user-interfaces/ADR-029-cli-theory-of-operation.md) | CLI Theory of Operation | Proposed | Hybrid Unix/domain-specific design with verb shortcuts and universal JSON mode |
| [ADR-030](query-search/ADR-030-concept-deduplication-validation.md) | Concept Deduplication Validation | Accepted | Quality test suite for embedding-based concept matching |
| [ADR-031](authentication-security/ADR-031-encrypted-api-key-storage.md) | Encrypted API Key Storage | Accepted | Fernet encryption with container secrets and service token authorization |
| [ADR-032a](vocabulary-relationships/ADR-032a-automatic-edge-vocabulary-expansion.md) | Automatic Edge Vocabulary Expansion | Proposed | Auto-expand vocabulary on first use with intelligent pruning (naive/HITL/AITL modes) and sliding window (30-90 types) |
| [ADR-033](ingestion-content/ADR-033-multimodal-ingestion-configurable-prompts.md) | Multimodal Image Ingestion with Configurable Prompts | Proposed | Vision AI describes images for concept extraction; database-stored prompts enable domain-specific extraction profiles |
| [ADR-034](user-interfaces/ADR-034-graph-visualization-query-workbench.md) | Graph Visualization & Interactive Query Explorers | Proposed | React + TypeScript web application with modular explorer plugins (Force-Directed, Hierarchical, Sankey, Matrix, Timeline, Density) for interactive graph exploration |
| [ADR-035](user-interfaces/ADR-035-explorer-methods-uses-capabilities.md) | Explorer Methods, Uses, and Capabilities | Proposed | Comprehensive documentation of 6 explorer types, 5 query workbenches, and 7 navigation enhancements including "You Are Here" persistent highlighting |
| [ADR-036](user-interfaces/ADR-036-universal-visual-query-builder.md) | Universal Visual Query Builder | Proposed | Tri-mode query system (Smart Search, Visual Blocks, openCypher) that teaches Apache AGE syntax through "Rosetta Stone" learning pattern - blocks generate code users can view and learn from |
| [ADR-037](ingestion-content/ADR-037-human-guided-graph-editing.md) | Human-Guided Graph Editing | Proposed | Human-in-the-loop system for connecting disconnected concepts and invalidating incorrect relationships - treats human justifications as first-class evidence fed through ingestion pipeline |
| [ADR-038](access-workflow/ADR-038-official-project-apparel.md) | Official Project Apparel Design Specifications | Proposed | Commemorative merchandise celebrating streaming entity resolution with O(n) full-scan cosine similarity - a genuinely unusual architectural choice backed by comprehensive scaling research |
| [ADR-039](ai-embeddings/ADR-039-local-embedding-service.md) | Local Embedding Service with Hybrid Client/Server Architecture | Proposed | Replace OpenAI embeddings with local models (nomic-embed-text, BGE) via single model-aware API endpoint; optional browser-side quantized search with two-pass reranking |
| [ADR-040](database-schema/ADR-040-database-schema-migrations.md) | Database Schema Migration Management | Proposed | Simple bash-based migration system with schema_migrations tracking table and numbered migration files for safe schema evolution |
| [ADR-041](ai-embeddings/ADR-041-ai-extraction-config.md) | AI Extraction Provider Configuration | Proposed | Database-first configuration for LLM provider/model selection with hot-reload capability and unified management interface |
| [ADR-042](ai-embeddings/ADR-042-local-extraction-inference.md) | Local LLM Inference for Concept Extraction | Accepted | Ollama integration for local extraction with GPU acceleration, eliminating cloud API dependency and enabling air-gapped deployment |
| [ADR-043](ai-embeddings/ADR-043-single-node-resource-management.md) | Single-Node Resource Management for Local Inference | Accepted | Dynamic device selection with intelligent CPU fallback for embeddings when VRAM contention detected (~100ms penalty, prevents silent failures) |
| [ADR-044](ai-embeddings/ADR-044-probabilistic-truth-convergence.md) | Probabilistic Truth Convergence | Proposed | Embedding-based grounding strength calculation using semantic similarity to prototypical edge types (SUPPORTS/CONTRADICTS) - no hard-coded polarity, scales with vocabulary expansion. **Requires ADR-045** |
| [ADR-045](ai-embeddings/ADR-045-unified-embedding-generation.md) | Unified Embedding Generation System | Proposed | Centralized EmbeddingWorker for all embedding generation (concepts, vocabulary, cold start, model migration) - enables ADR-044 grounding and supports ADR-032 vocabulary expansion |
| [ADR-046](vocabulary-relationships/ADR-046-grounding-aware-vocabulary-management.md) | Grounding-Aware Vocabulary Management | Proposed | Enhanced VocabularyScorer with grounding contribution metrics; embedding-based synonym detection; dynamic LLM prompt curation (40-50 types instead of 200); sliding window lifecycle management |
| [ADR-047](vocabulary-relationships/ADR-047-probabilistic-vocabulary-categorization.md) | Probabilistic Vocabulary Categorization | Proposed | Embedding-based category assignment for LLM-generated relationship types using semantic similarity to 30 seed types - no manual classification, categories emerge from similarity scores |
| [ADR-048](vocabulary-relationships/ADR-048-vocabulary-metadata-as-graph.md) | Vocabulary Metadata as First-Class Graph | In Progress (Phase 3.1 ✅) | Move vocabulary metadata from SQL tables to Apache AGE graph nodes with namespace safety layer (GraphQueryFacade) - vocabulary becomes part of timeless graph, operations become graph-native traversals |
| [ADR-049](ai-embeddings/ADR-049-rate-limiting-and-concurrency.md) | Rate Limiting and Per-Provider Concurrency | Accepted | Exponential backoff retry (8 attempts) + per-provider semaphores (OpenAI=8, Anthropic=4, Ollama=1) with database-first configuration to eliminate 429 errors across concurrent workers |
| [ADR-050](infrastructure/ADR-050-scheduled-jobs-system.md) | Scheduled Jobs System | Proposed | Simple scheduler loop + launcher pattern extends existing job queue for automated maintenance tasks (category refresh, vocab consolidation) with ownership permissions and polling-based condition checks |
| [ADR-051a](ingestion-content/ADR-051a-graph-document-deduplication.md) | Graph-Based Provenance Tracking | Proposed | DocumentMeta nodes + edge metadata for complete audit trail (enhances ADR-014) - prevents job deletion from breaking deduplication, tracks source provenance (file/stdin/mcp/api) and relationship origin (who/when/how), MCP silent enrichment maintains ADR-044 compliance |
| [ADR-052](vocabulary-relationships/ADR-052-vocabulary-expansion-consolidation-cycle.md) | Vocabulary Expansion-Consolidation Cycle | Accepted | Optimistic vocabulary generation + selective pruning mirrors biological memory consolidation - vocabulary must exist before knowledge can be expressed (general methods > prediction, per Sutton's Bitter Lesson) |
| [ADR-053](vocabulary-relationships/ADR-053-eager-vocabulary-categorization.md) | Eager Vocabulary Categorization | Implemented | Automatically categorize edge types during ingestion using embedding similarity to category seeds (~65-90% confidence) - eliminates manual refresh step, includes similarity analysis tools (similar/opposite/analyze commands) |
| [ADR-054](authentication-security/ADR-054-oauth-client-management.md) | OAuth 2.0 Client Management | Accepted | OAuth 2.0 server with client registration and three grant types: authorization code + PKCE (web), device authorization (CLI), client credentials (MCP) - replaces JWT password flow and API keys for proper multi-client authentication |
| [ADR-055](infrastructure/ADR-055-cdn-serverless-deployment-model.md) | CDN and Serverless Deployment Model | Proposed | Runtime configuration via `/config.json` for CDN-deployed static apps - enables single build deployed to multiple environments with OAuth 2.0 PKCE flow and proper redirect URI validation |
| [ADR-056](infrastructure/ADR-056-timezone-aware-datetime-utilities.md) | Timezone-Aware Datetime Utilities | Accepted | Centralized datetime utilities with strict UTC enforcement - eliminates naive/aware comparison errors via explicit UTC conversions and timezone-aware PostgreSQL queries (13/34 violations fixed, auth/OAuth/jobs complete) |
| [ADR-057a](ingestion-content/ADR-057a-multimodal-image-ingestion.md) | Multimodal Image Ingestion | Proposed | Single unified upsert with visual context injection - images follow "hairpin" through existing text pipeline with ontology-aware visual similarity search, dual embeddings (image + text), MinIO storage, and support for Granite Vision/GPT-4V/Claude backends |
| [ADR-058](ai-embeddings/ADR-058-polarity-axis-triangulation.md) | Polarity Axis Triangulation for Grounding | Accepted | Replaces binary classification with geometric projection onto polarity axis derived from 5 opposing relationship pairs - produces nuanced grounding percentiles (-5%, +4%) instead of extreme values (±100%) by averaging difference vectors and projecting via dot product |
| [ADR-059](vocabulary-relationships/ADR-059-llm-determined-relationship-direction.md) | LLM-Determined Relationship Direction | Proposed | LLM-determined relationship semantics with directional validation - addresses extraction ambiguity through semantic analysis and bidirectional relationship type inference |
| [ADR-060](authentication-security/ADR-060-endpoint-security-architecture.md) | API Endpoint Security Architecture | Proposed | Per-endpoint dependency injection following FastAPI Full-Stack Template pattern - type-annotated dependencies (CurrentUser), superuser checks for admin routes, startup validation, and central security policy document for auditability |
| [ADR-061](database-schema/ADR-061-operator-pattern-lifecycle.md) | Operator Pattern for Platform Lifecycle | Accepted | Single kg-operator CLI managing four-layer architecture (Infrastructure → Schema → Configuration → Application) - eliminates script sprawl, enforces correct bootstrap sequence, enables clean Docker builds with secrets from environment not files |
| [ADR-062](authentication-security/ADR-062-mcp-file-ingestion-security.md) | MCP File Ingestion Security Model | Draft | Path allowlist security for MCP file/directory ingestion - fail-secure validation prevents path traversal, agent-readable (not writable) allowlist enables bulk ingestion from pre-approved locations with auto-naming by directory structure |
| [ADR-063](query-search/ADR-063-semantic-diversity-authenticity-signal.md) | Semantic Diversity as Authenticity Signal | Proposed | Measures semantic diversity of related concepts within N-hop traversal - authentic facts supported by diverse independent domains (37.7% diversity), fabricated claims show homogeneous circular reasoning (23.2% diversity) - complements grounding strength for authenticity assessment |
| [ADR-064](user-interfaces/ADR-064-specialized-truth-convergence-visualizations.md) | Specialized Truth Convergence Visualizations | Proposed | Expands web visualization beyond force graphs with specialized explorers: confidence heatmaps, polarity spectrums, provenance Sankey diagrams, concept lifecycle timelines, semantic diversity sunbursts, and 3D evidence mountains - leverages platform's unique truth convergence, semantic diversity, and provenance capabilities |
| [ADR-065](vocabulary-relationships/ADR-065-vocabulary-based-provenance-relationships.md) | Vocabulary-Based Provenance Relationships | Accepted | Extends vocabulary system to provenance relationships (APPEARS, EVIDENCED_BY, FROM_SOURCE) - treats structural relationships as emergent vocabulary with embeddings and semantic matching, eliminating architectural asymmetry between concept-concept and concept-source relationships |
| [ADR-066](query-search/ADR-066-published-query-endpoints.md) | Published Query Endpoints | Proposed | Saved query flows become REST API endpoints accessible via OAuth client credentials - enables external systems to execute curated queries without user sessions, supports JSON/CSV output formats, machine-to-machine authentication |
| [ADR-067](user-interfaces/ADR-067-web-app-workstation-architecture.md) | Web Application Workstation Architecture | Proposed | Restructure web app from visualization tool to knowledge workstation with sidebar categories: Explorers, Block Editor, Ingest, Jobs, Report, Edit, Admin - unified interface for all platform capabilities |
| [ADR-068](ai-embeddings/ADR-068-source-text-embeddings.md) | Source Text Embeddings for Grounding Truth Retrieval | Proposed | Async embedding generation for Source nodes with configurable chunking strategies (sentence/paragraph/count/semantic) - enables direct source passage search, hybrid concept+source queries, and completes LCM foundation where all graph elements (concepts, edges, sources) have embeddings for multi-modal retrieval |
| [ADR-069](user-interfaces/ADR-069-semantic-fuse-filesystem.md) | Semantic FUSE Filesystem | Proposed | Expose knowledge graph as FUSE mount point enabling semantic navigation via standard Unix tools (ls, cd, cat, grep, find) - partial filesystem (like /sys/) with 4-level hierarchy (shard/facet/ontology/concepts), directory creation as semantic query, relationship navigation via subdirectories, write-as-ingest - implementation via rclone backend recommended for instant interop with cloud storage |
| [ADR-070](ai-embeddings/ADR-070-polarity-axis-analysis.md) | Polarity Axis Analysis for Bidirectional Semantic Dimensions | Accepted | Direct query pattern (~2-3s) enables discovery of conceptual spectrums (Modern ↔ Traditional), semantic positioning of concepts on axes, and grounding correlation validation - uses vector projection onto opposing concept pairs with auto-discovery, API endpoint, CLI command, and MCP tool integration |
| [ADR-071](query-search/ADR-071-parallel-graph-queries.md) | Parallel Graph Query Optimization | Accepted | Application-level parallelization using ThreadPoolExecutor with connection pooling to execute multiple small Cypher queries concurrently instead of one large variable-length path query - achieves 3x speedup (3 min → 83s) primarily from batched queries with IN clauses, not parallelization overhead (ADR-071a findings) |
| [ADR-072](ingestion-content/ADR-072-concept-matching-strategies.md) | Concept Matching Strategies and Configuration | Draft | Database-first configuration for concept similarity matching with pgvector indexing (100x speedup) and three search strategies (exhaustive/degree_biased/degree_only) - applies ADR-071 epsilon-greedy pattern to ingestion, default exhaustive 0.85 threshold unchanged, prepares for evidence-aware matching (ADR-073) |
| [ADR-074](authentication-security/ADR-074-platform-admin-role.md) | Platform Admin Role | Proposed | Three-tier admin structure (user → admin → platform_admin) with 6 new resource types (api_keys, embedding_config, extraction_config, oauth_clients, ontologies, backups) and hardcoded permission bypass for platform_admin role to ensure emergency recovery |
| [ADR-076](ADR-076-pathfinding-optimization.md) | Pathfinding Optimization for Apache AGE | Accepted | Bidirectional BFS in application code replaces exhaustive Cypher path enumeration - O(b^(d/2)) vs O(b^d) complexity. AGE lacks shortestPath() function; variable-length patterns cause exponential blowup. Includes incremental depth search, path caching, and documentation fixes |
| [ADR-077](ADR-077-vocabulary-explorers.md) | Vocabulary Explorers | Proposed | Two visual exploration tools for edge vocabulary: Edge Explorer (system-wide chord/radial/matrix views) and Vocabulary Chord (query-specific analysis from 2D/3D explorer). Shows category flows, type distribution, vocabulary health, builtin vs custom types |
| [ADR-078](visualization/ADR-078-embedding-landscape-explorer.md) | Embedding Landscape Explorer | Proposed | 3D t-SNE/UMAP visualization of concept embeddings with epistemic overlays (grounding color, diversity size) - enables visual axis discovery by clicking two points to define polarity axis, bridging macro exploration with existing micro neighborhood exploration |
| [ADR-079](ADR-079-projection-artifact-storage.md) | Projection Artifact Storage | Accepted | Store t-SNE/UMAP projections in Garage (S3) with changelist-based freshness validation - enables efficient caching, historical playback, and time-series analysis without polluting graph schema. Generalized by ADR-083 |
| [ADR-080](ADR-080-garage-service-architecture.md) | Garage Service Architecture | Proposed | Refactor monolithic GarageClient (732 lines) into focused service modules (base, images, projections) following Single Responsibility Principle - establishes modular architecture for future storage features |
| [ADR-081](ADR-081-source-document-lifecycle.md) | Source Document Lifecycle | Proposed | Pre-ingestion document storage in Garage with content hashing, character offsets in Source nodes, and regeneration capability - enables re-processing with improved extraction while maintaining deduplication |
| [ADR-082](ADR-082-user-scoping-artifact-ownership.md) | User Scoping and Artifact Ownership | Accepted | Groups-based ownership model with Unix-style ID ranges (1-999 system, 1000+ users), `public` meta-group for all authenticated users, and grant-based access control for ontologies and artifacts |
| [ADR-083](ADR-083-artifact-persistence-pattern.md) | Artifact Persistence Pattern | Accepted | Multi-tier storage (DB metadata → Zustand pointers → LocalStorage cache → Garage blobs) for computed artifacts with lazy loading, graph epoch freshness tracking, and async job integration for expensive computations |

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

**Last Updated:** 2025-12-17

**Note:** When creating a new ADR file, remember to add it to this index table with its title, status, and a brief summary.
