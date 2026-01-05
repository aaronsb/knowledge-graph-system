# search

> Auto-generated from MCP tool schema

### search

Search for concepts, source passages, or documents using semantic similarity. Your ENTRY POINT to the graph.

CONCEPT SEARCH (type: "concepts", default) - Find concepts by semantic similarity:
- Grounding strength (-1.0 to 1.0): Reliability/contradiction score
- Diversity score: Conceptual richness (% of diverse connections)
- Authenticated diversity: Support vs contradiction indicator (✅✓⚠❌)
- Evidence samples: Quoted text from source documents
- Image indicators: Visual evidence when available
- Document sources: Where concepts originated

SOURCE SEARCH (type: "sources") - Find source text passages directly (ADR-068):
- Searches source document embeddings, not concept embeddings
- Returns matched text chunks with character offsets for highlighting
- Shows concepts extracted from those passages
- Useful for RAG workflows and finding original context

DOCUMENT SEARCH (type: "documents") - Find documents by semantic similarity (ADR-084):
- Searches at document level (aggregates source chunks)
- Returns documents ranked by best matching chunk similarity
- Shows concepts extracted from each document
- Use with document tool for content retrieval

RECOMMENDED WORKFLOW: After search, use concept (action: "connect") to find HOW concepts relate - this reveals narrative flows and cause/effect chains that individual searches cannot show. Connection paths are often more valuable than isolated concepts.

Use 2-3 word phrases (e.g., "linear thinking patterns").

**Parameters:**

- `query` (`string`) **(required)** - Search query text (2-3 word phrases work best, e.g., "linear thinking patterns")
- `type` (`string`) - Search type: "concepts" (default), "sources" (passage search), or "documents" (document-level search)
  - Allowed values: `concepts`, `sources`, `documents`
  - Default: `"concepts"`
- `limit` (`number`) - Maximum number of results to return (default: 10, max: 100)
  - Default: `10`
- `min_similarity` (`number`) - Minimum similarity score 0.0-1.0 (default: 0.7 for 70%, lower to 0.5-0.6 for broader matches)
  - Default: `0.7`
- `offset` (`number`) - Number of results to skip for pagination (default: 0)
  - Default: `0`
- `ontology` (`string`) - Filter by ontology/document name (sources only)

---
