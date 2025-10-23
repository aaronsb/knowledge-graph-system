# Documentation Reorganization - Content Mapping

This document maps existing documentation files to the new book structure defined in `BOOK_STRUCTURE.md`.

**Status Legend:**
- ✅ **PORT** - Content exists, needs minor edits for flow
- 🔄 **CONSOLIDATE** - Multiple files need merging
- ✏️ **UPDATE** - Content needs significant updates (Neo4j→AGE, status fixes)
- 📝 **CREATE** - New content needs to be written
- 🗂️ **EXTRACT** - Content exists in code/ADRs, needs extraction

---

## Part I: Foundations (01-09)

### 01 - What Is a Knowledge Graph? ✅ PORT
**Source Files:**
- `reference/CONCEPT.md` (164 lines) - "Why Knowledge Graphs, Not Just RAG?"
- `reference/CONCEPTS_AND_TERMINOLOGY.md` (543 lines) - First 200 lines (intro + core concepts)

**Actions:**
- Merge CONCEPT.md into opening narrative
- Extract conceptual definitions from CONCEPTS_AND_TERMINOLOGY.md
- Add simple examples contrasting linear vs. graph thinking
- ~400 lines total

---

### 02 - System Overview ✏️ UPDATE
**Source Files:**
- `architecture/ARCHITECTURE_OVERVIEW.md` (361 lines)

**Actions:**
- ⚠️ **CRITICAL**: Update all Neo4j references → Apache AGE
- Update diagrams to show PostgreSQL + AGE instead of Neo4j
- Add component diagram showing FastAPI + TypeScript client + PostgreSQL
- Verify architecture matches current implementation (ADR-016)
- ~400 lines total

---

### 03 - Quick Start: Your First Knowledge Graph ✅ PORT
**Source Files:**
- `guides/QUICKSTART.md` (255 lines)

**Actions:**
- Light editing for flow
- Ensure reflects current setup (Ollama optional, not required)
- Add "What you just did" explanation section
- ~300 lines total

---

### 04 - Understanding Concepts and Relationships 🔄 CONSOLIDATE
**Source Files:**
- `guides/SCHEMA_REFERENCE.md` (423 lines)
- `architecture/ADR-022-semantic-relationship-taxonomy.md` (349 lines) - 30-type overview
- `reference/CONCEPTS_AND_TERMINOLOGY.md` (543 lines) - Data model sections

**Actions:**
- Start with SCHEMA_REFERENCE.md as base
- Integrate 30-type relationship taxonomy from ADR-022 (simplified for users)
- Add visual diagrams of graph structure
- Extract terminology from CONCEPTS_AND_TERMINOLOGY.md
- ~500 lines total

---

### 05 - The Extraction Process 🔄 CONSOLIDATE + ✏️ UPDATE
**Source Files:**
- `architecture/RECURSIVE_UPSERT_ARCHITECTURE.md` (3,189 lines) - **Needs simplification!**
- `architecture/ADR-014-job-approval-workflow.md` (689 lines) - Job lifecycle
- `development/DEV_JOURNAL_chunked_ingestion.md` (548 lines) - Chunking details

**Actions:**
- ⚠️ **CHALLENGE**: Simplify RECURSIVE_UPSERT_ARCHITECTURE.md to ~600 lines
- Focus on conceptual flow, not implementation details
- Use ADR-014 to explain job workflow (estimate → approve → ingest)
- Incorporate chunking explanation from DEV_JOURNAL
- Save full technical details for Section 32 (developer deep dive)
- ~700 lines total (user-friendly version)

---

### 06 - Querying Your Knowledge Graph 🔄 CONSOLIDATE
**Source Files:**
- `guides/CLI_USAGE.md` (911 lines) - Extract query commands only
- `api/OPENCYPHER_QUERIES.md` (754 lines) - Extract basic patterns only

**Actions:**
- Focus on common CLI commands: `kg search query`, `kg search details`, `kg search related`, `kg search connect`
- Simple openCypher examples (defer advanced to Section 14)
- Real query outputs from EXAMPLES.md
- ~500 lines total

---

### 07 - Real World Example: Project History Analysis ✅ PORT
**Source Files:**
- `guides/use_cases/github_project_history.md` (514 lines)
- `guides/EXAMPLES.md` (308 lines) - Selected examples

**Actions:**
- Start with github_project_history.md as narrative
- Integrate relevant examples from EXAMPLES.md
- Show actual queries and outputs
- ~600 lines total

---

### 08 - Choosing Your AI Provider 🔄 CONSOLIDATE
**Source Files:**
- `guides/AI_PROVIDERS.md` (308 lines)
- `guides/EXTRACTION_QUALITY_COMPARISON.md` (859 lines)
- `guides/SWITCHING_EXTRACTION_PROVIDERS.md` (492 lines)

**Actions:**
- Start with AI_PROVIDERS.md overview
- Integrate quality comparison matrix from EXTRACTION_QUALITY_COMPARISON.md
- Add decision tree: "Which provider should I use?"
- Include quick switching guide from SWITCHING_EXTRACTION_PROVIDERS.md
- ~800 lines total

---

### 09 - Common Workflows and Use Cases ✅ PORT
**Source Files:**
- `guides/USE_CASES.md` (194 lines)
- `guides/INGESTION.md` (489 lines)
- `guides/EXAMPLES.md` (308 lines) - Remaining examples

**Actions:**
- Merge USE_CASES.md + INGESTION.md into workflow patterns
- Organize by scenario: research, documentation, lecture notes, code analysis
- Include step-by-step examples
- ~700 lines total

---

## Part II: Configuration & Customization (10-19)

### 10 - AI Extraction Configuration 🔄 CONSOLIDATE + ✏️ UPDATE
**Source Files:**
- `guides/EXTRACTION_CONFIGURATION.md` (767 lines)
- `architecture/ADR-041-ai-extraction-config.md` (1,381 lines) - Database config system

**Actions:**
- Start with EXTRACTION_CONFIGURATION.md for operators
- ⚠️ **STATUS FIX**: Verify ADR-041 implementation status (Proposed but appears partially done)
- Add provider/model selection guide
- Include configuration examples for OpenAI, Anthropic, Ollama
- ~800 lines total

---

### 11 - Embedding Models and Vector Search 🔄 CONSOLIDATE + ✏️ UPDATE
**Source Files:**
- `guides/EMBEDDING_CONFIGURATION.md` (595 lines)
- `architecture/ADR-039-local-embedding-service.md` (900 lines)

**Actions:**
- Start with EMBEDDING_CONFIGURATION.md
- ⚠️ **STATUS FIX**: Verify ADR-039 implementation status (Proposed but seems partially implemented)
- Explain OpenAI embeddings vs. local sentence-transformers
- Performance comparison: latency, cost, quality
- ~700 lines total

---

### 12 - Local LLM Inference with Ollama ✅ PORT + ✏️ UPDATE
**Source Files:**
- `guides/LOCAL_INFERENCE_IMPLEMENTATION.md` (969 lines)
- `architecture/ADR-042-local-extraction-inference.md` (916 lines)
- `architecture/ADR-043-single-node-resource-management.md` (383 lines)

**Actions:**
- ✅ These ADRs are **Accepted** and **Implemented** - just port
- Start with LOCAL_INFERENCE_IMPLEMENTATION.md (user guide)
- Reference ADR-042 for architecture
- Integrate ADR-043 VRAM management guidance
- Hardware requirements and recommendations
- ~1,100 lines total (comprehensive guide)

---

### 13 - Managing Relationship Vocabulary 🔄 CONSOLIDATE + ✏️ UPDATE
**Source Files:**
- `guides/VOCABULARY_CONSOLIDATION.md` (853 lines)
- `architecture/ADR-032-automatic-edge-vocabulary-expansion.md` (1,955 lines) - **HUGE**
- `architecture/ADR-032-IMPLEMENTATION-NOTES.md` (301 lines)

**Actions:**
- Start with VOCABULARY_CONSOLIDATION.md for operators
- ⚠️ **STATUS FIX**: Clarify ADR-032 implementation status (Proposed but has IMPLEMENTATION-NOTES)
- Simplify ADR-032 to user-facing guide (save technical for Section 40)
- Practical guide to `kg vocab` commands
- ~700 lines total (defer deep architecture to Part V)

---

### 14 - Advanced Query Patterns ✅ PORT
**Source Files:**
- `api/CYPHER_PATTERNS.md` (438 lines)
- `api/OPENCYPHER_QUERIES.md` (754 lines) - Advanced sections

**Actions:**
- Start with CYPHER_PATTERNS.md
- Integrate advanced patterns from OPENCYPHER_QUERIES.md
- Fuzzy matching, weighted paths, multi-hop traversals
- Regex queries and pattern matching
- ~800 lines total

---

### 15 - Integration with Claude Desktop (MCP) ✅ PORT
**Source Files:**
- `guides/MCP_SETUP.md` (359 lines)
- `architecture/ADR-013-unified-typescript-client.md` (520 lines) - MCP architecture section

**Actions:**
- Start with MCP_SETUP.md
- Add architecture context from ADR-013
- Troubleshooting MCP connections
- Example conversations
- ~500 lines total

---

## Part III: System Administration (20-29)

### 20 - User Management and Authentication 🔄 CONSOLIDATE
**Source Files:**
- `guides/AUTHENTICATION.md` (608 lines)
- `architecture/ADR-027-user-management-api.md` (572 lines)

**Actions:**
- Start with AUTHENTICATION.md operational guide
- Reference ADR-027 for design decisions
- Login workflows, JWT tokens, session management
- User lifecycle (create, update, delete)
- ~700 lines total

---

### 21 - Role-Based Access Control (RBAC) 🔄 CONSOLIDATE + ✏️ UPDATE
**Source Files:**
- `guides/RBAC.md` (632 lines)
- `architecture/ADR-028-dynamic-rbac-system.md` (577 lines)

**Actions:**
- Start with RBAC.md
- ⚠️ **STATUS FIX**: ADR-028 is Proposed - clarify what's implemented vs. planned
- Role creation, permission assignment
- Resource policies
- ~700 lines total

---

### 22 - Securing API Keys ✅ PORT
**Source Files:**
- `guides/SECURITY.md` (722 lines)
- `architecture/ADR-031-encrypted-api-key-storage.md` (1,466 lines) - **LARGE**

**Actions:**
- Start with SECURITY.md (operational guide)
- Reference ADR-031 architecture (already Accepted/Implemented)
- Fernet encryption, secrets management, key rotation
- ~800 lines total

---

### 23 - Account Recovery Procedures ✅ PORT
**Source Files:**
- `guides/PASSWORD_RECOVERY.md` (409 lines)

**Actions:**
- Light editing for flow
- Add troubleshooting section
- ~450 lines total

---

### 24 - Database Operations 🔄 CONSOLIDATE
**Source Files:**
- `guides/BACKUP_RESTORE.md` (455 lines)
- `guides/DATABASE_MIGRATIONS.md` (778 lines)
- `architecture/ADR-015-backup-restore-streaming.md` (662 lines)
- `architecture/ADR-040-database-schema-migrations.md` (429 lines)

**Actions:**
- Merge BACKUP_RESTORE.md + DATABASE_MIGRATIONS.md
- Reference ADR-015 (Accepted) and ADR-040 (check implementation status)
- ⚠️ **STATUS FIX**: ADR-040 appears implemented but marked Proposed
- Practical procedures for backup/restore and migrations
- ~1,000 lines total

---

### 25 - System Maintenance and Monitoring 📝 CREATE
**Source Files:**
- None (extract from various guides' troubleshooting sections)

**Actions:**
- Extract monitoring guidance from existing docs
- Health check procedures
- Log analysis
- Disk usage management
- Performance tuning basics
- ~400 lines total (new content)

---

### 26 - Troubleshooting Guide 📝 CREATE
**Source Files:**
- Extract troubleshooting sections from all guides

**Actions:**
- Consolidate all troubleshooting sections
- Organize by symptom → diagnosis → solution
- Connection issues, extraction failures, query timeouts, VRAM problems
- ~500 lines total (new index)

---

## Part IV: Architecture Deep Dives (30-39)

### 30 - Core System Architecture 🔄 CONSOLIDATE
**Source Files:**
- `architecture/ADR-012-api-server-architecture.md` (385 lines)
- `architecture/ADR-013-unified-typescript-client.md` (520 lines)
- `architecture/ADR-011-cli-admin-separation.md` (218 lines)
- `architecture/ADR-020-admin-module-architecture.md` (255 lines)

**Actions:**
- Merge all 4 ADRs into cohesive architecture chapter
- FastAPI design patterns
- TypeScript CLI + MCP shared codebase
- Module boundaries and separation
- ~1,000 lines total

---

### 31 - Apache AGE and PostgreSQL Integration ✏️ UPDATE
**Source Files:**
- `architecture/ADR-016-apache-age-migration.md` (1,094 lines)
- `architecture/ADR-024-multi-schema-postgresql-architecture.md` (600 lines)

**Actions:**
- ⚠️ **CRITICAL**: Update ADR-016 status (In Progress → Implemented)
- Explain AGE vs. Neo4j architectural differences
- openCypher (open standard) vs. proprietary Cypher
- Multi-schema organization from ADR-024 (check implementation status)
- ~1,200 lines total

---

### 32 - The Concept Extraction Pipeline 🔄 CONSOLIDATE
**Source Files:**
- `architecture/RECURSIVE_UPSERT_ARCHITECTURE.md` (3,189 lines) - **FULL VERSION**
- `development/DEV_JOURNAL_chunked_ingestion.md` (548 lines)
- `architecture/ADR-023-markdown-structured-content-preprocessing.md` (770 lines)

**Actions:**
- This is the **developer deep dive** version (vs. Section 05 user version)
- Full RECURSIVE_UPSERT_ARCHITECTURE.md details
- Smart chunking algorithms
- LLM prompting strategies
- Error handling and retry logic
- Preprocessing pipeline from ADR-023
- ~2,500 lines total (technical reference)

---

### 33 - Concept Deduplication and Matching 🔄 CONSOLIDATE
**Source Files:**
- `architecture/ADR-030-concept-deduplication-validation.md` (382 lines)
- `architecture/FUZZY_MATCHING_ANALYSIS.md` (148 lines)

**Actions:**
- Start with ADR-030 (Accepted/Implemented)
- Integrate fuzzy matching analysis
- Vector similarity algorithms
- Threshold tuning
- Quality metrics
- ~500 lines total

---

### 34 - Authentication and Security Architecture 🔄 CONSOLIDATE
**Source Files:**
- `architecture/CLI_AUTHENTICATION_ARCHITECTURE.md` (818 lines)
- `architecture/ADR-027-user-management-api.md` (572 lines)
- `architecture/ADR-028-dynamic-rbac-system.md` (577 lines)
- `architecture/ADR-031-encrypted-api-key-storage.md` (1,466 lines)

**Actions:**
- Developer-focused architecture deep dive
- Token flow diagrams
- Encryption implementation details
- RBAC technical design
- Threat model
- ~1,800 lines total (comprehensive security architecture)

---

### 35 - Job Management and Approval Workflows 🔄 CONSOLIDATE
**Source Files:**
- `architecture/ADR-014-job-approval-workflow.md` (689 lines)
- `architecture/ADR-018-server-sent-events-streaming.md` (401 lines)

**Actions:**
- Job lifecycle architecture
- Cost estimation algorithms
- Approval gates
- SSE progress streaming from ADR-018
- ~900 lines total

---

### 36 - Data Contracts and Schema Governance 🔄 CONSOLIDATE
**Source Files:**
- `architecture/DATA_CONTRACT.md` (439 lines)
- `architecture/ADR-040-database-schema-migrations.md` (429 lines)

**Actions:**
- Data contract patterns
- Schema versioning strategies
- Migration system architecture
- Backward compatibility
- ~700 lines total

---

### 37 - REST API Reference 🗂️ EXTRACT
**Source Files:**
- Extract from `src/api/routes/*.py`

**Actions:**
- Document all REST endpoints
- Request/response schemas
- Authentication patterns
- Error codes and handling
- Example curl commands
- ~1,000 lines total (new reference)

---

## Part V: Advanced Topics (40-49)

### 40 - Relationship Vocabulary Evolution 🔄 CONSOLIDATE
**Source Files:**
- `architecture/ADR-022-semantic-relationship-taxonomy.md` (349 lines) - Current: 30-type fixed
- `architecture/ADR-025-dynamic-relationship-vocabulary.md` (1,042 lines) - Proposed: Dynamic
- `architecture/ADR-026-autonomous-vocabulary-curation.md` (688 lines) - Proposed: Autonomous
- `architecture/ADR-032-automatic-edge-vocabulary-expansion.md` (1,955 lines) - Proposed: Auto-expansion

**Actions:**
- ⚠️ **CLARIFY ROADMAP**: What's current (ADR-022), what's next (ADR-025/026/032)?
- Technical deep dive into each approach
- Evolution path from fixed → dynamic → autonomous
- ~2,500 lines total (full technical details)

---

### 41 - Graph Visualization and Interactive Exploration 🔄 CONSOLIDATE
**Source Files:**
- `architecture/ADR-034-graph-visualization-query-workbench.md` (1,156 lines)
- `architecture/ADR-035-explorer-methods-uses-capabilities.md` (1,136 lines)
- `architecture/ADR-036-universal-visual-query-builder.md` (931 lines)
- `architecture/visualization.md` (211 lines)

**Actions:**
- Merge all 4 visualization documents
- 6 explorer types + 5 workbenches from ADR-034/035
- Visual query builder from ADR-036
- UI design notes from visualization.md
- ~2,500 lines total (comprehensive visualization architecture)

---

### 42 - Human-Guided Graph Editing ✅ PORT
**Source Files:**
- `architecture/ADR-037-human-guided-graph-editing.md` (638 lines)

**Actions:**
- Light editing for flow
- Human-in-the-loop curation
- Connection proposals
- Quality improvement workflows
- ~700 lines total

---

### 43 - Multimodal Ingestion: Images and Documents ✅ PORT
**Source Files:**
- `architecture/ADR-033-multimodal-ingestion-configurable-prompts.md` (1,270 lines)

**Actions:**
- Vision AI integration
- Image description extraction
- Configurable prompts
- Multimodal grounding
- ~1,300 lines total

---

### 44 - Advanced Governance and Access Control 🔄 CONSOLIDATE
**Source Files:**
- `architecture/ADR-001-multi-tier-agent-access.md` (113 lines)
- `architecture/ADR-002-node-fitness-scoring.md` (109 lines)
- `architecture/ADR-003-semantic-tool-hints.md` (149 lines)
- `architecture/ADR-004-pure-graph-design.md` (103 lines)
- `architecture/ADR-017-sensitive-auth-verification.md` (608 lines)
- `architecture/ADR-029-cli-theory-of-operation.md` (527 lines)

**Actions:**
- ⚠️ **UPDATE**: All reference Neo4j security model → update for PostgreSQL + AGE
- Merge exploratory ADRs into advanced governance chapter
- Multi-tier access patterns
- Node fitness scoring
- Token revocation (ADR-017)
- ~1,200 lines total

---

### 45 - Distributed Deployment and Scaling 🔄 CONSOLIDATE
**Source Files:**
- `reference/DISTRIBUTED_SHARDING_RESEARCH.md` (1,006 lines)
- `architecture/ADR-006-staging-migration-workflows.md` (160 lines)
- `architecture/ADR-008-multi-agent-coordination.md` (not written yet)
- `architecture/ADR-009-cross-graph-querying.md` (not written yet)

**Actions:**
- Start with DISTRIBUTED_SHARDING_RESEARCH.md
- Integrate ADR-006 staging/prod/archive separation
- Reference future ADR-008/009 placeholders
- Horizontal scaling strategies
- ~1,100 lines total

---

### 46 - Research Notes and Experimental Features 🔄 CONSOLIDATE
**Source Files:**
- `development/pattern-repetition-notes.md` (107 lines)
- `development/LEARNED_KNOWLEDGE_MCP.md` (506 lines)
- `architecture/ADR-007-edge-fitness-scoring.md` (not written)
- `architecture/ADR-010-llm-assisted-curation.md` (not written)

**Actions:**
- Consolidate development notes
- Reference future ADR placeholders
- Experimental features in development
- ~600 lines total

---

## Part VI: Developer Reference (50-59)

### 50 - Contributing to the Project 🗂️ EXTRACT
**Source Files:**
- Extract from `CLAUDE.md` (project instructions)
- No formal CONTRIBUTING.md exists

**Actions:**
- Development environment setup
- Code style guidelines
- Testing requirements
- PR workflow
- ADR process
- ~800 lines total (new guide)

---

### 51 - Testing Strategy and Coverage 🔄 CONSOLIDATE
**Source Files:**
- `testing/TEST_COVERAGE.md` (957 lines)
- `testing/SCHEMA_MIGRATION_TEST_REPORT.md` (404 lines)

**Actions:**
- Start with TEST_COVERAGE.md philosophy
- Integrate migration test report as example
- Testing patterns and practices
- ~1,000 lines total

---

### 52 - Architecture Decision Records (Index) ✏️ UPDATE
**Source Files:**
- `architecture/ARCHITECTURE_DECISIONS.md` (138 lines)

**Actions:**
- Expand ADR index with themed navigation
- Fix status mismatches (Proposed vs. Implemented)
- Add implementation dates/branches
- Cross-reference to book sections
- ~400 lines total (enhanced index)

---

### 53 - Development Journals ✅ PORT
**Source Files:**
- `development/DEV_JOURNAL_chunked_ingestion.md` (548 lines)
- `development/pattern-repetition-notes.md` (107 lines)
- `development/LEARNED_KNOWLEDGE_MCP.md` (506 lines)

**Actions:**
- Consolidate development journals
- Experimental work documentation
- Lessons learned
- ~800 lines total

---

## Part VII: Case Studies & Learning (60-69)

### 60 - Case Study: Multi-Perspective Enrichment ✅ PORT
**Source Files:**
- `reference/ENRICHMENT_JOURNEY.md` (381 lines)

**Actions:**
- Light editing for flow
- Emphasize multi-perspective learning
- ~400 lines total

---

### 61 - Case Study: GitHub Project History ✅ PORT
**Source Files:**
- `guides/use_cases/github_project_history.md` (514 lines)

**Actions:**
- Already covered in Section 07 - mark as cross-reference only
- Or create extended version with more examples
- ~500 lines total

---

### 62 - Query Examples Gallery ✅ PORT
**Source Files:**
- `guides/EXAMPLES.md` (308 lines)

**Actions:**
- Expand examples
- Include outputs from all query types
- ~400 lines total

---

## Appendices

### Appendix A: Glossary of Terms ✅ PORT
**Source Files:**
- `reference/CONCEPTS_AND_TERMINOLOGY.md` (543 lines)

**Actions:**
- Light reorganization
- Alphabetical + conceptual grouping
- ~600 lines total

---

### Appendix B: Architecture Decisions (Complete) 📝 CREATE
**Source Files:**
- All 43 ADRs organized thematically

**Actions:**
- Create themed ADR navigation
- Group by: Core Architecture, Auth/Security, Data Management, LLM/AI, Visualization, Advanced, Future
- ~200 lines (index only, ADRs remain separate)

---

### Appendix C: Command Line Reference ✅ PORT
**Source Files:**
- `guides/CLI_USAGE.md` (911 lines)

**Actions:**
- Reformat as quick reference
- Organize by command family
- ~900 lines total

---

### Appendix D: Configuration Reference 📝 CREATE
**Source Files:**
- Extract from all config guides

**Actions:**
- All config parameters in one place
- Environment variables
- Config file options
- ~400 lines total (new reference)

---

### Appendix E: Troubleshooting Index 📝 CREATE
**Source Files:**
- Extract from all guides

**Actions:**
- Symptom → solution mapping
- Common errors and fixes
- ~300 lines total (new index)

---

### Appendix F: Project Roadmap 📝 CREATE
**Source Files:**
- `docs/TODO.md` (76 lines)
- All Proposed ADRs

**Actions:**
- Timeline for proposed features
- Implementation priority
- Status tracking
- ~400 lines total (new roadmap)

---

### Appendix G: API Endpoint Reference 🗂️ EXTRACT
**Source Files:**
- Extract from `src/api/routes/*.py`

**Actions:**
- Same as Section 37 or cross-reference
- ~100 lines (if cross-reference)

---

## Summary Statistics

### Source Content by Action Type

| Action | Files | Lines | Notes |
|--------|-------|-------|-------|
| ✅ PORT (minor edits) | 15 | ~8,500 | Already well-written |
| 🔄 CONSOLIDATE | 24 | ~26,000 | Merge related docs |
| ✏️ UPDATE (significant) | 8 | ~7,000 | Neo4j→AGE, status fixes |
| 📝 CREATE (new) | 7 | ~3,000 | Fill gaps |
| 🗂️ EXTRACT (from code) | 3 | ~2,000 | API docs from source |
| **TOTAL** | **57** | **~46,500** | Excludes ADR-038 (apparel) |

### Critical Updates Needed

1. **Neo4j → Apache AGE** (8 files, ~3,000 lines)
   - ADR-001, ADR-004, ADR-005, ADR-006, ADR-012, ADR-016, ADR-044, ARCHITECTURE_OVERVIEW.md

2. **Status Fixes** (6 ADRs)
   - ADR-016: In Progress → Implemented
   - ADR-040: Proposed → Implemented (if migration system is done)
   - ADR-041: Proposed → verify partial implementation
   - ADR-039: Proposed → verify partial implementation
   - ADR-032: Proposed → verify if IMPLEMENTATION-NOTES means in-progress
   - ADR-028: Proposed → clarify what's implemented

3. **Major Consolidations** (5 areas, ~15,000 lines)
   - Authentication (6 docs → 2 sections)
   - AI Configuration (6 docs → 3 sections)
   - Vocabulary (5 docs → 2 sections)
   - Visualization (4 docs → 1 section)
   - Extraction Pipeline (3 docs → 2 sections)

### New Content Required

1. **System Administration** (3 new docs)
   - Section 25: System Maintenance (~400 lines)
   - Section 26: Troubleshooting Guide (~500 lines)
   - Section 50: Contributing Guide (~800 lines)

2. **Reference Material** (4 new docs)
   - Section 37: REST API Reference (~1,000 lines)
   - Appendix D: Configuration Reference (~400 lines)
   - Appendix E: Troubleshooting Index (~300 lines)
   - Appendix F: Project Roadmap (~400 lines)

---

## Implementation Order (Commit-Based)

### Commit 1: Critical Updates - Neo4j → Apache AGE
**Files to modify:** 8 files (~3,000 lines)
- `architecture/ADR-001-multi-tier-agent-access.md`
- `architecture/ADR-004-pure-graph-design.md`
- `architecture/ADR-005-source-text-tracking.md`
- `architecture/ADR-006-staging-migration-workflows.md`
- `architecture/ADR-012-api-server-architecture.md`
- `architecture/ADR-016-apache-age-migration.md`
- `architecture/ARCHITECTURE_OVERVIEW.md`
- Section 44 content (when creating)

**Actions:**
- Global find/replace: "Neo4j" → "Apache AGE" (with context review)
- Update security model references (Neo4j roles → PostgreSQL schemas)
- Update diagrams in ARCHITECTURE_OVERVIEW.md
- Verify all technical accuracy

---

### Commit 2: Status Fixes - ADR Implementation Status
**Files to modify:** 7 files
- `architecture/ARCHITECTURE_DECISIONS.md` (master index)
- `architecture/ADR-016-apache-age-migration.md` (In Progress → Implemented)
- `architecture/ADR-028-dynamic-rbac-system.md` (verify status)
- `architecture/ADR-032-automatic-edge-vocabulary-expansion.md` (verify status)
- `architecture/ADR-039-local-embedding-service.md` (verify status)
- `architecture/ADR-040-database-schema-migrations.md` (verify status)
- `architecture/ADR-041-ai-extraction-config.md` (verify status)

**Actions:**
- Check implementation status in codebase
- Update status fields: Proposed/Accepted/Implemented
- Add implementation dates where applicable
- Update ARCHITECTURE_DECISIONS.md index table

---

### Commit 3: Part I - Foundations (Sections 01-09)
**Create 9 new numbered files:**
- `01-what-is-a-knowledge-graph.md` (PORT: CONCEPT.md + CONCEPTS intro)
- `02-system-overview.md` (UPDATE: ARCHITECTURE_OVERVIEW.md)
- `03-quick-start-your-first-knowledge-graph.md` (PORT: QUICKSTART.md)
- `04-understanding-concepts-and-relationships.md` (CONSOLIDATE: 3 files)
- `05-the-extraction-process.md` (CONSOLIDATE: 3 files, simplified)
- `06-querying-your-knowledge-graph.md` (CONSOLIDATE: CLI_USAGE + OPENCYPHER basics)
- `07-real-world-example-project-history.md` (PORT: github_project_history.md)
- `08-choosing-your-ai-provider.md` (CONSOLIDATE: 3 files)
- `09-common-workflows-and-use-cases.md` (CONSOLIDATE: USE_CASES + INGESTION)

**Estimated:** ~4,500 lines total, mostly porting/consolidating

---

### Commit 4: Part II - Configuration (Sections 10-15)
**Create 6 new numbered files:**
- `10-ai-extraction-configuration.md` (CONSOLIDATE: EXTRACTION_CONFIG + ADR-041)
- `11-embedding-models-and-vector-search.md` (CONSOLIDATE: EMBEDDING_CONFIG + ADR-039)
- `12-local-llm-inference-with-ollama.md` (PORT: LOCAL_INFERENCE + ADR-042/043)
- `13-managing-relationship-vocabulary.md` (CONSOLIDATE: VOCAB_CONSOLIDATION + ADR-032)
- `14-advanced-query-patterns.md` (PORT: CYPHER_PATTERNS.md)
- `15-integration-with-claude-desktop.md` (PORT: MCP_SETUP.md)

**Estimated:** ~4,700 lines total

---

### Commit 5: Part III - System Administration (Sections 20-26)
**Create 7 new numbered files:**
- `20-user-management-and-authentication.md` (CONSOLIDATE: AUTHENTICATION + ADR-027)
- `21-role-based-access-control.md` (CONSOLIDATE: RBAC + ADR-028)
- `22-securing-api-keys.md` (PORT: SECURITY + ADR-031)
- `23-account-recovery-procedures.md` (PORT: PASSWORD_RECOVERY)
- `24-database-operations.md` (CONSOLIDATE: BACKUP_RESTORE + DB_MIGRATIONS + ADRs)
- `25-system-maintenance-and-monitoring.md` (CREATE: new operational guide)
- `26-troubleshooting-guide.md` (CREATE: consolidate troubleshooting sections)

**Estimated:** ~4,600 lines total (includes 2 new guides)

---

### Commit 6: Part IV - Architecture Deep Dives (Sections 30-37)
**Create 8 new numbered files:**
- `30-core-system-architecture.md` (CONSOLIDATE: 4 ADRs)
- `31-apache-age-and-postgresql-integration.md` (CONSOLIDATE: ADR-016 + ADR-024)
- `32-the-concept-extraction-pipeline.md` (CONSOLIDATE: RECURSIVE_UPSERT full version)
- `33-concept-deduplication-and-matching.md` (CONSOLIDATE: ADR-030 + FUZZY_MATCHING)
- `34-authentication-and-security-architecture.md` (CONSOLIDATE: 4 auth ADRs)
- `35-job-management-and-approval-workflows.md` (CONSOLIDATE: ADR-014 + ADR-018)
- `36-data-contracts-and-schema-governance.md` (CONSOLIDATE: DATA_CONTRACT + ADR-040)
- `37-rest-api-reference.md` (EXTRACT: from src/api/routes/)

**Estimated:** ~7,900 lines total (most complex section)

---

### Commit 7: Part V - Advanced Topics (Sections 40-46)
**Create 7 new numbered files:**
- `40-relationship-vocabulary-evolution.md` (CONSOLIDATE: 4 vocabulary ADRs)
- `41-graph-visualization-and-interactive-exploration.md` (CONSOLIDATE: 4 visualization ADRs)
- `42-human-guided-graph-editing.md` (PORT: ADR-037)
- `43-multimodal-ingestion-images-and-documents.md` (PORT: ADR-033)
- `44-advanced-governance-and-access-control.md` (CONSOLIDATE: 6 ADRs, update Neo4j refs)
- `45-distributed-deployment-and-scaling.md` (CONSOLIDATE: DISTRIBUTED_SHARDING + ADRs)
- `46-research-notes-and-experimental-features.md` (CONSOLIDATE: dev notes)

**Estimated:** ~7,700 lines total (proposed features)

---

### Commit 8: Part VI - Developer Reference (Sections 50-53)
**Create 4 new numbered files:**
- `50-contributing-to-the-project.md` (EXTRACT: CLAUDE.md + new)
- `51-testing-strategy-and-coverage.md` (CONSOLIDATE: TEST_COVERAGE + report)
- `52-architecture-decision-records-index.md` (UPDATE: ARCHITECTURE_DECISIONS)
- `53-development-journals.md` (CONSOLIDATE: 3 dev journals)

**Estimated:** ~2,300 lines total

---

### Commit 9: Part VII - Case Studies (Sections 60-62)
**Create 3 new numbered files:**
- `60-case-study-multi-perspective-enrichment.md` (PORT: ENRICHMENT_JOURNEY)
- `61-case-study-github-project-history.md` (cross-ref to section 07 or expand)
- `62-query-examples-gallery.md` (PORT: EXAMPLES.md expanded)

**Estimated:** ~1,300 lines total

---

### Commit 10: Appendices (A-G)
**Create 7 appendix files:**
- `appendix-a-glossary-of-terms.md` (PORT: CONCEPTS_AND_TERMINOLOGY)
- `appendix-b-architecture-decisions-complete.md` (CREATE: themed ADR navigation)
- `appendix-c-command-line-reference.md` (PORT: CLI_USAGE as reference)
- `appendix-d-configuration-reference.md` (CREATE: all config params)
- `appendix-e-troubleshooting-index.md` (CREATE: symptom→solution)
- `appendix-f-project-roadmap.md` (CREATE: from TODO + Proposed ADRs)
- `appendix-g-api-endpoint-reference.md` (cross-ref to section 37)

**Estimated:** ~3,200 lines total

---

### Commit 11: Main Index and Archive
**Update/create:**
- `docs/README.md` (replace with new book structure index)
- `docs/_archive/old-structure/` (move all old files)
- Update cross-references throughout

**Actions:**
- Create new README.md with book TOC
- Move old structure to _archive/
- Verify all internal links
- Add navigation helpers (prev/next section)

---

### Commit 12: Validation and Final Polish
**Test and validate:**
- Read-through test of sections 01-09
- Ingest documentation into knowledge graph
- Verify concept extraction quality
- Fix any broken links or formatting issues
- Update CLAUDE.md to reference new structure

---

## Validation Checklist

- [ ] Can a new user read Sections 01-09 and understand the system?
- [ ] Are all Neo4j references updated to Apache AGE?
- [ ] Do ADR statuses match actual implementation?
- [ ] Are configuration guides consolidated and easy to follow?
- [ ] Does the documentation ingest cleanly into the knowledge graph?
- [ ] Are all cross-references correct?
- [ ] Is the numbered structure consistent (NN, NN.N)?
- [ ] Are all code examples tested and working?
- [ ] Do diagrams reflect current architecture?
- [ ] Is the glossary comprehensive and accurate?

---

## Archive Strategy

**Move to `docs/_archive/old-structure/`:**
- All current `docs/architecture/*.md` files (after porting content)
- All current `docs/guides/*.md` files (after porting content)
- All current `docs/reference/*.md` files (after porting content)
- Current `docs/README.md` (replace with book structure index)

**Keep in place:**
- `docs/media/` directory (referenced by new docs)
- `docs/TODO.md` (until integrated into Appendix F)

**Delete (no longer relevant):**
- `docs/architecture/ADR-038-official-project-apparel.md` (tongue-in-cheek)
