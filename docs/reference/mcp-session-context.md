---
id: 07.006.R
domain: ui
mode: reference
---

# MCP Session Context

Two MCP tools — `session_context` and `session_ingest` — give agents persistent memory across sessions by reading from and writing to the Kappa Graph.

## How the cycle works

```
Session N                          Kappa Graph                         Session N+1
┌──────────┐                      ┌──────────────┐                    ┌──────────┐
│ Agent     │──session_ingest────>│  Concepts    │──ListTools────────>│ Agent    │
│ works...  │  "save summary"     │  extracted   │  description has   │ sees     │
│           │                     │  from text   │  recent concepts   │ context  │
└──────────┘                      └──────────────┘                    └──────────┘
```

**On connect (passive):** When the MCP server responds to `ListTools`, the `session_context` tool description is dynamically populated with the last N concepts from the graph. The agent sees what the graph contains without calling anything.

**During a session (active):** Call `session_context` at any time to refresh the view, change the limit, or filter by ontology.

**Before disconnect (write):** Call `session_ingest` with a session summary. The text is ingested into an ontology derived from the OAuth client name (e.g., `kg CLI (admin)`), creating concepts that appear in the next session's tool listing. The ingest job is auto-approved.

## Multi-agent memory

Each agent writes to its own ontology (derived from its OAuth client name), but the graph links concepts across ontologies via semantic matching. Agent A's "distributed consensus" can link to Agent B's "CAP theorem" through the graph's relationship extraction.

- Each agent sees its own recent concepts via `session_context`.
- Graph relationships bridge agent boundaries automatically.

## Configuration

Set in `~/.config/kg/config.json` under the `session` key:

```json
{
  "session": {
    "context_enabled": true,
    "context_limit": 10,
    "context_ontology": null
  }
}
```

| Key | Default | Description |
|-----|---------|-------------|
| `context_enabled` | `true` | Populate `session_context` tool description with recent concepts on `ListTools`. |
| `context_limit` | `10` | Number of recent concepts included in the tool listing. |
| `context_ontology` | `null` | Restrict to a specific ontology. `null` includes all ontologies. |

Configuration changes take effect on the next MCP connection; no API restart is required.

## Tool reference

### session_context

Returns concepts grouped by epoch with labels, IDs, and ontology tags.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | number | `10` | Maximum concepts to return. Upper bound: 50. |
| `ontology` | string | all ontologies | Filter results to a single ontology name. |

### session_ingest

Ingests a session summary as text. The ingest job is auto-approved.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `text` | string | yes | Session summary to ingest. |
| `filename` | string | no | Source label for tracking (e.g., `session-2025-01-15.md`). |

## Integration with Claude Code

Session context works with Claude Code hooks and ways:

- **PreCompact way:** A way that fires before context compaction can instruct the agent to call `session_ingest` with a summary of key topics, decisions, and insights. Example path: `~/.claude/hooks/ways/meta/compaction-checkpoint/way.md`.
- **SessionStart:** Recent concepts are already embedded in the tool listing description — no explicit action needed at session start.
- **SDK agents:** Agents built with the Anthropic SDK can call `session_ingest` programmatically as part of their shutdown routine.
