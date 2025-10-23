# Knowledge Graph System - Documentation Book Structure

## Design Philosophy

This documentation is organized as a **coherent narrative** that can be read front-to-back, introducing concepts progressively like a lecture series. The structure mirrors the same linear-yet-interconnected approach used in our test ingestion content (Alan Watts lectures), allowing the documentation itself to serve as validation of the knowledge graph system.

**Key Principles:**
- **Progressive Introduction**: Prerequisites before advanced topics
- **Numbered Sections**: Decimal numbering (01, 01.1, 01.2) allows future insertions
- **Conceptual Building**: Each section builds on previous understanding
- **Verifiable Structure**: Documentation should ingest cleanly into the system
- **Human-Centric**: Mirrors natural learning progression

---

## Part I: Foundations (01-09)

### 01 - What Is a Knowledge Graph?
**Purpose:** Establish core concepts and mental models
**Current Content:** CONCEPT.md, CONCEPTS_AND_TERMINOLOGY.md
**Audience:** Everyone
**Key Concepts:** Graph vs. linear thinking, nodes/edges, semantic relationships, why not just RAG?

### 02 - System Overview
**Purpose:** High-level architecture understanding
**Current Content:** ARCHITECTURE_OVERVIEW.md (updated for AGE)
**Audience:** Everyone
**Key Concepts:** Components, data flow, Apache AGE, REST API, TypeScript client

### 03 - Quick Start: Your First Knowledge Graph
**Purpose:** Get users from zero to working system in 5 minutes
**Current Content:** QUICKSTART.md
**Audience:** New users
**Key Concepts:** Installation, first ingestion, first query

### 04 - Understanding Concepts and Relationships
**Purpose:** Deep dive into the data model
**Current Content:** SCHEMA_REFERENCE.md, ADR-022 (30-type taxonomy)
**Audience:** All users
**Key Concepts:** Concept nodes, Instance nodes, Source nodes, relationship types

### 05 - The Extraction Process
**Purpose:** How documents become graphs
**Current Content:** RECURSIVE_UPSERT_ARCHITECTURE.md (simplified), ADR-014 (job workflow)
**Audience:** All users
**Key Concepts:** Chunking, LLM extraction, embedding matching, concept deduplication

### 06 - Querying Your Knowledge Graph
**Purpose:** Basic query patterns and CLI usage
**Current Content:** CLI_USAGE.md (essentials), OPENCYPHER_QUERIES.md (basics)
**Audience:** All users
**Key Concepts:** Search by text, find related concepts, explore connections, path finding

### 07 - Real World Example: Project History Analysis
**Purpose:** Show the system in action with real data
**Current Content:** github_project_history.md, EXAMPLES.md
**Audience:** All users
**Key Concepts:** Ingesting code history, exploring development decisions, multi-perspective learning

### 08 - Choosing Your AI Provider
**Purpose:** Understand the LLM landscape and make informed choices
**Current Content:** AI_PROVIDERS.md, EXTRACTION_QUALITY_COMPARISON.md, SWITCHING_EXTRACTION_PROVIDERS.md
**Audience:** All users
**Key Concepts:** Cloud vs. local, extraction quality, cost tradeoffs, switching procedures

### 09 - Common Workflows and Use Cases
**Purpose:** Patterns for different scenarios
**Current Content:** USE_CASES.md, INGESTION.md
**Audience:** All users
**Key Concepts:** Research workflows, documentation analysis, learning from lectures

---

## Part II: Configuration & Customization (10-19)

### 10 - AI Extraction Configuration
**Purpose:** Configure LLM providers for concept extraction
**Current Content:** EXTRACTION_CONFIGURATION.md, ADR-041 (overview)
**Audience:** Operators, administrators
**Key Concepts:** Provider selection, model selection, extraction parameters

### 11 - Embedding Models and Vector Search
**Purpose:** Configure similarity matching
**Current Content:** EMBEDDING_CONFIGURATION.md, ADR-039 (overview)
**Audience:** Operators, administrators
**Key Concepts:** OpenAI vs. local embeddings, vector similarity, performance tradeoffs

### 12 - Local LLM Inference with Ollama
**Purpose:** Air-gapped deployment with local models
**Current Content:** LOCAL_INFERENCE_IMPLEMENTATION.md, ADR-042, ADR-043
**Audience:** Privacy-conscious users, operators
**Key Concepts:** Ollama setup, hardware requirements, VRAM management, CPU fallback

### 13 - Managing Relationship Vocabulary
**Purpose:** Curate and expand semantic relationship types
**Current Content:** VOCABULARY_CONSOLIDATION.md, ADR-032 (overview)
**Audience:** Curators, administrators
**Key Concepts:** Fixed taxonomy, dynamic expansion, merging relationships, pruning

### 14 - Advanced Query Patterns
**Purpose:** Complex graph traversals and analysis
**Current Content:** CYPHER_PATTERNS.md
**Audience:** Power users, developers
**Key Concepts:** Fuzzy matching, weighted paths, regex queries, multi-hop traversals

### 15 - Integration with Claude Desktop (MCP)
**Purpose:** Connect your knowledge graph to AI assistants
**Current Content:** MCP_SETUP.md, ADR-013 (MCP architecture)
**Audience:** Claude users
**Key Concepts:** MCP protocol, tool installation, conversation-driven exploration

---

## Part III: System Administration (20-29)

### 20 - User Management and Authentication
**Purpose:** Secure multi-user deployments
**Current Content:** AUTHENTICATION.md, ADR-027
**Audience:** Administrators
**Key Concepts:** JWT tokens, bcrypt hashing, session management, user lifecycle

### 21 - Role-Based Access Control (RBAC)
**Purpose:** Granular permissions and access policies
**Current Content:** RBAC.md, ADR-028 (overview)
**Audience:** Administrators
**Key Concepts:** Roles, permissions, resource policies, dynamic registration

### 22 - Securing API Keys
**Purpose:** Encrypted credential storage
**Current Content:** SECURITY.md, ADR-031
**Audience:** Administrators
**Key Concepts:** Fernet encryption, secrets management, key rotation, recovery

### 23 - Account Recovery Procedures
**Purpose:** Handle locked accounts and forgotten passwords
**Current Content:** PASSWORD_RECOVERY.md
**Audience:** Administrators
**Key Concepts:** Recovery workflows, manual intervention, security considerations

### 24 - Database Operations
**Purpose:** Backup, restore, and migrations
**Current Content:** BACKUP_RESTORE.md, DATABASE_MIGRATIONS.md, ADR-015, ADR-040
**Audience:** DBAs, administrators
**Key Concepts:** AGE backup strategies, schema evolution, migration scripts, rollback

### 25 - System Maintenance and Monitoring
**Purpose:** Keep the system healthy and performant
**Current Content:** *NEW* (consolidate operational notes)
**Audience:** Operators, administrators
**Key Concepts:** Health checks, log monitoring, disk usage, performance tuning

### 26 - Troubleshooting Guide
**Purpose:** Diagnose and fix common issues
**Current Content:** *NEW* (consolidate troubleshooting sections from guides)
**Audience:** All administrators
**Key Concepts:** Connection issues, extraction failures, query timeouts, VRAM problems

---

## Part IV: Architecture Deep Dives (30-39)

### 30 - Core System Architecture
**Purpose:** Understand the technical design
**Current Content:** ADR-012 (API server), ADR-013 (TypeScript client), ADR-011 (CLI/admin), ADR-020 (admin module)
**Audience:** Developers, architects
**Key Concepts:** FastAPI design, REST API patterns, CLI architecture, module boundaries

### 31 - Apache AGE and PostgreSQL Integration
**Purpose:** The graph database foundation
**Current Content:** ADR-016 (Apache AGE migration), ADR-024 (multi-schema)
**Audience:** Developers, DBAs
**Key Concepts:** Apache AGE vs. Neo4j, openCypher vs. proprietary Cypher, schema organization

### 32 - The Concept Extraction Pipeline
**Purpose:** How LLMs turn text into graphs
**Current Content:** RECURSIVE_UPSERT_ARCHITECTURE.md, DEV_JOURNAL_chunked_ingestion.md, ADR-023 (preprocessing)
**Audience:** Developers, ML engineers
**Key Concepts:** Smart chunking, LLM prompting, JSON parsing, error handling, embedding generation

### 33 - Concept Deduplication and Matching
**Purpose:** Keep the graph clean and coherent
**Current Content:** ADR-030, FUZZY_MATCHING_ANALYSIS.md
**Audience:** Developers, data engineers
**Key Concepts:** Vector similarity thresholds, canonical labels, merge strategies, quality metrics

### 34 - Authentication and Security Architecture
**Purpose:** Technical design of auth systems
**Current Content:** CLI_AUTHENTICATION_ARCHITECTURE.md, ADR-027, ADR-028, ADR-031
**Audience:** Security engineers, developers
**Key Concepts:** Token flow, encryption schemes, RBAC implementation, threat models

### 35 - Job Management and Approval Workflows
**Purpose:** Asynchronous ingestion with cost control
**Current Content:** ADR-014, ADR-018 (SSE streaming)
**Audience:** Developers
**Key Concepts:** Job lifecycle, cost estimation, approval gates, progress streaming

### 36 - Data Contracts and Schema Governance
**Purpose:** Maintain data integrity across changes
**Current Content:** DATA_CONTRACT.md, ADR-040 (migrations)
**Audience:** Data engineers, architects
**Key Concepts:** Schema versioning, backward compatibility, migration patterns

### 37 - REST API Reference
**Purpose:** Complete HTTP endpoint documentation
**Current Content:** *NEW* (extract from source code)
**Audience:** Developers, integrators
**Key Concepts:** Authentication, endpoints, request/response formats, error codes

---

## Part V: Advanced Topics (40-49)

### 40 - Relationship Vocabulary Evolution
**Purpose:** From fixed taxonomy to dynamic curation
**Current Content:** ADR-022 (current), ADR-025 (dynamic), ADR-026 (autonomous), ADR-032 (auto-expansion)
**Audience:** Architects, curators
**Key Concepts:** Vocabulary roadmap, curator-driven vs. LLM-driven, versioning strategies

### 41 - Graph Visualization and Interactive Exploration
**Purpose:** Visual interfaces for knowledge navigation
**Current Content:** ADR-034, ADR-035, ADR-036, visualization.md
**Audience:** UX designers, frontend developers
**Key Concepts:** 6 explorer types, 5 workbenches, visual query builder, force-directed layouts

### 42 - Human-Guided Graph Editing
**Purpose:** Manual curation and correction
**Current Content:** ADR-037
**Audience:** Curators, domain experts
**Key Concepts:** Human-in-the-loop, connection proposals, concept merging, quality improvement

### 43 - Multimodal Ingestion: Images and Documents
**Purpose:** Beyond text: visual content extraction
**Current Content:** ADR-033
**Audience:** ML engineers, architects
**Key Concepts:** Vision AI, image descriptions, configurable prompts, multimodal grounding

### 44 - Advanced Governance and Access Control
**Purpose:** Sophisticated multi-tenant patterns
**Current Content:** ADR-001, ADR-002, ADR-003, ADR-004, ADR-017, ADR-029
**Audience:** Enterprise architects
**Key Concepts:** Multi-tier access, node fitness scoring, semantic tool hints, token revocation

### 45 - Distributed Deployment and Scaling
**Purpose:** Beyond single-node: horizontal scaling
**Current Content:** DISTRIBUTED_SHARDING_RESEARCH.md, ADR-006, ADR-008, ADR-009
**Audience:** Infrastructure engineers, architects
**Key Concepts:** Graph sharding, federated queries, staging/prod/archive separation, event streaming

### 46 - Research Notes and Experimental Features
**Purpose:** Ideas in development
**Current Content:** pattern-repetition-notes.md, LEARNED_KNOWLEDGE_MCP.md, ADR-007, ADR-010
**Audience:** Contributors, researchers
**Key Concepts:** Edge fitness scoring, LLM-assisted curation, cross-graph querying

---

## Part VI: Developer Reference (50-59)

### 50 - Contributing to the Project
**Purpose:** Onboarding guide for new contributors
**Current Content:** *NEW* (CLAUDE.md + contribution patterns)
**Audience:** Developers
**Key Concepts:** Setup, code style, testing, PR workflow, ADR process

### 51 - Testing Strategy and Coverage
**Purpose:** Quality assurance approach
**Current Content:** TEST_COVERAGE.md, SCHEMA_MIGRATION_TEST_REPORT.md
**Audience:** Developers, QA engineers
**Key Concepts:** Functional correctness, end-to-end tests, migration testing, no code coverage metrics

### 52 - Architecture Decision Records (Index)
**Purpose:** Complete ADR reference
**Current Content:** ARCHITECTURE_DECISIONS.md
**Audience:** All technical roles
**Key Concepts:** ADR status, decision rationale, themed navigation

### 53 - Development Journals
**Purpose:** In-progress design work
**Current Content:** DEV_JOURNAL_chunked_ingestion.md, pattern-repetition-notes.md
**Audience:** Contributors
**Key Concepts:** Experimental features, design exploration, lessons learned

---

## Part VII: Case Studies & Learning (60-69)

### 60 - Case Study: Multi-Perspective Enrichment
**Purpose:** Show how the graph enables non-linear learning
**Current Content:** ENRICHMENT_JOURNEY.md
**Audience:** All users
**Key Concepts:** 280 commits + 31 PRs, multi-perspective exploration, concept interconnection

### 61 - Case Study: GitHub Project History
**Purpose:** Practical example of code repository analysis
**Current Content:** github_project_history.md
**Audience:** Developers, product managers
**Key Concepts:** Commit analysis, evolution tracking, decision tracing

### 62 - Query Examples Gallery
**Purpose:** Practical query patterns with real results
**Current Content:** EXAMPLES.md
**Audience:** All users
**Key Concepts:** Search patterns, path finding, relationship exploration

---

## Appendices (A-Z)

### Appendix A: Glossary of Terms
**Current Content:** CONCEPTS_AND_TERMINOLOGY.md
**Purpose:** Quick reference for terminology

### Appendix B: Architecture Decisions (Complete)
**Current Content:** All 43 ADRs organized by theme
**Purpose:** Comprehensive decision record

### Appendix C: Command Line Reference
**Current Content:** CLI_USAGE.md (complete command listing)
**Purpose:** Quick CLI reference

### Appendix D: Configuration Reference
**Current Content:** Consolidated config options from all guides
**Purpose:** All configuration parameters in one place

### Appendix E: Troubleshooting Index
**Current Content:** *NEW* (extract from all guides)
**Purpose:** Symptom → solution mapping

### Appendix F: Project Roadmap
**Current Content:** *NEW* (based on Proposed ADRs + TODO.md)
**Purpose:** Implementation timeline and status

### Appendix G: API Endpoint Reference
**Current Content:** *NEW*
**Purpose:** HTTP API quick reference

---

## Document Numbering Scheme

**Format:** `NN` or `NN.N` or `NN.N.N`

**Examples:**
- `01` - What Is a Knowledge Graph?
- `01.1` - Graph Theory Basics (future insertion)
- `01.2` - Semantic Networks vs. Property Graphs (future insertion)
- `03` - Quick Start
- `03.1` - Docker Installation (future detailed guide)
- `03.2` - Native Installation (future detailed guide)

**Advantages:**
- Decimal numbering allows infinite insertions without renumbering
- Clear progression through material
- Easy to reference ("see section 12.3")
- Supports reorganization without breaking references

---

## File Naming Convention

**Pattern:** `docs/NN-title-in-kebab-case.md`

**Examples:**
- `docs/01-what-is-a-knowledge-graph.md`
- `docs/03-quick-start-your-first-knowledge-graph.md`
- `docs/12-local-llm-inference-with-ollama.md`
- `docs/appendix-a-glossary-of-terms.md`

**Directory Structure:**
```
docs/
├── 01-what-is-a-knowledge-graph.md
├── 02-system-overview.md
├── 03-quick-start-your-first-knowledge-graph.md
...
├── 60-case-study-multi-perspective-enrichment.md
├── appendix-a-glossary-of-terms.md
├── appendix-b-architecture-decisions.md
...
├── media/
│   ├── screenshots/
│   └── diagrams/
└── _archive/
    ├── old-structure/
    └── superseded/
```

---

## Migration Strategy

### Phase 1: Structure Definition (Current)
- ✅ Define book structure
- [ ] Map existing content to new structure
- [ ] Identify gaps and overlaps

### Phase 2: Content Consolidation
- [ ] Merge related documents (auth, config, vocabulary)
- [ ] Update Neo4j → Apache AGE references
- [ ] Fix status mismatches (Proposed vs. Implemented)
- [ ] Create missing sections (troubleshooting, API reference, operations)

### Phase 3: Reorganization
- [ ] Create new numbered files
- [ ] Port content with progressive flow edits
- [ ] Add cross-references between sections
- [ ] Archive old structure

### Phase 4: Validation
- [ ] Read-through test (can it be read front-to-back?)
- [ ] Ingest into knowledge graph system
- [ ] Verify concept extraction quality
- [ ] Check for structural coherence in graph

### Phase 5: Maintenance
- [ ] Update CLAUDE.md with new structure
- [ ] Create contribution guide for new sections
- [ ] Establish ADR → documentation sync process

---

## Success Criteria

1. **Linear Readability**: A new user can read sections 01-09 and understand the system
2. **Progressive Depth**: Each part builds on previous knowledge
3. **Clean Ingestion**: Documentation creates high-quality concept graph when ingested
4. **Easy Navigation**: Numbered sections allow quick reference
5. **Future-Proof**: Decimal numbering supports growth without reorganization
6. **Verifiable**: Graph analysis shows proper concept relationships

---

## Notes

This structure is inspired by the narrative flow of the Alan Watts lectures used in testing. Just as those lectures build philosophical concepts progressively, this documentation builds technical understanding from foundations through advanced topics.

The meta-goal: **The documentation itself serves as validation that our knowledge graph system can handle coherent, interconnected narratives.**
