# Description Search Status

## Summary

**Description search is already fully operational across all interfaces.** Concept descriptions are included in the embedding vectors, so semantic search (query, connect, etc.) automatically matches against descriptions in addition to labels and search terms.

## How It Works

### Embedding Generation (src/api/lib/ingestion.py:289-294)

When concepts are ingested, embeddings are created from:
```python
embedding_text = label
if description:
    embedding_text += f". {description}"
if search_terms:
    embedding_text += f". {', '.join(search_terms)}"
```

This means a query for "blue sky" will match concepts where:
- The label contains "blue sky"
- The description contains "blue sky"
- The search terms contain "blue sky"

### Interface Coverage

| Interface | Query Search | Connection Search (connect) | Description Search |
|-----------|-------------|----------------------------|-------------------|
| **API** | ✅ `/query/search` | ✅ `/query/connect-by-search` | ✅ Via embeddings |
| **CLI** | ✅ `kg search query` | ✅ `kg search connect` | ✅ Via embeddings |
| **MCP** | ✅ `search_concepts` | ✅ `find_connection_by_search` | ✅ Via embeddings |
| **Viz App** | ✅ Concept mode | ✅ Path mode (2-step) | ✅ Via embeddings |

## Examples

### API

**Query Search (matches description):**
```bash
curl -X POST http://localhost:8000/query/search \
  -H "Content-Type: application/json" \
  -d '{"query": "expanse of air over earth", "limit": 5, "min_similarity": 0.7}'
```

This will match the "Sky" concept because its description is: "The sky is the expanse of air over the Earth, visible as a dome above the horizon."

**Connection Search (matches descriptions in from/to concepts):**
```bash
curl -X POST http://localhost:8000/query/connect-by-search \
  -H "Content-Type: application/json" \
  -d '{
    "from_query": "blue expanse above",
    "to_query": "water droplets suspended",
    "max_hops": 5,
    "threshold": 0.5
  }'
```

### CLI

**Query Search:**
```bash
kg search query "expanse of air over earth" --min-similarity 0.7
```

**Connection Search with auto-detection:**
```bash
# Using concept IDs (auto-detected)
kg search connect sha256:abc123 sha256:def456

# Using semantic phrases (auto-detected, matches descriptions)
kg search connect "blue expanse above" "water droplets suspended" --min-similarity 0.5
```

### MCP Server

**search_concepts tool (matches descriptions):**
```json
{
  "name": "search_concepts",
  "arguments": {
    "query": "expanse of air over earth",
    "limit": 5,
    "min_similarity": 0.7
  }
}
```

**find_connection_by_search tool (matches descriptions in from/to):**
```json
{
  "name": "find_connection_by_search",
  "arguments": {
    "from_query": "blue expanse above",
    "to_query": "water droplets suspended",
    "max_hops": 5,
    "threshold": 0.5
  }
}
```

### Viz App

**Concept Search (matches descriptions):**
1. Click "Smart Search" → "Concept" tab
2. Type "expanse of air over earth" in search box
3. Results will include "Sky" concept because description matches

**Path Search (2-step process, matches descriptions):**
1. Click "Smart Search" → "Path" tab
2. Search for From concept: "blue expanse above" (matches Sky via description)
3. Select "Sky" from results
4. Search for To concept: "water droplets suspended" (matches Clouds via description)
5. Select "Clouds" from results
6. Click "Find Paths"
7. Results show paths between Sky and Clouds

**Note:** Viz app currently uses a 2-step process (search → select → connect) rather than direct phrase-to-phrase search like CLI/MCP. This provides more user control over concept selection but requires an extra step.

## Implementation Details

### Vector Search (src/api/lib/age_client.py:681-721)

The `vector_search()` method:
1. Fetches all concepts with embeddings (including description field)
2. Calculates cosine similarity between query embedding and concept embeddings
3. Returns matches above threshold

Since embeddings include descriptions, similarity scores naturally reflect description matches.

### Connection Search (src/api/routes/queries.py:716-849)

The `find_connection_by_search()` endpoint:
1. Generates embeddings for `from_query` and `to_query` phrases
2. Uses `vector_search()` to find best matching concepts (searches in descriptions)
3. Finds shortest paths between matched concepts
4. Returns paths with match quality scores

## Testing Description Search

### Test Case: Match via Description Only

Create a concept where only the description matches the query:

**Concept:**
- Label: "Sky"
- Description: "The expanse of air over the Earth visible as a dome above the horizon"
- Search Terms: ["blue sky", "atmosphere", "heavens"]

**Query:** "air dome above ground"

**Expected:** Should match "Sky" concept via description, even though "air dome above ground" doesn't appear in label or search terms.

**Actual Test:**
```bash
# Create test concept
kg ingest text -o "Test" "The sky is a blue expanse. It is the air dome above ground that we see every day."

# Search for description-specific phrase
kg search query "air dome above ground" --min-similarity 0.6

# Expected: Sky concept appears in results with moderate-high similarity
```

## Future Enhancements

### Viz App Direct Semantic Search (Optional)

Currently, the viz app Path mode requires two steps:
1. Search for concepts (description matching works)
2. Select concepts from results
3. Find paths between selected concepts

**Potential Enhancement:** Add option for direct phrase-to-phrase search:
1. Enter "from" phrase directly
2. Enter "to" phrase directly
3. Click "Find Paths" (auto-matches best concepts via descriptions)
4. See paths with match quality indicators

**Benefits:**
- Faster workflow for exploratory path finding
- Matches CLI/MCP user experience
- Still shows which concepts were matched

**Implementation:** The viz-app client already has `findConnectionBySearch()` method. Would need to add UI option to toggle between "Select Concepts" mode (current) and "Direct Search" mode (new).

## Conclusion

Description search is **fully operational** across all interfaces via the embedding mechanism. Users can search for text that appears in concept descriptions, and it will be matched via vector similarity just like labels and search terms.

No additional implementation is needed for basic description search functionality. Optional enhancements could improve the viz-app UX, but the core functionality is complete.
