# ADR-057: Multimodal Image Ingestion with Visual Context Injection

**Status:** Proposed
**Date:** 2025-11-03
**Deciders:** System Architects
**Related ADRs:**
- [ADR-042: Ollama Local Inference Integration](./ADR-042-ollama-local-inference.md)
- [ADR-043: Embedding Strategy and Resource Management](./ADR-043-embedding-strategy-resource-management.md)

---

## Context

The knowledge graph system currently excels at ingesting prose text and extracting semantic concepts. However, a significant portion of valuable knowledge exists in visual formats:

- **PDF documents** (lecture notes, research papers, presentations)
- **Diagrams and flowcharts** (architecture diagrams, process flows)
- **Whiteboards and photos** (brainstorming sessions, sketches)
- **Screenshots** (code samples, UI mockups, error messages)
- **Charts and graphs** (data visualizations, metrics)

### The "Text-to-Speech Test" Problem

Our current system assumes all input can be read aloud as prose (the "text-to-speech test"). This works perfectly for natural language but fails for:
- Visual diagrams where spatial relationships convey meaning
- Tables where structure is semantic
- Code samples where indentation and symbols matter
- Mathematical formulas and equations
- Annotated screenshots with arrows and highlights

### Key Requirements

1. **Ingest visual content** into the knowledge graph
2. **Preserve ground truth** - keep original images, not just derived text
3. **Multimodal search** - find content by text query, image similarity, or cross-modal
4. **Unified pipeline** - reuse existing concept extraction and recursive upsert
5. **Ontology-aware** - respect knowledge domain boundaries
6. **Local-first** - support offline processing without cloud APIs
7. **Licensing clean** - avoid AGPL contamination

### Prior Art and Rejected Approaches

**MinerU (rejected)**: Sophisticated PDF→markdown tool with state-of-the-art accuracy, but AGPL v3 licensed. The network copyleft clause would contaminate our entire API codebase.

**PyMuPDF (rejected)**: Excellent PDF rendering library, but also AGPL v3 licensed.

**Separate image pipeline (rejected)**: Maintaining two upsert systems (one for text, one for images) creates code duplication, inconsistent behavior, and complexity.

**Vision-only approach (rejected)**: Direct image→concepts without text intermediate loses the ability to leverage existing extraction pipeline and text-based search.

---

## Decision

### Architecture Overview: Hairpin Pattern with Visual Context Injection

We adopt a **single unified upsert system** where images follow a "hairpin" route:

```
Image → Visual Analysis → Text Description + Visual Context → Existing Text Upsert
```

**Key architectural decisions**:

1. **Storage separation**: MinIO for heavy image blobs, PostgreSQL for lightweight embeddings and metadata
2. **Vision backend**: Granite Vision 3.3 2B (local, Apache 2.0) with fallback to GPT-4V/Claude
3. **Dual embeddings**: Nomic Vision for image embeddings, Nomic Text for description embeddings
4. **Visual context injection**: Similar images provide context during concept extraction
5. **Ontology-aware search**: Boost same-ontology results, enable cross-domain discovery
6. **LLM-driven relationships**: Model chooses appropriate relationship types (IMPLIES, CONTRADICTS, SUPPORTS, etc.)

---

## Architecture Components

### 1. Vision Backend Abstraction

Like our existing AI provider system (OpenAI, Anthropic, Ollama), vision models are abstracted:

```python
class VisionBackend(ABC):
    @abstractmethod
    async def describe_image(self, image_bytes: bytes, prompt: str) -> str:
        """Convert image to prose description"""
        pass

class GraniteVisionBackend(VisionBackend):
    """Local inference via Ollama (default)"""
    model = "granite-vision-3.3:2b"

class OpenAIVisionBackend(VisionBackend):
    """GPT-4V / GPT-4o via OpenAI API"""
    model = "gpt-4o"

class AnthropicVisionBackend(VisionBackend):
    """Claude 3.5 Sonnet via Anthropic API"""
    model = "claude-3-5-sonnet-20241022"
```

**Simple usage example**:
```python
# Standard OpenAI "tell me what this is" pattern
vision_backend = get_vision_backend()  # Based on config
description = await vision_backend.describe_image(
    image_bytes,
    prompt="Describe this image in detail."
)
```

### 2. Storage Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ PostgreSQL + Apache AGE (Lightweight, Frequently Accessed)  │
├─────────────────────────────────────────────────────────────┤
│ (:ImageAsset {                                              │
│   asset_id: "uuid",                                         │
│   minio_key: "images/Watts Lectures/2024-11-03/uuid.jpg",  │
│   image_embedding: [768 floats],  ← ~3KB                   │
│   ontology: "Watts Lectures",                               │
│   mime_type: "image/jpeg",                                  │
│   width: 1920,                                              │
│   height: 1080,                                             │
│   vision_model: "gpt-4o",  ← Tracks which model was used   │
│   embedding_model: "nomic-embed-vision:latest"              │
│ })                                                           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ MinIO (Heavy Binary Storage, Rarely Accessed)               │
├─────────────────────────────────────────────────────────────┤
│ Bucket: knowledge-graph-images/                             │
│   └── images/                                               │
│       └── Watts Lectures/                                   │
│           └── 2024-11-03/                                   │
│               └── uuid.jpg (200KB)                          │
└─────────────────────────────────────────────────────────────┘
```

**Why this split?**
- Embeddings need fast vector similarity search (graph database)
- Images are rarely accessed (only when user clicks "show source")
- Graph stays fast (~5KB per image node)
- MinIO handles cheap blob storage (~200KB per compressed image)

### 2. Graph Schema

```cypher
// ImageAsset with visual embedding
(:ImageAsset {
  asset_id: "uuid",
  minio_key: "images/{ontology}/{date}/{uuid}.jpg",
  image_embedding: vector(768),
  ontology: "Watts Lectures",
  mime_type: "image/jpeg",
  width: 1920,
  height: 1080,
  file_size: 245678,
  vision_model: "granite-vision-3.3:2b",
  embedding_model: "nomic-embed-vision:latest",
  created_at: timestamp
})

// Source with prose description (existing schema)
(:Source {
  source_id: "uuid",
  document: "watts_lecture_1_page_2.jpg",
  paragraph: "Page 2",
  full_text: "This flowchart shows a recursive awareness loop...",
  text_embedding: vector(768),
  ontology: "Watts Lectures"
})

// Link Source to ImageAsset
(:Source)-[:HAS_IMAGE]->(:ImageAsset)

// Concepts and relationships (existing schema, unchanged)
(:Concept {
  concept_id: "uuid",
  label: "recursive self-reference",
  embedding: vector(768),
  ontology: "Watts Lectures"
})

(:Concept)-[:EVIDENCED_BY]->(:Instance)-[:FROM_SOURCE]->(:Source)
(:Concept)-[:IMPLIES|SUPPORTS|CONTRADICTS|ENABLES|RELATES_TO]->(:Concept)
```

**Key points**:
- ImageAsset is separate from Source (separation of concerns)
- Both have embeddings in same vector space (Nomic's 768-dimensional space)
- Ontology stored on all nodes for filtering
- Relationships use full vocabulary (not limited to RELATES_TO)

### 3. Technology Stack

| Component | Technology | License | Why |
|-----------|-----------|---------|-----|
| **Vision Model** | Granite Vision 3.3 2B | Apache 2.0 | Local-first, 2B parameters, runs on consumer GPU |
| **Image Embeddings** | Nomic Embed Vision v2.0 | Apache 2.0 | Multimodal (text + images in same space), 768-dim |
| **Text Embeddings** | Nomic Embed Text v1.5 | Apache 2.0 | Already using, consistent with vision embeddings |
| **Object Storage** | MinIO | AGPL v3 | Network-isolated (S3 API only), no code integration |
| **PDF Conversion** | External (user's choice) | N/A | pdftoppm, ImageMagick, etc. - out of our scope |

**Note on MinIO licensing**: While MinIO is AGPL v3, we interact with it purely through the S3-compatible API (network boundary). We never link against MinIO code, import MinIO libraries, or modify MinIO source. This is similar to using PostgreSQL (also network service) - AGPL network copyleft does not apply across API boundaries.

---

## Implementation: Unified Ingestion Pipeline

### Ingestion Flow (Hairpin Pattern)

```python
async def ingest_image(
    image_bytes: bytes,
    filename: str,
    ontology: str
) -> dict:
    """
    Single unified ingestion pipeline with visual context injection.
    Images follow a "hairpin" route through text upsert.
    """

    # ═══════════════════════════════════════════════════════════
    # PHASE 1: Visual Analysis (Image-Specific)
    # ═══════════════════════════════════════════════════════════

    # 1. Generate image embedding for similarity search
    image_embedding = await nomic_vision.embed_image(image_bytes)

    # 2. Search for visually similar images WITH ONTOLOGY AWARENESS
    similar_images = await search_similar_images_with_ontology(
        embedding=image_embedding,
        target_ontology=ontology,
        min_similarity=0.60,
        limit=5,
        ontology_boost=0.1  # Boost same-ontology results
    )

    # 3. Build visual context from similar images
    visual_context = await build_visual_context(
        similar_images=similar_images,
        target_ontology=ontology
    )
    # Returns: {
    #   "target_ontology": "Watts Lectures",
    #   "similar_images": [
    #     {
    #       "similarity": 0.87,
    #       "ontology": "Watts Lectures",
    #       "same_ontology": True,
    #       "description": "Diagram showing layers of ego consciousness...",
    #       "concepts": ["ego transcendence", "self-awareness layers"],
    #       "document": "watts_lecture_1_page_1.jpg"
    #     }
    #   ]
    # }

    # 4. Generate prose description using vision model
    prose_description = await granite_vision.describe_image(
        image_bytes,
        prompt=VISION_DESCRIPTION_PROMPT
    )

    # 5. Store original image in MinIO (organized by ontology)
    asset_id = str(uuid.uuid4())
    minio_key = f"images/{ontology}/{datetime.now().strftime('%Y-%m-%d')}/{asset_id}.jpg"
    await minio_client.put_object(
        bucket="knowledge-graph-images",
        key=minio_key,
        data=image_bytes,
        content_type="image/jpeg"
    )

    # 6. Create ImageAsset node in graph
    image_asset = await create_image_asset(
        asset_id=asset_id,
        minio_key=minio_key,
        image_embedding=image_embedding,
        ontology=ontology,
        vision_model="granite-vision-3.3:2b",
        embedding_model="nomic-embed-vision:latest"
    )

    # 7. Create Source node with prose description
    source = await create_source(
        document=filename,
        full_text=prose_description,
        ontology=ontology
    )

    # 8. Link Source to ImageAsset
    await create_relationship(source, "HAS_IMAGE", image_asset)

    # ═══════════════════════════════════════════════════════════
    # PHASE 2: HAIRPIN - Feed into Existing Text Upsert Pipeline
    # ═══════════════════════════════════════════════════════════

    # 9. Extract concepts with VISUAL CONTEXT INJECTED
    concepts = await extract_and_upsert_concepts(
        text=prose_description,
        source_id=source.source_id,
        ontology=ontology,
        additional_context=visual_context  # ← Visual context injection!
    )

    # From here, everything is identical to text ingestion:
    # - LLM extracts concepts with visual context
    # - Searches for existing concepts by embedding similarity
    # - Recursive upsert (merge or create)
    # - Creates relationships (IMPLIES, SUPPORTS, etc.)
    # - All existing logic just works!

    return {
        "source_id": source.source_id,
        "asset_id": asset_id,
        "image_url": f"/api/sources/{source.source_id}/image",
        "concept_ids": [c.concept_id for c in concepts],
        "prose_description": prose_description,
        "visual_context_used": len(visual_context["similar_images"])
    }
```

### Visual Context in LLM Prompt

```python
async def extract_and_upsert_concepts(
    text: str,
    source_id: str,
    ontology: str,
    additional_context: dict = None
) -> list[Concept]:
    """
    Unified concept extraction with optional visual context.
    Works for both pure text and image-derived text.
    """

    # Base extraction prompt
    base_prompt = f"""
Extract semantic concepts from the following text for the "{ontology}" ontology.

For each concept, identify:
1. The concept label (clear, concise phrase)
2. Relationships to other concepts with type, target, and strength (0.0-1.0)

Valid relationship types:
- IMPLIES: Logical consequence, prerequisite, sequential dependency
- SUPPORTS: Corroborating evidence, reinforcement
- CONTRADICTS: Opposing viewpoint, alternative approach
- ENABLES: Provides foundation for, makes possible
- RELATES_TO: General connection, shared context or visualization
- SPECIALIZES: More specific version of a concept
- GENERALIZES: Broader category that encompasses concept

Text to analyze:
{text}
"""

    # INJECT visual context if present
    if additional_context and "similar_images" in additional_context:
        visual_section = f"""

## Visual Context
This text was extracted from an image in the "{additional_context['target_ontology']}" ontology.
It is visually similar to the following images:

"""

        for i, similar in enumerate(additional_context["similar_images"], 1):
            ontology_marker = "✓ SAME ONTOLOGY" if similar["same_ontology"] else f"(from '{similar['ontology']}' ontology)"

            visual_section += f"""
### Similar Image {i} (similarity: {similar['similarity']:.2f}) {ontology_marker}
Source document: {similar['document']}
Description: {similar['description']}
Concepts: {', '.join(similar['concepts'])}
"""

        visual_section += """
When creating relationships, consider:
- Sequential diagrams → IMPLIES (temporal/logical dependency)
- Corroborating evidence → SUPPORTS (reinforcement)
- Alternative approaches → CONTRADICTS (opposing methods)
- Foundational concepts → ENABLES (prerequisite)
- Shared visualization style → RELATES_TO (similar representation)

Same-ontology images provide strong evidence for relationships (likely same document/context).
Cross-ontology images may indicate genuine conceptual connections or coincidental visual similarity.
"""

        base_prompt = base_prompt + visual_section

    # Extract concepts from LLM
    extraction = await llm_provider.extract_concepts(base_prompt)

    # Parse and validate
    concepts = parse_extraction_response(extraction)

    # EXISTING RECURSIVE UPSERT (unchanged!)
    upserted_concepts = []
    for concept in concepts:
        # Search for existing concept by embedding similarity
        existing = await search_concepts_by_embedding(
            embedding=concept.embedding,
            ontology=ontology,
            threshold=0.85
        )

        if existing:
            # Merge into existing concept
            concept_id = await upsert_concept(existing.concept_id, concept, source_id)
        else:
            # Create new concept
            concept_id = await create_concept(concept, source_id, ontology)

        upserted_concepts.append(concept_id)

        # Create relationships (LLM chose types based on visual context)
        for rel in concept.relationships:
            await create_concept_relationship(
                from_concept_id=concept_id,
                to_concept_id=rel.target_concept_id,
                relationship_type=rel.type,  # IMPLIES, SUPPORTS, CONTRADICTS, etc.
                strength=rel.strength,
                metadata={
                    "reason": rel.reason,
                    "via_visual_context": additional_context is not None
                }
            )

    return upserted_concepts
```

---

## Multimodal Search Capabilities

The dual embedding strategy (image + text in same vector space) enables four search modes:

### 1. Text → Concepts (Existing, Unchanged)
```python
POST /api/search/concepts
Body: { "query": "recursive algorithms", "ontology": "Computer Science" }

# Searches concept text embeddings
# Returns: Concepts matching query
```

### 2. Image → Images (NEW: Visual Similarity)
```python
POST /api/search/images/by-image
Body: { "image": <uploaded-flowchart.jpg>, "ontology": "Computer Science" }

# Embeds uploaded image
# Searches image embeddings
# Returns: Visually similar images + their concepts
```

### 3. Text → Images (NEW: Cross-Modal)
```python
POST /api/search/images/by-text
Body: { "query": "architecture diagram", "ontology": "Computer Science" }

# Embeds query text
# Searches image embeddings (same vector space!)
# Returns: Images containing architecture diagrams
```

### 4. Image → Concepts (NEW: Visual to Semantic)
```python
POST /api/search/concepts/by-image
Body: { "image": <uploaded-diagram.jpg>, "ontology": "Computer Science" }

# Embeds uploaded image
# Finds visually similar images
# Returns: Concepts from those images
```

---

## Example Scenarios

### Scenario 1: Same Document, Text + Images

**Step 1**: User ingests `watts_lecture_1.txt`
```
Ontology: "Watts Lectures"
Concepts extracted: ["ego transcendence", "recursive awareness", "self-reference"]
```

**Step 2**: User converts `watts_lecture_1.pdf` to images, ingests page 1
```
Ontology: "Watts Lectures"
Visual search: No similar images yet
Concepts extracted: ["layers of consciousness", "observer-observed paradox"]
```

**Step 3**: User ingests page 2 (flowchart of recursive loops)
```
Ontology: "Watts Lectures"
Visual search finds:
  - Page 1 (similarity: 0.72) ✓ SAME ONTOLOGY
  - Description: "Diagram showing layers of ego consciousness"
  - Concepts: ["layers of consciousness", "observer-observed paradox"]

LLM sees visual context:
  "This image is from the same ontology as a diagram showing consciousness layers.
   Consider strong relationships as they're likely from the same lecture."

LLM extracts concept: "recursive self-reference"
LLM creates relationship:
  "recursive self-reference" -[ENABLES {strength: 0.90}]-> "ego transcendence"
  Reason: "Understanding recursive nature enables transcendence; same lecture context"
```

**Result**: Text and images from same document are strongly linked.

### Scenario 2: Cross-Domain Visual Discovery

**Step 1**: Ingest flowchart in "Watts Lectures"
```
Image: Flowchart showing "recursive awareness feedback loop"
Concept: "recursive self-reference"
```

**Step 2**: Later, ingest flowchart in "Computer Science"
```
Image: Flowchart showing "recursive function call stack"
Visual search finds:
  - Watts flowchart (similarity: 0.81) (from 'Watts Lectures' ontology)

LLM sees visual context:
  "Cross-ontology image with similar flowchart structure.
   Consider if there's genuine conceptual parallel or just visual coincidence."

LLM extracts concept: "recursive function call"
LLM creates relationship:
  "recursive function call" -[RELATES_TO {strength: 0.70}]-> "recursive self-reference"
  Reason: "Both describe recursive patterns in different domains; shared structural similarity"
```

**Result**: Cross-domain connection discovered through visual similarity.

### Scenario 3: Visual Pattern Clustering

**Over time**: User ingests 20 documents with bar graphs across ontologies
```
Ontology: "Sales Reports" - 5 bar graphs
Ontology: "HR Analytics" - 3 bar graphs
Ontology: "Product Metrics" - 12 bar graphs
```

**Visual clustering emerges**:
- All bar graphs are visually similar (0.75-0.90 similarity)
- Concepts get RELATES_TO relationships based on shared visualization
- User can query: "Show me all concepts visualized as bar graphs"
- System returns: Concepts from all three ontologies that use bar graph visualization

**Insight**: Visual patterns reveal presentation style, even across unrelated domains.

---

## API Routes

### Image Ingestion
```python
POST /api/ingest/image
Content-Type: multipart/form-data
Body: {
  image: <file>,
  ontology: "Watts Lectures",
  filename: "watts_lecture_1_page_2.jpg"  # Optional
}

Response: {
  "source_id": "src-123",
  "asset_id": "img-456",
  "image_url": "/api/sources/src-123/image",
  "concept_ids": ["concept-789", "concept-012"],
  "prose_description": "This flowchart shows a recursive awareness loop...",
  "visual_context_used": 2
}
```

### Image Retrieval
```python
GET /api/sources/{source_id}/image
Query: ?size=full|thumb  # Optional

Response: JPEG image (with Cache-Control headers)

# Alternative: Presigned URL for direct MinIO access
GET /api/sources/{source_id}/image/presigned
Response: {
  "url": "https://minio.local/kg-images/images/...",
  "expires_at": "2024-11-03T14:45:00Z"
}
```

### Image Similarity Search
```python
POST /api/search/images/by-image
Content-Type: multipart/form-data
Body: {
  image: <file>,
  ontology: "Computer Science",  # Optional, filters results
  limit: 10
}

Response: [
  {
    "asset_id": "img-222",
    "similarity": 0.87,
    "ontology": "Computer Science",
    "thumbnail_url": "/api/sources/src-333/image?size=thumb",
    "description": "Flowchart showing algorithm steps...",
    "source": {
      "source_id": "src-333",
      "document": "algorithm_lecture_5.jpg"
    },
    "concepts": [
      { "concept_id": "c-111", "label": "depth-first search" },
      { "concept_id": "c-222", "label": "tree traversal" }
    ]
  }
]
```

### Cross-Modal Search (Text → Images)
```python
POST /api/search/images/by-text
Body: {
  "query": "architecture diagram",
  "ontology": "Computer Science",
  "limit": 10
}

Response: [Same structure as by-image search]
```

### Visual to Semantic Search (Image → Concepts)
```python
POST /api/search/concepts/by-image
Content-Type: multipart/form-data
Body: {
  image: <file>,
  ontology: "Computer Science",
  limit: 10
}

Response: [
  {
    "concept_id": "c-456",
    "label": "event-driven architecture",
    "grounding_strength": 0.95,
    "via_images": [
      {
        "asset_id": "img-789",
        "similarity": 0.88,
        "thumbnail_url": "/api/sources/src-999/image?size=thumb"
      }
    ]
  }
]
```

---

## Configuration

### Environment Variables
```bash
# Vision Model (image → text)
VISION_PROVIDER=ollama  # Options: ollama (local), openai, anthropic
VISION_MODEL=granite-vision-3.3:2b

# For OpenAI (standard "send image to OpenAI" pattern)
# VISION_PROVIDER=openai
# VISION_MODEL=gpt-4o  # or gpt-4-turbo, gpt-4o-mini
# OPENAI_API_KEY=sk-...

# For Anthropic
# VISION_PROVIDER=anthropic
# VISION_MODEL=claude-3-5-sonnet-20241022  # or claude-3-opus, claude-3-haiku
# ANTHROPIC_API_KEY=sk-ant-...

# Embeddings (image → vector)
EMBEDDING_PROVIDER=ollama  # Must support vision embeddings
IMAGE_EMBEDDING_MODEL=nomic-embed-vision:latest
TEXT_EMBEDDING_MODEL=nomic-embed-text:latest

# MinIO Storage
MINIO_ENDPOINT=http://minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=knowledge-graph-images
MINIO_USE_SSL=false
```

### Configuration File
```yaml
# config/ingestion.yaml

visual_context:
  # Visual similarity search
  search_scope: "global"  # global, same_ontology_only, same_ontology_preferred
  min_similarity: 0.60
  max_similar_images: 5

  # Ontology boosting
  ontology_boost: 0.1  # Add 0.1 to similarity for same-ontology images

  # Cross-ontology relationships
  allow_cross_ontology_relationships: true

  # LLM prompt context
  include_ontology_info: true
  include_document_name: true
  include_concept_list: true
  max_concepts_per_image: 5
  max_description_length: 200

image_storage:
  # Compression
  format: "jpeg"  # jpeg, png, webp
  quality: 85  # 0-100 for JPEG/WebP

  # Organization
  organize_by_ontology: true  # images/{ontology}/{date}/{uuid}.jpg
  organize_by_date: true

  # Thumbnails
  generate_thumbnails: true
  thumbnail_max_width: 300

embeddings:
  # Image embeddings
  image_embedding_model: "nomic-embed-vision:latest"
  image_embedding_dimensions: 768

  # Text embeddings (for prose descriptions)
  text_embedding_model: "nomic-embed-text:latest"
  text_embedding_dimensions: 768

  # Vector search
  similarity_threshold: 0.60
  max_candidates: 20
```

---

## Database Schema Updates

### New Table: image_assets
```sql
CREATE TABLE image_assets (
    asset_id UUID PRIMARY KEY,
    minio_key VARCHAR(500) NOT NULL,
    image_embedding vector(768) NOT NULL,
    ontology VARCHAR(255) NOT NULL,
    mime_type VARCHAR(50) NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    file_size BIGINT NOT NULL,
    vision_model VARCHAR(100) NOT NULL,
    embedding_model VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Vector index for fast similarity search
CREATE INDEX idx_image_assets_embedding
ON image_assets
USING ivfflat (image_embedding vector_cosine_ops)
WITH (lists = 100);

-- Ontology filter index
CREATE INDEX idx_image_assets_ontology ON image_assets(ontology);

-- MinIO key lookup
CREATE INDEX idx_image_assets_minio_key ON image_assets(minio_key);
```

### Updated Table: sources
```sql
-- Add text_embedding for prose descriptions
ALTER TABLE sources
ADD COLUMN text_embedding vector(768);

CREATE INDEX idx_sources_text_embedding
ON sources
USING ivfflat (text_embedding vector_cosine_ops)
WITH (lists = 100);
```

### Relationship Table: source_images
```sql
CREATE TABLE source_images (
    source_id UUID NOT NULL REFERENCES sources(source_id),
    asset_id UUID NOT NULL REFERENCES image_assets(asset_id),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_id, asset_id)
);

CREATE INDEX idx_source_images_asset ON source_images(asset_id);
```

---

## Deployment

### Docker Compose Updates

```yaml
# docker-compose.yml

services:
  # ... existing services (postgres, ollama, api) ...

  minio:
    image: minio/minio:latest
    container_name: knowledge-graph-minio
    ports:
      - "9000:9000"  # S3 API
      - "9001:9001"  # Web console
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    volumes:
      - minio-data:/data
    command: server /data --console-address ":9001"
    networks:
      - kg-network
    restart: unless-stopped

volumes:
  minio-data:
    driver: local
```

### Initialization Script

```bash
#!/bin/bash
# scripts/initialize-minio.sh

# Wait for MinIO to be ready
until curl -sf http://localhost:9000/minio/health/live; do
  echo "Waiting for MinIO..."
  sleep 2
done

# Create bucket
mc alias set kg http://localhost:9000 minioadmin minioadmin
mc mb kg/knowledge-graph-images --ignore-existing

# Set bucket policy (public read for development)
mc anonymous set download kg/knowledge-graph-images

echo "MinIO initialized successfully"
```

### Ollama Model Setup

```bash
# Pull required models
docker exec kg-ollama ollama pull granite-vision-3.3:2b
docker exec kg-ollama ollama pull nomic-embed-vision:latest
docker exec kg-ollama ollama pull nomic-embed-text:latest

# Verify
docker exec kg-ollama ollama list
```

---

## Benefits

### 1. **Unified Architecture**
- Single upsert system for text and images
- No code duplication
- Consistent behavior across modalities
- Easy to maintain and extend

### 2. **Intelligent Relationship Discovery**
- LLM chooses appropriate relationship types
- Considers semantic meaning + visual context
- Not limited to rigid rules
- Discovers cross-domain connections

### 3. **Ground Truth Preservation**
- Original images stored forever in MinIO
- Text descriptions are derived evidence
- Users can always verify source material
- Addresses "telephone game" fidelity loss

### 4. **Multimodal Search**
- Text → concepts (existing)
- Image → images (visual similarity)
- Text → images (cross-modal)
- Image → concepts (visual to semantic)

### 5. **Ontology-Aware**
- Respects knowledge domain boundaries
- Boosts same-ontology results
- Enables cross-domain discovery
- Consistent with text ingestion

### 6. **Local-First**
- Granite Vision 3.3 2B runs locally
- Nomic embeddings via Ollama
- No cloud API required
- Zero per-image cost

### 7. **Licensing Clean**
- Apache 2.0: Granite Vision, Nomic embeddings
- MinIO: Network-isolated (no code integration)
- No AGPL contamination
- Safe for commercial use

### 8. **Scalable Storage**
- Graph: Lightweight (5KB per image node)
- MinIO: Heavy blobs (200KB per compressed image)
- Can migrate to S3/Azure Blob later
- Proper separation of concerns

---

## Trade-offs and Limitations

### Trade-offs

**Pro**: Single unified upsert system
**Con**: Visual context adds complexity to text extraction prompt

**Pro**: Local-first with Granite Vision
**Con**: Slower than cloud APIs (GPT-4V ~5s, Granite ~15s per image)

**Pro**: Ground truth preservation
**Con**: Storage costs (200KB per image vs. text-only)

**Pro**: Multimodal search
**Con**: Additional vector index maintenance

**Pro**: LLM-driven relationship discovery
**Con**: Less predictable than rigid rules

### Current Limitations

1. **PDF Conversion External**: Users must convert PDF→images outside our system (pdftoppm, etc.)
2. **No OCR Fallback**: Pure vision model approach; no text-layer extraction from PDFs
3. **Single Image Per Source**: One Source per image (not multi-page grouping)
4. **No Video Support**: Images only (could extend to video frames later)
5. **MinIO Single-Node**: No replication/HA in initial implementation
6. **English-Centric**: Granite Vision optimized for English text in images

### Known Issues

1. **Vision Model Hallucination**: LLMs may hallucinate details not in image
   - *Mitigation*: Keep original image for verification

2. **Embedding Similarity Noise**: High visual similarity doesn't always mean semantic relevance
   - *Mitigation*: LLM reasons about visual context, can ignore irrelevant similarities

3. **Cross-Ontology Pollution**: Too many weak cross-ontology relationships
   - *Mitigation*: Ontology boosting (0.1), LLM considers domain relevance

4. **Storage Growth**: Images consume more space than text
   - *Mitigation*: JPEG compression (85%), can migrate to cheaper object storage

---

## Future Enhancements

### Near-Term (Next 3-6 months)
- [ ] Thumbnail generation for faster UI loading
- [ ] Batch image ingestion (multiple images per API call)
- [ ] Image compression options (JPEG quality slider)
- [ ] GPT-4V and Claude 3.5 Sonnet backend support
- [ ] MinIO replication for HA

### Medium-Term (6-12 months)
- [ ] PDF→image conversion integrated (using pdf.js or similar permissive library)
- [ ] Multi-page document grouping (one Source, multiple ImageAssets)
- [ ] OCR fallback for text-heavy images
- [ ] Image annotation in UI (draw bounding boxes, add notes)
- [ ] Visual concept clustering (k-means on image embeddings)

### Long-Term (12+ months)
- [ ] Video frame extraction and analysis
- [ ] Temporal relationships between video frames (PRECEDES, FOLLOWS)
- [ ] Interactive image exploration (zoom to region, extract sub-concepts)
- [ ] Collaborative annotation (multiple users tag same image)
- [ ] Advanced visual analytics (heatmaps, attention visualization)

---

## Security Considerations

### Input Validation
- File type validation (JPEG, PNG only)
- File size limits (max 10MB per image)
- Image dimension limits (max 8000×8000 pixels)
- Malware scanning for uploaded files

### MinIO Access Control
- Private bucket by default
- Presigned URLs for time-limited access
- API server mediates all image access
- No direct public access to MinIO

### Rate Limiting
- Max 10 images per minute per user
- Max 100 images per hour per user
- Prevents abuse of vision model API

### Data Privacy
- Images stored with UUID filenames (not original names)
- Ontology-based access control (users see only their ontologies)
- Audit log for all image uploads/retrievals
- Option to purge images after concept extraction

---

## Testing Strategy

### Unit Tests
```python
def test_image_embedding_generation():
    """Test Nomic vision embedding generation"""
    image = load_test_image("flowchart.jpg")
    embedding = nomic_vision.embed_image(image)
    assert len(embedding) == 768
    assert all(isinstance(x, float) for x in embedding)

def test_visual_similarity_search():
    """Test image similarity search"""
    query_embedding = [0.1] * 768
    results = search_similar_images(query_embedding, min_similarity=0.60)
    assert all(r.similarity >= 0.60 for r in results)

def test_ontology_boost():
    """Test same-ontology results are boosted"""
    results = search_similar_images_with_ontology(
        embedding=[0.1] * 768,
        target_ontology="Watts Lectures",
        ontology_boost=0.1
    )
    same_ontology = [r for r in results if r.same_ontology]
    assert all(r.adjusted_similarity > r.similarity for r in same_ontology)
```

### Integration Tests
```python
@pytest.mark.integration
async def test_full_image_ingestion_pipeline():
    """Test complete image → concepts flow"""
    # Upload image
    image = load_test_image("bar_graph.jpg")
    result = await ingest_image(
        image_bytes=image,
        filename="test_graph.jpg",
        ontology="Test Ontology"
    )

    # Verify ImageAsset created
    asset = await get_image_asset(result["asset_id"])
    assert asset.ontology == "Test Ontology"
    assert len(asset.image_embedding) == 768

    # Verify Source created
    source = await get_source(result["source_id"])
    assert source.document == "test_graph.jpg"
    assert len(source.full_text) > 0  # Prose description exists

    # Verify concepts extracted
    assert len(result["concept_ids"]) > 0
    concepts = await get_concepts(result["concept_ids"])
    assert all(c.ontology == "Test Ontology" for c in concepts)

    # Verify image retrievable
    image_bytes = await retrieve_image(source.source_id)
    assert len(image_bytes) > 0

@pytest.mark.integration
async def test_visual_context_injection():
    """Test that similar images provide context"""
    # Ingest first image
    image1 = load_test_image("flowchart_1.jpg")
    result1 = await ingest_image(image1, "flowchart_1.jpg", "Test")

    # Ingest similar image
    image2 = load_test_image("flowchart_2.jpg")  # Visually similar
    result2 = await ingest_image(image2, "flowchart_2.jpg", "Test")

    # Check that visual context was used
    assert result2["visual_context_used"] > 0

    # Check that concepts are related
    concepts1 = await get_concepts(result1["concept_ids"])
    concepts2 = await get_concepts(result2["concept_ids"])
    relationships = await get_relationships_between(concepts1, concepts2)
    assert len(relationships) > 0  # LLM created relationships based on visual similarity
```

### Load Tests
```python
@pytest.mark.load
async def test_concurrent_image_ingestion():
    """Test system under concurrent load"""
    images = [load_test_image(f"test_{i}.jpg") for i in range(50)]

    # Ingest 50 images concurrently
    tasks = [
        ingest_image(img, f"test_{i}.jpg", "Load Test")
        for i, img in enumerate(images)
    ]
    results = await asyncio.gather(*tasks)

    # Verify all succeeded
    assert len(results) == 50
    assert all("source_id" in r for r in results)

    # Verify MinIO has all images
    assert await minio_client.object_count() >= 50
```

---

## Monitoring and Observability

### Key Metrics

```python
# Ingestion metrics
image_ingestion_duration_seconds = Histogram("image_ingestion_duration_seconds")
image_ingestion_total = Counter("image_ingestion_total", ["ontology", "status"])
visual_context_matches = Histogram("visual_context_matches")

# Storage metrics
minio_storage_bytes = Gauge("minio_storage_bytes")
minio_object_count = Gauge("minio_object_count")
image_embedding_dimension = Gauge("image_embedding_dimension")

# Search metrics
image_search_duration_seconds = Histogram("image_search_duration_seconds", ["search_type"])
image_search_results = Histogram("image_search_results")

# Vision model metrics
vision_model_latency_seconds = Histogram("vision_model_latency_seconds", ["provider"])
vision_model_errors = Counter("vision_model_errors", ["provider", "error_type"])
```

### Logging

```python
# Structured logging with context
logger.info(
    "Image ingested successfully",
    extra={
        "source_id": source.source_id,
        "asset_id": asset.asset_id,
        "ontology": ontology,
        "file_size": len(image_bytes),
        "vision_model": "granite-vision-3.3:2b",
        "visual_context_matches": len(similar_images),
        "concepts_extracted": len(concept_ids)
    }
)
```

---

## Migration Path

### Phase 1: Foundation (Week 1-2)
- [ ] Add MinIO to docker-compose
- [ ] Create image_assets table with vector index
- [ ] Implement ImageAsset node creation
- [ ] Test MinIO connectivity and storage

### Phase 2: Embeddings (Week 3-4)
- [ ] Integrate Nomic vision embeddings
- [ ] Implement image similarity search
- [ ] Add ontology-aware boosting
- [ ] Test visual similarity search

### Phase 3: Vision Model (Week 5-6)
- [ ] Integrate Granite Vision 3.3 2B
- [ ] Implement image → prose description
- [ ] Add visual context building
- [ ] Test end-to-end image ingestion

### Phase 4: Unified Pipeline (Week 7-8)
- [ ] Implement visual context injection
- [ ] Test hairpin pattern with existing upsert
- [ ] Verify relationship creation
- [ ] Integration testing

### Phase 5: API & UI (Week 9-10)
- [ ] Add image ingestion endpoint
- [ ] Add multimodal search endpoints
- [ ] Add image retrieval endpoint
- [ ] Update CLI commands

### Phase 6: Production (Week 11-12)
- [ ] Performance optimization
- [ ] Load testing
- [ ] Documentation
- [ ] Deployment guide

---

## Success Criteria

The implementation will be considered successful when:

1. ✅ **Images can be ingested** into the knowledge graph with concepts extracted
2. ✅ **Visual similarity search works** (find similar images by uploading an image)
3. ✅ **Cross-modal search works** (find images by text query)
4. ✅ **Ontology awareness functions** (same-ontology results are boosted)
5. ✅ **Visual context injection works** (similar images provide context for concept extraction)
6. ✅ **Relationships are created** based on visual similarity (IMPLIES, SUPPORTS, RELATES_TO, etc.)
7. ✅ **Ground truth is preserved** (original images retrievable from MinIO)
8. ✅ **Unified pipeline works** (image ingestion uses existing text upsert)
9. ✅ **Performance is acceptable** (<30s per image with local models, <10s with cloud)
10. ✅ **Storage is manageable** (<500KB per image including embeddings and metadata)

---

## Conclusion

This ADR proposes a **multimodal image ingestion system** that extends our text-based knowledge graph to visual documents while maintaining architectural consistency through:

- **Single unified upsert system** (no parallel pipelines)
- **Visual context injection** (LLM-driven relationship discovery)
- **Ontology-aware search** (respects knowledge domains)
- **Ground truth preservation** (original images stored)
- **Local-first approach** (Granite Vision, Nomic embeddings)
- **Licensing clean** (Apache 2.0, no AGPL contamination)

The "hairpin pattern" allows images to flow through the existing text upsert pipeline with visual context injected, enabling intelligent relationship discovery without code duplication.

This approach balances:
- **Simplicity**: One extraction system, one upsert logic
- **Intelligence**: LLM reasons about visual similarity
- **Performance**: Lightweight embeddings in graph, heavy blobs in MinIO
- **Flexibility**: Supports multiple vision backends (Granite, GPT-4V, Claude)
- **Cost**: Local inference for zero per-image cost

By treating images as first-class citizens with dual embeddings (visual + textual), we enable true multimodal knowledge discovery where concepts can be found through text queries, image similarity, or cross-modal search.
