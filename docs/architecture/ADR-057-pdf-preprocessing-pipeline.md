# ADR-057: PDF Preprocessing Pipeline for Non-Markdown Ingestion

**Status:** Proposed
**Date:** 2025-11-03
**Deciders:** Core Team
**Related:** ADR-002 (Document Ingestion), ADR-041 (AI Extraction Config)

---

## Context

### The Markdown-First Reality

Our system excels at ingesting **markdown and prose text**:
- Markdown is "first-order compatible" - directly consumable by our chunker
- Text is processed through LLM extraction to identify concepts
- The extraction prompt expects natural language prose

**What works well:**
- Documentation (README, guides, ADRs)
- Commit messages and PR descriptions
- Meeting notes and design documents
- Any human-written narrative text

**What breaks down:**
- Source code (syntax, not prose)
- Mermaid diagrams (special syntax)
- ASCII art and ANSI graphs
- Embedded SVG or base64 images
- Non-prose symbology

### The "Text-to-Speech" Test

Think of it this way: if content was run through a naive text-to-speech converter:

```
Bad TTS: "Message from Bob: check this out h-t-t-p colon slash slash
mysite dot com slash two trillion nine hundred eighty three thousand
four hundred and twenty four slash a dot dot dot"

Good TTS: "Message from Bob: check out this link about the new feature"
```

Our system is like that naive TTS converter - it assumes **text is mostly prose**. The chunker and extraction prompt can handle some code or diagrams, but gets confused when encountering:
- Long blocks of source code
- Complex mermaid diagrams
- Embedded images or SVG
- Tables with unusual formatting
- Non-standard symbology

### The PDF Problem

**PDFs are extremely common** in enterprise contexts:
- Research papers
- Slide decks "printed" to PDF
- Technical specifications
- Reports and whitepapers
- Scanned documents

**Why PDF is challenging:**
1. **Format complexity:** PDFs can contain text, images, vectors, embedded fonts
2. **Extraction varies:** Text extraction quality depends on how PDF was created
3. **Layout preservation:** Converting to markdown loses visual layout
4. **Mixed content:** A single PDF might have prose + diagrams + code + tables
5. **Security risks:** PDFs can contain malicious content (white-on-white text, embedded scripts)

**Current workaround:** Users must manually convert PDF → markdown before ingestion. This is:
- Time-consuming
- Error-prone
- Requires technical knowledge
- Loses visual context

---

## Decision

We will implement a **two-tier ingestion architecture**:

### Tier 1: First-Order Compatible (Existing)
**Direct ingestion** - no preprocessing needed
- Markdown files (`.md`)
- Plain text files (`.txt`)
- Any prose-heavy formats

### Tier 2: Second-Order Compatible (New)
**Requires preprocessing** to convert to first-order (markdown)
- PDF files (`.pdf`)
- Future: PowerPoint, Word, images, etc.

### PDF Preprocessing Pipeline Architecture

**High-level flow:**
```
PDF File → [Preprocessing Pipeline] → Markdown + Metadata → [Existing Ingestion]
```

**Detailed pipeline:**
```
1. PDF Upload
   ↓
2. Page Extraction (convert each page to high-DPI bitmap)
   - Render PDF pages at 300 DPI
   - Output: PNG images (one per page)
   ↓
3. Visual-to-Text Conversion (LLM vision model per page)
   - Prompt: "Describe this page in markdown format"
   - Preserves structure, headings, lists, tables
   - Captures visual elements as descriptions
   - Output: Markdown text (one per page)
   ↓
4. Assembly
   - Combine page markdowns with page breaks
   - Add metadata (original filename, page numbers)
   - Output: Single markdown document
   ↓
5. Handoff to Existing Ingestion
   - User receives converted markdown
   - User can review/edit before final ingestion
   - Converted markdown is what gets grounded in concept nodes
```

### Key Design Principles

**1. Bitmap Conversion as Security Barrier**
- Rendering PDF to raster image neutralizes most attacks
- White-on-white text: visible in bitmap
- Embedded scripts: not executed, just rendered
- PDF exploits: bypassed by treating as image

**2. Page-by-Page Processing**
- Each page gets its own LLM vision call
- 1:1 mapping: page N → markdown section N
- Preserves document structure
- Allows parallel processing

**3. Expensive but Valuable**
- Vision model calls are costly (~$0.01-0.05 per page)
- 100-page PDF might cost $1-5 to process
- But: one-time cost, creates reusable markdown
- User approves cost estimate before processing

**4. Conversion is Ground Truth**
- The generated markdown is what gets chunked and conceptified
- Original PDF is referenced for provenance
- Converted markdown should be returned to user for inspection
- Future queries cite the markdown, not PDF structure

---

## Implementation Options

### Option 1: Plugin Architecture for Web App

**Structure:**
```
viz-app/
├── plugins/
│   └── pdf-preprocessor/
│       ├── upload.ts        # File upload interface
│       ├── pipeline.ts      # Orchestrates conversion
│       └── preview.ts       # Shows converted markdown
```

**Pros:**
- Integrated into existing web UI
- Users stay in one application
- Can reuse authentication and API client

**Cons:**
- Adds complexity to viz-app
- Vision model calls in browser context
- Large file uploads through web UI

### Option 2: Separate Companion App ("ingest-app")

**Structure:**
```
ingest-app/              # New application
├── src/
│   ├── pdf/
│   │   ├── converter.ts
│   │   └── vision.ts
│   ├── ui/
│   │   └── upload.vue
│   └── api-client.ts
```

**Analogous to viz-app:** Just as viz-app handles visualization, ingest-app handles preprocessing

**Pros:**
- Clean separation of concerns
- Can be deployed independently
- Specialized UI for ingestion workflows
- Doesn't bloat viz-app

**Cons:**
- Another app to maintain
- User switches between apps
- Duplicate auth/config setup

### Option 3: API Server Extension + CLI

**Structure:**
```
src/api/preprocessing/
├── pdf_pipeline.py      # PDF → markdown conversion
├── vision_client.py     # LLM vision API calls
└── routes.py            # POST /preprocess/pdf

client/src/cli/preprocess.ts   # kg preprocess pdf file.pdf
```

**Pros:**
- Leverages existing API server
- CLI for power users
- Can be called from both viz-app and scripts
- Server-side processing (no browser limits)

**Cons:**
- Adds preprocessing logic to API server
- Server needs access to vision models

### Option 4: Hybrid (Recommended)

**Combine Option 3 (API + CLI) with Option 2 (UI app):**

```
API Server:
  POST /preprocess/pdf          # Core conversion logic
  GET  /preprocess/jobs/:id     # Job status
  GET  /preprocess/result/:id   # Download markdown

CLI:
  kg preprocess pdf file.pdf    # Calls API, shows progress

Ingest App (separate):
  - Upload PDF via web UI
  - Calls API server for processing
  - Shows real-time progress
  - Displays converted markdown for review
  - Sends to main ingestion when approved
```

**Benefits:**
- API provides conversion as a service
- CLI for automation and scripts
- Ingest-app provides user-friendly UI
- Each component does one thing well

---

## Technical Implementation Details

### PDF → Bitmap Conversion

**Libraries:**
- Python: `pdf2image` (wraps poppler)
- Node.js: `pdf-poppler` or `pdfjs-dist`

**Settings:**
```python
from pdf2image import convert_from_path

images = convert_from_path(
    pdf_path,
    dpi=300,           # High enough for text clarity
    fmt='png',         # Lossless for vision model
    thread_count=4     # Parallel page rendering
)
```

### Vision Model Integration

**Options:**
1. **GPT-4 Vision** (OpenAI)
   - Excellent at understanding document layouts
   - Cost: ~$0.01-0.02 per image
   - Max resolution: 2048x2048 (might need to resize)

2. **Claude 3.5 Sonnet with Vision** (Anthropic)
   - Great at long-form content description
   - Cost: ~$0.015 per image
   - Better at tables and structured content

3. **Gemini Pro Vision** (Google)
   - Strong at multi-page context
   - Cost: Lower (~$0.0025 per image)
   - Might need more prompt engineering

**Prompt Template:**
```markdown
You are converting a PDF page to markdown format.

Analyze this image and convert it to markdown following these rules:
1. Preserve all headings with appropriate # levels
2. Convert tables to markdown table syntax
3. Describe diagrams and images in [Image: description] format
4. Maintain list structures (bullet points, numbered lists)
5. Preserve emphasized text (bold, italic)
6. For code blocks, use triple backticks with language if identifiable
7. Include any visible URLs or citations

Focus on semantic structure, not exact visual layout.

Return ONLY the markdown, no preamble or explanation.
```

### Metadata Preservation

**Generated markdown header:**
```markdown
---
source_type: pdf
original_file: research_paper.pdf
total_pages: 45
preprocessed_date: 2025-11-03
conversion_cost: $0.67
page_range: 1-45
---

# [Content starts here]
```

### Cost Estimation

**Before processing, show user:**
```
PDF: research_paper.pdf (45 pages)

Preprocessing estimate:
- Bitmap conversion: ~30 seconds (free)
- Vision model calls: 45 pages × $0.015 = $0.68
- Total time: ~3-5 minutes
- Total cost: $0.68

Proceed? [y/N]
```

---

## Conversion Workflow UX

### CLI Experience

```bash
$ kg preprocess pdf research_paper.pdf

📄 Analyzing PDF: research_paper.pdf
   Pages: 45
   Size: 2.3 MB

💰 Cost Estimate:
   Vision model: 45 pages × $0.015 = $0.68
   Processing time: ~3-5 minutes

Proceed with conversion? [y/N]: y

🔄 Converting to markdown...
   ✓ Page 1/45 (2s)
   ✓ Page 2/45 (2s)
   ✓ Page 3/45 (2s)
   ...
   ✓ Page 45/45 (2s)

✓ Conversion complete!
   Output: research_paper.md
   Tokens: 45,230
   Cost: $0.68

Review the markdown file before ingestion:
   cat research_paper.md

Ready to ingest?
   kg ingest file research_paper.md -o "Research Papers"
```

### Ingest App Experience

**Step 1: Upload**
```
┌─────────────────────────────────────┐
│  📤 Upload PDF for Preprocessing    │
├─────────────────────────────────────┤
│                                     │
│  [Drag PDF here or click to browse]│
│                                     │
│  Supported: PDF up to 200 pages    │
│  Max size: 50 MB                   │
└─────────────────────────────────────┘
```

**Step 2: Cost Preview**
```
┌─────────────────────────────────────┐
│  📊 Preprocessing Estimate          │
├─────────────────────────────────────┤
│  File: research_paper.pdf           │
│  Pages: 45                          │
│  Size: 2.3 MB                       │
│                                     │
│  Vision model: $0.68                │
│  Processing time: ~3-5 min          │
│                                     │
│  [Cancel]  [Start Preprocessing]   │
└─────────────────────────────────────┘
```

**Step 3: Progress**
```
┌─────────────────────────────────────┐
│  🔄 Converting PDF to Markdown      │
├─────────────────────────────────────┤
│  Progress: 23/45 pages (51%)        │
│  [████████░░░░░░░░░░░░] 51%        │
│                                     │
│  Elapsed: 1m 15s                    │
│  Remaining: ~1m 10s                 │
│                                     │
│  [Cancel Conversion]                │
└─────────────────────────────────────┘
```

**Step 4: Review**
```
┌─────────────────────────────────────┐
│  📝 Review Converted Markdown       │
├─────────────────────────────────────┤
│  [Preview] [Download] [Edit]       │
│                                     │
│  ┌──────────────────────────────┐  │
│  │ # Introduction               │  │
│  │                              │  │
│  │ This paper presents a novel  │  │
│  │ approach to...               │  │
│  │                              │  │
│  │ [Image: Figure 1 shows...]   │  │
│  └──────────────────────────────┘  │
│                                     │
│  Tokens: 45,230                     │
│  Cost: $0.68                        │
│                                     │
│  [Download Markdown] [Ingest Now]  │
└─────────────────────────────────────┘
```

**Step 5: Ingest**
```
┌─────────────────────────────────────┐
│  📥 Ingest Converted Document       │
├─────────────────────────────────────┤
│  Document: research_paper.md        │
│  Source: research_paper.pdf         │
│  Pages: 45                          │
│  Tokens: 45,230                     │
│                                     │
│  Ontology: [Research Papers ▼]     │
│                                     │
│  [Back] [Ingest Document]           │
└─────────────────────────────────────┘
```

---

## Storage and Provenance

### What to Store

**Option A: Store Converted Markdown Only**
```
Concept Node:
  - evidenced_by: Instance
    - quote: "This paper presents..."
    - source: Document
      - document: "research_paper.md"
      - metadata:
          original_pdf: "research_paper.pdf"
          page: 1
          conversion_date: "2025-11-03"
```

**Option B: Store Both Original + Converted**
```
filesystem/
├── originals/
│   └── research_paper.pdf         # Original file
└── converted/
    └── research_paper.md           # Converted markdown

Database:
  - Document references converted markdown
  - Metadata links to original PDF
  - Page mappings preserved
```

**Recommendation: Option B**
- Keep original for reference
- Converted markdown is ground truth for concepts
- Users can download either format

### Image Handling (Future)

**Current approach:** Describe images as text
```markdown
[Image: Figure 1 shows a flow diagram with three main components:
1. Input Layer (blue box)
2. Processing Layer (green boxes connected by arrows)
3. Output Layer (red box)
The diagram illustrates data flow from left to right.]
```

**Future enhancement:** Store actual images
```markdown
![Figure 1: System Architecture](images/page_5_figure_1.png)

*Figure 1 shows a flow diagram with three main components...*
```

Store images in graph:
```cypher
(:Concept)-[:EVIDENCED_BY]->(:Instance)
  -[:HAS_IMAGE]->(:Image {
    data: <base64 or blob>,
    page: 5,
    caption: "Figure 1: System Architecture"
  })
```

**Not implementing in ADR-057:** Images in graph would be massive undertaking.
**Future ADR:** ADR-058 "Image Storage in Knowledge Graph"

---

## Security Considerations

### PDF Attack Surface

**Threats neutralized by bitmap conversion:**
1. **White-on-white text:** Visible in rendered bitmap
2. **Embedded JavaScript:** Not executed during render
3. **Malicious links:** Become text in vision model output
4. **PDF exploits:** Only rendering engine exposed, not full PDF parser
5. **Embedded files:** Not extracted, only visual content processed

**Remaining risks:**
1. **Large file DoS:** Limit PDF size (50 MB, 200 pages max)
2. **Malicious vision model prompts:** Sanitize extracted markdown
3. **Cost attacks:** Require approval before processing
4. **Storage exhaustion:** Cleanup old converted files

### Mitigation Strategies

```python
# File validation
MAX_PDF_SIZE_MB = 50
MAX_PAGES = 200

def validate_pdf(file_path):
    size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if size_mb > MAX_PDF_SIZE_MB:
        raise ValueError(f"PDF too large: {size_mb:.1f}MB (max {MAX_PDF_SIZE_MB}MB)")

    page_count = get_pdf_page_count(file_path)
    if page_count > MAX_PAGES:
        raise ValueError(f"Too many pages: {page_count} (max {MAX_PAGES})")

# Sandboxed rendering
def render_pdf_safe(pdf_path):
    # Run pdf2image in separate process with timeout
    # Kill if takes more than 60s per page
    pass

# Output sanitization
def sanitize_markdown(text):
    # Remove any embedded scripts or suspicious content
    # Validate markdown structure
    pass
```

---

## Cost Analysis

### Per-Document Costs

**Small document (10 pages):**
- Vision model: 10 × $0.015 = $0.15
- Processing time: ~1 minute
- Storage: ~50 KB markdown

**Medium document (50 pages):**
- Vision model: 50 × $0.015 = $0.75
- Processing time: ~5 minutes
- Storage: ~250 KB markdown

**Large document (200 pages):**
- Vision model: 200 × $0.015 = $3.00
- Processing time: ~20 minutes
- Storage: ~1 MB markdown

### Cost-Saving Strategies

**1. Batch Processing**
- Process multiple documents overnight
- Lower priority queue with discount pricing

**2. Caching**
- Hash PDF content
- Check if already converted
- Reuse converted markdown

**3. Selective Processing**
- Allow users to specify page ranges
- "Process pages 10-20 only"

**4. Vision Model Tiers**
- Fast/cheap: Gemini Pro Vision ($0.0025/page)
- Standard: GPT-4 Vision ($0.015/page)
- Premium: Claude 3.5 Sonnet ($0.02/page)

---

## Migration Path

### Phase 1: Foundation (This ADR)
- [ ] Design preprocessing pipeline architecture
- [ ] Choose implementation option (recommend Hybrid)
- [ ] Define API contracts

### Phase 2: Core Implementation
- [ ] Implement PDF → bitmap conversion
- [ ] Integrate vision model API
- [ ] Build API endpoints (POST /preprocess/pdf)
- [ ] Add job tracking and status

### Phase 3: CLI Support
- [ ] Implement `kg preprocess pdf` command
- [ ] Add cost estimation display
- [ ] Progress indicators

### Phase 4: UI (Ingest App)
- [ ] Build ingest-app skeleton
- [ ] Upload interface
- [ ] Progress tracking
- [ ] Markdown preview/editor
- [ ] Handoff to main ingestion

### Phase 5: Production Readiness
- [ ] Security hardening
- [ ] Rate limiting
- [ ] Cost controls
- [ ] Monitoring and logging
- [ ] User documentation

---

## Alternatives Considered

### Alternative 1: Use Existing PDF-to-Markdown Tools

**Tools:** `pdftotext`, `pdftomarkdown`, `marker`

**Why rejected:**
- Text extraction quality varies wildly
- Loses visual layout context
- Can't handle scanned PDFs
- No description of diagrams/images
- Not "prose-aware"

**Vision model approach is superior:**
- Understands document structure
- Describes visual elements
- Handles scanned documents
- More robust to PDF variations

### Alternative 2: Store PDF Binary in Graph

**Approach:** Store original PDF, parse on query

**Why rejected:**
- PDF parsing at query time is slow
- Can't chunk/conceptify PDF directly
- Doesn't solve the "not prose" problem
- Storage bloat (PDFs are large)

**Our approach is better:**
- Convert once, query many times
- Markdown is chunkable and conceptifiable
- Smaller storage footprint

### Alternative 3: Manual Conversion Only

**Approach:** Users must convert PDF → markdown themselves

**Why rejected:**
- Poor user experience
- Error-prone
- Limits adoption
- Loses visual context

**Automated pipeline is worth the complexity:**
- Much better UX
- Consistent quality
- Enables enterprise adoption

---

## Success Criteria

**Must have:**
1. ✅ PDF uploads result in markdown output
2. ✅ Page-by-page vision model conversion works
3. ✅ Cost estimates shown before processing
4. ✅ Converted markdown is ingestion-ready
5. ✅ Original PDF preserved for provenance

**Should have:**
6. ✅ CLI command `kg preprocess pdf` works
7. ✅ Progress tracking for long documents
8. ✅ Markdown preview before ingestion
9. ✅ Batch processing support

**Nice to have:**
10. ⚠️ Web UI for non-technical users
11. ⚠️ Page range selection
12. ⚠️ Multiple vision model options
13. ⚠️ Caching for duplicate PDFs

---

## Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Vision model quality varies | Medium | Medium | Test multiple models, allow re-processing |
| Processing costs too high | High | Medium | Show estimates, add approval step, offer cheaper models |
| Conversion takes too long | Medium | High | Parallel page processing, progress indicators |
| Security vulnerability in PDF rendering | High | Low | Sandbox rendering, limit file sizes |
| Storage fills up | Medium | Medium | Cleanup old conversions, set retention policy |
| Users don't review converted markdown | Medium | High | Make review step prominent, show diffs |

---

## Future Enhancements (Separate ADRs)

**ADR-058: Image Storage in Knowledge Graph**
- Store extracted images from PDFs
- Link images to concept evidence
- Enable image-based queries

**ADR-059: PowerPoint/Word Preprocessing**
- Extend pipeline to other Office formats
- Similar vision-based approach

**ADR-060: OCR for Scanned Documents**
- Specialized handling for pure image PDFs
- Tesseract integration

**ADR-061: Batch Preprocessing Service**
- Background job queue
- Scheduled processing
- Email notifications

---

## Decision Rationale

We choose to implement a **PDF preprocessing pipeline** with the following characteristics:

1. **Hybrid Architecture:** API + CLI + Ingest App
2. **Vision-based Conversion:** Use LLM vision models, not text extraction
3. **Bitmap Security Barrier:** Render to image before processing
4. **User Review Required:** Show converted markdown before ingestion
5. **Original Preservation:** Store both PDF and markdown

**Why this approach wins:**
- Handles widest variety of PDF types (including scanned)
- Provides security through rendering
- Gives users control (cost approval, review step)
- Extensible to other formats
- Leverages existing LLM capabilities

**What we're not doing (yet):**
- Storing images in graph (too complex for now)
- Automatic ingestion without review (too risky)
- Full Office suite support (start with PDF)

---

## Appendix: Example Conversions

### Example 1: Research Paper

**Input PDF:** Dense academic paper with equations, figures, citations

**Converted Markdown:**
```markdown
---
source_type: pdf
original_file: neural_networks_2024.pdf
total_pages: 12
page_range: 1-12
---

# Neural Network Optimization Techniques

## Abstract

This paper presents novel approaches to optimizing deep neural networks...

## 1. Introduction

Recent advances in machine learning have demonstrated...

[Image: Figure 1 shows a comparison of convergence rates across three
optimization algorithms: SGD (red line), Adam (blue line), and our
proposed method RMSProp+ (green line). The graph shows training loss
on the y-axis and epochs on the x-axis over 100 epochs.]

## 2. Related Work

Previous research by Smith et al. (2023) explored...
```

### Example 2: Slide Deck

**Input PDF:** Corporate slide deck with minimal text, lots of visuals

**Converted Markdown:**
```markdown
---
source_type: pdf
original_file: q4_review.pdf
total_pages: 25
page_range: 1-25
---

# Q4 Business Review

---

## Slide 1: Title Slide

**Q4 2024 Business Review**
Engineering Department
November 2024

---

## Slide 2: Key Metrics

[Image: Dashboard showing four metric cards:
- Revenue: $2.4M (↑ 23%)
- Active Users: 45K (↑ 12%)
- System Uptime: 99.8%
- Support Tickets: 234 (↓ 18%)]

---

## Slide 3: Product Launches

### Launched in Q4:
- Feature A (October)
- Feature B (November)
- Feature C (December)

[Image: Timeline diagram showing three feature launches with icons and dates]
```

### Example 3: Technical Specification

**Input PDF:** API documentation with code examples

**Converted Markdown:**
```markdown
---
source_type: pdf
original_file: api_spec_v2.pdf
total_pages: 34
page_range: 1-34
---

# API Specification v2.0

## Authentication

All API requests must include an authentication token:

```http
GET /api/v2/resources
Authorization: Bearer <token>
```

## Endpoints

### GET /api/v2/resources

Retrieves a list of resources.

**Parameters:**
- `limit` (integer, optional): Maximum number of results (default: 10)
- `offset` (integer, optional): Pagination offset (default: 0)

**Response:**
```json
{
  "data": [...],
  "total": 42,
  "limit": 10,
  "offset": 0
}
```

[Image: Sequence diagram showing the request flow between Client,
API Gateway, Auth Service, and Database with arrows indicating the
authentication and data retrieval process]
```

---

**Status:** Proposed - Ready for team review and implementation planning
