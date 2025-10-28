# MCP Server Tool Reference (Auto-Generated)

> **Auto-Generated Documentation**
> 
> Generated from MCP server tool schemas.
> Last updated: 2025-10-28

---

## Overview

The Knowledge Graph MCP server provides tools for Claude Desktop to interact with the knowledge graph.
These tools enable semantic search, concept exploration, and graph traversal directly from Claude.

---

## Available Tools

- [`search_concepts`](#search-concepts) - Search for concepts using semantic similarity. Your ENTRY POINT to the graph. Returns grounding strength + evidence samples. Then use: get_concept_details (all evidence), find_connection_by_search (paths), find_related_concepts (neighbors). Use 2-3 word phrases (e.g., "linear thinking patterns").
- [`get_concept_details`](#get-concept-details) - Retrieve ALL evidence (quoted text) and relationships for a concept. Use to see the complete picture: ALL quotes, source locations, SUPPORTS/CONTRADICTS relationships. Contradicted concepts (negative grounding) are VALUABLE - show problems/outdated approaches.
- [`find_related_concepts`](#find-related-concepts) - Explore concept neighborhood. Discovers what's connected and how (SUPPORTS, CONTRADICTS, ENABLES). Returns concepts grouped by distance. Use depth=1-2 for neighbors, 3-4 for broader exploration.
- [`find_connection`](#find-connection) - Find shortest paths between two concepts using exact concept IDs. Uses graph traversal to find up to 5 shortest paths. For semantic phrase matching, use find_connection_by_search instead.
- [`find_connection_by_search`](#find-connection-by-search) - Discover HOW concepts connect. Find paths between ideas, trace problem→solution chains, see grounding+evidence at each step. Returns narrative flow through the graph. Use 2-3 word phrases (e.g., "licensing issues", "AGE benefits").
- [`get_database_stats`](#get-database-stats) - Get database statistics including total counts of concepts, sources, instances, relationships, and ontologies. Useful for understanding graph size and structure.
- [`get_database_info`](#get-database-info) - Get database connection information including PostgreSQL version, Apache AGE extension details, and connection status.
- [`get_database_health`](#get-database-health) - Check database health status. Verifies PostgreSQL connection and Apache AGE graph availability.
- [`list_ontologies`](#list-ontologies) - List all ontologies (collections) in the knowledge graph with concept counts and statistics.
- [`get_ontology_info`](#get-ontology-info) - Get detailed information about a specific ontology including concept count, relationship types, and source documents.
- [`get_ontology_files`](#get-ontology-files) - List all source files that have been ingested into a specific ontology with metadata.
- [`delete_ontology`](#delete-ontology) - Delete an entire ontology and all its concepts, relationships, and evidence. Requires force=true for confirmation.
- [`get_job_status`](#get-job-status) - Get status of an ingestion job including progress, cost estimates, and any errors. Use job_id from ingest operations.
- [`list_jobs`](#list-jobs) - List recent ingestion jobs with optional filtering by status (pending, awaiting_approval, running, completed, failed).
- [`approve_job`](#approve-job) - Approve a job for processing after reviewing cost estimates (ADR-014 approval workflow). Job must be in awaiting_approval status.
- [`cancel_job`](#cancel-job) - Cancel a pending or running job. Cannot cancel completed or failed jobs.
- [`ingest_text`](#ingest-text) - Submit text content to the knowledge graph for concept extraction. Automatically processes and extracts concepts, relationships, and evidence. Specify which ontology (knowledge domain) to add the concepts to. The system will chunk the text, extract concepts using LLM, and add them to the graph. Returns a job ID for tracking progress.
- [`get_api_health`](#get-api-health) - Check API server health status. Returns status and timestamp.
- [`get_system_status`](#get-system-status) - Get comprehensive system status including database, job scheduler, and resource usage statistics.

---

### search_concepts

Search for concepts using semantic similarity. Your ENTRY POINT to the graph. Returns grounding strength + evidence samples. Then use: get_concept_details (all evidence), find_connection_by_search (paths), find_related_concepts (neighbors). Use 2-3 word phrases (e.g., "linear thinking patterns").

**Parameters:**

- `query` (`string`) **(required)** - Search query text (2-3 word phrases work best, e.g., "linear thinking patterns")
- `limit` (`number`) - Maximum number of results to return (default: 10, max: 100)
  - Default: `10`
- `min_similarity` (`number`) - Minimum similarity score 0.0-1.0 (default: 0.7 for 70%, lower to 0.5-0.6 for broader matches)
  - Default: `0.7`
- `offset` (`number`) - Number of results to skip for pagination (default: 0)
  - Default: `0`

---

### get_concept_details

Retrieve ALL evidence (quoted text) and relationships for a concept. Use to see the complete picture: ALL quotes, source locations, SUPPORTS/CONTRADICTS relationships. Contradicted concepts (negative grounding) are VALUABLE - show problems/outdated approaches.

**Parameters:**

- `concept_id` (`string`) **(required)** - The unique concept identifier (from search results or graph traversal)
- `include_grounding` (`boolean`) - Include grounding_strength calculation (ADR-044: probabilistic truth convergence). Default: true. Set to false only for faster queries when grounding not needed.
  - Default: `true`

---

### find_related_concepts

Explore concept neighborhood. Discovers what's connected and how (SUPPORTS, CONTRADICTS, ENABLES). Returns concepts grouped by distance. Use depth=1-2 for neighbors, 3-4 for broader exploration.

**Parameters:**

- `concept_id` (`string`) **(required)** - Starting concept ID for traversal
- `max_depth` (`number`) - Maximum traversal depth in hops (1-5, default: 2). Depth 1-2 is fast, 3-4 moderate, 5 can be slow.
  - Default: `2`
- `relationship_types` (`array`) - Optional filter for specific relationship types (e.g., ["IMPLIES", "SUPPORTS", "CONTRADICTS"])

---

### find_connection

Find shortest paths between two concepts using exact concept IDs. Uses graph traversal to find up to 5 shortest paths. For semantic phrase matching, use find_connection_by_search instead.

**Parameters:**

- `from_id` (`string`) **(required)** - Starting concept ID (exact match required)
- `to_id` (`string`) **(required)** - Target concept ID (exact match required)
- `max_hops` (`number`) - Maximum path length to search (1-10 hops, default: 5)
  - Default: `5`

---

### find_connection_by_search

Discover HOW concepts connect. Find paths between ideas, trace problem→solution chains, see grounding+evidence at each step. Returns narrative flow through the graph. Use 2-3 word phrases (e.g., "licensing issues", "AGE benefits").

**Parameters:**

- `from_query` (`string`) **(required)** - Semantic phrase for starting concept (use specific 2-3 word phrases for best results)
- `to_query` (`string`) **(required)** - Semantic phrase for target concept (use specific 2-3 word phrases)
- `max_hops` (`number`) - Maximum path length to search (default: 5)
  - Default: `5`
- `threshold` (`number`) - Minimum similarity threshold 0.0-1.0 (default: 0.5 for 50%, lower to 0.3-0.4 for weaker matches)
  - Default: `0.5`

---

### get_database_stats

Get database statistics including total counts of concepts, sources, instances, relationships, and ontologies. Useful for understanding graph size and structure.

**Parameters:**



---

### get_database_info

Get database connection information including PostgreSQL version, Apache AGE extension details, and connection status.

**Parameters:**



---

### get_database_health

Check database health status. Verifies PostgreSQL connection and Apache AGE graph availability.

**Parameters:**



---

### list_ontologies

List all ontologies (collections) in the knowledge graph with concept counts and statistics.

**Parameters:**



---

### get_ontology_info

Get detailed information about a specific ontology including concept count, relationship types, and source documents.

**Parameters:**

- `ontology_name` (`string`) **(required)** - Name of the ontology to retrieve

---

### get_ontology_files

List all source files that have been ingested into a specific ontology with metadata.

**Parameters:**

- `ontology_name` (`string`) **(required)** - Name of the ontology

---

### delete_ontology

Delete an entire ontology and all its concepts, relationships, and evidence. Requires force=true for confirmation.

**Parameters:**

- `ontology_name` (`string`) **(required)** - Name of the ontology to delete
- `force` (`boolean`) **(required)** - Must be true to confirm deletion
  - Default: `false`

---

### get_job_status

Get status of an ingestion job including progress, cost estimates, and any errors. Use job_id from ingest operations.

**Parameters:**

- `job_id` (`string`) **(required)** - Job ID returned from ingest operation

---

### list_jobs

List recent ingestion jobs with optional filtering by status (pending, awaiting_approval, running, completed, failed).

**Parameters:**

- `status` (`string`) - Filter by job status (optional)
- `limit` (`number`) - Maximum number of jobs to return (default: 50)
  - Default: `50`

---

### approve_job

Approve a job for processing after reviewing cost estimates (ADR-014 approval workflow). Job must be in awaiting_approval status.

**Parameters:**

- `job_id` (`string`) **(required)** - Job ID to approve

---

### cancel_job

Cancel a pending or running job. Cannot cancel completed or failed jobs.

**Parameters:**

- `job_id` (`string`) **(required)** - Job ID to cancel

---

### ingest_text

Submit text content to the knowledge graph for concept extraction. Automatically processes and extracts concepts, relationships, and evidence. Specify which ontology (knowledge domain) to add the concepts to. The system will chunk the text, extract concepts using LLM, and add them to the graph. Returns a job ID for tracking progress.

**Parameters:**

- `text` (`string`) **(required)** - Text content to ingest into the knowledge graph
- `ontology` (`string`) **(required)** - Ontology/collection name (ask user which knowledge domain this belongs to, e.g., "Project Documentation", "Research Notes", "Meeting Notes")
- `filename` (`string`) - Optional filename for source tracking (default: "text_input")
- `auto_approve` (`boolean`) - Auto-approve and start processing immediately (default: true). Set to false to require manual approval.
  - Default: `true`
- `force` (`boolean`) - Force re-ingestion even if content already exists (default: false)
  - Default: `false`
- `processing_mode` (`string`) - Processing mode: serial (clean, recommended) or parallel (fast, may duplicate concepts)
  - Allowed values: `serial`, `parallel`
  - Default: `"serial"`
- `target_words` (`number`) - Target words per chunk (default: 1000, range: 500-2000)
  - Default: `1000`
- `overlap_words` (`number`) - Word overlap between chunks for context (default: 200)
  - Default: `200`

---

### get_api_health

Check API server health status. Returns status and timestamp.

**Parameters:**



---

### get_system_status

Get comprehensive system status including database, job scheduler, and resource usage statistics.

**Parameters:**



---
