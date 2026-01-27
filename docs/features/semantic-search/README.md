# Semantic Search

Find concepts by meaning, not just keywords.

## What It Does

Semantic search uses vector embeddings to find concepts based on their meaning. Search for "causes of rising prices" and find concepts about inflation—even if the word "inflation" never appears in your query.

## How It Works

Every concept gets an embedding vector built from its label, description, and search terms. When you search, your query becomes a vector too, and the system finds concepts with similar vectors.

This means you can:
- Search with natural language questions
- Find concepts using synonyms or related phrases
- Match concepts through their descriptions, not just titles

## Example

**Query:** "expanse of air over earth"

**Result:** Matches the "Sky" concept, whose description includes "the expanse of air over the Earth, visible as a dome above the horizon"

The search found it through meaning, not keyword matching.

## Key Capabilities

- **Natural Language Queries** — Ask questions in plain English
- **Description Matching** — Search matches concept descriptions, not just labels
- **Similarity Scoring** — Results ranked by semantic closeness (0.0–1.0)
- **Threshold Control** — Set minimum similarity to filter results

## Clients

| Client | Command |
|--------|---------|
| API | `POST /query/search` |
| CLI | `kg search query "your question"` |
| MCP | `search_concepts` tool |
| Web | Smart Search panel |

## Related

- [Path Finding](../path-finding/) — Find connections between concepts
- [Document Search](../document-search/) — Search at document level
