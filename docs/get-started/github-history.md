---
id: 3.T.02
domain: ingest
mode: tutorial
---

# Mining a Git Repository

This tutorial walks through ingesting a GitHub repository's commit and pull-request history into Kappa Graph, so you can query why decisions were made and trace how features evolved.

## What you need

- Kappa Graph running (`./operator.sh status`)
- The `kg` CLI installed and connected
- The GitHub CLI (`gh`) installed and authenticated

Install `gh` if you do not have it:

```bash
# macOS
brew install gh

# Linux — https://github.com/cli/cli/blob/trunk/docs/install_linux.md

# Authenticate
gh auth login

# Confirm access
gh repo view
```

## Step 1: Extract commits and pull requests

Create a directory structure to hold the extracted documents, then pull the data from GitHub.

**Extract commits:**

```bash
mkdir -p project_history/commits

gh api repos/{owner}/{repo}/commits --paginate --jq '.[] | {
  sha: .sha,
  author: .commit.author.name,
  email: .commit.author.email,
  date: .commit.author.date,
  message: .commit.message,
  url: .html_url
}' > commits.json

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
mkdir -p project_history/pull_requests

gh pr list --state all --limit 1000 \
  --json number,title,author,body,createdAt,mergedAt,url \
  --jq '.[]' > prs.json

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

You now have two directories, each containing one document per item:

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

## Step 2: Ingest commits first

Ingest the commits directory as its own ontology. Commits are the atomic units — ingest them before pull requests so the graph has a base of specific concepts to link against.

```bash
kg ingest directory project_history/commits \
  --ontology "commits" \
  --pattern "*.txt"
```

The LLM extracts concepts from each commit message: feature areas, authors, referenced ADRs, change types. Relationships form between commits that share terminology even without explicit cross-references.

Preview first with `--dry-run` to see how many chunks and what the cost estimate is before approving:

```bash
kg ingest directory project_history/commits \
  --ontology "commits" \
  --pattern "*.txt" \
  --dry-run
```

## Step 3: Ingest pull requests

After commits are ingested, ingest pull requests as a second ontology:

```bash
kg ingest directory project_history/pull_requests \
  --ontology "pull_requests" \
  --pattern "*.txt"
```

When a PR description references concepts already in the graph — commit SHAs, ADR numbers, feature names — the graph links them automatically. No manual tagging is needed.

## Step 4: Query the connected graph

Search across both ontologies with a single query:

```bash
kg search query "security encryption authentication"
```

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
```

Find relationships at depth to trace the implementation journey of a concept:

```bash
# Locate the concept ID
kg search query "encrypted API key storage" --ontology pull_requests

# Traverse two hops out
kg search related <concept-id> --depth 2
```

```
Distance 1 (direct relationships):
  • ADR-031 Implementation → [IMPLEMENTS]
  • Service Token Authorization → [PART_OF]
  • Fernet Encryption → [USES]

Distance 2 (indirect relationships):
  • Security Guide Documentation → [DOCUMENTS] → ADR-031 Implementation
  • API Server Architecture → [PART_OF] → Service Token Authorization
```

## What you can query

| Goal | Query |
|---|---|
| All work touching a feature | `kg search query "job approval workflow"` |
| How a concept evolved over time | `kg search details <concept-id>` — evidence is ordered chronologically |
| Contributor expertise | `kg search query "authentication rbac <name>"` |
| Pre-refactor impact | `kg search query "api server architecture"` |
| Features that may lack documentation | compare results across `--ontology commits` vs `--ontology pull_requests` |

## Extending to issues

The same pattern works for GitHub Issues:

```bash
mkdir -p project_history/issues

gh issue list --state all --limit 500 \
  --json number,title,body,author \
  --jq '.[]' > issues.json

# Convert with the same document pattern as commits/PRs

kg ingest directory project_history/issues --ontology "issues"
```

With commits, pull requests, and issues all ingested, a query like `"authentication bug user login"` returns the bug report, the fix commits, and the PR that closed it.

## Incremental updates

Re-ingestion deduplicates automatically. To add only recent commits:

```bash
gh api repos/{owner}/{repo}/commits \
  --jq '.[] | select(.commit.author.date > "2026-01-01")' \
  > recent_commits.json

# Convert to documents, then ingest the commits directory again
kg ingest directory project_history/commits \
  --ontology "commits"
```

## Tips

**Metadata improves extraction.** The structured header lines (`Commit:`, `Author:`, `Date:`) become searchable concepts. Enriching filenames helps too — `abc1234-add-encryption-support.txt` is more useful than `abc1234.txt`, because the filename itself is part of what the LLM sees.

**Large repositories.** For repos with thousands of commits, extract a time-bounded slice first (`select(.commit.author.date > "...")`) or filter to a specific branch. Bot commits (version bumps, CI automation) add noise — filter them by author before converting.

**Organize by component or time.** Each directory becomes a separate ontology. Splitting by component (`frontend_commits/`, `backend_commits/`) or quarter (`2025_q4_commits/`) enables targeted queries scoped to one ontology while still traversing cross-ontology edges.
