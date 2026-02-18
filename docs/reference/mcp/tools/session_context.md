# session_context & session_ingest

Cross-session memory for MCP-connected AI agents.

## How It Works

Two tools form a read/write cycle that gives agents persistent memory across sessions:

```
Session N                          Knowledge Graph                     Session N+1
┌──────────┐                      ┌──────────────┐                    ┌──────────┐
│ Agent     │──session_ingest────>│  Concepts    │──ListTools────────>│ Agent    │
│ works...  │  "save summary"     │  extracted   │  description has   │ sees     │
│           │                     │  from text   │  recent concepts   │ context  │
└──────────┘                      └──────────────┘                    └──────────┘
```

### On Connect (Passive)

When the MCP server sends its tool listing, the `session_context` tool description is **dynamically populated** with the last N concepts from the graph. The agent sees what the graph has been thinking about without calling anything.

### During Session (Active)

The agent can call `session_context` at any time to refresh or get more detail (different limit, ontology filter).

### Before Disconnect (Write)

The `session_ingest` tool description instructs the agent to save a session summary before context compacts or the session ends. The summary is ingested into an ontology named after the OAuth client (e.g., `kg CLI (admin)`), creating concepts that appear in the next session's tool listing.

## Multi-Agent Memory

Each agent gets its own ontology (derived from its OAuth client name), but the graph connects concepts across ontologies via semantic matching. Agent A's "distributed consensus" links to Agent B's "CAP theorem" through the graph's relationship extraction.

- **Local recall**: each agent sees its own recent concepts
- **Shared understanding**: graph relationships bridge agent boundaries
- **No coordination needed**: the graph handles cross-pollination

## Configuration

In `~/.config/kg/config.json`:

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
| `context_enabled` | `true` | Include recent concepts in tool listing |
| `context_limit` | `10` | Number of recent concepts to show |
| `context_ontology` | `null` | Filter to specific ontology (`null` = all) |

## Tool Schemas

### session_context

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | number | 10 | Max concepts (up to 50) |
| `ontology` | string | all | Filter by ontology name |

Returns concepts grouped by epoch with labels, IDs, and ontology tags.

### session_ingest

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `text` | string | yes | Session summary to ingest |
| `filename` | string | no | Source tracking (e.g., `session-2025-01-15.md`) |

Returns a confirmation message. The ingest job is auto-approved.

## Integration with Claude Code

The session context cycle can be reinforced through Claude Code hooks and ways:

1. **PreCompact hook**: A way that fires before context compaction, reminding the agent to call `session_ingest` with a summary
2. **SessionStart way**: On session start, the agent already sees recent concepts via the tool listing — no explicit action needed
3. **SDK agents**: Custom agents built with the Claude Agent SDK can call `session_ingest` programmatically as part of their shutdown routine

### Example Way (concept)

A Claude Code way at `~/.claude/hooks/ways/meta/compaction-checkpoint/way.md` could include:

```
Before context compacts, save your session state to the knowledge graph
using the session_ingest tool. Include: key topics discussed, decisions made,
and any insights worth preserving for the next session.
```

This creates a natural cycle: connect (see context) -> work -> compact/disconnect (save context).
