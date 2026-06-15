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

```
Documents ──→ [FastAPI] ──→ LLM Extraction ──→ [PostgreSQL 18 + AGE 1.7.0]
                  │                                         │
                  │                                  [graph_accel]
                  │                               in-memory traversal
                  │                                         │
              [Garage S3]                           [AGE graph store]
               doc storage                        source of truth (ACID)
                  │                                         │
              [React + D3] ←──── REST API ────────→ [FastAPI]
            web visualization                      query + ingest
                  │
           [kg CLI / MCP / FUSE]
             client interfaces
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
