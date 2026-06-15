---
id: 9.E.02
domain: meta
mode: explanation
---

# Kappa Graph — κ(G)

Kappa Graph extracts concepts from documents, tracks how well-supported each concept is across your corpus, and preserves contradictions rather than resolving them.

The system stores concepts and the typed relationships between them — IMPLIES, CONTRADICTS, ENABLES. Traditional retrieval finds similar text chunks; Kappa Graph stores the graph of relationships between ideas and computes confidence from evidence. Queries traverse these edges. Every result carries a grounding score and a provenance chain to source text or images.

## What You Can Do

**Ingest documents** — PDFs, markdown, images, plain text. Concepts, relationships, and evidence are extracted automatically via an LLM extraction pipeline.

**Search by meaning** — Vector similarity finds concepts related to your query even when exact terms differ.

**Explore connections** — Traverse paths between concepts. See how ideas relate across sources.

**Check confidence** — Every concept carries a grounding score computed from supporting versus contradicting evidence. Know what is well-evidenced and what is contested.

**Trace sources** — Every concept links to the original text or image that generated it.

**Query via AI** — The MCP server lets Claude and other assistants use the graph as persistent, grounded memory.

**Navigate via filesystem** — The FUSE driver mounts the graph as a filesystem. Use `ls`, `grep`, and `find` on semantic space.

## Architecture

```mermaid
flowchart TD
    DOCS([("External Documents<br>PDF / MD / Images / Text")])
    API(["FastAPI<br>Extraction Pipeline and REST API"])
    LLM(["LLM Extraction<br>Concept and Relationship Mining"])
    PG[("PostgreSQL 18 + AGE 1.7.0<br>Graph Store — ACID Source of Truth")]
    GA(["graph_accel<br>Rust Extension — In-Memory BFS and Shortest Path"])
    S3[("Garage S3<br>Document Asset Storage")]
    WEB(["React + D3<br>Web Visualization"])
    CLI(["kg CLI / MCP / FUSE<br>Client Interfaces"])

    DOCS -->|ingest| API
    API -->|chunk + extract| LLM
    LLM -->|upsert concepts and edges| PG
    PG -->|epoch-based read model| GA
    API -->|store assets| S3
    WEB -->|REST API| API
    CLI -->|REST / MCP| API

    style DOCS fill:#c2410c,color:#ffffff,stroke:#9a3412
    style API  fill:#6d28d9,color:#ffffff,stroke:#4c1d95
    style LLM  fill:#0d9488,color:#ffffff,stroke:#0f766e
    style PG   fill:#16a34a,color:#ffffff,stroke:#15803d
    style GA   fill:#0d9488,color:#ffffff,stroke:#0f766e
    style S3   fill:#16a34a,color:#ffffff,stroke:#15803d
    style WEB  fill:#64748b,color:#ffffff,stroke:#475569
    style CLI  fill:#64748b,color:#ffffff,stroke:#475569
```

**PostgreSQL 18 + Apache AGE 1.7.0** — Graph database with native openCypher queries. ACID transactions, schema integrity, vector search via pgvector.

**graph_accel** — Rust PostgreSQL extension that maintains an adjacency structure in shared memory for instant BFS and shortest-path traversal. AGE handles writes; graph_accel handles reads. Epoch-based invalidation keeps the read model current. ([ADR-201](architecture/database-schema/ADR-201-in-memory-graph-acceleration-extension.md))

**FastAPI** — Extraction pipeline and REST API.

**React + D3** — Interactive graph visualization and exploration.

**kg CLI** — Command-line interface and MCP server for AI assistant integration. Requires Node.js 20.12.0 or later.

**Garage** — S3-compatible object storage for document assets.

**Ollama** — Optional local inference for air-gapped operation.

## Where to Go Next

| If you want to… | Start here |
|---|---|
| Install and run Kappa Graph | [Self-Host: Quick Start](self-host/quick-start.md) |
| Ingest your first document | [Get Started: Your First Graph](get-started/first-graph.md) |
| Connect an AI assistant via MCP | [Get Started: Connect via MCP](get-started/mcp-quickstart.md) |
| Understand how grounding works | [Explanation: Grounding and Epistemic Confidence](explanation/grounding.md) |
| Look up a CLI command or API endpoint | [Reference](reference/cli.md) |
| Configure AI providers or embeddings | [How-To: Configure AI Providers](how-to/ai-providers.md) |
| Understand the design decisions | [Architecture Decisions](architecture/INDEX.md) |

## License

Apache License 2.0 — use, modify, and distribute freely. Patent grant included.
