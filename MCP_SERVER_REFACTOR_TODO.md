# MCP Server Consolidation - Implementation TODO

**Branch:** `fix/mcp-server-simplify`

**Goal:** Reduce MCP server from 22 tools → 6 tools + 5 resources (73% reduction in context budget)

## Design (Documented in ADR-013)

### Tools (6 total)
1. **search** - Search concepts (unchanged from current)
2. **concept** - Consolidates 4 tools via action parameter
   - `action: "details" | "related" | "connect"`
   - Replaces: get_concept_details, find_related_concepts, find_connection, find_connection_by_search
3. **ontology** - Consolidates 4 tools via action parameter
   - `action: "list" | "info" | "files" | "delete"`
   - Replaces: list_ontologies, get_ontology_info, get_ontology_files, delete_ontology
4. **job** - Consolidates 4 tools via action parameter
   - `action: "status" | "list" | "approve" | "cancel"`
   - Replaces: get_job_status, list_jobs, approve_job, cancel_job
5. **ingest** - Keep as-is (ingest_text)
6. **source** - Keep as-is (get_source_image)

### Resources (5 total) - NEW!
MCP resources for status/health queries (fresh data on-demand, don't consume tool budget):
1. **database/stats** - Concept counts, relationship counts, ontology stats
2. **database/info** - PostgreSQL version, Apache AGE extension details
3. **database/health** - Database connection status, graph availability
4. **system/status** - Job scheduler status, resource usage
5. **api/health** - API server health and timestamp

## Implementation Approach

**DO NOT modify existing `cli/src/mcp-server.ts`** - use it as reference!

### Step 1: Rename existing file
```bash
cd cli/src
mv mcp-server.ts mcp-server.old.ts
```

### Step 2: Create new mcp-server.ts structure

Copy the header section from old file (lines 1-181):
- Imports
- Server creation
- OAuth authentication functions
- Client creation
- Exploration guide comment

Then implement NEW tool/resource structure.

### Step 3: Implement ListToolsRequestSchema handler

Replace the massive 22-tool list (lines 191-548) with 6 consolidated tools.

**Key files to reference:**
- Old tool definitions: `cli/src/mcp-server.old.ts` lines 191-548
- Design doc: `docs/architecture/ADR-013-unified-typescript-client.md` (MCP Tool Organization section)

**Example tool structure:**
```typescript
{
  name: 'concept',
  description: 'Work with concepts: get details, find related, or discover connections',
  inputSchema: {
    type: 'object',
    properties: {
      action: {
        type: 'string',
        enum: ['details', 'related', 'connect'],
        description: 'Operation to perform'
      },
      concept_id: { type: 'string', description: 'Concept ID (for details, related)' },
      // Connection params...
      from_id: { type: 'string', description: 'Starting concept (for connect with exact IDs)' },
      to_id: { type: 'string', description: 'Target concept (for connect with exact IDs)' },
      from_query: { type: 'string', description: 'Starting phrase (for semantic connect)' },
      to_query: { type: 'string', description: 'Target phrase (for semantic connect)' },
      connection_mode: {
        type: 'string',
        enum: ['exact', 'semantic'],
        description: 'Connection mode'
      },
      max_depth: { type: 'number', description: 'Max depth/hops' }
    },
    required: ['action']
  }
}
```

### Step 4: Implement ListResourcesRequestSchema handler (NEW!)

Add AFTER ListToolsRequestSchema handler:

```typescript
server.setRequestHandler(ListResourcesRequestSchema, async () => {
  return {
    resources: [
      {
        uri: 'database/stats',
        name: 'Database Statistics',
        description: 'Concept counts, relationship counts, ontology statistics',
        mimeType: 'application/json'
      },
      {
        uri: 'database/info',
        name: 'Database Information',
        description: 'PostgreSQL version, Apache AGE extension details',
        mimeType: 'application/json'
      },
      {
        uri: 'database/health',
        name: 'Database Health',
        description: 'Database connection status, graph availability',
        mimeType: 'application/json'
      },
      {
        uri: 'system/status',
        name: 'System Status',
        description: 'Job scheduler status, resource usage',
        mimeType: 'application/json'
      },
      {
        uri: 'api/health',
        name: 'API Health',
        description: 'API server health and timestamp',
        mimeType: 'application/json'
      }
    ]
  };
});
```

### Step 5: Implement ReadResourceRequestSchema handler (NEW!)

Add resource read handler:

```typescript
server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
  const { uri } = request.params;

  try {
    switch (uri) {
      case 'database/stats': {
        const result = await client.getDatabaseStats();
        return {
          contents: [{
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(result, null, 2)
          }]
        };
      }

      case 'database/info': {
        const result = await client.getDatabaseInfo();
        return {
          contents: [{
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(result, null, 2)
          }]
        };
      }

      case 'database/health': {
        const result = await client.getDatabaseHealth();
        return {
          contents: [{
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(result, null, 2)
          }]
        };
      }

      case 'system/status': {
        const result = await client.getSystemStatus();
        return {
          contents: [{
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(result, null, 2)
          }]
        };
      }

      case 'api/health': {
        const result = await client.health();
        return {
          contents: [{
            uri,
            mimeType: 'application/json',
            text: JSON.stringify(result, null, 2)
          }]
        };
      }

      default:
        throw new Error(`Unknown resource: ${uri}`);
    }
  } catch (error: any) {
    throw new Error(`Failed to read resource ${uri}: ${error.message}`);
  }
});
```

### Step 6: Implement CallToolRequestSchema handler

Replace old handler (lines 668-943) with consolidated tool routing.

**Reference old handlers for logic:**
- search_concepts: lines 677-697
- get_concept_details: lines 699-711
- find_related_concepts: lines 713-725
- find_connection: lines 727-742
- find_connection_by_search: lines 744-759
- list_ontologies: lines 784-788
- get_ontology_info: lines 790-794
- get_ontology_files: lines 796-800
- delete_ontology: lines 802-813
- get_job_status: lines 816-822
- list_jobs: lines 824-833
- approve_job: lines 835-840
- cancel_job: lines 842-847
- ingest_text: lines 850-868
- get_source_image: lines 886-919

**New handler structure:**
```typescript
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  const toolArgs = args || {};

  try {
    switch (name) {
      case 'search': {
        // Copy logic from old 'search_concepts' handler
        // ...
      }

      case 'concept': {
        const action = toolArgs.action as string;

        switch (action) {
          case 'details': {
            // Copy logic from old 'get_concept_details' handler
            // ...
          }

          case 'related': {
            // Copy logic from old 'find_related_concepts' handler
            // ...
          }

          case 'connect': {
            const mode = toolArgs.connection_mode as string || 'semantic';

            if (mode === 'exact') {
              // Copy logic from old 'find_connection' handler
              // ...
            } else {
              // Copy logic from old 'find_connection_by_search' handler
              // ...
            }
          }

          default:
            throw new Error(`Unknown concept action: ${action}`);
        }
      }

      case 'ontology': {
        const action = toolArgs.action as string;

        switch (action) {
          case 'list': {
            // Copy logic from old 'list_ontologies'
            // ...
          }
          case 'info': {
            // Copy logic from old 'get_ontology_info'
            // ...
          }
          case 'files': {
            // Copy logic from old 'get_ontology_files'
            // ...
          }
          case 'delete': {
            // Copy logic from old 'delete_ontology'
            // ...
          }
          default:
            throw new Error(`Unknown ontology action: ${action}`);
        }
      }

      case 'job': {
        const action = toolArgs.action as string;

        switch (action) {
          case 'status': {
            // Copy logic from old 'get_job_status'
            // ...
          }
          case 'list': {
            // Copy logic from old 'list_jobs'
            // ...
          }
          case 'approve': {
            // Copy logic from old 'approve_job'
            // ...
          }
          case 'cancel': {
            // Copy logic from old 'cancel_job'
            // ...
          }
          default:
            throw new Error(`Unknown job action: ${action}`);
        }
      }

      case 'ingest': {
        // Copy logic from old 'ingest_text' handler
        // ...
      }

      case 'source': {
        // Copy logic from old 'get_source_image' handler
        // ...
      }

      default:
        throw new Error(`Unknown tool: ${name}`);
    }
  } catch (error: any) {
    return {
      content: [{
        type: 'text',
        text: JSON.stringify({
          error: error.message,
          details: error.response?.data || error.toString()
        }, null, 2)
      }],
      isError: true
    };
  }
});
```

### Step 7: Keep helper functions and main() unchanged

- Keep `segmentPath()` helper (lines 556-586)
- Keep prompt handlers (lines 591-661)
- Keep `main()` function (lines 948-963)

### Step 8: Add missing imports

If not already present, add to imports at top:

```typescript
import {
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
```

And update server capabilities:

```typescript
const server = new Server(
  {
    name: 'knowledge-graph-server',
    version: '0.1.0',
  },
  {
    capabilities: {
      tools: {},
      prompts: {},
      resources: {},  // ADD THIS
    },
  }
);
```

## Testing

After implementation:

1. **Build:**
   ```bash
   cd cli
   npm run build
   ```

2. **Test with Claude Desktop:**
   - Restart Claude Desktop
   - Check tools list (should see 6 tools instead of 22)
   - Check resources list (should see 5 resources)
   - Test a tool: `kg search "test"`
   - Test a resource: Query database/stats

3. **Verify formatters still work:**
   - Search results should show grounding, evidence, etc.
   - Concept details should show all evidence
   - Connections should show full paths with grounding

## Files Modified

- `cli/src/mcp-server.ts` - Completely rewritten (keep old as .old.ts)
- `cli/src/mcp-server.old.ts` - Renamed for reference (don't commit)

## Commits Completed

- ✅ `refactor: remove legacy MCP tool configuration from kg CLI`
- ✅ `docs: update ADR-013 with MCP tool consolidation design`
- ✅ `docs: move database/health info to MCP resources instead of removing`

## Next Commit

After implementation and testing:
```
refactor: consolidate MCP server from 22 tools to 6 tools + 5 resources

Reduces context budget consumption by 73% while preserving all rich
output formatting and functionality.

Tools (22 → 6):
- search (unchanged)
- concept (consolidates 4: details, related, connect via action param)
- ontology (consolidates 4: list, info, files, delete via action param)
- job (consolidates 4: status, list, approve, cancel via action param)
- ingest (unchanged)
- source (unchanged)

Resources (0 → 5):
- database/stats, database/info, database/health
- system/status, api/health

All formatters (formatSearchResults, formatConceptDetails, etc.) remain
unchanged - tools still return complete grounding scores, evidence chains,
relationship paths, and sample quotes.

Design documented in ADR-013.
```

## Notes

- **ALL formatters stay the same** - `cli/src/mcp/formatters.ts` is unchanged
- **Rich output preserved** - grounding, evidence, paths, quotes all intact
- **Client methods unchanged** - `cli/src/api/client.ts` already has all needed methods
- **Only routing changes** - we're just consolidating tool definitions and routing

## Reference Line Numbers (Old File)

- Header/imports/auth: 1-181
- ListToolsRequestSchema: 191-548
- segmentPath helper: 556-586
- Prompt handlers: 591-661
- CallToolRequestSchema: 668-943
- main(): 948-963
