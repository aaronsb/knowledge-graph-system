# Knowledge Graph System

A semantic knowledge graph that extracts concepts from documents, tracks how well-supported they are, and remembers where sources disagree.

## Why External AI Memory Matters

Today's LLMs are static. They learn during training, then freeze. You can fine-tune or retrain, but the model itself doesn't accumulate knowledge from conversations. Every session starts fresh.

This is changing. Google's Titans architecture introduces neural long-term memory that updates during inference—"surprise-driven memorization" that prioritizes unexpected information, scaling to 2+ million tokens. Mixture-of-experts models route queries to specialized subnetworks. The boundary between model and memory is blurring.

But these are internal mechanisms. You don't control what they remember. You can't audit their confidence. You can't see where their sources disagree.

**External memory systems**—knowledge you manage outside the model—remain essential:
- You control what's stored
- You can trace provenance
- You can measure confidence
- You can preserve contradictions

Many external memory systems exist. Paid services like Mem0, Zep, and Pinecone offer managed infrastructure. Open source options like LlamaIndex, LangChain, and GraphRAG provide frameworks. They vary widely in features, production-readiness, cost, and what they optimize for.

This system optimizes for **epistemic rigor**—knowing how well-supported your knowledge is, not just retrieving it.

## The Evolution of External AI Memory

**Stage 1: Context Window** — Paste documents into the prompt. Works until you hit token limits. No persistence. Re-paste everything next conversation.

**Stage 2: Vector Database** — Embed documents as vectors. Search by similarity. "Find chunks related to this query." But: no relationships between chunks. No way to know if sources agree or disagree. Every chunk is equally trusted.

**Stage 3: RAG (Retrieval-Augmented Generation)** — Vector search feeds context to an LLM. Better answers grounded in your documents. But still: chunks are isolated. No accumulated understanding. The LLM sees fragments, not structure.

**Stage 4: Knowledge Graph** — Extract entities and relationships. Build structure. "Person X works at Company Y." Now you have connections. But: most graphs assume everything is true. No confidence. No contradiction handling. Microsoft's GraphRAG lives here—impressive comprehensiveness, but conflicts require LLM judgment at query time.

**Stage 5: Epistemic Knowledge Graph** — This system. Concepts have grounding scores computed from evidence. Contradictions are preserved, not hidden. Semantic diversity detects fabrication. You know *what* and *how sure*.

The progression: retrieval → structure → **confidence**.

## The Problem with Most AI Memory

Most AI memory systems store facts and retrieve them by similarity. They can't tell you:
- **How confident** should I be in this?
- **Do sources disagree** about this?
- **Where did this come from** originally?

Vector databases find similar content. They don't know if it's contested, well-supported, or fabricated.

## What This System Does Differently

### Grounding: Measuring Confidence Mathematically

Every concept has a **grounding score** (-1.0 to +1.0) computed from supporting vs. contradicting evidence. Not a label someone assigned—a calculation from the actual evidence graph.

A concept with 47 supporting edges and 12 contradicting edges gets grounding ≈ 0.77. You know exactly how contested it is.

*No other system we researched computes grounding this way.* GraphRAG stores conflicting nodes but relies on LLMs to resolve them at query time. We measure it.

### Diversity: Detecting Fabrication

Authentic information connects to many independent domains. Fabricated claims create echo chambers—circular reasoning with low conceptual diversity.

We tested this: Apollo 11 mission data showed **37.7% semantic diversity** across 33 related concepts. Moon landing conspiracy theories showed **23.2% diversity** across 3 concepts.

*This metric is unique to this system.*

### Contradiction Preservation

When sources disagree, the system doesn't pick a winner. It preserves both perspectives with evidence attribution, letting you (or an AI agent) reason about the disagreement.

### Emergent Spatial Mapping

Feed the system street view images or photos of a physical place. The relationships extracted ("next to", "across from", "visible from") naturally encode physical topology.

The graph becomes a spatial map—without GPS coordinates. "The pharmacy is between the bank and the cafe" emerges from visual evidence alone.

## How It Compares

| Capability | This System | GraphRAG | Zep/Graphiti | Vector DBs |
|------------|-------------|----------|--------------|------------|
| Contradiction detection | Native (mathematical) | LLM-dependent | Limited | No |
| Grounding scores | Continuous 0-1 | Source citations only | No | Similarity only |
| Semantic diversity | Yes (authenticity signal) | No | No | No |
| Epistemic status | Per-relationship | No | No | No |
| FUSE filesystem | Yes | No | No | No |
| Air-gapped operation | Yes (Ollama) | Cloud required | Cloud required | Some local |
| Dynamic vocabulary | Emergent + consolidation | Fixed schema | Fixed schema | N/A |

**Closest competitor:** Zep/Graphiti has sophisticated temporal tracking (bi-temporal model). We have better epistemic metrics; they have better time-travel queries.

## Quick Start

### Connect to an Existing Platform

If someone else is running the platform:

```bash
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/client-install.sh | bash
```

Or just install the CLI: `npm install -g @aaronsb/kg-cli`

### Deploy Your Own Platform

```bash
curl -fsSL https://raw.githubusercontent.com/aaronsb/knowledge-graph-system/main/install.sh | bash
```

Or from source:
```bash
git clone https://github.com/aaronsb/knowledge-graph-system.git
cd knowledge-graph-system
./operator.sh init    # Interactive setup
./operator.sh start   # Start containers
```

Access points:
- **Web UI**: http://localhost:3000
- **API**: http://localhost:8000/docs
- **CLI**: `kg search "your query"`

See [Quick Start Guide](docs/operating/quick-start.md) for details.

## What You Can Do

**Ingest documents** — PDFs, markdown, images, text. The system extracts concepts, relationships, and evidence automatically.

**Search by meaning** — "economic downturn" finds content about recessions, crashes, and crises even if those exact words aren't used.

**Explore connections** — Find paths between concepts. See how ideas relate across documents.

**Check confidence** — Every result includes grounding scores. Know what's well-supported vs. contested.

**Trace sources** — Every concept links back to the original text or image that generated it.

**Query via AI** — MCP server integration lets Claude and other assistants use the graph as persistent memory.

**Navigate via filesystem** — Mount the graph as a FUSE filesystem. Use `ls`, `grep`, `find` on semantic space.

## Use Cases

**Research synthesis** — Ingest papers, find connections across them, see where authors disagree. Grounding scores tell you which claims have broad support.

**Technical documentation** — Extract architecture concepts from diagrams, meeting notes, design docs. Query how components relate.

**Agent memory** — Give AI assistants persistent, grounded memory. They can check confidence before making claims.

**Spatial understanding** — Ingest place photos. The graph learns physical relationships without coordinates.

**Compliance/audit** — Full provenance chain. Every concept traces to source evidence.

## Architecture

- **PostgreSQL + Apache AGE** — Graph database with native openCypher queries
- **FastAPI** — Extraction pipeline and REST API
- **React + D3** — Interactive visualization
- **TypeScript CLI** — Command-line and MCP server
- **Ollama** — Optional local inference (air-gapped operation)

## Documentation

| Audience | Start Here |
|----------|------------|
| Understanding the concepts | [docs/concepts/](docs/concepts/) |
| Deploying and operating | [docs/operating/](docs/operating/) |
| Using the system | [docs/using/](docs/using/) |
| Architecture decisions | [docs/architecture/](docs/architecture/) |

88 Architecture Decision Records document the design evolution.

## Why Try It

If you need:
- **Epistemic reliability** — knowing *how sure* you should be, not just *what* the answer is
- **Contradiction awareness** — preserving disagreement rather than hiding it
- **Full provenance** — tracing every claim to source evidence
- **Local operation** — running without cloud API dependencies
- **Unix integration** — using standard tools on semantic data

This system was built for those requirements. Most alternatives optimize for retrieval accuracy or comprehensiveness. We optimize for *knowing what you know and how well you know it*.

## License

**Elastic License 2.0** — Free for internal use and product integration. Not permitted as a managed service.

## Acknowledgments

Built with [Apache AGE](https://age.apache.org/), [Model Context Protocol](https://modelcontextprotocol.io/), [FastAPI](https://fastapi.tiangolo.com/), and local inference via [Ollama](https://ollama.ai/).
