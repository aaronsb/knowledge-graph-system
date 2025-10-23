# Knowledge Graph System - Documentation

**Version:** 1.0 (Book Structure)
**Last Updated:** 2025-10-23
**Format:** Progressive narrative designed for front-to-back reading

---

## About This Documentation

This documentation is organized as a **coherent narrative** that builds understanding progressively, like a lecture series or technical book. Each section introduces concepts that build on previous knowledge, while the ADR (Architecture Decision Record) collection provides the historical decision-making context.

**Reading Paths:**
- **New Users:** Start with [Part I](#part-i-foundations-01-09) (Sections 01-09)
- **Operators:** Jump to [Part II](#part-ii-configuration--customization-10-19) and [Part III](#part-iii-system-administration-20-29)
- **Developers:** Begin with [Part I](#part-i-foundations-01-09), then [Part IV](#part-iv-architecture-deep-dives-30-39)
- **Architects:** [Part IV](#part-iv-architecture-deep-dives-30-39), [Part V](#part-v-advanced-topics-40-49), [ADR Index](#part-vi-developer-reference-50-59)

---

## Part I: Foundations (01-09)

**Goal:** Understand what knowledge graphs are, why they matter, and how to use this system.

- [01 - What Is a Knowledge Graph?](01-what-is-a-knowledge-graph.md)
- [02 - System Overview](02-system-overview.md)
- [03 - Quick Start: Your First Knowledge Graph](03-quick-start-your-first-knowledge-graph.md)
- [04 - Understanding Concepts and Relationships](04-understanding-concepts-and-relationships.md)
- [05 - The Extraction Process](05-the-extraction-process.md)
- [06 - Querying Your Knowledge Graph](06-querying-your-knowledge-graph.md)
- [07 - Real World Example: Project History Analysis](07-real-world-example-project-history.md)
- [08 - Choosing Your AI Provider](08-choosing-your-ai-provider.md)
- [09 - Common Workflows and Use Cases](09-common-workflows-and-use-cases.md)

---

## Part II: Configuration & Customization (10-19)

**Goal:** Configure the system for your specific needs and environment.

- [10 - AI Extraction Configuration](10-ai-extraction-configuration.md)
- [11 - Embedding Models and Vector Search](11-embedding-models-and-vector-search.md)
- [12 - Local LLM Inference with Ollama](12-local-llm-inference-with-ollama.md)
- [13 - Managing Relationship Vocabulary](13-managing-relationship-vocabulary.md)
- [14 - Advanced Query Patterns](14-advanced-query-patterns.md)
- [15 - Integration with Claude Desktop (MCP)](15-integration-with-claude-desktop.md)

---

## Part III: System Administration (20-29)

**Goal:** Operate and maintain a production knowledge graph system.

- [20 - User Management and Authentication](20-user-management-and-authentication.md)
- [21 - Role-Based Access Control (RBAC)](21-role-based-access-control.md)
- [22 - Securing API Keys](22-securing-api-keys.md)
- [23 - Account Recovery Procedures](23-account-recovery-procedures.md)
- [24 - Database Operations](24-database-operations.md)
- [25 - System Maintenance and Monitoring](25-system-maintenance-and-monitoring.md)
- [26 - Troubleshooting Guide](26-troubleshooting-guide.md)

---

## Part IV: Architecture Deep Dives (30-39)

**Goal:** Understand the technical design and implementation details.

- [30 - Core System Architecture](30-core-system-architecture.md)
- [31 - Apache AGE and PostgreSQL Integration](31-apache-age-and-postgresql-integration.md)
- [32 - The Concept Extraction Pipeline](32-the-concept-extraction-pipeline.md)
- [33 - Concept Deduplication and Matching](33-concept-deduplication-and-matching.md)
- [34 - Authentication and Security Architecture](34-authentication-and-security-architecture.md)
- [35 - Job Management and Approval Workflows](35-job-management-and-approval-workflows.md)
- [36 - Data Contracts and Schema Governance](36-data-contracts-and-schema-governance.md)
- [37 - REST API Reference](37-rest-api-reference.md)

---

## Part V: Advanced Topics (40-49)

**Goal:** Explore advanced features and future directions.

- [40 - Relationship Vocabulary Evolution](40-relationship-vocabulary-evolution.md)
- [41 - Graph Visualization and Interactive Exploration](41-graph-visualization-and-interactive-exploration.md)
- [42 - Human-Guided Graph Editing](42-human-guided-graph-editing.md)
- [43 - Multimodal Ingestion: Images and Documents](43-multimodal-ingestion-images-and-documents.md)
- [44 - Advanced Governance and Access Control](44-advanced-governance-and-access-control.md)
- [45 - Distributed Deployment and Scaling](45-distributed-deployment-and-scaling.md)
- [46 - Research Notes and Experimental Features](46-research-notes-and-experimental-features.md)

---

## Part VI: Developer Reference (50-59)

**Goal:** Contribute to the project and understand development practices.

- [50 - Contributing to the Project](50-contributing-to-the-project.md)
- [51 - Testing Strategy and Coverage](51-testing-strategy-and-coverage.md)
- [52 - Architecture Decision Records (Index)](52-architecture-decision-records-index.md)
- [53 - Development Journals](53-development-journals.md)

---

## Part VII: Case Studies (60-69)

**Goal:** See the system in action with real-world examples.

- [60 - Case Study: Multi-Perspective Enrichment](60-case-study-multi-perspective-enrichment.md)
- [61 - Case Study: GitHub Project History Analysis](61-case-study-github-project-history.md)
- [62 - Query Examples Gallery](62-query-examples-gallery.md)

---

## Appendices

**Quick reference materials for looking up specific information.**

- [Appendix A: Glossary of Terms](appendix-a-glossary-of-terms.md)
- [Appendix B: Architecture Decisions (Complete)](appendix-b-architecture-decisions-complete.md)
- [Appendix C: Command Line Reference](appendix-c-command-line-reference.md)
- [Appendix D: Configuration Reference](appendix-d-configuration-reference.md)
- [Appendix E: Troubleshooting Index](appendix-e-troubleshooting-index.md)
- [Appendix F: Project Roadmap](appendix-f-project-roadmap.md)
- [Appendix G: API Endpoint Reference](appendix-g-api-endpoint-reference.md)

---

## Original Documentation (Archive)

The original documentation structure has been preserved in subdirectories:

- `architecture/` - Architecture Decision Records (ADRs) and design documents
- `guides/` - Operational guides and how-tos
- `reference/` - Reference material and conceptual documents
- `api/` - API and query language documentation
- `testing/` - Testing strategy and reports
- `development/` - Development journals and notes

**Important:** ADRs remain the authoritative source for design decisions. The numbered sections reference and consolidate ADRs but do not replace them.

---

## Documentation Philosophy

### Progressive Refinement

This documentation is built through **progressive refinement passes**:

1. **Structure First:** Create numbered files with goals and outlines
2. **Content Consolidation:** Port and merge existing content
3. **Cross-Referencing:** Link related sections
4. **Validation:** Ingest documentation into the knowledge graph system itself

### ADRs as Historical Record

Architecture Decision Records (ADRs) in `architecture/` are **kept as-is** - they represent the historical decision-making process, including decisions about migration from Neo4j to Apache AGE. These provide valuable context for why the system works the way it does.

### Lessons Learned

Decisions about system evolution (like the Neo4j → Apache AGE migration) are incorporated as **lessons learned** in relevant sections, explaining not just what we built but why we made those choices.

---

## Contributing to Documentation

See [Section 50 - Contributing to the Project](50-contributing-to-the-project.md) for guidelines on:
- Adding new sections (decimal numbering allows insertions)
- Updating existing content
- Creating new ADRs
- Cross-referencing between sections

---

## Meta-Validation

This documentation structure is designed to validate the knowledge graph system itself. When ingested, it should:

- Create clean concept extraction
- Show proper relationship structures
- Demonstrate multi-perspective learning
- Validate the system can handle technical documentation

See [BOOK_STRUCTURE.md](BOOK_STRUCTURE.md) for the design rationale and [CONTENT_MAPPING.md](CONTENT_MAPPING.md) for the implementation plan.

---

**Start Reading:** [01 - What Is a Knowledge Graph?](01-what-is-a-knowledge-graph.md) →
