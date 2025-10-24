# 07 - Real World Example: Project History Analysis

**Part:** I - Foundations
**Reading Time:** ~12 minutes
**Prerequisites:** [Section 03 - Quick Start](03-quick-start-your-first-knowledge-graph.md), [Section 06 - Querying Your Knowledge Graph](06-querying-your-knowledge-graph.md)

---

This section shows the knowledge graph system working with real data: analyzing a software project's git history to understand architectural decisions, track feature evolution, and discover connections between commits and pull requests.

## The Scenario

You maintain a software project with 280 commits and 60 pull requests spread across 8 months of development. The repository contains:

- Architecture decision records (ADRs)
- Implementation commits
- Pull request discussions
- Documentation updates
- Bug fixes and refactors

**The problem:** New team members ask "why did we implement it this way?" Existing team members can't remember all the context from months ago. The project's narrative is scattered across git history.

**The solution:** Extract commit messages and PR descriptions into a knowledge graph, then query it semantically.

**The power multiplier:** When coupling this ingested data with a coding agent that has MCP server access to the graph (Claude Code, Cline, Copilot, etc.), it becomes an extremely powerful concept accelerator. The agent can query precise relationships and architectural decisions directly from the knowledge graph, reducing context consumption and often providing higher accuracy than built-in search systems that rely on text similarity alone.

---

## Step 1: Extracting Git History

Use the GitHub CLI to export commits and pull requests as text documents.

**Extract recent commits:**

```bash
mkdir -p project_history/commits

gh api repos/owner/repo/commits --paginate | \
  jq -r '.[] | "\(.sha[0:7])\t\(.commit.author.name)\t\(.commit.message)"' | \
  while IFS=$'\t' read sha author message; do
    cat > "project_history/commits/${sha}.txt" << EOF
Commit: ${sha}
Author: ${author}

${message}
EOF
  done
```

**Extract pull requests:**

```bash
mkdir -p project_history/pull_requests

gh pr list --state all --limit 100 --json number,title,author,body | \
  jq -c '.[]' | \
  while read pr; do
    number=$(echo "$pr" | jq -r '.number')
    title=$(echo "$pr" | jq -r '.title')
    author=$(echo "$pr" | jq -r '.author.login')
    body=$(echo "$pr" | jq -r '.body // "No description"')

    cat > "project_history/pull_requests/pr-${number}.txt" << EOF
Pull Request #${number}: ${title}
Author: ${author}

${body}
EOF
  done
```

**Result:** Two directories with individual text files, ready for ingestion.

```
project_history/
├── commits/
│   ├── a1b2c3d.txt  (280 files)
│   └── ...
└── pull_requests/
    ├── pr-1.txt     (60 files)
    └── ...
```

---

## Step 2: Ingest Commits First

```bash
kg ingest file project_history/commits/*.txt \
  --ontology "Project Commits" \
  --yes
```

The system processes each commit:

- Extracts concepts from commit messages
- Identifies patterns ("authentication," "job queue," "security")
- Links related commits through shared concepts
- Creates evidence instances with commit metadata

**Processing output:**

```
Ingesting 280 documents into ontology "Project Commits"

Processing: a1b2c3d.txt (1/280)
  Extracted: 3 concepts, 2 relationships
Processing: b4c5d6e.txt (2/280)
  Extracted: 2 concepts, 1 relationship, 1 merged with existing
...
Processing: x7y8z9a.txt (280/280)
  Extracted: 4 concepts, 3 relationships

✓ Ingestion complete!
  Concepts created: 847
  Concepts updated: 412 (merged with existing)
  Relationships: 1,103
  Duration: 11m 23s
  Cost: $1.47
```

---

## Step 3: Ingest Pull Requests

After commits are in the graph, ingest pull requests:

```bash
kg ingest file project_history/pull_requests/*.txt \
  --ontology "Project Pull Requests" \
  --yes
```

**What happens:**

The LLM reads PR descriptions and notices phrases like "implements ADR-031" or "adds job approval workflow." These match existing concepts from commits, so the graph automatically links them.

**Processing output:**

```
Ingesting 60 documents into ontology "Project Pull Requests"

Processing: pr-1.txt (1/60)
  Extracted: 5 concepts, 2 relationships
  Linked to existing: "Apache AGE Migration" from commits
Processing: pr-42.txt (42/60)
  Extracted: 3 concepts, 4 relationships
  Linked to existing: "Encrypted API Key Storage", "Security Enhancement"
...

✓ Ingestion complete!
  Concepts created: 203
  Concepts updated: 147 (linked to commits)
  Relationships: 289
  Cross-ontology links: 67
  Duration: 3m 41s
  Cost: $0.51
```

The graph now contains 1,050 concepts connected by 1,392 relationships across two ontologies.

---

## Step 4: Query the Graph

Now you can ask questions about your project's history.

### Find Security-Related Work

```bash
kg search query "security encryption authentication"
```

**Returns:**

```
Found 15 concepts:

1. Encrypted API Key Storage (similarity: 0.91)
   ID: encrypted-api-key-storage
   Ontologies: Project Pull Requests, Project Commits
   Evidence: 7 instances
   Related: 9 concepts

2. Service Token Authorization (similarity: 0.88)
   ID: service-token-authorization
   Ontologies: Project Commits
   Evidence: 4 instances
   Related: 5 concepts

3. Security Enhancement (similarity: 0.85)
   ID: security-enhancement
   Ontologies: Project Commits
   Evidence: 3 instances
   Related: 6 concepts

...
```

Notice concepts appear in BOTH ontologies - the graph automatically connected commits and PRs discussing the same topics.

### Trace a Feature from Idea to Implementation

```bash
kg search details encrypted-api-key-storage
```

**Returns:**

```
Concept: Encrypted API Key Storage
ID: encrypted-api-key-storage

Search Terms:
  - API key encryption
  - Fernet encryption
  - secret management
  - container secrets

Relationships:
  IMPLEMENTS → ADR-031 Service Tokens (confidence: 0.93)
  PART_OF → Security Enhancement (confidence: 0.89)
  USES → Fernet Encryption Algorithm (confidence: 0.87)
  PRECEDED_BY → Initial Security Design (confidence: 0.82)

Evidence (7 instances):

  1. "Add Fernet encryption for API keys stored in containers"
     Source: PR #42, Project Pull Requests

  2. "feat(ADR-031): Implement encrypted API key storage with container secrets"
     Source: commit c3f9a2b, Project Commits

  3. "Store API keys using Fernet symmetric encryption before writing to disk"
     Source: commit d4a8b1c, Project Commits

  4. "Validate encrypted keys can be decrypted on server restart"
     Source: commit e5b9c2d, Project Commits

  5. "Document encryption key rotation procedure"
     Source: commit f6c0d3e, Project Commits

  6. "Update security guide with API key encryption details"
     Source: commit g7d1e4f, Project Commits

  7. "Test encrypted key storage with Docker secrets"
     Source: commit h8e2f5g, Project Commits
```

You can trace the entire journey:
1. The design decision (ADR-031)
2. The PR proposing implementation (#42)
3. The actual implementation commits
4. Related documentation updates
5. Testing and validation

### Find What Connects Two Features

```bash
kg search connect job-approval-workflow encrypted-api-key-storage
```

**Returns:**

```
Path found (3 hops):

  Job Approval Workflow
    → [PART_OF] Cost Estimation System
    → [REQUIRES] Secure Configuration Storage
    → [IMPLEMENTED_BY] Encrypted API Key Storage

Supporting evidence:
  - "Approval workflow requires cost estimates from API" (Job Approval Workflow)
  - "Cost estimates need secure API key storage" (Cost Estimation System)
  - "API keys stored with Fernet encryption" (Encrypted API Key Storage)
```

Non-obvious connection: The job approval feature depends on cost estimation, which requires secure API keys. The graph discovered this relationship automatically.

### Find Who Worked on Authentication

```bash
kg search query "authentication oauth tokens"
```

Pick a concept:

```bash
kg search details service-token-authorization
```

**Returns:**

```
...
Evidence (4 instances):

  1. "feat(ADR-031): Add service token authorization for multi-client deployments"
     Source: commit c24c0fa, Project Commits
     Author: Alice (from commit metadata)

  2. "Implement token validation in API middleware"
     Source: commit d35d1ab, Project Commits
     Author: Bob

  3. "Add service token authentication guide to documentation"
     Source: commit e46e2bc, Project Commits
     Author: Alice

  4. "Refactor token validation for better error messages"
     Source: commit f57f3cd, Project Commits
     Author: Carol
```

Alice designed it, Bob and Carol implemented different parts. The graph shows collaboration patterns.

### Find Undocumented Features

```bash
# Search in commits
kg search query "job queue implementation" --ontology "Project Commits"
```

Returns 8 concepts about job queue work.

```bash
# Search in pull requests
kg search query "job queue implementation" --ontology "Project Pull Requests"
```

Returns 2 concepts - fewer than expected. Check which commits lack PR documentation:

```bash
kg search details job-queue-processing
```

If evidence shows commits but no PR, that feature might lack high-level documentation.

---

## What This Reveals

### Architecture Evolution

Query "apache age migration" to see:
- Initial Neo4j design (early commits)
- Performance issues discovered (bug fix commits)
- Decision to migrate (ADR-016)
- Migration implementation (PR #28)
- Post-migration refinements (multiple commits)

The graph shows WHY the decision was made and HOW it was executed.

### Feature Dependencies

Query any feature and explore relationships:
- What does it REQUIRE?
- What does it ENABLE?
- What PRECEDED it?
- What was IMPLEMENTED_BY commits?

This reveals implicit dependencies not documented elsewhere.

### Team Patterns

Search for concepts and check evidence authors:
- "Security" → mostly Alice and Bob
- "Frontend" → mostly Carol
- "Database" → Alice, Bob, Dave

Useful for onboarding and resource planning.

### Temporal Analysis

Evidence instances include timestamps. You can see:
- When concepts first appeared
- How often they're mentioned over time
- Whether they're still active or legacy

---

## Practical Queries for Daily Work

### Before Refactoring

```bash
kg search query "api server architecture"
```

Returns all commits, PRs, and decisions related to API server structure. Read the evidence before making changes.

### When Reviewing Code

```bash
# Reviewer sees a PR about "rate limiting"
kg search query "rate limiting throttling"
```

Returns previous work on the same topic. Check if the new PR is consistent with past decisions.

### For Onboarding

```bash
# New developer asks "how does auth work?"
kg search query "authentication authorization security"
```

Returns the design decision, implementation commits, tests, and documentation in one query.

### Finding Similar Past Work

```bash
# About to implement "webhook retries"
kg search query "retry logic error handling"
```

Returns past retry implementations. Reuse patterns that worked.

---

## Cost and Effort

**Initial ingestion:**
- 280 commits + 60 PRs = 340 documents
- ~10 minutes processing time
- ~$2.00 in API costs (GPT-4o)

**Incremental updates:**
- Add new commits weekly: ~5-20 documents
- ~1 minute processing
- ~$0.10 per update

**Value:**
- Instant access to 8 months of context
- Discover connections impossible to find manually
- Onboard new developers faster
- Avoid repeating past mistakes

---

## Limitations

**Commit message quality matters:** "fix bug" extracts poorly. "Fix authentication token expiration edge case" extracts well.

**PR descriptions matter:** Empty PR bodies provide no context. Descriptive PRs create rich concepts.

**Extraction isn't perfect:** The LLM might miss connections or create false positives. Confidence scores help identify uncertain relationships.

**Not a replacement for documentation:** The graph helps navigate existing documentation, not replace it. Well-documented projects extract better.

---

## Tips for Better Results

**Write descriptive commit messages:**

```
# Poor
git commit -m "fix"

# Good
git commit -m "fix: Handle token refresh race condition in auth middleware"
```

**Write PR descriptions:**

Include context, motivation, and implementation details. The LLM extracts these as concepts.

**Reference ADRs and issues:**

Mention "implements ADR-031" or "fixes #123" in commits and PRs. The graph links them automatically.

**Extract incrementally:**

Don't wait until you have 1000 commits. Start early and update weekly.

**Query early and often:**

The more you query, the better you understand what concepts exist and how they connect.

---

## What's Next

Now that you've seen the system with real data, you can:

- **[Section 08 - Choosing Your AI Provider](08-choosing-your-ai-provider.md)**: Compare LLMs for extraction quality
- **[Section 09 - Common Workflows and Use Cases](09-common-workflows-and-use-cases.md)**: More practical workflows

For deeper case studies:
- **[Section 60 - Case Study: Multi-Perspective Enrichment](60-case-study-multi-perspective-enrichment.md)**: 280 commits analyzed in depth
- **[Section 61 - Case Study: GitHub Project History](61-case-study-github-project-history.md)**: Complete workflow with scripts

---

← [Previous: Querying Your Knowledge Graph](06-querying-your-knowledge-graph.md) | [Documentation Index](README.md) | [Next: Choosing Your AI Provider →](08-choosing-your-ai-provider.md)
