# Using the Knowledge Graph

Guides for working with the knowledge graph system as a user.

## Getting Started

Once the system is [running](../operating/quick-start.md):

1. **Log in** to the web interface at http://localhost:3000 (or your configured hostname)
2. **Ingest documents** to build your knowledge base
3. **Search and explore** to discover connections
4. **Query via CLI or MCP** for programmatic access

## Guides

| Guide | Description |
|-------|-------------|
| [Ingesting Documents](ingesting.md) | Adding documents to the system |
| [Exploring Knowledge](exploring.md) | Finding and navigating concepts |
| [Querying](querying.md) | CLI, API, and MCP access |
| [Understanding Grounding](understanding-grounding.md) | Confidence and contradiction |

## Quick Examples

### Ingest a Document

**Via CLI:**
```bash
kg ingest /path/to/document.pdf --ontology research
```

**Via Web:**
Navigate to Ingest → Upload file → Approve job

### Search for Concepts

**Via CLI:**
```bash
kg search "climate change effects"
```

**Via Web:**
Use the search bar in the top navigation

### Explore Connections

**Via CLI:**
```bash
kg concept details <concept-id>
kg concept related <concept-id>
kg concept connect --from "concept A" --to "concept B"
```

**Via Web:**
Click any concept to see its relationships and sources

## For AI Assistants

If you're an AI agent using this system via MCP:

- Use `search` to find concepts by meaning
- Use `concept` with `action: "details"` for full evidence
- Use `concept` with `action: "connect"` to find paths between ideas
- Check `grounding_strength` to assess reliability

See [Querying](querying.md) for full MCP tool documentation.

---

See [Concepts](../concepts/README.md) for the conceptual foundation behind the system.
