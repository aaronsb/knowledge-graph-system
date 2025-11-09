# MCP Server Tool Reference (Auto-Generated)

> **Auto-Generated Documentation**
> 
> Generated from MCP server tool schemas.
> Last updated: 2025-11-08

---

## Overview

The Knowledge Graph MCP server provides tools for Claude Desktop to interact with the knowledge graph.
These tools enable semantic search, concept exploration, and graph traversal directly from Claude.

---

## Available Tools

- [`search`](#search) - Search for concepts using semantic similarity. Your ENTRY POINT to the graph. Returns grounding strength + evidence samples. Then use: concept (details, related, connect), find_connection_by_search (paths), find_related_concepts (neighbors). Use 2-3 word phrases (e.g., "linear thinking patterns").
- [`concept`](#concept) - Work with concepts: get details (ALL evidence + relationships), find related concepts (neighborhood exploration), or discover connections (paths between concepts). Use action parameter to specify operation.
- [`ontology`](#ontology) - Manage ontologies (knowledge domains/collections): list all, get info, list files, or delete. Use action parameter to specify operation.
- [`job`](#job) - Manage ingestion jobs: get status, list jobs, approve, or cancel. Use action parameter to specify operation.
- [`ingest`](#ingest) - Submit text content for concept extraction. Chunks text, extracts concepts using LLM, and adds them to the specified ontology. Returns job ID for tracking.
- [`source`](#source) - Retrieve original image for a source node (ADR-057). Use when evidence has image metadata. Enables visual verification and refinement loop.
- [`inspect-file`](#inspect-file) - Validate and inspect a file before ingestion (ADR-062). Checks path allowlist, shows metadata (size, type, permissions), and returns validation result. Use this to verify files are allowed before attempting ingestion.

---

### search

Search for concepts using semantic similarity. Your ENTRY POINT to the graph. Returns grounding strength + evidence samples. Then use: concept (details, related, connect), find_connection_by_search (paths), find_related_concepts (neighbors). Use 2-3 word phrases (e.g., "linear thinking patterns").

**Parameters:**

- `query` (`string`) **(required)** - Search query text (2-3 word phrases work best, e.g., "linear thinking patterns")
- `limit` (`number`) - Maximum number of results to return (default: 10, max: 100)
  - Default: `10`
- `min_similarity` (`number`) - Minimum similarity score 0.0-1.0 (default: 0.7 for 70%, lower to 0.5-0.6 for broader matches)
  - Default: `0.7`
- `offset` (`number`) - Number of results to skip for pagination (default: 0)
  - Default: `0`

---

### concept

Work with concepts: get details (ALL evidence + relationships), find related concepts (neighborhood exploration), or discover connections (paths between concepts). Use action parameter to specify operation.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "details" (get ALL evidence), "related" (explore neighborhood), "connect" (find paths)
  - Allowed values: `details`, `related`, `connect`
- `concept_id` (`string`) - Concept ID (required for details, related)
- `include_grounding` (`boolean`) - Include grounding_strength (default: true)
  - Default: `true`
- `max_depth` (`number`) - Max traversal depth for related (1-5, default: 2)
  - Default: `2`
- `relationship_types` (`array`) - Filter relationships (e.g., ["SUPPORTS", "CONTRADICTS"])
- `connection_mode` (`string`) - Connection mode: "exact" (IDs) or "semantic" (phrases)
  - Allowed values: `exact`, `semantic`
  - Default: `"semantic"`
- `from_id` (`string`) - Starting concept ID (for exact mode)
- `to_id` (`string`) - Target concept ID (for exact mode)
- `from_query` (`string`) - Starting phrase (for semantic mode, 2-3 words)
- `to_query` (`string`) - Target phrase (for semantic mode, 2-3 words)
- `max_hops` (`number`) - Max path length (default: 5)
  - Default: `5`
- `threshold` (`number`) - Similarity threshold for semantic mode (default: 0.5)
  - Default: `0.5`

---

### ontology

Manage ontologies (knowledge domains/collections): list all, get info, list files, or delete. Use action parameter to specify operation.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "list" (all ontologies), "info" (details), "files" (source files), "delete" (remove)
  - Allowed values: `list`, `info`, `files`, `delete`
- `ontology_name` (`string`) - Ontology name (required for info, files, delete)
- `force` (`boolean`) - Confirm deletion (required for delete)
  - Default: `false`

---

### job

Manage ingestion jobs: get status, list jobs, approve, or cancel. Use action parameter to specify operation.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "status" (get job status), "list" (list jobs), "approve" (approve job), "cancel" (cancel job)
  - Allowed values: `status`, `list`, `approve`, `cancel`
- `job_id` (`string`) - Job ID (required for status, approve, cancel)
- `status` (`string`) - Filter by status for list (pending, awaiting_approval, running, completed, failed)
- `limit` (`number`) - Max jobs to return for list (default: 50)
  - Default: `50`

---

### ingest

Submit text content for concept extraction. Chunks text, extracts concepts using LLM, and adds them to the specified ontology. Returns job ID for tracking.

**Parameters:**

- `text` (`string`) **(required)** - Text content to ingest
- `ontology` (`string`) **(required)** - Ontology name (e.g., "Project Documentation", "Research Notes")
- `filename` (`string`) - Optional filename for source tracking
- `auto_approve` (`boolean`) - Auto-approve processing (default: true)
  - Default: `true`
- `force` (`boolean`) - Force re-ingestion (default: false)
  - Default: `false`
- `processing_mode` (`string`) - Processing mode (default: serial)
  - Allowed values: `serial`, `parallel`
  - Default: `"serial"`
- `target_words` (`number`) - Words per chunk (default: 1000)
  - Default: `1000`
- `overlap_words` (`number`) - Overlap between chunks (default: 200)
  - Default: `200`

---

### source

Retrieve original image for a source node (ADR-057). Use when evidence has image metadata. Enables visual verification and refinement loop.

**Parameters:**

- `source_id` (`string`) **(required)** - Source ID from evidence (has_image=true)

---

### inspect-file

Validate and inspect a file before ingestion (ADR-062). Checks path allowlist, shows metadata (size, type, permissions), and returns validation result. Use this to verify files are allowed before attempting ingestion.

**Parameters:**

- `path` (`string`) **(required)** - File path to inspect (absolute or relative, ~ supported)

---
