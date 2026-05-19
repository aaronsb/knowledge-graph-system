# epoch

> Auto-generated from MCP tool schema

### epoch

Read the graph epoch event log (ADR-203).

Every mutation to the knowledge graph (ingestion job, agent reasoning, ontology breathing, manual edit) records a monotonic event with a wall-clock timestamp. This tool exposes that log so you can ask "when did the system come to know X?" or "what arrived in the graph during this window?" — without inventing causal edges between concepts.

Two dimensions matter:
  - event_id (logical time): always meaningful — strictly ordered, even for events whose wall-clock is forensic.
  - occurred_at (wall-clock): semantically meaningful for kinds like 'ingestion' / 'edit'; treat as forensic-only for 'reasoning' / 'breathing'.

Cursor-paginated. Pass the previous response's next_cursor as cursor to walk further back.

For the per-concept re-evidence stream (which Concepts were touched in which epochs), use the concept tool's 'lifetime' action instead.

**Parameters:**

- `kind` (`string`) - Filter to a specific event kind. Omit for all kinds.
  - Allowed values: `ingestion`, `reasoning`, `breathing`, `edit`
- `since` (`string`) - ISO-8601 lower bound on occurred_at (UTC, e.g., "2026-05-01T00:00:00Z")
- `until` (`string`) - ISO-8601 upper bound on occurred_at (UTC)
- `actor` (`string`) - Filter by exact actor string (user id, agent session id, system component)
- `cursor` (`number`) - Pagination cursor — returns events with event_id < cursor. Omit for the first page.
- `limit` (`number`) - Max events per page (1-500, default 50)
  - Default: `50`

---
