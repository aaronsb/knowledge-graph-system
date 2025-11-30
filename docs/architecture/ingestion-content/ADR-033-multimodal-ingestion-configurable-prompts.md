# ADR-033: Multimodal Image Ingestion with Configurable Prompt System

**Status:** Proposed
**Date:** 2025-10-16
**Deciders:** Development Team
**Related:** ADR-014 (Job Approval Workflow), ADR-015 (Smart Chunking), ADR-023 (Markdown Preprocessing)

## Overview

Right now, the knowledge graph system can only process text documents. But what about all the valuable knowledge locked in PowerPoint presentations, technical diagrams, screenshots, and charts? These visual formats contain concepts and relationships that would be incredibly useful to capture, but the system currently can't see them at all.

Modern AI vision models like GPT-4o and Claude can look at images and describe what they see in detail. This ADR proposes adding image ingestion by having vision AI translate images into detailed text descriptions, which then flow through the same concept extraction pipeline we already use for documents. A photo of a flowchart becomes a prose description of that flowchart, and the system extracts concepts from the description just like it would from written text.

But different types of documents benefit from different extraction strategies. Academic papers need formal terminology and citations, business presentations focus on strategic concepts and metrics, and technical documentation emphasizes implementation details. Currently, the system uses a single hardcoded prompt for all content types, which limits its ability to adapt to different knowledge domains.

This ADR also introduces a configurable prompt system where extraction strategies are stored in the database and can be customized per content type or even per ontology. Organizations can experiment with different prompts without code changes, and the system can optimize extraction for specific knowledge domains while maintaining a unified architecture underneath.

---

## Context

The knowledge graph system currently processes only text documents. However, valuable knowledge exists in visual formats:

- **PowerPoint/Google Slides**: Presentation decks with diagrams, frameworks, and concepts
- **Technical Diagrams**: Architecture diagrams, flowcharts, UML, entity-relationship models
- **Charts and Visualizations**: Data visualizations, graphs, infographics
- **Screenshots**: UI mockups, code snippets, documentation captures
- **Scanned Documents**: PDFs converted to images, handwritten notes

### Current Limitations

1. **Text-only ingestion**: Cannot process `.png`, `.jpg`, `.pdf` (image-based), etc.
2. **Manual conversion required**: Users must OCR or manually transcribe visual content
3. **Loss of context**: Diagrams, layouts, and visual relationships lost in transcription
4. **Missed opportunities**: Multimodal AI (GPT-4o Vision, Claude 3.5 Sonnet Vision) can describe images

### Prompt Customization Need

Different content types benefit from different extraction strategies:

| Content Type | Optimal Prompt Focus |
|--------------|----------------------|
| Academic papers | Formal terminology, citations, methodology |
| Technical documentation | Code snippets, API references, implementation details |
| Business presentations | Strategic concepts, metrics, frameworks |
| Legal documents | Precise language, definitions, obligations |
| Meeting notes | Action items, decisions, attendees |

Currently, the system uses a single hardcoded prompt in `llm_extractor.py`. This limits:
- **Domain adaptation**: Cannot tune extraction for specific knowledge domains
- **Experimentation**: Changing prompts requires code edits and deployment
- **User control**: Organizations cannot optimize for their content
- **Multi-tenancy**: Different users/ontologies cannot have specialized extraction

## Decision

Implement **multimodal image ingestion** with **database-stored configurable prompts** using a **profile-based system**.

### Architecture

```
┌───────────────────────────────────────────────────────────┐
│ Phase 1: Multimodal Image Ingestion                      │
│                                                           │
│  POST /ingest (file upload)                              │
│    ├─> Detect image file (.png, .jpg, .jpeg, .gif, .webp)│
│    ├─> If image:                                         │
│    │     └─> provider.describe_image(bytes, prompt)     │
│    │           └─> Returns text description             │
│    ├─> Replace content with description text            │
│    └─> Continue normal flow (chunking → extraction)     │
│                                                           │
│  Injection Point: routes/ingest.py:156 (single location) │
│  Downstream: 100% code reuse (no changes needed)         │
└───────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────┐
│ Phase 2: Configurable Prompts (Proposed)                 │
│                                                           │
│  Database Table: prompt_profiles                         │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ profile_id     | SERIAL PRIMARY KEY                 │ │
│  │ profile_name   | VARCHAR(100) UNIQUE                │ │
│  │ prompt_type    | VARCHAR(50) (image_description,    │ │
│  │                  concept_extraction, code_translation)│ │
│  │ prompt_text    | TEXT                               │ │
│  │ is_default     | BOOLEAN DEFAULT FALSE              │ │
│  │ created_by     | VARCHAR(100)                       │ │
│  │ created_at     | TIMESTAMP                          │ │
│  │ updated_at     | TIMESTAMP                          │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
│  Usage:                                                   │
│    - POST /ingest?prompt_profile=academic               │
│    - Ontology-level default: ontology → prompt_profile  │
│    - System default: is_default = true                  │
└───────────────────────────────────────────────────────────┘
```

### Phase 1: Multimodal Image Ingestion (Immediate)

#### Image Detection & Processing

```python
# src/api/routes/ingest.py (line ~156)

def _is_image_file(filename: str) -> bool:
    """Check if file is a supported image format"""
    if not filename:
        return False
    ext = filename.lower().split('.')[-1]
    return ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']

# Injection point
content = await file.read()

# NEW: Detect and process images
if _is_image_file(file.filename):
    from ..lib.ai_providers import get_provider

    provider = get_provider()
    description_response = provider.describe_image(
        image_data=content,
        prompt=IMAGE_DESCRIPTION_PROMPT  # Hardcoded in Phase 1
    )

    # Replace image bytes with text description
    content = description_response["text"].encode('utf-8')

    # TODO: Track vision tokens for cost estimation
    vision_tokens = description_response.get("tokens", 0)

# Continue normal flow (hashing, base64, job creation)
content_hash = hasher.hash_content(content)
# ...
```

#### Default Image Description Prompt (Phase 1)

```python
# src/api/lib/ai_providers.py

IMAGE_DESCRIPTION_PROMPT = """Analyze this image for knowledge extraction. Provide a detailed description:

**Text Content:** Transcribe ALL visible text exactly as written (titles, headings, bullets, labels, annotations).

**Visual Structure:** Describe diagrams, charts, tables, hierarchies, and layout organization.

**Relationships:** Explain connections shown via arrows, lines, groupings, proximity, or color coding.

**Key Concepts:** Identify main ideas, frameworks, terminology, principles, or models presented.

**Context:** Note the content type (e.g., presentation slide, flowchart, system diagram).

Be thorough - capture information density over brevity. Focus on facts and structure, not interpretation."""
```

#### AIProvider Interface Extension

```python
# src/api/lib/ai_providers.py

class AIProvider(ABC):
    @abstractmethod
    def describe_image(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        """
        Generate detailed description of an image using multimodal AI.

        Args:
            image_data: Raw image bytes (PNG, JPEG, etc.)
            prompt: Description prompt (e.g., "Describe this slide in detail")

        Returns:
            Dict with 'text' (description) and 'tokens' (usage info)
        """
        pass
```

#### OpenAI Implementation (GPT-4o Vision)

```python
class OpenAIProvider(AIProvider):
    def describe_image(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        import base64

        image_base64 = base64.b64encode(image_data).decode('utf-8')

        response = self.client.chat.completions.create(
            model="gpt-4o",  # Has vision capabilities
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_base64}",
                            "detail": "high"  # High detail for better extraction
                        }
                    }
                ]
            }],
            max_tokens=2000,  # Allow detailed descriptions
            temperature=0.3   # Lower for consistency
        )

        return {
            "text": response.choices[0].message.content.strip(),
            "tokens": response.usage.total_tokens
        }
```

#### Anthropic Implementation (Claude 3.5 Sonnet Vision)

```python
class AnthropicProvider(AIProvider):
    def describe_image(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        import base64

        image_base64 = base64.b64encode(image_data).decode('utf-8')

        # Detect image type from magic bytes
        image_type = "image/png"  # Default
        if image_data[:2] == b'\xff\xd8':
            image_type = "image/jpeg"
        elif image_data[:4] == b'GIF8':
            image_type = "image/gif"
        elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
            image_type = "image/webp"

        message = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",  # Latest vision model
            max_tokens=2000,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_type,
                            "data": image_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }]
        )

        return {
            "text": message.content[0].text.strip(),
            "tokens": message.usage.input_tokens + message.usage.output_tokens
        }
```

### Phase 2: Configurable Prompt System (Proposed)

#### Database Schema

```sql
-- Prompt profiles for customizable extraction strategies
CREATE TABLE IF NOT EXISTS prompt_profiles (
    profile_id SERIAL PRIMARY KEY,
    profile_name VARCHAR(100) UNIQUE NOT NULL,
    prompt_type VARCHAR(50) NOT NULL,  -- 'image_description', 'concept_extraction', 'code_translation'
    prompt_text TEXT NOT NULL,
    is_default BOOLEAN DEFAULT FALSE,
    created_by VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure only one default per prompt_type
    CONSTRAINT unique_default_per_type UNIQUE NULLS NOT DISTINCT (prompt_type, is_default)
);

-- Ontology-level prompt profile assignments
CREATE TABLE IF NOT EXISTS ontology_prompt_profiles (
    ontology_name VARCHAR(255) NOT NULL,
    prompt_type VARCHAR(50) NOT NULL,
    profile_id INTEGER NOT NULL REFERENCES prompt_profiles(profile_id) ON DELETE CASCADE,
    PRIMARY KEY (ontology_name, prompt_type)
);

-- Example: Predefined profiles
INSERT INTO prompt_profiles (profile_name, prompt_type, prompt_text, is_default, created_by) VALUES
('default_image_description', 'image_description',
 'Analyze this image for knowledge extraction...' -- Full prompt from Phase 1
 , TRUE, 'system'),

('academic_extraction', 'concept_extraction',
 'Extract concepts from this academic text. Focus on:
  - Formal definitions and terminology
  - Research methodologies
  - Citations and references
  - Theoretical frameworks
  - Hypotheses and findings',
 FALSE, 'system'),

('business_extraction', 'concept_extraction',
 'Extract concepts from this business document. Focus on:
  - Strategic objectives and KPIs
  - Organizational structures
  - Business processes
  - Decision frameworks
  - Stakeholder relationships',
 FALSE, 'system');
```

#### API Endpoints for Prompt Management

```python
# src/api/routes/admin_prompts.py

@router.post("/admin/prompts", status_code=201)
async def create_prompt_profile(
    profile_name: str,
    prompt_type: Literal["image_description", "concept_extraction", "code_translation"],
    prompt_text: str,
    is_default: bool = False,
    admin = Depends(require_admin)
):
    """
    Create a new prompt profile.

    Admin can create custom prompts for different content types.
    Setting is_default=true makes it the fallback for that prompt_type.
    """
    # Validation, duplicate check, database insert
    pass

@router.get("/admin/prompts")
async def list_prompt_profiles(
    prompt_type: Optional[str] = None,
    admin = Depends(require_admin)
):
    """List all prompt profiles, optionally filtered by type"""
    pass

@router.patch("/admin/prompts/{profile_id}")
async def update_prompt_profile(
    profile_id: int,
    prompt_text: Optional[str] = None,
    is_default: Optional[bool] = None,
    admin = Depends(require_admin)
):
    """Update prompt text or default status"""
    pass

@router.delete("/admin/prompts/{profile_id}")
async def delete_prompt_profile(
    profile_id: int,
    admin = Depends(require_admin)
):
    """Delete a prompt profile (cannot delete if in use by ontologies)"""
    pass

@router.post("/admin/ontologies/{ontology_name}/prompts")
async def assign_ontology_prompt(
    ontology_name: str,
    prompt_type: str,
    profile_id: int,
    admin = Depends(require_admin)
):
    """
    Assign a prompt profile to an ontology.

    Future ingestions for this ontology will use this profile.
    """
    pass
```

#### Prompt Resolution Logic

```python
# src/api/lib/prompt_resolver.py

class PromptResolver:
    """Resolve which prompt to use for a given operation"""

    def __init__(self, db_connection):
        self.db = db_connection

    def get_prompt(
        self,
        prompt_type: str,
        ontology_name: Optional[str] = None,
        profile_id: Optional[int] = None
    ) -> str:
        """
        Get prompt text with fallback chain:

        1. Explicit profile_id (user override)
        2. Ontology-specific profile
        3. System default for prompt_type
        4. Hardcoded fallback

        Args:
            prompt_type: 'image_description', 'concept_extraction', 'code_translation'
            ontology_name: Optional ontology name for context
            profile_id: Optional explicit profile ID override

        Returns:
            Prompt text to use
        """
        # 1. Explicit profile_id
        if profile_id:
            prompt = self._get_profile_by_id(profile_id)
            if prompt:
                return prompt

        # 2. Ontology-specific
        if ontology_name:
            prompt = self._get_ontology_prompt(ontology_name, prompt_type)
            if prompt:
                return prompt

        # 3. System default
        prompt = self._get_default_prompt(prompt_type)
        if prompt:
            return prompt

        # 4. Hardcoded fallback
        return FALLBACK_PROMPTS[prompt_type]
```

#### Usage in Ingestion

```python
# src/api/routes/ingest.py (Phase 2 enhancement)

@router.post("")
async def ingest_document(
    file: UploadFile,
    ontology: str,
    prompt_profile_id: Optional[int] = Form(None),  # NEW: Allow profile override
    ...
):
    content = await file.read()

    # Image detection
    if _is_image_file(file.filename):
        from ..lib.prompt_resolver import PromptResolver
        from ..lib.age_client import get_age_client

        # Resolve prompt
        resolver = PromptResolver(get_age_client().conn)
        prompt = resolver.get_prompt(
            prompt_type="image_description",
            ontology_name=ontology,
            profile_id=prompt_profile_id
        )

        # Describe image
        provider = get_provider()
        description_response = provider.describe_image(content, prompt)
        content = description_response["text"].encode('utf-8')

    # ... continue normal flow
```

### Phase 3: Original Image Preservation (Future)

**Rationale:** Store both text description AND original image for:
- Visual verification during curation
- Re-processing with improved models
- Display in UI/search results
- Audit trail

**Implementation Strategy:**

```python
# Database schema addition
CREATE TABLE IF NOT EXISTS image_sources (
    image_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id VARCHAR(255) NOT NULL REFERENCES sources(source_id),  -- Link to Source node
    original_image BYTEA NOT NULL,  -- Raw image bytes
    image_type VARCHAR(20) NOT NULL,  -- 'png', 'jpg', 'gif', etc.
    width INTEGER,
    height INTEGER,
    file_size INTEGER,
    description_text TEXT,  -- The generated description
    description_tokens INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

# Modification to ingestion flow
if _is_image_file(file.filename):
    # Generate description (same as Phase 1)
    description_response = provider.describe_image(content, prompt)

    # Store original image in database
    image_id = await store_original_image(
        image_data=content,
        source_id=source_id,  # Will be created later
        description_text=description_response["text"],
        description_tokens=description_response["tokens"]
    )

    # Replace content with description (same as Phase 1)
    content = description_response["text"].encode('utf-8')
```

**Considerations:**
- Storage overhead: Images are large (~100KB-5MB per slide)
- Retrieval API: `GET /sources/{source_id}/image` for UI display
- Compression: Consider PNG → WebP conversion for storage efficiency
- CDN integration: For large deployments, store in S3/GCS and keep URLs

## Consequences

### Positive

1. **✅ Multimodal knowledge extraction**
   - Ingest PowerPoint decks, diagrams, screenshots directly
   - No manual transcription required
   - Preserves visual relationships in textual form

2. **✅ 100% code reuse**
   - Single injection point at `routes/ingest.py:156`
   - All downstream logic unchanged (chunking, extraction, graph upsert)
   - Job approval, cost estimation, streaming work identically

3. **✅ Minimal implementation complexity**
   - ~50 lines of code for Phase 1
   - Leverages existing provider abstraction
   - No new dependencies (uses existing OpenAI/Anthropic SDKs)

4. **✅ Cost-aware processing**
   - Vision tokens tracked like extraction tokens
   - Job approval workflow shows image processing costs
   - User can estimate before committing

5. **✅ Provider flexibility**
   - Works with both OpenAI (GPT-4o) and Anthropic (Claude 3.5 Sonnet)
   - Easy to add other vision models (Gemini, LLaVA, etc.)

6. **✅ Prompt customization (Phase 2)**
   - Organizations can optimize for their content types
   - No code changes required to experiment with prompts
   - A/B testing different extraction strategies

7. **✅ Multi-tenancy support (Phase 2)**
   - Different ontologies can use different prompts
   - Academic, business, technical, legal domains have tailored extraction
   - Users can create custom profiles without admin intervention

8. **✅ Experimentation-friendly**
   - Prompt changes take effect immediately
   - Track prompt effectiveness via extracted concept quality
   - Iterate without redeployment

### Negative

1. **❌ No original image stored (Phase 1)**
   - Cannot re-process if better models become available
   - No visual verification during curation
   - Mitigated: Phase 3 adds optional image preservation

2. **❌ Description quality depends on AI**
   - Some visual nuances may be lost in translation
   - Complex diagrams may be simplified
   - Mitigated: Use high-detail mode, specialized prompts

3. **❌ Higher token costs**
   - Vision API calls are more expensive than text
   - GPT-4o: ~765 tokens per high-detail image
   - Mitigated: Job approval shows costs upfront

4. **❌ Additional database complexity (Phase 2)**
   - New tables for prompt management
   - Admin UI needed for non-technical users
   - Mitigated: Gradual rollout, defaults work without configuration

### Neutral

1. **Image formats supported**
   - Phase 1: PNG, JPEG, GIF, WebP, BMP
   - Future: PDF page extraction, TIFF, SVG rasterization

2. **Prompt types**
   - Phase 1: Image description only
   - Phase 2: Concept extraction, code translation, custom types

3. **Storage approach**
   - Phase 1: Text description only (minimal storage)
   - Phase 3: Optional image preservation (larger storage footprint)

## Alternatives Considered

### Alternative 1: Pre-process Images Externally

**Approach:** Users run OCR/description tools before upload

**Pros:**
- No changes to ingestion system
- Users have full control over description process

**Cons:**
- Manual workflow friction
- Inconsistent quality across users
- Cannot leverage system-wide prompt optimization
- Loses integration with cost estimation

**Verdict:** Rejected - Defeats purpose of unified ingestion system

### Alternative 2: Separate Image Ingestion Endpoint

**Approach:** `POST /ingest/image` with different flow

**Pros:**
- Clear separation of concerns
- Can optimize image-specific parameters

**Cons:**
- Code duplication (chunking, extraction, graph upsert)
- Two parallel ingestion systems to maintain
- Users must know which endpoint to use
- Complicates CLI/UI

**Verdict:** Rejected - Violates DRY principle, adds complexity

### Alternative 3: Convert Images to Markdown Tables

**Approach:** Vision AI outputs structured Markdown, not prose

**Pros:**
- More structured input for concept extraction
- Preserves hierarchies explicitly

**Cons:**
- Not all images map to tables (diagrams, flows)
- Added complexity in prompt engineering
- Markdown still needs chunking/extraction
- Harder to get right across diverse images

**Verdict:** Rejected - Premature optimization, prose is more flexible

### Alternative 4: Store Prompts in Files, Not Database

**Approach:** Prompts in `.prompt` files, versioned in Git

**Pros:**
- Version control built-in
- Easy to diff and review changes
- No database schema changes

**Cons:**
- Requires redeployment to change prompts
- Cannot assign prompts per-ontology at runtime
- No user-facing management UI
- Difficult for non-developers to customize

**Verdict:** Rejected for Phase 2 - Database provides runtime flexibility

## Implementation Plan

### Phase 1: Multimodal Image Ingestion (Week 1-2)

**Backend:**
1. Add `describe_image()` to `AIProvider` base class
2. Implement for `OpenAIProvider` (GPT-4o)
3. Implement for `AnthropicProvider` (Claude 3.5 Sonnet)
4. Add image detection helper in `routes/ingest.py`
5. Inject image → text conversion at line 156
6. Track vision tokens in job analysis

**Testing:**
1. Unit tests for image detection
2. Integration test with sample slide deck
3. Cost estimation accuracy test
4. Both OpenAI and Anthropic providers

**Documentation:**
1. Update `docs/guides/INGESTION.md` with image support
2. Add example: Ingesting PowerPoint decks
3. Cost comparison: text vs. images

### Phase 2: Configurable Prompts (Week 3-4)

**Backend:**
1. Create `prompt_profiles` and `ontology_prompt_profiles` tables
2. Implement `PromptResolver` class
3. Add admin API routes for prompt management
4. Integrate into ingestion flow (optional parameter)
5. Seed database with default profiles

**CLI:**
1. `kg admin prompts list`
2. `kg admin prompts create <name> <type> --text <prompt>`
3. `kg admin prompts assign <ontology> <profile>`
4. `kg ontology describe <name>` - show assigned prompts

**Testing:**
1. Prompt resolution logic tests
2. Default fallback tests
3. Ontology-specific assignment tests
4. A/B comparison with different prompts

**Documentation:**
1. Prompt engineering guide
2. Example profiles for common domains
3. Best practices for customization

### Phase 3: Image Preservation (Future)

**Backend:**
1. Create `image_sources` table
2. Add image storage API
3. Image retrieval endpoint
4. Optional compression (WebP)
5. S3/GCS integration for large deployments

**UI (if built):**
1. Display original image next to concepts
2. Side-by-side comparison view
3. Re-process button with new prompt

## Testing Strategy

### Unit Tests

```python
# test_image_ingestion.py

def test_image_detection():
    assert _is_image_file("slide.png") == True
    assert _is_image_file("doc.txt") == False
    assert _is_image_file(None) == False

def test_openai_describe_image():
    provider = OpenAIProvider()
    with open("test_slide.png", "rb") as f:
        result = provider.describe_image(f.read(), "Describe this image")
    assert "text" in result
    assert "tokens" in result
    assert len(result["text"]) > 50  # Non-trivial description

def test_anthropic_describe_image():
    provider = AnthropicProvider()
    # Similar to OpenAI test
```

### Integration Tests

```python
# test_multimodal_ingestion.py

async def test_ingest_png_slide():
    """Test full ingestion flow with PNG slide"""
    with open("samples/tbm_slide_1.png", "rb") as f:
        files = {"file": ("slide.png", f, "image/png")}
        data = {"ontology": "Test", "auto_approve": True}

        response = client.post("/ingest", files=files, data=data)
        assert response.status_code == 200

        job_id = response.json()["job_id"]

        # Wait for completion
        job = poll_until_complete(job_id)
        assert job["status"] == "completed"

        # Verify concepts extracted from image description
        concepts = client.get(f"/ontologies/Test/concepts").json()
        assert len(concepts) > 0
```

### Cost Analysis

```python
# Cost comparison test
def test_image_vs_text_cost():
    # Ingest text description manually
    text_job = ingest_text(slide_description_text)

    # Ingest image
    image_job = ingest_image(slide_image_bytes)

    # Compare costs
    text_cost = calculate_cost(text_job["tokens"])
    image_cost = calculate_cost(image_job["tokens"]) + vision_cost

    # Image should be 2-3x more expensive
    assert 2 <= (image_cost / text_cost) <= 3
```

## Migration Path

### For Existing Deployments

**No migration needed** - This is purely additive:
- Existing text ingestion unchanged
- New image capability opt-in
- No database schema changes (Phase 1)

### For Users with Manual Image Transcriptions

If users previously transcribed images to text:

```bash
# Option 1: Re-ingest images directly (recommended)
kg ingest file -o "TBM Model" -y slides/*.png

# Option 2: Keep existing text, add images separately
kg ontology create "TBM Model - Images"
kg ingest file -o "TBM Model - Images" -y slides/*.png

# Option 3: Merge ontologies later
kg ontology merge "TBM Model" "TBM Model - Images" --into "TBM Model Complete"
```

## Queue Management & Batch Processing (Phase 4 - Proposed)

### Current Limitation: Serial Processing

**Observed Behavior (2025-10-16):**
- Batch ingestion of multiple images submits jobs one-by-one
- Each job completes before the next begins (serial mode enforced)
- Vision description happens inline during job submission (blocking)
- No queue batching for multimodal content

**Example:** Ingesting 122 slides:
```bash
for slide in *.png; do
    curl -X POST /ingest -F "file=@$slide" -F "ontology=TBM" -F "auto_approve=true"
done
```

Each iteration:
1. Uploads image (160KB)
2. Calls vision AI to describe (~20s)
3. Submits job with text description
4. Job processes serially
5. Next slide begins

**Total time:** Linear with number of images × (upload + vision + extraction)

### Proposed: Media Type Abstraction & Batch Queue

#### Media Type Registry

```python
# src/api/lib/media_types.py

from enum import Enum
from typing import Protocol, Dict, Any
from abc import abstractmethod

class MediaType(Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"

class MediaProcessor(Protocol):
    """Protocol for media-specific processing"""

    @abstractmethod
    async def preprocess(self, content: bytes, **kwargs) -> Dict[str, Any]:
        """
        Convert media to text representation.

        Returns:
            {
                "text": str,           # Text representation
                "tokens": int,         # Tokens used
                "metadata": Dict,      # Media-specific metadata
                "cache_key": str       # Optional cache identifier
            }
        """
        pass

    @abstractmethod
    def detect(self, filename: str, mime_type: str) -> bool:
        """Check if this processor handles the file"""
        pass

class ImageProcessor(MediaProcessor):
    """Image → text via vision AI"""

    def detect(self, filename: str, mime_type: str) -> bool:
        ext = filename.lower().split('.')[-1]
        return ext in ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp']

    async def preprocess(self, content: bytes, **kwargs) -> Dict[str, Any]:
        provider = get_provider()
        prompt = kwargs.get("prompt", IMAGE_DESCRIPTION_PROMPT)

        result = provider.describe_image(content, prompt)

        return {
            "text": result["text"],
            "tokens": result["tokens"],
            "metadata": {
                "size_bytes": len(content),
                "processing_model": provider.get_provider_name()
            },
            "cache_key": f"vision_{hashlib.sha256(content).hexdigest()}"
        }

class AudioProcessor(MediaProcessor):
    """Audio → text via speech-to-text (future)"""

    def detect(self, filename: str, mime_type: str) -> bool:
        ext = filename.lower().split('.')[-1]
        return ext in ['mp3', 'wav', 'ogg', 'm4a', 'flac']

    async def preprocess(self, content: bytes, **kwargs) -> Dict[str, Any]:
        # Future: OpenAI Whisper, AssemblyAI, etc.
        # 1. Transcribe audio → text
        # 2. Optionally: Speaker diarization
        # 3. Optionally: Timestamp alignment

        transcription = await self._transcribe(content)

        return {
            "text": transcription["text"],
            "tokens": transcription["tokens"],
            "metadata": {
                "duration_seconds": transcription["duration"],
                "speaker_count": transcription.get("speakers", 1),
                "language": transcription.get("language", "en")
            },
            "cache_key": f"audio_{hashlib.sha256(content).hexdigest()}"
        }
```

#### Temporary Media Cache

```python
# src/api/lib/media_cache.py

from pathlib import Path
import hashlib
import json
from datetime import datetime, timedelta

class MediaCache:
    """
    Temporary cache for multimodal content during batch processing.

    Stores:
    - Original media bytes
    - Preprocessed text representation
    - Metadata (tokens, processing time, model used)

    Cleanup:
    - Auto-purge after job completion
    - TTL-based cleanup (24 hours)
    - Disk space monitoring (purge LRU if >10GB)
    """

    def __init__(self, cache_dir: Path = Path("/tmp/kg_media_cache")):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(exist_ok=True)

    def store(
        self,
        content: bytes,
        processed_text: str,
        metadata: Dict[str, Any],
        ttl_hours: int = 24
    ) -> str:
        """
        Store media in cache.

        Returns:
            cache_key: Unique identifier for retrieval
        """
        cache_key = hashlib.sha256(content).hexdigest()

        # Store original media
        media_path = self.cache_dir / f"{cache_key}.media"
        media_path.write_bytes(content)

        # Store processed data
        meta_path = self.cache_dir / f"{cache_key}.json"
        meta_path.write_text(json.dumps({
            "text": processed_text,
            "metadata": metadata,
            "expires_at": (datetime.now() + timedelta(hours=ttl_hours)).isoformat(),
            "stored_at": datetime.now().isoformat()
        }))

        return cache_key

    def retrieve(self, cache_key: str) -> Dict[str, Any]:
        """Retrieve processed text and metadata"""
        meta_path = self.cache_dir / f"{cache_key}.json"

        if not meta_path.exists():
            raise KeyError(f"Cache key not found: {cache_key}")

        data = json.loads(meta_path.read_text())

        # Check expiration
        expires_at = datetime.fromisoformat(data["expires_at"])
        if datetime.now() > expires_at:
            self.delete(cache_key)
            raise KeyError(f"Cache key expired: {cache_key}")

        return data

    def delete(self, cache_key: str):
        """Remove media and metadata from cache"""
        (self.cache_dir / f"{cache_key}.media").unlink(missing_ok=True)
        (self.cache_dir / f"{cache_key}.json").unlink(missing_ok=True)

    def cleanup_expired(self):
        """Remove all expired entries"""
        now = datetime.now()

        for meta_file in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(meta_file.read_text())
                expires_at = datetime.fromisoformat(data["expires_at"])

                if now > expires_at:
                    cache_key = meta_file.stem
                    self.delete(cache_key)
            except Exception:
                pass  # Corrupt file, skip
```

#### Batch Ingestion Flow

```python
# src/api/routes/ingest.py - Enhanced batch endpoint

@router.post("/batch")
async def ingest_batch(
    files: List[UploadFile],
    ontology: str = Form(...),
    auto_approve: bool = Form(False),
    processing_mode: str = Form("serial")
):
    """
    Batch ingest multiple files (text, images, audio).

    Workflow:
    1. Detect media type for each file
    2. Preprocess in parallel (vision AI, speech-to-text)
    3. Cache preprocessed text
    4. Submit batch job referencing cache keys
    5. Worker processes cache entries sequentially
    6. Auto-cleanup on completion

    Benefits:
    - Parallel preprocessing (vision/STT can run concurrently)
    - Single job for batch tracking
    - Reduced API calls (batch submission)
    - Automatic cache cleanup
    """
    media_cache = MediaCache()
    processors = [ImageProcessor(), AudioProcessor()]  # Registry

    # Phase 1: Preprocess all media in parallel
    preprocessing_tasks = []

    for file in files:
        content = await file.read()

        # Detect media type
        processor = None
        for p in processors:
            if p.detect(file.filename, file.content_type):
                processor = p
                break

        if processor:
            # Async preprocess
            task = asyncio.create_task(processor.preprocess(content))
            preprocessing_tasks.append((file.filename, task, content))
        else:
            # Text file, no preprocessing
            preprocessing_tasks.append((file.filename, None, content))

    # Phase 2: Wait for all preprocessing to complete
    cache_entries = []

    for filename, task, original_content in preprocessing_tasks:
        if task:
            # Wait for preprocessing
            result = await task

            # Store in cache
            cache_key = media_cache.store(
                content=original_content,
                processed_text=result["text"],
                metadata=result["metadata"]
            )

            cache_entries.append({
                "filename": filename,
                "cache_key": cache_key,
                "tokens": result["tokens"]
            })
        else:
            # Text content, store directly
            cache_key = media_cache.store(
                content=original_content,
                processed_text=original_content.decode('utf-8'),
                metadata={"type": "text"}
            )

            cache_entries.append({
                "filename": filename,
                "cache_key": cache_key,
                "tokens": 0
            })

    # Phase 3: Create batch job
    batch_job_data = {
        "type": "batch_ingestion",
        "ontology": ontology,
        "cache_entries": cache_entries,
        "processing_mode": processing_mode
    }

    job_id = queue.enqueue("batch_ingestion", batch_job_data)

    # Phase 4: Auto-approve or wait
    if auto_approve:
        queue.execute_job_async(job_id)

    return {
        "job_id": job_id,
        "files_queued": len(files),
        "preprocessing_tokens": sum(e["tokens"] for e in cache_entries),
        "message": "Batch job submitted. Media cached and ready for processing."
    }
```

#### Batch Worker

```python
# src/api/workers/batch_ingestion_worker.py

def run_batch_ingestion_worker(job_data: Dict, job_id: str, queue, service_token: str):
    """
    Process batch ingestion job.

    Retrieves cached media, processes sequentially, cleans up.
    """
    cache = MediaCache()
    ontology = job_data["ontology"]
    cache_entries = job_data["cache_entries"]

    stats = ChunkedIngestionStats()

    try:
        for entry in cache_entries:
            filename = entry["filename"]
            cache_key = entry["cache_key"]

            # Retrieve from cache
            cached = cache.retrieve(cache_key)
            text_content = cached["text"]

            # Process as normal text ingestion
            # (chunking, extraction, graph upsert)
            process_text_content(
                text=text_content,
                filename=filename,
                ontology=ontology,
                stats=stats
            )

            # Clean up this entry
            cache.delete(cache_key)

        # Update job with results
        queue.update_job(job_id, {
            "status": "completed",
            "result": stats.to_dict()
        })

    except Exception as e:
        # Clean up all cache entries on failure
        for entry in cache_entries:
            cache.delete(entry["cache_key"])

        queue.update_job(job_id, {
            "status": "failed",
            "error": str(e)
        })
```

### Benefits of Batch Processing

1. **Parallel preprocessing**: Vision AI and STT run concurrently
2. **Single job tracking**: Monitor entire batch as one unit
3. **Automatic cleanup**: Cache purged on completion or TTL
4. **Cost visibility**: Preprocessing tokens tracked separately
5. **Resilient**: Cache survives worker crashes, can retry

### Audio Ingestion (Future)

**Use Cases:**
- Meeting recordings → extract concepts from discussions
- Podcast episodes → build knowledge from interviews
- Lecture recordings → academic knowledge extraction
- Voice notes → capture ideas spoken aloud

**Implementation:**
```python
class AudioProcessor(MediaProcessor):
    async def preprocess(self, content: bytes, **kwargs) -> Dict[str, Any]:
        # Option 1: OpenAI Whisper (open source or API)
        # Option 2: AssemblyAI (commercial, excellent diarization)
        # Option 3: Google Speech-to-Text

        # Example with OpenAI Whisper API:
        audio_file = BytesIO(content)
        audio_file.name = "audio.mp3"

        transcription = openai.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="verbose_json",
            timestamp_granularities=["word"]
        )

        # Format with speaker labels if available
        text = self._format_transcription(transcription)

        return {
            "text": text,
            "tokens": len(transcription.text.split()) * 1.3,  # Estimate
            "metadata": {
                "duration": transcription.duration,
                "language": transcription.language,
                "word_count": len(transcription.words)
            }
        }
```

### Video Ingestion (Future)

**Approach:** Multimodal combination
1. Extract audio → transcribe (speech-to-text)
2. Sample keyframes → describe (vision AI)
3. Merge transcription + visual descriptions
4. Extract concepts from combined text

## Future Enhancements

1. **Multi-page PDF support**: Extract pages as individual images, describe each
2. **OCR fallback**: For pure text images, use faster OCR instead of vision models
3. **Diagram type detection**: Specialized prompts for UML, ER diagrams, flowcharts
4. **Image preprocessing**: Enhance contrast, remove backgrounds, crop borders
5. **Batch processing**: `/ingest/batch` endpoint with parallel preprocessing (detailed above)
6. **Vision model selection**: Let users choose model per-ontology (GPT-4o vs Claude vs Gemini)
7. **Prompt templates**: Mustache-style templates with variables ({{ontology_name}}, {{page_number}})
8. **Prompt versioning**: Track prompt changes over time, A/B test effectiveness
9. **Automatic prompt tuning**: Analyze extracted concepts, suggest prompt improvements
10. **UI for prompt editing**: Rich text editor with syntax highlighting for prompts
11. **Audio transcription**: Meeting recordings, podcasts, lectures via Whisper/AssemblyAI
12. **Video processing**: Keyframe extraction + audio transcription for video content
13. **Real-time streaming**: WebSocket endpoint for live audio/video transcription

## References

- [OpenAI GPT-4o Vision Documentation](https://platform.openai.com/docs/guides/vision)
- [Anthropic Claude 3 Vision Documentation](https://docs.anthropic.com/claude/docs/vision)
- [Best Practices for Multimodal Prompting](https://www.promptingguide.ai/applications/vision)
- Related: ADR-014 (Job Approval Workflow)
- Related: ADR-015 (Smart Chunking Strategy)
- Related: ADR-023 (Markdown Structured Content Preprocessing)

## Approval & Sign-Off

- [ ] Development Team Review
- [ ] Architecture Review
- [ ] Security Review (image storage, prompt injection)
- [ ] Cost Analysis Approval (token budgets for vision)
- [ ] Documentation Complete
- [ ] Implementation Checklist Created
