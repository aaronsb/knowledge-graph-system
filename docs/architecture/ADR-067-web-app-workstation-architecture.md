# ADR-067: Web Application Workstation Architecture

**Status:** Proposed
**Date:** 2025-11-18
**Deciders:** Engineering Team
**Related ADRs:**
- ADR-034 (Graph Visualization Architecture) - Original explorer pattern
- ADR-064 (Specialized Visualizations) - Additional explorer types
- ADR-066 (Published Query Endpoints) - Block flow publishing

---

## Context

### Current State: Visualization-Centric Application

The web application evolved from a visualization tool with a single focus:

```
┌─────────────────────────────────────┐
│ Visualization Explorer              │
│                                     │
│ ┌─────────┐  ┌────────────────────┐ │
│ │Explorers│  │  Main Content      │ │
│ │• 2D     │  │  • Query tabs      │ │
│ │• 3D     │  │  • Graph canvas    │ │
│ └─────────┘  └────────────────────┘ │
└─────────────────────────────────────┘
```

This served well for exploring knowledge graphs, but the platform has grown capabilities that don't fit this model:

- **Ingestion** - Currently CLI/MCP only, no web interface
- **Job management** - No visibility into job queue from web
- **Graph editing** - No manual CRUD operations
- **OAuth/security** - Configuration via operator container only
- **Published endpoints** - ADR-066 introduces flow publishing with no management UI
- **Reporting** - No tabular/export views

### The Opportunity

Users need a **knowledge graph workstation** - a unified interface for:
1. **Exploring** - Visualizing and querying (current strength)
2. **Creating** - Ingesting content, editing graph
3. **Managing** - Jobs, security, published flows
4. **Reporting** - Tabular views, exports

## Decision

### Restructure Web Application as Multi-Function Workstation

Transform the left sidebar from "Explorer selector" to "Workstation navigation" with multiple functional categories.

### Navigation Structure

```
┌─────────────────────────────┐
│ Knowledge Graph             │
├─────────────────────────────┤
│ ▼ Explorers                 │
│   • 2D Force Graph          │
│   • 3D Force Graph          │
│   • [Future visualizations] │
│                             │
│ ▸ Block Editor              │
│                             │
│ ▸ Ingest                    │
│                             │
│ ▸ Jobs                      │
│                             │
│ ▸ Report                    │
│                             │
│ ▸ Edit                      │
│                             │
│ ▸ Admin                     │
└─────────────────────────────┘
```

### Category Definitions

#### Explorers (Existing, Enhanced)
Interactive graph visualizations with embedded query tools.

**Each explorer includes:**
- Query mode tabs: Smart Search | Block Builder | openCypher
- Graph canvas (2D/3D/Sankey/Heatmap/etc.)
- Node info panel
- Results list

**Pattern:** Build query → visualize → iterate → save

#### Block Editor (New - Standalone Mode)
Focused flow management environment.

**Features:**
- Saved diagrams list (left panel)
- Full block canvas (main area)
- Properties panel (right):
  - Name, description, tags
  - Execution mode toggle (Interactive ↔ Published)
  - Output format (Visualization/JSON/CSV)
  - Permissions (for published flows)

**Pattern:** Organize flows → configure → publish

#### Ingest (New)
Web-based content ingestion.

**Features:**
- Drag-and-drop file upload
- URL input field
- Batch directory selection
- Ontology selector
- Job preview with cost estimate
- Submit to job queue

**Pattern:** Drop files → configure → approve → monitor

#### Jobs (New)
Job queue visibility and management.

**Features:**
- Queue view (pending, running)
- History view (completed, failed)
- Job details (progress, logs, results)
- Approve/cancel actions
- Filter by status, ontology, date

**Pattern:** Monitor → approve → investigate

#### Report (New)
Tabular and export views.

**Features:**
- Saved queries list
- Tabular result view
- Export formats (JSON, CSV, Markdown)
- Column selection
- Sort/filter
- Pagination

**Pattern:** Query → view table → export

#### Edit (New)
Manual graph editing.

**Features:**
- Node browser/search
- Create/update/delete nodes
- Create/update/delete edges
- Bypass upsert (direct graph manipulation)
- LLM-mediated quality suggestions (optional)
- Audit trail for manual edits

**Pattern:** Find node → edit properties → save

#### Admin (New)
Platform administration.

**Features:**
- OAuth client management
  - Register clients
  - View/revoke tokens
  - Configure scopes
- User management
  - Create/edit users
  - Assign roles
- Published flow management
  - View all published flows
  - Revoke access
  - Usage analytics
- System status
  - Database stats
  - Embedding status
  - AI provider status

**Pattern:** Configure → monitor → secure

### Block Editor: Dual-Mode Architecture

The Block Builder appears in two contexts with shared state:

```
┌─────────────────────────────────────────────────┐
│           blockDiagramStore (Zustand)           │
│  • workingNodes/Edges (current canvas)          │
│  • savedDiagrams list                           │
│  • currentDiagramId                             │
│  • hasUnsavedChanges                            │
└─────────────────────────────────────────────────┘
              ▲                    ▲
              │                    │
   ┌──────────┴──────┐    ┌───────┴────────┐
   │ Embedded Mode   │    │ Standalone Mode │
   │ (in Explorers)  │    │ (sidebar item)  │
   │                 │    │                 │
   │ • Query tabs    │    │ • Diagram list  │
   │ • Compact UI    │    │ • Full canvas   │
   │ • Quick save    │    │ • Properties    │
   │ • See results   │    │ • Publish config│
   └─────────────────┘    └─────────────────┘
```

**Behavior:**
- Save in embedded → appears in standalone list
- Create in standalone → loadable in any explorer
- Switch views → same working diagram stays loaded
- Unsaved changes persist across view switches

### Routing Architecture

```typescript
// App.tsx routes
<Routes>
  <Route path="/" element={<Navigate to="/explore/2d" />} />

  {/* Explorers */}
  <Route path="/explore/2d" element={<ForceGraph2DExplorer />} />
  <Route path="/explore/3d" element={<ForceGraph3DExplorer />} />
  <Route path="/explore/sankey" element={<SankeyExplorer />} />

  {/* Block Editor */}
  <Route path="/blocks" element={<BlockEditorWorkspace />} />
  <Route path="/blocks/:diagramId" element={<BlockEditorWorkspace />} />

  {/* Ingest */}
  <Route path="/ingest" element={<IngestWorkspace />} />

  {/* Jobs */}
  <Route path="/jobs" element={<JobsWorkspace />} />
  <Route path="/jobs/:jobId" element={<JobDetail />} />

  {/* Report */}
  <Route path="/report" element={<ReportWorkspace />} />

  {/* Edit */}
  <Route path="/edit" element={<GraphEditor />} />
  <Route path="/edit/node/:nodeId" element={<NodeEditor />} />

  {/* Admin */}
  <Route path="/admin" element={<AdminDashboard />} />
  <Route path="/admin/clients" element={<OAuthClientManager />} />
  <Route path="/admin/users" element={<UserManager />} />
  <Route path="/admin/flows" element={<PublishedFlowManager />} />
</Routes>
```

### Component Architecture

```
src/
├── components/
│   ├── layout/
│   │   ├── Sidebar.tsx           # Main navigation
│   │   ├── SidebarCategory.tsx   # Collapsible category
│   │   └── MainLayout.tsx        # Shell with sidebar
│   │
│   ├── explorers/                # Existing + enhanced
│   │   ├── ForceGraph2D/
│   │   ├── ForceGraph3D/
│   │   └── common/
│   │       └── QueryTabs.tsx     # Shared query mode tabs
│   │
│   ├── blocks/                   # Block Builder
│   │   ├── BlockBuilder.tsx      # Canvas component
│   │   ├── BlockEditorWorkspace.tsx  # Standalone view
│   │   └── ...
│   │
│   ├── ingest/                   # New
│   │   ├── IngestWorkspace.tsx
│   │   ├── FileDropZone.tsx
│   │   └── IngestionForm.tsx
│   │
│   ├── jobs/                     # New
│   │   ├── JobsWorkspace.tsx
│   │   ├── JobQueue.tsx
│   │   ├── JobHistory.tsx
│   │   └── JobDetail.tsx
│   │
│   ├── report/                   # New
│   │   ├── ReportWorkspace.tsx
│   │   ├── TabularView.tsx
│   │   └── ExportPanel.tsx
│   │
│   ├── edit/                     # New
│   │   ├── GraphEditor.tsx
│   │   ├── NodeEditor.tsx
│   │   └── EdgeEditor.tsx
│   │
│   └── admin/                    # New
│       ├── AdminDashboard.tsx
│       ├── OAuthClientManager.tsx
│       ├── UserManager.tsx
│       └── PublishedFlowManager.tsx
│
└── store/
    ├── graphStore.ts
    ├── blockDiagramStore.ts
    ├── jobStore.ts              # New
    └── adminStore.ts            # New
```

### API Endpoints Required

**Existing:**
- `/api/v1/queries/*` - Graph queries
- `/api/v1/ontology/*` - Ontology management
- `/api/v1/jobs/*` - Job operations

**New or Enhanced:**

```python
# Ingest (enhanced for web)
POST /api/v1/ingest/upload       # Multipart file upload
POST /api/v1/ingest/url          # URL ingestion

# Jobs (enhanced for web)
GET  /api/v1/jobs                # List with filters
GET  /api/v1/jobs/{id}/logs      # Stream job logs

# Admin
GET  /api/v1/admin/clients       # List OAuth clients
POST /api/v1/admin/clients       # Register client
DELETE /api/v1/admin/clients/{id}

GET  /api/v1/admin/users         # List users
POST /api/v1/admin/users         # Create user
PATCH /api/v1/admin/users/{id}   # Update user

GET  /api/v1/admin/flows         # List all published flows
DELETE /api/v1/admin/flows/{id}  # Unpublish flow

# Graph editing
POST   /api/v1/graph/nodes       # Create node
PATCH  /api/v1/graph/nodes/{id}  # Update node
DELETE /api/v1/graph/nodes/{id}  # Delete node
POST   /api/v1/graph/edges       # Create edge
DELETE /api/v1/graph/edges/{id}  # Delete edge
```

### Shared Component Library

Common UI patterns across workspaces warrant a shared component library:

```
web/src/components/shared/
├── data-display/
│   ├── DataTable.tsx           # Sortable, filterable, paginated tables
│   ├── StatusBadge.tsx         # Running/Pending/Failed/Completed
│   ├── MetricCard.tsx          # Stats with label
│   └── EmptyState.tsx          # "No results" with action
│
├── layout/
│   ├── ListDetailLayout.tsx    # Left list, right detail pattern
│   ├── ActionToolbar.tsx       # Icon buttons with tooltips
│   └── PanelHeader.tsx         # Title + actions
│
├── input/
│   ├── SearchFilterBar.tsx     # Text + filters + sort
│   ├── FileDropZone.tsx        # Drag-drop with preview
│   ├── FormField.tsx           # Label + input + validation
│   └── OntologySelector.tsx    # Reusable ontology picker
│
├── feedback/
│   ├── ConfirmDialog.tsx       # Destructive action confirmation
│   ├── Toast.tsx               # Success/error/info notifications
│   ├── LoadingSkeleton.tsx     # Consistent loading states
│   └── ProgressBar.tsx         # Job/upload progress
│
└── index.ts                    # Barrel export
```

**Design tokens** (colors, spacing, typography) should be centralized in Tailwind config or CSS variables for consistent theming across all workspaces.

### Existing Patterns to Generalize

The explorer codebase already has patterns that should be extracted for workstation-wide use:

**From `explorers/common/`:**

```typescript
// PanelStack - auto-positioning panels with collapse support
<PanelStack side="right" gap={16}>
  <NodeInfoBox />
  <Legend />
</PanelStack>

// Collapsible sections pattern (NodeInfoBox, GraphSettingsPanel)
const [expanded, setExpanded] = useState(true);
<button onClick={() => setExpanded(!expanded)}>
  {expanded ? <ChevronDown /> : <ChevronRight />}
  Section Title
</button>
{expanded && <SectionContent />}

// Formatted metrics (utils.ts)
formatGrounding(0.73)        // "+73%"
formatDiversity(0.42)        // "42%"
formatAuthenticatedDiversity // "✓ 42%"
```

**From `components/shared/`:**

```typescript
// ModeDial - radio selection with icons
<ModeDial
  options={[
    { id: 'smart', label: 'Smart', icon: Search },
    { id: 'blocks', label: 'Blocks', icon: Blocks },
  ]}
  selected={mode}
  onChange={setMode}
/>

// Debounced input pattern (SearchBar)
const [query, setQuery] = useState('');
const debouncedQuery = useDebouncedValue(query, 300);
// Use debouncedQuery for API calls

// Results dropdown pattern
<SearchResultsDropdown
  results={results}
  onSelect={handleSelect}
  loading={isLoading}
/>
```

**Extraction priorities:**

1. **CollapsibleSection** - wrap the expand/collapse pattern
2. **DetailPanel** - header + scrollable content + actions
3. **MetricDisplay** - formatted number with label and indicator
4. **SearchableDropdown** - debounced input + results list
5. **SettingsForm** - labeled fields with validation

**Pattern usage by workspace:**

| Component | Explorers | Blocks | Ingest | Jobs | Report | Edit | Admin |
|-----------|:---------:|:------:|:------:|:----:|:------:|:----:|:-----:|
| DataTable |           |   ✓    |        |  ✓   |   ✓    |  ✓   |   ✓   |
| ListDetailLayout |    |   ✓    |        |  ✓   |        |  ✓   |   ✓   |
| SearchFilterBar | ✓   |   ✓    |        |  ✓   |   ✓    |  ✓   |   ✓   |
| FileDropZone |        |   ✓    |   ✓    |      |        |      |       |
| StatusBadge |         |   ✓    |        |  ✓   |        |      |   ✓   |
| ConfirmDialog |       |   ✓    |        |  ✓   |        |  ✓   |   ✓   |
| Toast | ✓             |   ✓    |   ✓    |  ✓   |   ✓    |  ✓   |   ✓   |
| EmptyState | ✓        |   ✓    |   ✓    |  ✓   |   ✓    |  ✓   |   ✓   |

### Code Reuse from CLI

The `cli/` directory contains substantial TypeScript code shared with MCP server that can be reused:

```
cli/src/
├── api/client.ts           # API client - reuse directly
├── cli/
│   ├── jobs.ts             # Job listing, approval, cancel
│   ├── ingest.ts           # File/URL ingestion logic
│   ├── oauth.ts            # OAuth client management
│   ├── admin.ts            # Admin operations
│   ├── search.ts           # Search operations
│   └── vocabulary.ts       # Vocabulary operations
└── lib/auth/
    ├── auth-client.ts      # Auth state management
    ├── device-flow.ts      # Device authorization
    └── oauth-types.ts      # Type definitions
```

**Reuse strategy:**
1. Extract shared types/interfaces to common package
2. API client methods directly portable to web
3. Auth library adapts to browser storage (localStorage vs file)
4. Business logic (validation, formatting) reusable as-is

**Benefits:**
- Consistent API interactions across CLI, MCP, and web
- Type safety shared across all clients
- Bug fixes propagate to all consumers
- Reduced development time for web workspaces

## Implementation Phases

### Phase 1: Navigation Restructure (Week 1-2)
- Refactor Sidebar to support categories
- Add routing for all workspaces
- Create placeholder components for new areas
- Block Editor standalone view (using existing BlockBuilder)

### Phase 2: Jobs Workspace (Week 3-4)
- Job list view with filters
- Job detail view with logs
- Approve/cancel actions
- Real-time status updates

### Phase 3: Ingest Workspace (Week 5-6)
- File drop zone component
- Upload API integration
- Ontology selector
- Job preview and submission

### Phase 4: Admin Workspace (Week 7-8)
- OAuth client management
- User management
- Published flow overview
- System status dashboard

### Phase 5: Report Workspace (Week 9-10)
- Tabular result view
- Export functionality
- Saved query integration

### Phase 6: Edit Workspace (Week 11-12)
- Node browser/search
- Node/edge CRUD forms
- Audit trail display

## Consequences

### Positive

1. **Unified Interface:** All platform capabilities accessible from one place
2. **Reduced CLI Dependency:** Web-first workflow for common operations
3. **Better Discoverability:** Users see full platform capabilities in sidebar
4. **Consistent UX:** Same patterns across all workspaces
5. **Enables ADR-066:** UI for publishing/managing query flows

### Negative

1. **Increased Complexity:** More routes, components, state management
2. **API Surface Growth:** Many new endpoints needed
3. **Auth Complexity:** Different capabilities need different permissions
4. **Testing Burden:** More UI to test across workspaces
5. **Bundle Size:** More code to ship (can mitigate with code splitting)

### Neutral

1. **Migration:** Existing explorer functionality unchanged
2. **Documentation:** Each workspace needs user guide
3. **Mobile:** Sidebar navigation works but some workspaces need responsive design

## Alternatives Considered

### Alternative 1: Separate Applications

**Option:** Build separate apps for admin, ingest, reporting.

**Rejected because:**
- Users must switch between apps
- Duplicate auth flows
- No unified state (e.g., can't jump from job to results)

### Alternative 2: Tab-Based Interface

**Option:** Top tabs instead of sidebar categories.

**Rejected because:**
- Limited space for 7+ categories
- Doesn't scale with ADR-064 explorer additions
- Sidebar pattern already established

### Alternative 3: Modal-Based Workflows

**Option:** Keep single explorer view, use modals for other functions.

**Rejected because:**
- Modals are disruptive for complex workflows
- Can't see job progress while editing
- No persistent state for lengthy operations

## Success Metrics

**Adoption:**
- % of users accessing non-explorer workspaces
- Web vs CLI usage for ingestion
- Time spent in each workspace category

**Efficiency:**
- Time to complete common workflows (ingest file, manage job, edit node)
- Reduction in CLI usage for routine tasks

**Discovery:**
- Users trying new workspaces after initial exposure
- Feature awareness in user surveys

---

## References

- ADR-034: Graph Visualization Architecture
- ADR-066: Published Query Endpoints
- React Router documentation
- Zustand state management patterns
