# Git Repository Knowledge Graph

Extract and conceptify your git repository's commit messages and GitHub pull requests into a knowledge graph.

## What This Does

This use case demonstrates how to build a knowledge graph from your development history:

1. **Extracts commit messages** with metadata (hash, author, date, time)
2. **Extracts GitHub pull requests** with descriptions and metadata
3. **Converts to markdown files** with frontmatter
4. **Ingests into knowledge graph** with consistent ontology naming
5. **Conceptifies the content** - commit/PR messages become concepts with relationships
6. **Grounds the knowledge** - grounding system identifies contradictions and evolution

## Why This Matters

When combined with other documentation (ADRs, design docs), your knowledge graph contains:

- **Decision evolution:** See how decisions changed over time
- **Context preservation:** Understand WHY changes were made
- **Contradiction detection:** Grounding system identifies when commits contradict earlier decisions
- **Semantic search:** Find relevant commits/PRs by concept, not just keywords
- **Cross-referencing:** Connect commits to ADRs, PRs to design decisions

## Example Output

After ingestion, you can query:

```bash
# Find commits related to a concept
kg search query "authentication implementation"

# See grounding scores for commit-related concepts
kg search details <concept-id>

# Find connections between commits and ADRs
kg search connect "JWT authentication commit" "ADR-028 RBAC system"
```

## Quick Start

### 1. Configure Repository

Edit `config.json` to point to your git repository:

```json
{
  "repositories": [
    {
      "name": "knowledge-graph-system",
      "path": "/home/aaron/Projects/ai/knowledge-graph-system",
      "ontology": "KG System Development",
      "last_commit": null,
      "last_pr": null,
      "github_repo": "aaronsb/knowledge-graph-system"
    }
  ]
}
```

### 2. Extract Commits and PRs

```bash
# Extract all commit messages to markdown
python extract_commits.py

# Extract GitHub pull requests to markdown
python extract_prs.py
```

This creates markdown files in `output/commits/` and `output/prs/`.

### 3. Ingest into Knowledge Graph

```bash
# Ingest all commits and PRs
./ingest.sh
```

This ingests all markdown files into the knowledge graph with the configured ontology name.

### 4. Query the Knowledge Graph

```bash
# Search for concepts from commits
kg search query "migration to Apache AGE"

# View grounding scores
kg database stats
```

## Incremental Updates

The config.json tracks the last processed commit and PR. Running the extraction scripts again will only process new items:

```bash
# Extract only new commits since last run
python extract_commits.py

# Extract only new PRs since last run
python extract_prs.py

# Ingest new documents
./ingest.sh
```

## File Structure

```
git-repo-knowledge/
├── README.md              - This file
├── config.json            - Repository configuration and pointers
├── extract_commits.py     - Extract commit messages to markdown
├── extract_prs.py         - Extract GitHub PRs to markdown
├── ingest.sh              - Ingest markdown files to knowledge graph
└── output/
    ├── commits/           - Generated commit markdown files
    └── prs/               - Generated PR markdown files
```

## Commit Markdown Format

Each commit becomes a markdown file with frontmatter:

```markdown
---
type: commit
hash: f6dfce3a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e
short_hash: f6dfce3
author: Aaron Barnes
email: aaron@example.com
date: 2025-10-26
time: 14:23:45
repository: knowledge-graph-system
ontology: KG System Development
---

# Commit: fix: correct ADR dates from 2025-01-* to 2025-10-*

Fixed date formatting issue where dates were incorrectly written as 2025-01-09,
2025-01-24, and 2025-01-25 instead of 2025-10-09, 2025-10-24, and 2025-10-25.

All ADRs were created in October 2025, not January 2025.

Files updated:
- ADR-019-type-based-table-formatting.md
- ADR-044-probabilistic-truth-convergence.md
...
```

## PR Markdown Format

Each pull request becomes a markdown file:

```markdown
---
type: pull_request
number: 66
title: "Grounding & Reliability System"
author: aaronsb
state: merged
created: 2025-10-24
merged: 2025-10-25
repository: knowledge-graph-system
ontology: KG System Development
---

# Pull Request #66: Grounding & Reliability System

Implementation of probabilistic truth convergence for timeless knowledge graphs.

## Description
This PR implements ADR-044, ADR-045, and ADR-046...

## Changes
- Grounding strength calculation
- Unified embedding generation
- Grounding-aware vocabulary management
...
```

## Use Cases

### 1. Project Documentation
Build a complete knowledge graph of your project including:
- Architecture Decision Records (ADRs)
- Commit messages
- Pull request descriptions
- Design documents

### 2. Onboarding
New team members can:
- Search for context on why decisions were made
- Trace evolution of features
- Understand contradictions and pivots

### 3. Code Archaeology
Answer questions like:
- "Why did we switch from Neo4j to Apache AGE?"
- "What commits relate to the RBAC implementation?"
- "Which PRs contradict earlier authentication approaches?"

### 4. Release Notes
Generate release notes by querying commits and PRs in a date range with semantic filtering.

## Requirements

- Python 3.11+
- `gitpython` library: `pip install gitpython`
- `PyGithub` library: `pip install PyGithub`
- GitHub personal access token (for PR extraction)
- Knowledge graph system running

## Configuration

### GitHub Token

For PR extraction, set your GitHub token:

```bash
export GITHUB_TOKEN="ghp_your_token_here"
```

Or add to `.env` file in repository root.

### Repository Path

The repository path in `config.json` can be:
- Absolute path: `/full/path/to/repo`
- Relative path: `../../other-repo`
- Current repo: `.` (for self-documentation)

## Advanced Usage

### Custom Ontology Names

Each repository can have its own ontology name. This allows:
- Separating different projects
- Querying across projects
- Comparing evolution patterns

### Filtering Commits

Edit `extract_commits.py` to filter commits:
- By date range
- By author
- By file paths
- By commit message pattern

### Filtering PRs

Edit `extract_prs.py` to filter PRs:
- By state (open, closed, merged)
- By labels
- By date range
- By author

## Tips

1. **Start with recent commits:** Set `last_commit` to go back only 100 commits for initial testing
2. **Use descriptive commit messages:** The better your commit messages, the better the concepts extracted
3. **Ingest ADRs first:** This provides context for commit/PR concepts
4. **Run incrementally:** Extract and ingest daily/weekly to keep knowledge graph current
5. **Query iteratively:** Use semantic search to discover unexpected connections

## Future Enhancements

- [ ] Extract commit diffs (code changes) as additional context
- [ ] Link commits to file paths mentioned in ADRs
- [ ] Visualize commit→PR→ADR relationships
- [ ] Detect contradictions between commits and documentation
- [ ] Generate timeline visualization of decision evolution
- [ ] Support GitLab, Bitbucket (not just GitHub)

## Example: Self-Documentation

For this repository itself:

```bash
cd examples/use-cases/git-repo-knowledge
python extract_commits.py  # Extracts all commits from this repo
python extract_prs.py      # Extracts all PRs (e.g., PR #66)
./ingest.sh                # Ingests into "KG System Development" ontology

# Now query your own development history!
kg search query "grounding system implementation"
kg search connect "ADR-044" "Pull Request 66"
```

---

**This use case demonstrates:** Knowledge graph construction from unstructured development artifacts, semantic search across commits/PRs/docs, and contradiction detection in evolving decisions.
