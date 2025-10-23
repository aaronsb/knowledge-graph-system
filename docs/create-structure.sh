#!/bin/bash
# Create skeletal structure for book-style documentation

cd /home/aaron/Projects/ai/knowledge-graph-system/docs

# Create all numbered sections with basic structure
# Format: section_number|title|sources|goal

declare -a sections=(
  "02|System Overview|architecture/ARCHITECTURE_OVERVIEW.md|High-level architecture understanding - components, data flow, Apache AGE foundation"
  "03|Quick Start Your First Knowledge Graph|guides/QUICKSTART.md|Get from zero to working system in 5 minutes"
  "04|Understanding Concepts and Relationships|guides/SCHEMA_REFERENCE.md, architecture/ADR-022|Deep dive into data model - nodes, edges, 30-type taxonomy"
  "05|The Extraction Process|architecture/RECURSIVE_UPSERT_ARCHITECTURE.md (simplified)|How documents become graphs (user-friendly version)"
  "06|Querying Your Knowledge Graph|guides/CLI_USAGE.md, api/OPENCYPHER_QUERIES.md|Basic queries and CLI usage"
  "07|Real World Example Project History|guides/use_cases/github_project_history.md|Show the system in action with real data"
  "08|Choosing Your AI Provider|guides/AI_PROVIDERS.md, guides/EXTRACTION_QUALITY_COMPARISON.md|Understand LLM landscape and make informed choices"
  "09|Common Workflows and Use Cases|guides/USE_CASES.md, guides/INGESTION.md|Patterns for different scenarios"
  "10|AI Extraction Configuration|guides/EXTRACTION_CONFIGURATION.md, architecture/ADR-041|Configure LLM providers for extraction"
  "11|Embedding Models and Vector Search|guides/EMBEDDING_CONFIGURATION.md, architecture/ADR-039|Configure similarity matching"
  "12|Local LLM Inference with Ollama|guides/LOCAL_INFERENCE_IMPLEMENTATION.md, architecture/ADR-042, ADR-043|Air-gapped deployment with local models"
  "13|Managing Relationship Vocabulary|guides/VOCABULARY_CONSOLIDATION.md, architecture/ADR-032|Curate and expand semantic relationships"
  "14|Advanced Query Patterns|api/CYPHER_PATTERNS.md|Complex traversals and analysis"
  "15|Integration with Claude Desktop|guides/MCP_SETUP.md, architecture/ADR-013|Connect knowledge graph to AI assistants"
  "20|User Management and Authentication|guides/AUTHENTICATION.md, architecture/ADR-027|Secure multi-user deployments"
  "21|Role Based Access Control|guides/RBAC.md, architecture/ADR-028|Granular permissions and policies"
  "22|Securing API Keys|guides/SECURITY.md, architecture/ADR-031|Encrypted credential storage"
  "23|Account Recovery Procedures|guides/PASSWORD_RECOVERY.md|Handle locked accounts and forgotten passwords"
  "24|Database Operations|guides/BACKUP_RESTORE.md, guides/DATABASE_MIGRATIONS.md|Backup, restore, migrations"
  "25|System Maintenance and Monitoring|NEW - consolidate operational notes|Keep system healthy and performant"
  "26|Troubleshooting Guide|NEW - consolidate troubleshooting sections|Diagnose and fix common issues"
  "30|Core System Architecture|architecture/ADR-012, ADR-013, ADR-011, ADR-020|Understand the technical design"
  "31|Apache AGE and PostgreSQL Integration|architecture/ADR-016, ADR-024|The graph database foundation"
  "32|The Concept Extraction Pipeline|architecture/RECURSIVE_UPSERT_ARCHITECTURE.md (full)|How LLMs turn text into graphs (technical)"
  "33|Concept Deduplication and Matching|architecture/ADR-030, FUZZY_MATCHING_ANALYSIS.md|Keep the graph clean and coherent"
  "34|Authentication and Security Architecture|architecture/CLI_AUTHENTICATION_ARCHITECTURE.md, multiple ADRs|Technical design of auth systems"
  "35|Job Management and Approval Workflows|architecture/ADR-014, ADR-018|Asynchronous ingestion with cost control"
  "36|Data Contracts and Schema Governance|architecture/DATA_CONTRACT.md, ADR-040|Maintain data integrity across changes"
  "37|REST API Reference|EXTRACT from src/api/routes/|Complete HTTP endpoint documentation"
  "40|Relationship Vocabulary Evolution|architecture/ADR-022, ADR-025, ADR-026, ADR-032|From fixed taxonomy to dynamic curation"
  "41|Graph Visualization and Interactive Exploration|architecture/ADR-034, ADR-035, ADR-036, visualization.md|Visual interfaces for navigation"
  "42|Human Guided Graph Editing|architecture/ADR-037|Manual curation and correction"
  "43|Multimodal Ingestion Images and Documents|architecture/ADR-033|Beyond text - visual content"
  "44|Advanced Governance and Access Control|architecture/ADR-001, ADR-002, ADR-003, ADR-004, ADR-017|Sophisticated multi-tenant patterns"
  "45|Distributed Deployment and Scaling|reference/DISTRIBUTED_SHARDING_RESEARCH.md, architecture/ADR-006|Beyond single-node - horizontal scaling"
  "46|Research Notes and Experimental Features|development/pattern-repetition-notes.md, LEARNED_KNOWLEDGE_MCP.md|Ideas in development"
  "50|Contributing to the Project|CLAUDE.md + new|Onboarding for contributors"
  "51|Testing Strategy and Coverage|testing/TEST_COVERAGE.md, SCHEMA_MIGRATION_TEST_REPORT.md|Quality assurance approach"
  "52|Architecture Decision Records Index|architecture/ARCHITECTURE_DECISIONS.md|Complete ADR reference with themes"
  "53|Development Journals|development/DEV_JOURNAL_chunked_ingestion.md, etc|In-progress design work"
  "60|Case Study Multi Perspective Enrichment|reference/ENRICHMENT_JOURNEY.md|Non-linear learning demonstration"
  "61|Case Study GitHub Project History|guides/use_cases/github_project_history.md|Code repository analysis"
  "62|Query Examples Gallery|guides/EXAMPLES.md|Practical query patterns with results"
)

for section in "${sections[@]}"; do
  IFS='|' read -r num title sources goal <<< "$section"

  # Convert title to filename
  filename=$(echo "$num-$(echo "$title" | tr '[:upper:]' '[:lower:]' | tr ' ' '-').md" | sed 's/--/-/g')

  # Determine part
  if [ "$num" -lt 10 ]; then
    part="I - Foundations"
  elif [ "$num" -lt 20 ]; then
    part="II - Configuration & Customization"
  elif [ "$num" -lt 30 ]; then
    part="III - System Administration"
  elif [ "$num" -lt 40 ]; then
    part="IV - Architecture Deep Dives"
  elif [ "$num" -lt 50 ]; then
    part="V - Advanced Topics"
  elif [ "$num" -lt 60 ]; then
    part="VI - Developer Reference"
  else
    part="VII - Case Studies"
  fi

  cat > "$filename" << EOF
# $num - $title

**Status:** DRAFT
**Part:** $part
**Reading Time:** TBD

## Goal

$goal

## Source Materials

$sources

## Outline

TBD - Define structure when consolidating content

## TODO

- [ ] Review source materials
- [ ] Create outline
- [ ] Write/consolidate content
- [ ] Add examples
- [ ] Cross-reference related sections

---

*This document is part of the Knowledge Graph System book-style documentation.*
EOF

  echo "Created: $filename"
done

echo ""
echo "Creating appendices..."

# Create appendices
declare -a appendices=(
  "appendix-a-glossary-of-terms|reference/CONCEPTS_AND_TERMINOLOGY.md|Quick reference for terminology"
  "appendix-b-architecture-decisions-complete|All ADRs organized thematically|Complete decision record reference"
  "appendix-c-command-line-reference|guides/CLI_USAGE.md|Quick CLI reference"
  "appendix-d-configuration-reference|All config guides|All configuration parameters in one place"
  "appendix-e-troubleshooting-index|Extract from all guides|Symptom to solution mapping"
  "appendix-f-project-roadmap|TODO.md + Proposed ADRs|Implementation timeline and status"
  "appendix-g-api-endpoint-reference|Cross-ref to section 37|HTTP API quick reference"
)

for appendix in "${appendices[@]}"; do
  IFS='|' read -r filename sources goal <<< "$appendix"

  title=$(echo "$filename" | sed 's/appendix-/Appendix /' | sed 's/-/ /g' | awk '{for(i=1;i<=NF;i++) $i=toupper(substr($i,1,1)) tolower(substr($i,2));}1')

  cat > "$filename.md" << EOF
# $title

**Status:** DRAFT
**Type:** Quick Reference

## Goal

$goal

## Source Materials

$sources

## TODO

- [ ] Consolidate source materials
- [ ] Organize for quick lookup
- [ ] Add cross-references

---

*This document is part of the Knowledge Graph System book-style documentation.*
EOF

  echo "Created: $filename.md"
done

echo ""
echo "Structure creation complete!"
echo "Total sections: 42 numbered + 7 appendices = 49 new files"
