# MCP Server

Model Context Protocol integration that gives AI assistants direct access to your knowledge graph. Claude Desktop, Claude Code, and other MCP-compatible clients can search, explore, and manipulate your knowledge.

![MCP Server](../media/mcp/mcp-server-help.png)

## Setup

```bash
# Generate MCP credentials
kg oauth create-mcp

# Add to Claude Desktop config (output includes ready-to-paste config)
```

---

## What AI Agents Can Do

### Search Your Knowledge

```
"Find concepts related to distributed systems"
"What does the knowledge graph say about eventual consistency?"
"Search for evidence about CAP theorem tradeoffs"
```

The agent uses semantic search to find relevant concepts, then retrieves evidence quotes from source documents.

---

### Explore Relationships

```
"How does 'microservices' connect to 'deployment complexity'?"
"What concepts are related to 'event sourcing'?"
"Find the path from 'technical debt' to 'team productivity'"
```

The agent traverses your knowledge graph to discover connections you might not have considered.

---

### Validate Claims

```
"What evidence supports the claim that caching improves performance?"
"Are there any contradicting viewpoints about serverless architecture?"
"Show me the sources for concepts about API design"
```

Every concept has grounding strength and evidence quotes. The agent can assess how well-supported a claim is.

---

### Build Knowledge

```
"Create a concept for 'blue-green deployment' in the devops ontology"
"Add a relationship: 'feature flags' ENABLES 'gradual rollout'"
"Ingest this text about Kubernetes patterns"
```

The agent can create concepts, add relationships, and submit documents for extraction.

---

### Manage Jobs

```
"What ingestion jobs are running?"
"Approve the pending job for the architecture document"
"Cancel the failed job"
```

Full control over the extraction pipeline.

---

## Available Tools

### Query Tools

| Tool | What It Does |
|------|--------------|
| **search** | Find concepts, sources, or documents by semantic similarity |
| **concept** (details) | Get full concept info with all evidence and relationships |
| **concept** (related) | Find concepts connected within N hops |
| **concept** (connect) | Discover paths between two concepts |

### Graph Tools

| Tool | What It Does |
|------|--------------|
| **graph** (create) | Create concepts or relationships |
| **graph** (edit) | Update existing concepts or edges |
| **graph** (delete) | Remove concepts or relationships |
| **graph** (list) | Query concepts/edges with filters |

### Ingestion Tools

| Tool | What It Does |
|------|--------------|
| **ingest** | Submit text, files, or directories for extraction |

### Management Tools

| Tool | What It Does |
|------|--------------|
| **ontology** | List, inspect, or delete knowledge domains |
| **job** | Monitor, approve, cancel, or delete jobs |
| **document** | List documents, retrieve content |
| **source** | Access original source text or images |
| **artifact** | Retrieve saved analysis results |

### Analysis Tools

| Tool | What It Does |
|------|--------------|
| **analyze_polarity_axis** | Project concepts onto semantic dimensions |
| **epistemic_status** | Check knowledge validation state |

---

## Example Conversations

### Knowledge Discovery

**User:** "What does our knowledge graph say about database scaling?"

**Agent:** *Uses search tool* → Finds concepts about sharding, replication, read replicas, connection pooling → *Uses concept details* → Retrieves evidence quotes → Synthesizes answer with citations

---

### Research Assistance

**User:** "I'm writing about microservices. What related topics should I cover?"

**Agent:** *Uses search* → Finds "microservices" concept → *Uses related* → Discovers connected concepts: service mesh, API gateway, distributed tracing, eventual consistency → Suggests outline based on knowledge graph structure

---

### Fact Checking

**User:** "Is it true that event sourcing improves auditability?"

**Agent:** *Searches for evidence* → Finds grounding strength of 0.85 (well-supported) → *Retrieves evidence quotes* → Shows sources confirming the claim with specific quotes

---

### Knowledge Building

**User:** "Add what I just learned about CQRS to the architecture ontology"

**Agent:** *Uses ingest tool* → Submits text → *Monitors job* → Reports when extraction completes → Shows new concepts created

---

## Performance Notes

- **Search:** ~200ms including vector similarity
- **Graph traversal:** ~150ms for 2-hop relationships
- **Path finding:** Use threshold ≥ 0.75 to avoid slow queries
- **Batch operations:** Up to 20 ops per queue

Lower similarity thresholds (0.60-0.74) are slower but more exploratory. Values below 0.60 can cause timeouts.
