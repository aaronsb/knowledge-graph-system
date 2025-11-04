# ADR-057: Multimodal Image Ingestion with Visual Context Injection

**Status:** In Progress
**Date:** 2025-11-03
**Updated:** 2025-11-04 (Migrated from MinIO to Garage)
**Deciders:** System Architects
**Related ADRs:**
- [ADR-042: Ollama Local Inference Integration](./ADR-042-ollama-local-inference.md)
- [ADR-043: Embedding Strategy and Resource Management](./ADR-043-embedding-strategy-resource-management.md)
- [ADR-016: Apache AGE Migration](./ADR-016-apache-age-migration.md) (Parallel vendor lock-in escape)

---

## Migration Note: MinIO → Garage (2025-11-04)

**Initial implementation** used MinIO for S3-compatible object storage. However, in March 2025, MinIO gutted the admin UI from their Community Edition, relegating it to their Enterprise edition at $96,000/year. This follows the exact same bait-and-switch pattern we encountered with Neo4j (which charges $180,000/year for RBAC and security features we considered table-stakes).

**Why we switched to Garage:**
- **Governance**: Deuxfleurs cooperative (can't pull license tricks like MinIO/Neo4j)
- **License**: AGPLv3 with no Enterprise edition trap
- **EU-funded**: Government-backed stability
- **S3 API**: Drop-in replacement requiring zero code changes to our abstraction layer
- **Philosophy alignment**: Same principles that led us to escape Neo4j via Apache AGE (ADR-016)

**Migration impact**: Since we only use the S3 API (never integrated MinIO client libraries), this is purely an infrastructure change. All references to "MinIO" in this document now refer to "Garage" instead. The architectural patterns, security model, and API interactions remain identical - only the underlying object storage implementation changed.

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

1. **Storage separation**: Garage for heavy image blobs, PostgreSQL for lightweight embeddings and metadata
2. **Vision backend**: GPT-4o (primary, cloud) or Claude 3.5 Sonnet, with Ollama/Granite as optional local fallback
3. **Dual embeddings**: Nomic Vision v1.5 for image embeddings (768-dim), Nomic Text for description embeddings
4. **Visual context injection**: Similar images provide context during concept extraction
5. **Ontology-aware search**: Boost same-ontology results, enable cross-domain discovery
6. **LLM-driven relationships**: Model chooses appropriate relationship types (IMPLIES, CONTRADICTS, SUPPORTS, etc.)

**Research validation** (Nov 2025): Comprehensive testing validated GPT-4o Vision as primary backend over Granite Vision 3.3 2B due to reliability (100% vs random refusals). Nomic Vision v1.5 embeddings achieved 0.847 average top-3 similarity (27% higher than CLIP). See `docs/research/vision-testing/` for complete findings.

### Security Model (ADR-031)

Garage credentials follow the same encrypted storage pattern as OpenAI/Anthropic API keys:

- **Encrypted at rest**: Credentials stored in `kg_api.system_api_keys` table using Fernet encryption (AES-128-CBC + HMAC-SHA256)
- **Master key**: `ENCRYPTION_KEY` environment variable or Docker secrets (never in database)
- **Configuration**: Interactive setup via `./scripts/setup/initialize-platform.sh` (option 7)
- **Runtime access**: API server retrieves credentials on-demand from encrypted store
- **Endpoint config only in .env**: `GARAGE_RPC_HOST`, `GARAGE_RPC_SECRET`, `GARAGE_S3_ENDPOINT`, `GARAGE_REGION`

This ensures consistent security across all service credentials. PostgreSQL credentials remain in .env (infrastructure requirement), while external/independent service credentials (OpenAI, Anthropic, Garage) are encrypted in the database.

**Migration note**: Existing deployments with plain-text Garage credentials in .env will automatically fall back to environment variables until credentials are configured via `initialize-platform.sh`.

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

class OpenAIVisionBackend(VisionBackend):
    """GPT-4o via OpenAI API (PRIMARY - validated in research)"""
    model = "gpt-4o"

    # Research shows: 100% reliable, excellent literal descriptions
    # Cost: ~$0.01/image, Speed: ~5s/image

class AnthropicVisionBackend(VisionBackend):
    """Claude 3.5 Sonnet via Anthropic API (ALTERNATE)"""
    model = "claude-3-5-sonnet-20241022"

    # Similar quality to GPT-4o, slightly higher cost
    # Cost: ~$0.015/image, Speed: ~5s/image

class OllamaVisionBackend(VisionBackend):
    """Local inference via Ollama (OPTIONAL - pattern in place)"""
    model = "granite-vision-3.3:2b"  # or llava, etc.

    # Research shows: Inconsistent quality, random refusals
    # Use only when cloud APIs unavailable
    # Cost: $0, Speed: ~15s/image
```

**Simple usage example**:
```python
# Standard OpenAI vision pattern (primary backend)
vision_backend = get_vision_backend()  # Returns OpenAIVisionBackend by default
description = await vision_backend.describe_image(
    image_bytes,
    prompt=LITERAL_DESCRIPTION_PROMPT  # See below for literal prompt
)
```

**Literal Description Prompt** (validated in research):
```python
LITERAL_DESCRIPTION_PROMPT = """
Describe everything visible in this image literally and exhaustively.

Do NOT summarize or interpret. Do NOT provide analysis or conclusions.

Instead, describe:
- Every piece of text you see, word for word
- Every visual element (boxes, arrows, shapes, colors)
- The exact layout and positioning of elements
- Any diagrams, charts, or graphics in detail
- Relationships between elements (what connects to what, what's above/below)
- Any logos, branding, or page numbers

Be thorough and literal. If you see text, transcribe it exactly. If you see a box with an arrow pointing to another box, describe that precisely.
"""
```

**Why literal prompts?** Two-stage pipeline requires raw descriptions. Stage 1 (vision) provides literal facts. Stage 2 (LLM extraction) interprets concepts. Interpretive summaries in Stage 1 reduce Stage 2 quality.

### 2. Storage Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ PostgreSQL + Apache AGE (Lightweight, Frequently Accessed)  │
├─────────────────────────────────────────────────────────────┤
│ (:ImageAsset {                                              │
│   asset_id: "uuid",                                         │
│   object_key: "images/Watts Lectures/2024-11-03/uuid.jpg", │
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
│ Garage (Heavy Binary Storage, Rarely Accessed)              │
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
- Garage handles cheap blob storage (~200KB per compressed image)

### 2. Graph Schema

```cypher
// ImageAsset with visual embedding
(:ImageAsset {
  asset_id: "uuid",
  object_key: "images/{ontology}/{date}/{uuid}.jpg",
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
| **Vision Model (Primary)** | GPT-4o Vision | Proprietary | **Research validated**: 100% reliable, excellent literal descriptions, ~$0.01/image |
| **Vision Model (Alternate)** | Claude 3.5 Sonnet Vision | Proprietary | Similar quality to GPT-4o, provider diversity |
| **Vision Model (Local)** | Ollama (Granite, LLaVA) | Apache 2.0 | **Optional**: Pattern in place, but inconsistent quality per research |
| **Image Embeddings** | Nomic Embed Vision v1.5 | Apache 2.0 | **Research validated**: 0.847 clustering quality (27% better than CLIP), 768-dim |
| **Text Embeddings** | Nomic Embed Text v1.5 | Apache 2.0 | Already using, consistent with vision embeddings (same 768-dim space) |
| **Object Storage** | Garage | AGPL v3 | Network-isolated (S3 API only), no code integration, cooperative governance |
| **PDF Conversion** | External (user's choice) | N/A | pdftoppm, ImageMagick, etc. - out of our scope |

**Research findings** (Nov 2025, `docs/research/vision-testing/`):
- **Vision quality**: GPT-4o: ⭐⭐⭐⭐⭐ (100% reliable), Granite: ⭐⭐ (random refusals)
- **Embedding quality**: Nomic Vision: 0.847 avg similarity, CLIP: 0.666, OpenAI API: 0.542
- **Decision**: GPT-4o primary, abstraction supports Anthropic/Ollama for flexibility
- **Cost**: ~$10 per 1000 images (GPT-4o) vs $0 (local, but unreliable)

**Note on Garage licensing**: While Garage is AGPL v3, we interact with it purely through the S3-compatible API (network boundary). We never link against Garage code, import Garage libraries, or modify Garage source. This is similar to using PostgreSQL (also network service) - AGPL network copyleft does not apply across API boundaries. Unlike MinIO (which moved to Enterprise licensing), Garage is maintained by a cooperative and will remain open-source.

---

## Embedding Architecture - Critical Design Principle

**⚠️ IMPORTANT**: The system uses a **unified concept space** with **system-wide embedding consistency**. Understanding this is critical to understanding how image and document concepts relate.

### Three Types of Embeddings

**1. Visual Embeddings (Image Sources Only)**
- **Model**: Nomic Vision v1.5 (768-dim) - **ONE model system-wide**
- **Stored on**: `sources.visual_embedding` (only when `content_type='image'`)
- **Generated from**: Raw image pixels
- **Used for**: Visual-to-visual similarity search (find similar-looking images)
- **NOT used for**: Concept matching

**2. Text Embeddings on Source Prose**
- **Model**: System-wide text embedding model (Nomic Text v1.5 OR OpenAI) - **ONE model system-wide**
- **Stored on**: `sources.embedding`
- **Generated from**:
  - Document sources: Original document text
  - Image sources: Vision model prose description
- **Used for**: Direct text query → search source descriptions (cross-modal bridge)

**3. Text Embeddings on Concepts**
- **Model**: **SAME** system-wide text embedding model as #2
- **Stored on**: `concept` nodes
- **Generated from**: Concept labels extracted by LLM
- **Used for**: Concept matching, merging, and semantic search

### Why This Matters: Automatic Cross-Source Concept Matching

```
Document: "The fog comes on little cat feet" (Carl Sandburg poem)
   ↓ LLM extraction
Concept: "little cat feet" → Text embedding vector A (from system-wide text model)

Image: Photo of cat paws
   ↓ Vision model (GPT-4o)
Prose: "Close-up of little cat feet with soft paw pads"
   ↓ LLM extraction (SAME extraction pipeline)
Concept: "little cat feet" → Text embedding vector B (from SAME text model)
   ↓
Cosine similarity(A, B) = 0.92 (high similarity)
   ↓
Concepts MERGE or get SUPPORTS edge (automatic via existing matching logic)
```

**Query "little cat feet":**
```sql
-- Search concept embeddings (ONE unified concept space)
SELECT c.* FROM concepts c WHERE cosine_similarity(c.embedding, query_embedding) > 0.7

-- Returns ONE concept "little cat feet" with TWO sources:
--   1. Source: Sandburg poem (content_type='document')
--   2. Source: Cat paws photo (content_type='image')
```

### Key Principles

1. **No "image concepts" vs "document concepts"** - All concepts live in the same namespace, use the same text embeddings
2. **System-wide embedding consistency** - ONE text model, ONE visual model
3. **Changing embedding models = rebuild entire graph** - No mixing 768-dim and 1536-dim embeddings
4. **Prose is the semantic bridge** - Image descriptions use text embeddings, enabling automatic concept matching
5. **Visual embeddings are orthogonal** - Used only for visual similarity, not concept matching

### Search Paths Enabled

```
Path 1 (Concept-based):
  Text query → Concept embeddings → Find concepts → Get all sources (images + documents)

Path 2 (Source-based):
  Text query → Source prose embeddings → Find images with matching descriptions

Path 3 (Visual):
  Upload image → Visual embeddings → Find visually similar images
```

All three paths work together because:
- Path 1 & 2 use the SAME text embedding model
- Path 3 uses visual embeddings (separate space, separate use case)
- The hairpin pattern (image → prose → concepts) collapses multimodal into text-based matching

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

    # 4. Generate prose description using vision model (GPT-4o by default)
    vision_backend = get_vision_backend()  # Returns OpenAIVisionBackend
    prose_description = await vision_backend.describe_image(
        image_bytes,
        prompt=LITERAL_DESCRIPTION_PROMPT  # Literal, non-interpretive
    )

    # 5. Store original image in Garage (organized by ontology)
    asset_id = str(uuid.uuid4())
    object_key = f"images/{ontology}/{datetime.now().strftime('%Y-%m-%d')}/{asset_id}.jpg"
    await garage_client.put_object(
        bucket="knowledge-graph-images",
        key=object_key,
        data=image_bytes,
        content_type="image/jpeg"
    )

    # 6. Create ImageAsset node in graph
    image_asset = await create_image_asset(
        asset_id=asset_id,
        object_key=object_key,
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

**Step 2**: User converts slide deck `watts_lecture_1.pdf` to images, ingests page 1
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

# Alternative: Presigned URL for direct Garage access
GET /api/sources/{source_id}/image/presigned
Response: {
  "url": "https://garage.local/kg-images/images/...",
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
# Vision Model (image → text) - PRIMARY: OpenAI GPT-4o
VISION_PROVIDER=openai  # Options: openai (recommended), anthropic, ollama
VISION_MODEL=gpt-4o  # or gpt-4o-mini for lower cost
OPENAI_API_KEY=sk-...

# For Anthropic (alternate provider)
# VISION_PROVIDER=anthropic
# VISION_MODEL=claude-3-5-sonnet-20241022  # or claude-3-opus, claude-3-haiku
# ANTHROPIC_API_KEY=sk-ant-...

# For Ollama (optional local fallback - not recommended per research)
# VISION_PROVIDER=ollama
# VISION_MODEL=granite-vision-3.3:2b  # or llava, etc.
# Note: Research shows inconsistent quality, use only if cloud unavailable

# Image Embeddings (image → vector) - Nomic Vision v1.5 (local, transformers)
# Note: Uses transformers library, not Ollama
IMAGE_EMBEDDING_MODEL=nomic-ai/nomic-embed-vision-v1.5
IMAGE_EMBEDDING_PROVIDER=transformers  # Direct model loading via transformers

# Text Embeddings (description → vector) - Nomic Text v1.5 (existing)
TEXT_EMBEDDING_MODEL=nomic-embed-text:latest
TEXT_EMBEDDING_PROVIDER=ollama  # or openai

# Garage Storage (ADR-031: Credentials encrypted in database)
# Credentials configured via: ./scripts/setup/initialize-platform.sh (option 7)
# Only endpoint configuration in .env:
GARAGE_S3_ENDPOINT=http://localhost:3900
GARAGE_S3_REGION=garage
GARAGE_RPC_HOST=localhost:3901
GARAGE_BUCKET=knowledge-graph-images

# Note: GARAGE_ACCESS_KEY_ID and GARAGE_SECRET_ACCESS_KEY stored encrypted in PostgreSQL
# for consistent security model with OpenAI/Anthropic API keys
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
    object_key VARCHAR(500) NOT NULL,
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

-- S3 object key lookup
CREATE INDEX idx_image_assets_object_key ON image_assets(object_key);
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

  garage:
    image: dxflrs/garage:v2.1.0
    container_name: knowledge-graph-garage
    ports:
      - "3900:3900"  # S3 API
      - "3903:3903"  # Admin API
    environment:
      GARAGE_RPC_SECRET: ${GARAGE_RPC_SECRET}
    volumes:
      - garage-data:/data
      - garage-meta:/meta
      - ./config/garage.toml:/etc/garage.toml:ro
    command: server
    networks:
      - kg-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "garage", "status"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  garage-data:
    driver: local
  garage-meta:
    driver: local
```

### Management Scripts (PostgreSQL Pattern)

#### scripts/garage/start-garage.sh
```bash
#!/bin/bash
# Start Garage object storage

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting Garage object storage...${NC}"

# Check if Garage is already running
if docker ps | grep -q knowledge-graph-garage; then
    echo -e "${YELLOW}Garage is already running${NC}"
    echo "Garage S3 API: http://localhost:3900"
    echo "Garage Admin API: http://localhost:3903"
    exit 0
fi

# Start Garage
cd "$PROJECT_ROOT"
docker-compose up -d garage

# Wait for Garage to be healthy
echo "Waiting for Garage to be ready..."
RETRIES=30
until docker exec knowledge-graph-garage garage status > /dev/null 2>&1; do
    RETRIES=$((RETRIES - 1))
    if [ $RETRIES -eq 0 ]; then
        echo -e "${RED}Garage failed to start${NC}"
        exit 1
    fi
    sleep 2
done

echo -e "${GREEN}Garage started successfully${NC}"
echo "Garage S3 API: http://localhost:3900"
echo "Garage Admin API: http://localhost:3903"

# Run initialization
"$SCRIPT_DIR/init-garage.sh"
```

#### scripts/garage/stop-garage.sh
```bash
#!/bin/bash
# Stop Garage object storage

set -e

# Colors
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${YELLOW}Stopping Garage object storage...${NC}"

# Check if Garage is running
if ! docker ps | grep -q knowledge-graph-garage; then
    echo "Garage is not running"
    exit 0
fi

# Stop Garage (keep data)
docker-compose stop garage

echo -e "${GREEN}Garage stopped successfully${NC}"
echo "Note: Data persists in docker volumes 'garage-data' and 'garage-meta'"
echo "To remove data: docker volume rm knowledge-graph-system_garage-data knowledge-graph-system_garage-meta"
```

#### scripts/garage/init-garage.sh
```bash
#!/bin/bash
# Initialize Garage buckets and keys

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}Initializing Garage...${NC}"

# Check if Garage is running
if ! docker ps | grep -q knowledge-graph-garage; then
    echo -e "${RED}Garage is not running. Start it first with: ./scripts/garage/start-garage.sh${NC}"
    exit 1
fi

# Initialize Garage cluster and create bucket
docker exec knowledge-graph-garage sh -c "
    # Create bucket
    garage bucket create knowledge-graph-images 2>/dev/null || echo 'Bucket may already exist'

    # Create access key for API server
    garage key create kg-api-key 2>/dev/null || echo 'Key may already exist'

    # Allow access key to use bucket
    garage bucket allow knowledge-graph-images --read --write --key kg-api-key

    echo 'Garage initialization complete'
"

echo -e "${GREEN}Garage initialized successfully${NC}"
echo ""
echo "Bucket: knowledge-graph-images"
echo "S3 API: http://localhost:3900"
echo "Admin API: http://localhost:3903"
echo ""
echo "Retrieve access credentials with:"
echo "  docker exec knowledge-graph-garage garage key info kg-api-key"
```

#### scripts/services/start-storage.sh (Combined)
```bash
#!/bin/bash
# Start all storage services (PostgreSQL + Garage)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}Starting all storage services...${NC}"
echo ""

# Start PostgreSQL
echo "=== Starting PostgreSQL ==="
"$SCRIPT_DIR/start-database.sh"
echo ""

# Start Garage
echo "=== Starting Garage ==="
"$SCRIPT_DIR/../garage/start-garage.sh"
echo ""

echo -e "${GREEN}All storage services started successfully${NC}"
echo ""
echo "PostgreSQL: localhost:5432"
echo "Garage S3 API: http://localhost:3900"
echo "Garage Admin API: http://localhost:3903"
```

#### scripts/services/stop-storage.sh (Combined)
```bash
#!/bin/bash
# Stop all storage services (PostgreSQL + Garage)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${YELLOW}Stopping all storage services...${NC}"

# Stop Garage
"$SCRIPT_DIR/../garage/stop-garage.sh"

# Stop PostgreSQL
"$SCRIPT_DIR/stop-database.sh"

echo -e "${GREEN}All storage services stopped${NC}"
```

### Development Mode Quick Start

```bash
# Complete fresh setup (first time)
./scripts/services/start-storage.sh      # Start PostgreSQL + Garage
./scripts/setup/initialize-platform.sh   # Set up authentication
./scripts/services/start-api.sh -y       # Start API server

# Pull text embedding model (vision embeddings use transformers, not Ollama)
docker exec kg-ollama ollama pull nomic-embed-text:latest

# Optional: Pull local vision model (not recommended - see research findings)
# docker exec kg-ollama ollama pull granite-vision-3.3:2b

# Verify everything is running
kg health                       # Check API
kg database stats               # Check database
curl http://localhost:3903/health  # Check Garage admin API

# Ingest first image
kg ingest image my-diagram.jpg -o "Test Ontology"
```

### Daily Development Workflow

```bash
# Start everything
./scripts/services/start-storage.sh      # PostgreSQL + Garage
./scripts/services/start-api.sh -y       # API server

# Work...
kg ingest image diagram.jpg -o "My Project"
kg search images --by-text "architecture diagram"

# Stop everything
./scripts/services/stop-api.sh
./scripts/services/stop-storage.sh       # PostgreSQL + Garage (data persists)
```

### Ollama Model Management (Optional)

**Note**: Primary setup uses GPT-4o (cloud) + Nomic Vision (transformers). Ollama only needed for text embeddings.

```bash
# scripts/setup-embedding-models.sh
#!/bin/bash
# Pull required embedding models

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Setting up embedding models...${NC}"

# Check if Ollama is running
if ! docker ps | grep -q kg-ollama; then
    echo "Ollama is not running. Starting..."
    docker-compose up -d ollama
    sleep 5
fi

# Pull text embedding model (required)
echo "Pulling Nomic Embed Text..."
docker exec kg-ollama ollama pull nomic-embed-text:latest

# Note about image embeddings
echo ""
echo -e "${YELLOW}Note: Image embeddings use Nomic Vision v1.5 via transformers library${NC}"
echo "No Ollama model needed for visual embeddings"
echo ""

# Optional: Pull local vision model (not recommended)
read -p "Pull Granite Vision for local fallback? (not recommended, see research) [y/N]: " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Pulling Granite Vision 3.3 2B..."
    docker exec kg-ollama ollama pull granite-vision-3.3:2b
    echo -e "${YELLOW}Warning: Research shows Granite Vision has inconsistent quality${NC}"
    echo "Use only when cloud APIs unavailable"
fi

# Verify
echo ""
echo -e "${GREEN}Models installed:${NC}"
docker exec kg-ollama ollama list

echo ""
echo "Text embedding model ready: nomic-embed-text"
echo "Image embeddings: nomic-ai/nomic-embed-vision-v1.5 (transformers, auto-downloaded)"
echo "Vision backend: GPT-4o (cloud API, set OPENAI_API_KEY in .env)"
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
- Original images stored forever in Garage
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

### 6. **Quality-First with Local Fallback**
- GPT-4o Vision (primary): Excellent quality, ~$0.01/image
- Nomic Vision embeddings: Local via transformers, 0.847 clustering quality
- Ollama vision (optional): Available but not recommended per research
- Smart trade-off: Pay for reliability, use local embeddings

### 7. **Licensing Clean**
- Apache 2.0: Nomic Vision embeddings, Nomic Text embeddings
- Garage: Network-isolated (no code integration), cooperative governance
- No AGPL contamination
- Safe for commercial use
- No Enterprise edition trap (learned from Neo4j, MinIO)

### 8. **Scalable Storage**
- Graph: Lightweight (5KB per image node)
- Garage: Heavy blobs (200KB per compressed image)
- Can migrate to S3/Azure Blob later if needed (standard S3 API)
- Proper separation of concerns

---

## Trade-offs and Limitations

### Trade-offs

**Pro**: Single unified upsert system
**Con**: Visual context adds complexity to text extraction prompt

**Pro**: GPT-4o Vision reliable and fast (~5s per image)
**Con**: API cost (~$0.01/image, ~$10 per 1000 images) vs free local (but unreliable)

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
5. **Garage Single-Node**: No replication/HA in initial implementation (Garage supports multi-node for future)
6. **English-Centric**: Vision models optimized for English text in images

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

### Near-Term
- [ ] Thumbnail generation for faster UI loading
- [ ] Batch image ingestion (multiple images per API call)
- [ ] Image compression options (JPEG quality slider)
- [ ] GPT-4V and Claude 4.5 Sonnet backend support
- [ ] Garage multi-node replication for HA

### Medium-Term
- [ ] Multi-page document grouping (one Source, multiple ImageAssets)
- [ ] OCR fallback for text-heavy images
- [ ] Image annotation in UI (draw bounding boxes, add notes)
- [ ] Visual concept clustering (k-means on image embeddings)

### Long-Term
- [ ] Video frame extraction and analysis
- [ ] Temporal relationships between video frames (PRECEDES, FOLLOWS)
- [ ] Interactive image exploration (zoom to region, extract sub-concepts)
- [ ] Collaborative annotation (multiple users tag same image)
- [ ] Advanced visual analytics (heatmaps, attention visualization)

---

## Security Considerations

### Garage Credential Management (PostgreSQL Pattern)

Like PostgreSQL, Garage credentials are **never hardcoded** in docker-compose.yml:

#### Development (.env file)
```bash
# .env (gitignored)

# PostgreSQL credentials
POSTGRES_USER=kg_user
POSTGRES_PASSWORD=securepassword123

# Garage credentials (mirroring PostgreSQL pattern)
GARAGE_RPC_SECRET=${GARAGE_RPC_SECRET:-generate_this_on_first_run}
GARAGE_ACCESS_KEY_ID=${GARAGE_ACCESS_KEY_ID}
GARAGE_SECRET_ACCESS_KEY=${GARAGE_SECRET_ACCESS_KEY}

# API server needs both
DATABASE_URL=postgresql://kg_user:securepassword123@localhost:5432/knowledge_graph
GARAGE_S3_ENDPOINT=http://garage:3900
GARAGE_REGION=garage
```

#### Docker Compose (No Hardcoded Credentials)
```yaml
# docker-compose.yml

services:
  postgres:
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    # No hardcoded passwords!

  garage:
    environment:
      GARAGE_RPC_SECRET: ${GARAGE_RPC_SECRET}
    # No hardcoded passwords!

  api:
    environment:
      # API server trusts both storage backends
      DATABASE_URL: ${DATABASE_URL}
      GARAGE_S3_ENDPOINT: ${GARAGE_S3_ENDPOINT}
      GARAGE_ACCESS_KEY_ID: ${GARAGE_ACCESS_KEY_ID}
      GARAGE_SECRET_ACCESS_KEY: ${GARAGE_SECRET_ACCESS_KEY}
```

#### Initialize Credentials (First Run)
```bash
# scripts/setup/initialize-storage-credentials.sh
#!/bin/bash
# Generate secure credentials for PostgreSQL and Garage

set -e

ENV_FILE=".env"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Initializing storage credentials...${NC}"

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

# Generate Garage RPC secret if not set
if ! grep -q "GARAGE_RPC_SECRET=" "$ENV_FILE" || grep -q "GARAGE_RPC_SECRET=\${" "$ENV_FILE"; then
    GARAGE_RPC_SECRET=$(openssl rand -hex 32)
    echo ""
    echo -e "${YELLOW}Generated Garage RPC secret:${NC}"
    echo "GARAGE_RPC_SECRET=$GARAGE_RPC_SECRET"
    echo ""

    # Update .env
    sed -i.bak "s|GARAGE_RPC_SECRET=.*|GARAGE_RPC_SECRET=$GARAGE_RPC_SECRET|" "$ENV_FILE"
    rm -f "$ENV_FILE.bak"
fi

echo -e "${GREEN}Storage credentials configured${NC}"
echo "Credentials are stored in .env (gitignored)"
echo ""
echo "Note: Garage S3 access keys are generated by Garage during init"
echo "Run ./scripts/garage/init-garage.sh to create bucket and keys"
```

### Garage API Server Trust

API server authenticates to Garage using credentials from environment:

```python
# src/api/lib/garage_client.py

import os
import boto3
from botocore.exceptions import ClientError

class GarageClient:
    """Garage client for image storage with secure credential handling."""

    def __init__(self):
        # Load from environment (like PostgreSQL connection)
        self.endpoint = os.getenv("GARAGE_S3_ENDPOINT", "http://garage:3900")
        self.access_key = os.getenv("GARAGE_ACCESS_KEY_ID")
        self.secret_key = os.getenv("GARAGE_SECRET_ACCESS_KEY")
        self.region = os.getenv("GARAGE_REGION", "garage")
        self.bucket = os.getenv("GARAGE_BUCKET", "knowledge-graph-images")

        if not self.access_key or not self.secret_key:
            raise ValueError(
                "Garage credentials not found. Set GARAGE_ACCESS_KEY_ID and GARAGE_SECRET_ACCESS_KEY "
                "in environment (like DATABASE_URL for PostgreSQL)"
            )

        # Create S3 client for Garage
        self.client = boto3.client(
            's3',
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name=self.region
        )

        # Verify connection
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            raise ValueError(f"Failed to connect to Garage: {e}")

    async def upload_image(self, object_name: str, data: bytes, content_type: str = "image/jpeg"):
        """Upload image to Garage (authenticated)."""
        self.client.put_object(
            Bucket=self.bucket,
            Key=object_name,
            Body=data,
            ContentType=content_type
        )

    async def get_image(self, object_name: str) -> bytes:
        """Retrieve image from Garage (authenticated)."""
        response = self.client.get_object(Bucket=self.bucket, Key=object_name)
        return response['Body'].read()
```

### Production Considerations

#### Docker Secrets (Production)
```yaml
# docker-compose.prod.yml

services:
  garage:
    environment:
      GARAGE_RPC_SECRET_FILE: /run/secrets/garage_rpc_secret
    secrets:
      - garage_rpc_secret

secrets:
  garage_rpc_secret:
    external: true
```

#### Garage Bucket Policies (Advanced)
For production, create a dedicated "application key" with scoped access:

```bash
# Create application key with limited permissions
docker exec knowledge-graph-garage garage key create kg-api-key

# Create bucket with specific permissions
docker exec knowledge-graph-garage garage bucket create knowledge-graph-images

# Grant read/write access to API key
docker exec knowledge-graph-garage garage bucket allow \
  knowledge-graph-images \
  --read --write \
  --key kg-api-key

# Deny public access
docker exec knowledge-graph-garage garage bucket deny \
  knowledge-graph-images \
  --read --write \
  --key '*'

# View key credentials
docker exec knowledge-graph-garage garage key info kg-api-key
```

### Security Trust Model

```
Development:
┌──────────┐ .env creds  ┌────────────┐
│ API      │─────────────▶│ PostgreSQL │
│ Server   │             └────────────┘
│          │ .env creds  ┌────────────┐
│          │─────────────▶│ Garage     │
└──────────┘             └────────────┘

Production:
┌──────────┐ secrets     ┌────────────┐
│ API      │─────────────▶│ PostgreSQL │
│ Server   │             └────────────┘
│          │ key policy  ┌────────────┐
│          │─────────────▶│ Garage     │
└──────────┘             └────────────┘
```

**Key principles**:
1. **No hardcoded credentials** (like PostgreSQL pattern)
2. **Environment-based config** (dev: .env, prod: secrets)
3. **Least privilege** (prod: scoped bucket permissions per key)
4. **API mediates all access** (users never directly access storage)

### Input Validation
- File type validation (JPEG, PNG only)
- File size limits (max 10MB per image)
- Image dimension limits (max 8000×8000 pixels)
- Malware scanning for uploaded files

### Garage Access Control
- Private bucket by default
- Presigned URLs for time-limited access
- API server mediates all image access
- No direct public access to Garage
- Ontology-based authorization (users only access their ontologies)

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

    # Verify Garage has all images
    assert await garage_client.object_count() >= 50
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
garage_storage_bytes = Gauge("garage_storage_bytes")
garage_object_count = Gauge("garage_object_count")
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

## Implementation Checklist

### Infrastructure
- [ ] Add Garage to docker-compose
- [ ] Create initialization script (create bucket, set keys)
- [ ] Pull Ollama models (granite-vision-3.3:2b for optional local vision)

### Database Schema
- [ ] Create image_assets table with vector index
- [ ] Add text_embedding column to sources table
- [ ] Create source_images relationship table
- [ ] Run database migration

### Vision Backend
- [ ] Implement VisionBackend abstract class
- [ ] Implement GraniteVisionBackend (Ollama)
- [ ] Implement OpenAIVisionBackend (GPT-4o)
- [ ] Implement AnthropicVisionBackend (Claude)
- [ ] Add provider factory function

### Core Pipeline
- [ ] Implement image embedding generation (Nomic Vision)
- [ ] Implement visual similarity search with ontology awareness
- [ ] Implement visual context builder
- [ ] Implement image → prose description
- [ ] Integrate visual context injection into existing upsert
- [ ] Test hairpin pattern with existing text pipeline

### Storage
- [ ] Implement Garage S3 client wrapper
- [ ] Implement image upload/compression
- [ ] Implement image retrieval (full + thumbnail)
- [ ] Implement presigned URL generation

### API Routes
- [ ] POST /api/ingest/image (image ingestion)
- [ ] GET /api/sources/{id}/image (image retrieval)
- [ ] GET /api/sources/{id}/image/presigned (presigned URL)
- [ ] POST /api/search/images/by-image (visual similarity)
- [ ] POST /api/search/images/by-text (cross-modal)
- [ ] POST /api/search/concepts/by-image (visual to semantic)

### CLI Commands
- [ ] kg ingest image (upload image)
- [ ] kg search images --by-image (visual similarity)
- [ ] kg search images --by-text (cross-modal)
- [ ] kg search concepts --by-image (visual to semantic)

### Testing
- [ ] Unit tests for vision backend
- [ ] Unit tests for visual similarity search
- [ ] Integration test for full pipeline
- [ ] Load test for concurrent ingestion

### Documentation
- [ ] Update QUICKSTART.md with image ingestion
- [ ] Add image ingestion guide
- [ ] Update API documentation
- [ ] Add troubleshooting guide

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

## Considered Alternatives

### MinIO (Initially Implemented, Then Rejected)

**Why initially chosen:**
- Mature S3-compatible object storage
- Well-documented API
- Popular in self-hosted environments
- Initially appeared to be open-source friendly

**Why rejected:**
- **Enterprise license trap**: In March 2025, MinIO gutted the admin UI from Community Edition
- **Pricing**: Enterprise edition costs $96,000/year for admin features we considered table-stakes
- **Pattern recognition**: Follows exact same bait-and-switch as Neo4j ($180k/year for RBAC)
- **Community vs Enterprise split**: Essential management features moved to proprietary license
- **Governance risk**: For-profit company that demonstrated willingness to gut open-source offering

**Migration to Garage:**
- Drop-in S3 API replacement (zero code changes required)
- Standard boto3 library works identically
- All architectural patterns preserved (presigned URLs, bucket policies, etc.)
- Cooperative governance (Deuxfleurs) prevents future license traps

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
