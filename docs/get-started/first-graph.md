---
id: 03.003.T
domain: ingest
mode: tutorial
---

# Your First Graph

This tutorial walks you through installing the `kg` CLI, connecting to a running Kappa Graph platform, ingesting your first document, and viewing the concepts extracted from it.

**Prerequisites:**

- Node.js 20.12.0 or later
- A running Kappa Graph platform (local or remote). If you need to deploy one, see [Quick Start](../self-host/quick-start.md).
- Your API URL and admin credentials from installation.

---

## Step 1: Install the CLI

```bash
npm install -g @aaronsb/kg-cli
```

Verify it installed:

```bash
kg --version
```

---

## Step 2: Point the CLI at your API

```bash
kg config set api_url http://localhost:8000
```

Replace `http://localhost:8000` with your API URL. For a production install, that is typically `https://your-hostname/api`.

---

## Step 3: Log in

```bash
kg login
```

The CLI prompts for your username and password, then creates a personal OAuth client and stores the credentials in `~/.config/kg/config.json`. You do not need to log in again on this machine unless you revoke the client or reinstall.

```
Knowledge Graph Login

Username: admin
Password: ········

Connecting to API...
Creating OAuth client credentials...

✅ Logged in successfully!
   Username: admin
   Client ID: kg-cli-admin-a1b2c3
   Scopes: read:*, write:*
```

Verify the connection:

```bash
kg health
```

```
✓ API healthy
✓ Database connected
✓ Storage connected
```

---

## Step 4: Ingest a document

Pick any text, Markdown, PDF, or Word file. The `-o` flag assigns the document to a named ontology — a logical collection that groups related knowledge. The ontology is created automatically if it does not exist.

```bash
kg ingest file /path/to/your-document.pdf -o "first-graph" -w
```

The `-w` flag streams progress until the job completes:

```
✓ Job submitted: job_a1b2c3d4
  Ontology: first-graph
  Chunks: 4
  Estimated cost: $0.003

Processing...
  [1/4] Extracting concepts...
  [2/4] Extracting concepts...
  [3/4] Extracting concepts...
  [4/4] Extracting concepts...
  Calculating grounding scores...

✓ Complete
  Concepts extracted: 31
  Relationships found: 18
  Sources stored: 1
```

What happened:

1. The document was stored in object storage and split into roughly 1,000-word chunks.
2. Each chunk was sent to your configured AI provider (OpenAI, Anthropic, or Ollama) for concept and relationship extraction.
3. New concepts were matched against any existing ones and merged where they overlap.
4. Grounding scores were calculated — a measure of how much evidence in your corpus supports each concept.

---

## Step 5: Search for concepts

```bash
kg search "your topic"
```

```
✓ Found 3 concepts:

  ● Your Topic Name
    ID: concept-a1b2c3d4
    Similarity: 91%
    Documents: first-graph
    Grounding: ✓ Well-supported

  ● Related Concept
    ID: concept-e5f6a7b8
    Similarity: 74%
    Documents: first-graph
    Grounding: ⚡ Some support (limited data)
```

Results include the concept ID you need for graph traversal. Search spans all ontologies; the Documents field shows which ontology each concept came from.

---

## Step 6: View relationships

Copy a concept ID from the search output, then traverse its edges:

```bash
kg search related concept-a1b2c3d4
```

```
✓ Found 4 related concepts:

Distance 1:
  ● Related Concept (concept-e5f6a7b8)
    Path: IMPLIES

Distance 2:
  ● Deeper Concept (concept-c9d0e1f2)
    Path: IMPLIES → SUPPORTS
```

This traverses the typed edges connecting concepts — `IMPLIES`, `SUPPORTS`, `CONTRADICTS`, `ENABLES`, and similar. The `-d` flag controls traversal depth (default 2 hops).

---

## Step 7: Open the web interface

Navigate to your Kappa Graph web URL (the same hostname, port 3000 for local dev):

```
http://localhost:3000
```

The Explore view shows an interactive graph of the concepts and relationships extracted from your document. Select a node to see its evidence quotes and grounding score.

---

## What to do next

- **Ingest more documents** — ingest a second document into the same ontology (`-o "first-graph"`) and watch grounding scores increase as concepts appear in multiple sources.
- **Query the graph** — [Your First Query](first-query.md) walks through Cypher traversals against the concepts you just extracted.
- **Connect an AI assistant** — [Connect via MCP](mcp-quickstart.md) lets Claude or another MCP-capable assistant query your graph as memory.
- **Ingest a Git repository** — [Mining a Git Repo](github-history.md) extracts concepts from commit history and code.
