# Git Repository Knowledge Graph

Extract and conceptify your git repository's commit messages and GitHub pull requests into a knowledge graph.

## Quick Start

```bash
cd examples/use-cases/git-repo-knowledge

# See what's available
./github.sh

# Preview what would be extracted
./github.sh preview

# Extract and ingest a batch
./github.sh run

# Or YOLO everything at once
./github.sh run --all
```

That's it! The script handles Python setup, dependencies, extraction, and ingestion automatically.

## Commands

```bash
./github.sh                     # Show help
./github.sh preview             # See what would be extracted (dry run)
./github.sh run                 # Extract + ingest next batch (50 per type)
./github.sh run --all           # YOLO: Extract + ingest EVERYTHING
./github.sh run --prs           # Only PRs
./github.sh run --commits       # Only commits
./github.sh run --limit 100     # Custom batch size
./github.sh status              # Show current progress
./github.sh reset               # Start over from beginning
./github.sh clean               # Remove output files
```

## What This Does

1. **Extracts commit messages** - From oldest to newest, with metadata (hash, author, date)
2. **Extracts GitHub PRs** - Descriptions, labels, stats (requires `gh` CLI)
3. **Converts to markdown** - With frontmatter for metadata
4. **Ingests to knowledge graph** - Concepts extracted, relationships formed
5. **Tracks progress** - Each run continues where the last left off

## Why This Matters

When combined with ADRs and design docs, your knowledge graph enables:

- **Decision evolution:** See how decisions changed over time
- **Context preservation:** Understand WHY changes were made
- **Contradiction detection:** Grounding system identifies when commits contradict earlier decisions
- **Semantic search:** Find relevant commits/PRs by concept, not just keywords
- **Cross-referencing:** Connect commits to ADRs, PRs to design decisions

## Example Queries

After ingestion:

```bash
# Find commits related to a concept
kg search query "authentication implementation"

# See grounding scores for concepts
kg search details <concept-id>

# Find connections between commits and ADRs
kg search connect "JWT authentication" "RBAC system"
```

## Incremental Updates

Progress is tracked in `config.json`. Running again only processes NEW items:

```bash
# Check current progress
./github.sh status

# Process next batch
./github.sh run

# Reset to start over
./github.sh reset
```

## File Structure

```
git-repo-knowledge/
├── github.sh              # Main entry point (all operations)
├── config.json            # Configuration and progress tracking
├── extract_commits.py     # Commit extractor (called by github.sh)
├── extract_prs.py         # PR extractor (called by github.sh)
├── requirements.txt       # Python dependencies
└── output/                # Generated markdown files (temporary)
    ├── commits/
    └── prs/
```

## Requirements

**Automatically handled:**
- Python 3.11+ virtual environment
- `gitpython` library

**Manual prerequisites:**
- `kg` CLI - Install from `client/` directory
- `jq` - JSON processor (`sudo apt install jq` or `brew install jq`)
- Knowledge graph API running (`http://localhost:8000`)

**Optional (for PR extraction):**
- `gh` CLI - [cli.github.com](https://cli.github.com)
- Run `gh auth login` once to authenticate

## Configuration

Edit `config.json` to customize:

```json
{
  "repositories": [
    {
      "name": "knowledge-graph-system",
      "path": "../../..",
      "ontology": "KG System Development",
      "github_repo": "aaronsb/knowledge-graph-system",
      "enabled": true
    }
  ],
  "commit_limit": 50,
  "pr_limit": 50
}
```

- **path**: Relative or absolute path to git repository
- **ontology**: Base name for ontologies (commits get `-Commits`, PRs get `-PRs` suffix)
- **github_repo**: `owner/repo` for PR extraction
- **commit_limit/pr_limit**: Default batch sizes

## Generated Markdown

### Commit Format

```markdown
---
type: commit
hash: f6dfce3a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e
short_hash: f6dfce3
author: Aaron Barnes
date: 2025-10-26
repository: knowledge-graph-system
ontology: KG System Development-Commits
---

# Commit: fix: correct ADR dates

Fixed date formatting issue where dates were incorrectly written...
```

### PR Format

```markdown
---
type: pull_request
number: 66
title: "Grounding & Reliability System"
author: aaronsb
state: MERGED
merged: True
repository: knowledge-graph-system
ontology: KG System Development-PRs
---

# Pull Request #66: Grounding & Reliability System

## Description
Implementation of probabilistic truth convergence...
```

## Use Cases

1. **Project Documentation** - Build complete knowledge from ADRs + commits + PRs
2. **Onboarding** - New team members search for decision context
3. **Code Archaeology** - "Why did we switch from Neo4j to Apache AGE?"
4. **Release Notes** - Query commits/PRs by date range with semantic filtering

## Tips

1. **Ingest ADRs first** - Provides context for commit/PR concepts
2. **Use descriptive commits** - Better messages = better concepts
3. **Run incrementally** - Daily/weekly to keep current
4. **Start small** - Use `--limit 20` for initial testing

---

**Related:** See [Code Intelligence Platforms Comparison](../../../docs/research/code-intelligence-platforms-comparison.md) for how this fits into the broader code intelligence ecosystem.
