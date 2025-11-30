# ADR-066: Published Query Endpoints

**Status:** Proposed
**Date:** 2025-11-18
**Deciders:** Engineering Team
**Related ADRs:**
- ADR-031 (Encrypted API Key Storage) - OAuth/auth infrastructure
- ADR-014 (Job Approval Workflow) - Existing approval patterns

## Overview

Imagine you've spent hours using the Visual Block Builder to craft the perfect query that extracts exactly the knowledge you need from your graph—maybe it's all the concepts related to machine learning with high grounding strength, formatted as a clean dataset. Right now, every time you need that data, you have to log into the web interface, load your query flow, click "Run Query," and manually export the results. If you want to use this data in an automated pipeline or let another application access it, you're out of luck.

This ADR introduces Published Query Endpoints, which transform your carefully crafted query flows into reusable REST API endpoints. Once you publish a query flow, external applications can execute it programmatically using OAuth credentials, receiving the results as JSON or CSV without any manual intervention. This is similar to how you might save a complex SQL query as a stored procedure or view in a traditional database, except these flows can include not just graph traversals but also semantic search, enrichment operations, and custom filters.

The key innovation is that these aren't just raw graph queries—they're curated data pipelines that encapsulate your domain expertise about what knowledge matters and how it should be filtered and formatted. You control who can access each published endpoint, making it possible to share specific views of your knowledge graph with different teams or applications while keeping the underlying data secure.

---

## Context

### Current State: Interactive-Only Query Execution

The Visual Block Builder creates query flows that can only be executed interactively within the web UI. Users must:

1. Build query in Block Builder
2. Execute via "Run Query" button
3. View results in graph visualization
4. Repeat for each query invocation

This works well for exploration and analysis, but limits the platform's utility for:

- **Automated pipelines** - CI/CD systems needing knowledge graph data
- **External applications** - Third-party tools integrating with the knowledge graph
- **Scheduled queries** - Periodic data extraction for reporting
- **Multi-tenant access** - Different applications accessing shared knowledge

### The Opportunity

Users invest significant effort designing query flows that extract valuable subsets of their knowledge graph. These flows should be reusable as programmatic endpoints without requiring the creator to be logged in or manually executing them.

## Decision

### Published Query Endpoints

Introduce the concept of **Published Query Endpoints** - saved query flows that become accessible via REST API using OAuth 2.0 client credentials.

### Architecture Overview

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│  Block Builder  │─────▶│  Query Registry  │◀─────│   REST API      │
│  (Create Flow)  │      │  (Store Flows)   │      │  (Execute Flow) │
└─────────────────┘      └──────────────────┘      └─────────────────┘
                                                            │
                                                            ▼
                                              ┌─────────────────────────┐
                                              │   External Consumers    │
                                              │  (OAuth client creds)   │
                                              └─────────────────────────┘
```

### Flow Lifecycle

1. **Create**: User builds query flow in Block Builder
2. **Publish**: User marks flow as "Published" (Start block execution mode)
3. **Register**: System generates unique Flow ID and registers endpoint
4. **Configure**: User sets output format (End block: JSON, CSV, or Graph data)
5. **Authorize**: User grants access to specific OAuth clients
6. **Execute**: External systems call endpoint with client credentials + flow ID

### Beyond Pure openCypher: Smart Block Operations

Query flows are more than graph traversals. The Block Builder compiles to **annotated openCypher** - valid Cypher with embedded markers that trigger additional operations:

**Smart Blocks (non-Cypher operations):**
- **Vector Search** - Semantic similarity via embedding API
- **Epistemic Filter** - Filter by vocabulary epistemic status
- **Enrich** - Fetch concept details (grounding, ontology, search terms)

**Cypher Blocks (pure graph operations):**
- **Neighborhood** - Graph traversal
- **Filter** - WHERE clauses
- **Limit** - Result constraints

This is conceptually similar to Neo4j's Cypher extensions or stored procedures - the execution engine interprets the annotated query and orchestrates calls to various services (embedding API, concept details API) alongside the graph database.

**Implication for Published Endpoints:**
The execution engine must be an internal worker that can:
1. Parse annotated openCypher
2. Execute Cypher portions against Apache AGE
3. Invoke smart block services (vector search, enrichment)
4. Compose final results

This makes published flows more powerful than raw Cypher endpoints - they're curated data pipelines that encapsulate complex multi-service operations behind a simple API call.

### Start Block: Execution Mode

```typescript
interface StartBlockParams {
  executionMode: 'interactive' | 'published';
  flowName?: string;  // Human-readable name
  // Future: flowSlug, description, tags
}
```

- **Interactive** (default): Execute in UI, results render to graph
- **Published**: Register as API endpoint, callable externally

### End Block: Output Format

```typescript
interface EndBlockParams {
  outputFormat: 'visualization' | 'json' | 'csv';
  // Future: pagination, field selection, transformations
}
```

- **Visualization** (default): Render to graph UI
- **JSON**: Return structured node/edge data
- **CSV**: Return flattened tabular data

### API Design

```
POST /api/v1/flows/{flow_id}/execute
Authorization: Bearer <access_token>
Content-Type: application/json

{
  "parameters": {
    // Flow-specific parameters if any
  }
}
```

Response varies by output format:
- **JSON**: `{ "nodes": [...], "edges": [...], "metadata": {...} }`
- **CSV**: Text/CSV with appropriate headers

### Authentication Model

Uses existing OAuth 2.0 infrastructure (ADR-031):

1. **Client Registration**: External applications register as OAuth clients
2. **Client Credentials Grant**: `client_id` + `client_secret` → `access_token`
3. **Flow Authorization**: Access tokens are scoped to specific published flows
4. **No User Session**: Machine-to-machine, not user-interactive

### Security Considerations

- **Flow Ownership**: Only flow owner can publish/unpublish
- **Scoped Access**: Clients authorized per-flow, not blanket access
- **Rate Limiting**: Prevent abuse of published endpoints
- **Audit Logging**: Track all external executions
- **Revocation**: Owner can unpublish or revoke client access

### Database Schema (Future)

```sql
-- Published query flows
CREATE TABLE published_flows (
  flow_id UUID PRIMARY KEY,
  owner_id UUID REFERENCES users(id),
  name VARCHAR(255) NOT NULL,
  slug VARCHAR(255) UNIQUE,
  description TEXT,
  flow_definition JSONB NOT NULL,  -- Serialized nodes/edges
  output_format VARCHAR(50) DEFAULT 'json',
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

-- Client authorization for flows
CREATE TABLE flow_authorizations (
  flow_id UUID REFERENCES published_flows(flow_id),
  client_id UUID REFERENCES oauth_clients(id),
  granted_at TIMESTAMP DEFAULT NOW(),
  granted_by UUID REFERENCES users(id),
  PRIMARY KEY (flow_id, client_id)
);

-- Execution audit log
CREATE TABLE flow_executions (
  execution_id UUID PRIMARY KEY,
  flow_id UUID REFERENCES published_flows(flow_id),
  client_id UUID REFERENCES oauth_clients(id),
  executed_at TIMESTAMP DEFAULT NOW(),
  duration_ms INTEGER,
  result_count INTEGER,
  status VARCHAR(50)
);
```

## Consequences

### Positive

- **Reusability**: Query flows become first-class platform resources
- **Integration**: External systems can consume knowledge graph data
- **Automation**: Enables scheduled and triggered query execution
- **Value extraction**: Users can share curated views without sharing raw data
- **API-first**: Moves platform toward headless/API-driven architecture

### Negative

- **Complexity**: Adds OAuth scoping, flow registry, execution engine
- **Security surface**: External API access requires careful authorization
- **Versioning**: Published flows may need versioning for breaking changes
- **Monitoring**: Must track performance and usage of published endpoints

### Neutral

- **UI changes**: Start/End blocks gain controls (already implemented as placeholders)
- **Migration path**: Existing saved diagrams remain interactive-only until published

## Alternatives Considered

### 1. GraphQL Endpoint

Expose full graph via GraphQL, let consumers write their own queries.

**Rejected because:**
- Exposes entire graph structure to external consumers
- No curation - users can't limit what's accessible
- Complex query language for non-technical users

### 2. Webhook Push Model

Flows push results to configured webhooks instead of pull API.

**Partially applicable:**
- Could complement pull API as output option
- Useful for event-driven architectures
- May add as future output format

### 3. Export Only (No Live API)

Users export flow results as static files (JSON/CSV) for sharing.

**Rejected because:**
- No live data - results stale immediately
- Manual process for updates
- Doesn't enable automation

## Implementation Phases

### Phase 1: UI Placeholders (Current)
- Add execution mode to Start block (interactive/published toggle)
- Add output format to End block (visualization/json/csv)
- Controls are visible but non-functional

### Phase 2: Flow Registry
- Database schema for published flows
- Save/load flows with publication metadata
- List published flows in UI

### Phase 3: Execution Engine
- REST endpoint for flow execution
- Query compilation from flow definition
- Output format rendering (JSON, CSV)

### Phase 4: Authorization
- OAuth client registration
- Per-flow client authorization
- Access token scoping

### Phase 5: Operations
- Rate limiting
- Audit logging
- Usage analytics
- Flow versioning

## Open Questions

1. **Parameterization**: Should published flows accept runtime parameters (e.g., search terms)?
2. **Caching**: Should results be cached for performance? How to invalidate?
3. **Versioning**: How to handle flow updates without breaking consumers?
4. **Pricing**: Should published endpoint usage be metered/billed differently?

---

## References

- OAuth 2.0 Client Credentials: [RFC 6749 Section 4.4](https://tools.ietf.org/html/rfc6749#section-4.4)
- Existing auth infrastructure: ADR-031
