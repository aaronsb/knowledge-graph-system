# Use Cases: Practical Workflows

This guide documents real-world use cases for the Knowledge Graph System, showing how to solve specific problems using multi-ontology ingestion, directory-based workflows, and cross-document analysis.

## Table of Contents

1. [GitHub Project History Analysis](#use-case-1-github-project-history-analysis)
2. [Future Use Cases](#future-use-cases)

---

## Use Case 1: GitHub Project History Analysis

**Problem:** Understanding a project's evolution through commits and pull requests, with the ability to query relationships between code changes, discussions, and contributor insights.

**Solution:** Extract GitHub data into structured documents, ingest as separate ontologies, and let the graph connect related concepts automatically.

### Overview

This workflow demonstrates:
- **Multi-source ingestion:** Commits and pull requests as separate data sources
- **Ontology organization:** Related data in separate but connected ontologies
- **Automatic concept linking:** The graph connects commits to PRs through shared concepts
- **Temporal analysis:** Query how ideas evolved over time
- **Contributor patterns:** Understand who worked on related concepts

### Workflow

#### Step 1: Extract GitHub Data

Use the GitHub CLI (`gh`) or GitHub API to extract commit history and pull requests.

**Extract commits:**
```bash
# Create directory structure
mkdir -p project_history/commits

# Extract commit history with metadata
gh api repos/{owner}/{repo}/commits --paginate --jq '.[] | {
  sha: .sha,
  author: .commit.author.name,
  email: .commit.author.email,
  date: .commit.author.date,
  message: .commit.message,
  url: .html_url
}' > commits.json

# Convert each commit to individual document
jq -c '.[]' commits.json | while read commit; do
  sha=$(echo "$commit" | jq -r '.sha' | cut -c1-7)
  author=$(echo "$commit" | jq -r '.author')
  date=$(echo "$commit" | jq -r '.date')
  message=$(echo "$commit" | jq -r '.message')
  url=$(echo "$commit" | jq -r '.url')

  cat > "project_history/commits/${sha}.txt" << EOF
Commit: ${sha}
Author: ${author}
Date: ${date}
URL: ${url}

${message}
EOF
done
```

**Extract pull requests:**
```bash
# Create directory
mkdir -p project_history/pull_requests

# Extract PR data with metadata
gh pr list --state all --limit 1000 --json number,title,author,body,createdAt,mergedAt,url \
  --jq '.[]' > prs.json

# Convert each PR to individual document
jq -c '.[]' prs.json | while read pr; do
  number=$(echo "$pr" | jq -r '.number')
  title=$(echo "$pr" | jq -r '.title')
  author=$(echo "$pr" | jq -r '.author.login')
  body=$(echo "$pr" | jq -r '.body // "No description"')
  created=$(echo "$pr" | jq -r '.createdAt')
  merged=$(echo "$pr" | jq -r '.mergedAt // "Not merged"')
  url=$(echo "$pr" | jq -r '.url')

  cat > "project_history/pull_requests/pr-${number}.txt" << EOF
Pull Request #${number}: ${title}
Author: ${author}
Created: ${created}
Merged: ${merged}
URL: ${url}

${body}
EOF
done
```

**Result:** Two directories containing individual documents:
```
project_history/
├── commits/
│   ├── abc1234.txt
│   ├── def5678.txt
│   └── ...
└── pull_requests/
    ├── pr-1.txt
    ├── pr-42.txt
    └── ...
```

#### Step 2: Ingest Commits (First)

Ingest the commits directory as the first ontology:

```bash
kg ingest directory project_history/commits \
  --ontology "commits" \
  --recurse \
  --pattern "*.txt"
```

**What happens:**
- Each commit becomes a source document
- LLM extracts concepts from commit messages and metadata
- Concepts like "bug fixes", "feature implementations", "refactoring" emerge
- Author names and patterns become discoverable concepts
- Relationships form between related commits (e.g., "fix for issue X" → "original feature Y")

**Example concepts extracted:**
- "Authentication System Refactor" (from commit 3f9a2b1)
- "API Server Architecture" (from commit c24c0fa)
- "Security Enhancement" (from commit 8b25dd6)
- "Documentation Update" (from commit 9d92ccd)

#### Step 3: Ingest Pull Requests (Second)

After commits are ingested, ingest pull requests:

```bash
kg ingest directory project_history/pull_requests \
  --ontology "pull_requests" \
  --recurse \
  --pattern "*.txt"
```

**What happens:**
- Each PR becomes a source document
- LLM extracts concepts from PR titles, descriptions, and discussions
- **Automatic linking:** When PR descriptions mention commits or concepts already in the graph, relationships form automatically
- PR concepts connect to related commit concepts through shared terminology

**Example automatic links:**
- PR #42 "Implement encrypted API keys" → links to commits about "ADR-031", "Security", "Encryption"
- PR #35 "Add job approval workflow" → links to commits about "ADR-014", "Job Queue", "Cost Estimation"

#### Step 4: Query the Connected Graph

Now you can query across both ontologies:

**Search for security-related work:**
```bash
kg search query "security encryption authentication"
```

**Result:** Concepts from BOTH commits and pull requests, automatically connected:
```
Found 12 concepts:

1. Encrypted API Key Storage (87.3%)
   Ontology: pull_requests
   Evidence: "Add Fernet encryption for API keys with container secrets"
   Related: 5 concepts from commits ontology

2. Security Enhancement (85.1%)
   Ontology: commits
   Evidence: "feat(ADR-031): Add service token authorization"
   Related: 3 concepts from pull_requests ontology

3. Authentication System (78.9%)
   Ontology: commits
   ...
```

**Find relationships between a PR and its commits:**
```bash
# Get PR concept ID
kg search query "encrypted API key storage" --ontology pull_requests

# Find related concepts
kg search related <pr-concept-id> --depth 2
```

**Result:** Shows the entire implementation journey:
```
Related concepts from: Encrypted API Key Storage (PR #42)

Distance 1 (direct relationships):
  • ADR-031 Implementation → [IMPLEMENTS]
  • Service Token Authorization → [PART_OF]
  • Fernet Encryption → [USES]

Distance 2 (indirect relationships):
  • Security Guide Documentation → [DOCUMENTS] → ADR-031 Implementation
  • API Server Architecture → [PART_OF] → Service Token Authorization
  • Job Queue System → [RELATED_TO] → ADR-031 Implementation
```

**Find contributor patterns:**
```bash
kg search query "aaron security"
```

**Result:** Discover all security-related work by a specific contributor across commits and PRs.

### What This Enables

#### 1. **Impact Analysis**
Query a concept and see all commits and PRs that touched it:
```bash
kg search query "job approval workflow"
→ See: ADR-014, implementation commits, related PRs, bug fixes
```

#### 2. **Temporal Understanding**
Trace how an idea evolved:
```bash
kg search details <concept-id>
→ Evidence shows: initial commit → PR discussion → refinement commits → docs
```

#### 3. **Contributor Insights**
Understand who worked on related areas:
```bash
kg search query "authentication rbac security"
→ Discovers: contributor A worked on auth, B worked on RBAC, both touched security
```

#### 4. **Refactoring Safety**
Before refactoring, query the history:
```bash
kg search query "api server architecture"
→ See: all related commits, PRs, discussions, and design decisions (ADRs)
```

#### 5. **Onboarding New Contributors**
New team member asks "How does the job queue work?"
```bash
kg search query "job queue approval workflow processing"
→ Returns: design doc (ADR-014), implementation PR, commits, and related concepts
```

#### 6. **Documentation Gaps**
Find implemented features without documentation:
```bash
# Search for features in commits
kg search query "encryption feature" --ontology commits

# Check if documented
kg search query "encryption feature" --ontology pull_requests

# Missing PR = potential documentation gap
```

### Tips and Best Practices

#### Ingestion Order Matters
**Always ingest commits FIRST, then pull requests.** Why?
- Commits are atomic units of work (smaller, focused)
- PRs reference commits and aggregate changes
- The graph builds from specific (commits) to general (PRs)
- Automatic linking works better this way

#### Document Naming Conventions
Use descriptive filenames that become searchable:
- **Good:** `abc1234-add-encryption-support.txt`
- **Bad:** `abc1234.txt`

Include commit SHA prefix in filename for easy traceability.

#### Metadata is Gold
Include structured metadata at the top of each document:
```
Commit: abc1234
Author: Jane Developer
Date: 2025-10-13
Tags: security, encryption, api
Related: ADR-031

[commit message and details...]
```

The LLM extracts this metadata as searchable concepts.

#### Incremental Updates
You don't need to re-ingest the entire history. Add new commits/PRs incrementally:

```bash
# Extract only recent commits (last 30 days)
gh api repos/{owner}/{repo}/commits \
  --jq '.[] | select(.commit.author.date > "2025-09-15")' \
  > recent_commits.json

# Convert and ingest
[...extraction process...]

kg ingest directory project_history/commits \
  --ontology "commits" \
  --recurse
```

The graph automatically deduplicates if a commit already exists.

#### Pattern Variations
Experiment with different patterns:

**By component:**
```
project_history/
├── frontend_commits/
├── backend_commits/
├── infrastructure_commits/
└── pull_requests/
```

**By time period:**
```
project_history/
├── 2024_q4_commits/
├── 2025_q1_commits/
└── pull_requests/
```

**By feature:**
```
project_history/
├── auth_system/
├── job_queue/
└── api_endpoints/
```

Each directory becomes an ontology, enabling targeted queries.

### Cost Considerations

**Estimation before ingestion:**

```bash
# Count documents
find project_history -type f -name "*.txt" | wc -l
→ 156 files

# Estimate: ~1000 words per commit/PR average
# Chunks: 156 documents ÷ ~1 chunk each = ~156 chunks
# LLM calls: 156 chunks × 2 (extraction + embedding) = 312 API calls
# Cost: ~$0.50 - $2.00 (depending on provider and model)
```

Use `--dry-run` to preview:
```bash
kg ingest directory project_history/commits --ontology "commits" --dry-run
→ Shows: files to ingest, estimated chunks, no actual ingestion
```

### Limitations and Gotchas

#### 1. **Large Repositories**
For repos with thousands of commits, consider:
- Time-bound extraction (last N months)
- Focus on main branch only
- Filter by file paths (e.g., only `/src` changes)

#### 2. **Binary Commits**
Commits that only modify binary files have limited value:
- Filter to commits with actual code/text changes
- Focus on commits with meaningful messages

#### 3. **Bot Commits**
Automated commits (e.g., version bumps, CI) add noise:
- Filter by author: exclude bots
- Use `--pattern` to ignore certain file types

#### 4. **PR Body Parsing**
GitHub PR bodies use markdown and may include:
- Code blocks (useful!)
- Checkboxes (task lists)
- References to other PRs/issues

The LLM handles these well, but very long PRs may be chunked.

### Advanced: Connecting to Issues and Discussions

Extend this workflow to include GitHub Issues and Discussions:

```bash
# Extract issues
mkdir -p project_history/issues
gh issue list --state all --limit 500 --json number,title,body,author \
  --jq '.[]' > issues.json

# Convert to documents (same pattern as commits/PRs)
[...conversion process...]

# Ingest
kg ingest directory project_history/issues --ontology "issues" --recurse
```

Now you have a complete project knowledge graph:
- **commits** (what changed)
- **pull_requests** (why it changed)
- **issues** (what problems existed)

Query across all three:
```bash
kg search query "authentication bug user login"
→ Returns: bug report (issue #34), fix commits, and the PR that closed it
```

### Example Query Session

Here's a real query session after ingesting this project's history:

```bash
# What security work has been done?
$ kg search query "security authentication encryption" --limit 5

Found 8 concepts:

1. Encrypted API Key Storage (91.2%)
   Ontologies: pull_requests, commits
   Evidence: 7 instances
   Relationships: 12 related concepts

2. Service Token Authorization (86.7%)
   Ontologies: commits
   Evidence: 3 instances
   Relationships: 5 related concepts

3. JWT Authentication System (84.3%)
   Ontologies: pull_requests
   ...

# Get details on the encryption implementation
$ kg search details encrypted_api_key_storage_<id>

Label: Encrypted API Key Storage
Ontologies: pull_requests, commits
Evidence (7 instances):

1. PR #42 (pull_requests):
   "Implements ADR-031 with Fernet encryption, container secrets,
    and service token authorization for API key management."

2. Commit 8b25dd6 (commits):
   "docs: Add comprehensive security guide (ADR-031)"

3. Commit 2da61a9 (commits):
   "feat(ADR-031): Add service token authorization and worker concurrency"

Relationships (12):
  → IMPLEMENTS → ADR-031 Architecture Decision
  → USES → Fernet Encryption Algorithm
  → PART_OF → API Server Security
  → REQUIRES → Container Secrets
  ...

# Trace the implementation journey
$ kg search related encrypted_api_key_storage_<id> --depth 2

Related concepts:

Distance 1:
  • ADR-031 Architecture Decision [IMPLEMENTS]
  • Security Guide Documentation [DOCUMENTS]
  • API Key Management [PART_OF]

Distance 2:
  • RBAC System [RELATED_TO] → Security Guide Documentation
  • Database Credentials [SIMILAR_TO] → API Key Management
  • Documentation Index Update [FOLLOWS] → Security Guide Documentation
```

This shows the entire implementation lifecycle: design decision → code → documentation → related systems.

---

## Future Use Cases

Additional use cases to be documented:

### Use Case 2: Research Paper Analysis
Ingest related papers as separate ontologies, discover connections between research threads.

### Use Case 3: Legal Document Comparison
Multiple versions of contracts or regulations, track changes and concept evolution.

### Use Case 4: Knowledge Base Migration
Ingest existing documentation sets, find gaps and redundancies.

### Use Case 5: Meeting Notes and Project Docs
Combine meeting transcripts with technical documentation for complete project context.

---

## Contributing Use Cases

Have you developed a novel workflow? Contribute it here:

1. Document the problem and solution
2. Provide step-by-step commands
3. Show example queries and results
4. Include tips and limitations
5. Submit a PR with your use case added to this guide

---

**Last Updated:** 2025-10-14

**Related Documentation:**
- [INGESTION.md](INGESTION.md) - Detailed ingestion configuration
- [EXAMPLES.md](EXAMPLES.md) - Query examples and results
- [CLI_USAGE.md](CLI_USAGE.md) - Complete CLI command reference
