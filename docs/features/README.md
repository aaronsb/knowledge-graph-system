# Features

The Knowledge Graph System transforms documents into interconnected concept graphs. Access the same powerful capabilities through whichever interface fits your workflow.

---

## Web Workstation

Visual interface for exploration, analysis, and administration.

### Explorers

| Workspace | Description |
|-----------|-------------|
| **2D Force Graph** | Interactive force-directed visualization of concepts and relationships |
| **3D Force Graph** | Immersive 3D exploration with spatial clustering |
| **Document Explorer** | Radial view from document to extracted concepts |
| **Polarity Explorer** | Map concepts onto bidirectional semantic spectrums |
| **Embedding Landscape** | 3D t-SNE projection showing concept neighborhoods |
| **Edge Explorer** | System-wide vocabulary and relationship analysis |
| **Vocabulary Analysis** | Query-specific breakdown of relationship types |

### Tools

| Workspace | Description |
|-----------|-------------|
| **Flow Editor** | Visual query builder for complex graph traversals |
| **Upload Content** | Drag-and-drop document and URL ingestion |
| **Job Queue** | Monitor extraction jobs with cost estimates and approval |
| **Data Export** | Tabular views and CSV/JSON exports |
| **Graph Editor** | Manual creation and editing of concepts and edges |
| **Administration** | User management, OAuth clients, system status |

---

## CLI Tool

Command-line interface for scripting and power users. Install with `cd cli && npm run build && ./install.sh`.

### Knowledge Operations

| Command | Description |
|---------|-------------|
| `kg search <query>` | Semantic search across concepts, sources, or documents |
| `kg ingest <path>` | Ingest files or directories into the graph |
| `kg document` | List and retrieve ingested documents |
| `kg source` | Access original source content and metadata |
| `kg ontology` | Manage knowledge domains (list, info, delete) |

### Analysis

| Command | Description |
|---------|-------------|
| `kg polarity` | Run polarity axis analysis between concept poles |
| `kg projection` | Manage embedding projections for visualization |
| `kg vocabulary` | Review and consolidate relationship types |
| `kg artifact` | Access stored computation results |

### System

| Command | Description |
|---------|-------------|
| `kg job` | Monitor and manage extraction jobs |
| `kg admin` | System administration and configuration |
| `kg health` | Check API server status |
| `kg login` / `kg logout` | Session authentication |

### Unix-style Shortcuts

| Command | Description |
|---------|-------------|
| `kg ls <resource>` | List resources (concepts, ontologies, jobs) |
| `kg stat <resource> <id>` | Show detailed status or statistics |
| `kg cat <resource> <id>` | Display resource details |
| `kg rm <resource> <id>` | Remove or delete resources |

---

## MCP Server

Model Context Protocol integration for AI assistants. Ten tools expose full graph capabilities.

| Tool | Description |
|------|-------------|
| **search** | Semantic search for concepts, sources, or documents |
| **concept** | Get details, find related concepts, discover connection paths |
| **ontology** | List ontologies, get info, manage knowledge domains |
| **ingest** | Submit text, files, or directories for extraction |
| **job** | Monitor job status, approve, cancel, or delete jobs |
| **document** | List documents, retrieve content, get extracted concepts |
| **source** | Retrieve original source text or images |
| **artifact** | Access saved search results and analysis |
| **epistemic_status** | Vocabulary classification (affirmative, contested, contradictory) |
| **analyze_polarity_axis** | Project concepts onto semantic spectrums |

---

## REST API

Full programmatic access at `http://localhost:8000`. OpenAPI documentation available at `/docs`.

Key endpoints:

- `POST /ingest/*` — Document ingestion (text, file, directory)
- `GET /search` — Semantic concept search
- `GET /concepts/{id}` — Concept details and relationships
- `GET /documents` — Document listing and retrieval
- `GET /ontologies` — Knowledge domain management
- `GET /jobs` — Job queue monitoring
- `POST /graph/*` — Direct graph manipulation (CRUD)
