# Vision Model Research Summary

**Date:** November 2025
**Purpose:** Evaluate vision models and embedding approaches for ADR-057 Multimodal Image Ingestion

## Research Question

Which vision model and embedding approach should we use for:
1. **Image → Prose** conversion (Stage 1)
2. **Visual similarity detection** for context injection

## Test Methodology

1. **Vision Quality Testing** - Test Granite Vision 3.3 2B vs GPT-4o on presentation slides and photos
2. **Embedding Comparison** - Compare CLIP (local), OpenAI CLIP API, and Nomic Vision on 10 test images
3. **Similarity Validation** - Verify that similar images cluster together with high cosine similarity

## Test Images

10 cell phone photos in `test-images/`:
- **IQ Puzzles** (3): arrow_pattern, iq_puzzle, stick_figure
- **People** (2): colorful_outfit_geometric, man_in_colorful
- **Western Town** (2): town_scene, town_sunset
- **Outdoor** (2): fluffy_clouds, white_bus
- **Indoor** (1): black_cat

Natural groupings allow us to validate clustering quality.

## Results

### Stage 1: Image → Prose

| Model | Quality | Reliability | Cost | Recommendation |
|-------|---------|-------------|------|----------------|
| **GPT-4o Vision** | ⭐⭐⭐⭐⭐ Excellent | 100% reliable | ~$0.01/image | ✅ **PRIMARY** |
| **Claude 3.5 Sonnet** | ⭐⭐⭐⭐⭐ Excellent | Not tested | ~$0.015/image | ✅ **ALTERNATE** |
| **Granite Vision 3.3 2B** | ⭐⭐ Inconsistent | Random refusals | Free (local) | ❌ **NOT SUITABLE** |

**Decision:** Use GPT-4o as primary, with provider abstraction to support Claude and Ollama (future).

### Stage 2: Visual Embeddings

| Model | Clustering | Speed | Dimensions | Cost | Recommendation |
|-------|-----------|-------|-----------|------|----------------|
| **Nomic Vision v1.5** | 0.847 | 1.94s | 768 | Free (local) | ✅ **PRIMARY** |
| **CLIP (local)** | 0.666 | 1.49s | 512 | Free (local) | ⚠️ FALLBACK |
| **OpenAI CLIP API** | 0.542 | 63.03s | 1536 | API costs | ❌ NOT RECOMMENDED |

**Decision:** Use Nomic Vision for visual embeddings.

### Clustering Quality Details

**Nomic Vision (Winner):**
- IQ Puzzles: 0.932-0.953 (near-perfect)
- People: 0.961 (near-perfect)
- Western Town: 0.891 (excellent)

**CLIP (Good but lower):**
- IQ Puzzles: 0.819-0.903 (good)
- People: 0.946 (excellent)
- Western Town: 0.799 (moderate)

**OpenAI API (Text-based fallback):**
- IQ Puzzles: 0.705-0.826 (moderate)
- People: 0.849 (good)
- Western Town: 0.750 (moderate)

## Implementation Decisions

### Architecture

```
Image → Vision Provider → Prose Description
                           ↓
                    LLM Extractor → Concepts
                           ↑
                    Visual Context (Nomic Vision embeddings)
```

### Stage 1: Image → Prose
- **Primary Provider:** GPT-4o Vision
- **Alternate Provider:** Claude 3.5 Sonnet Vision
- **Local Provider:** Ollama (Granite, LLaVA, etc.) - pattern in place but not production-ready
- **Abstraction:** `VisionProvider` interface (similar to `AIProvider` for text extraction)

### Stage 2: Visual Embeddings
- **Primary:** Nomic Vision v1.5 (768-dim, transformers library)
- **Fallback:** CLIP ViT-B-32 (512-dim, sentence-transformers)
- **Similarity Threshold:** 0.70 for context injection
- **Ontology Boost:** +0.1 for same-domain images

### Prompt Design (Literal, Non-Interpretive)

```
Describe everything visible in this image literally and exhaustively.

Do NOT summarize or interpret. Do NOT provide analysis or conclusions.

Instead, describe:
- Every piece of text you see, word for word
- Every visual element (boxes, arrows, shapes, colors)
- The exact layout and positioning of elements
- Any diagrams, charts, or graphics in detail
- Relationships between elements
- Any logos, branding, or page numbers

Be thorough and literal.
```

**Why Literal:** Two-stage pipeline requires raw descriptions so Stage 2 LLM can extract concepts accurately.

## Test Scripts

All scripts located in this directory:

1. **`compare_embeddings.py`** - Compare CLIP, OpenAI API, and Nomic Vision
2. **`compare_vision.py`** - Compare Granite Vision vs GPT-4o
3. **`test_nomic_similarity.py`** - Test visual similarity detection
4. **`test_vision.py`** - Test single vision model with custom prompts
5. **`rename_images.py`** - Rename images using vision descriptions
6. **`convert.py`** - Convert PDF to images (external preprocessing)

## Key Learnings

1. **Local vision models (Granite) are unreliable** - Random refusals make them unsuitable for production
2. **Cloud vision APIs (GPT-4o, Claude) are excellent** - Worth the $0.01/image cost for quality
3. **Nomic Vision beats CLIP for visual similarity** - 27% higher clustering quality
4. **Text-based embeddings don't work for visual search** - OpenAI API approach was significantly worse
5. **Literal prompts are critical** - Interpretive summaries reduce Stage 2 extraction quality
6. **Two-stage processing is correct** - Enables debugging, re-extraction, and higher quality

## Cost Analysis (per 1000 images)

### Stage 1: Image → Prose
- **GPT-4o:** ~$10 (1,500 tokens × $0.0025/1K input + 2,000 tokens × $0.01/1K output)
- **Claude 3.5:** ~$15 (similar token usage, higher rates)
- **Ollama:** $0 (local, but unreliable)

### Stage 2: Visual Embeddings
- **Nomic Vision:** $0 (local, one-time download)
- **CLIP:** $0 (local, one-time download)
- **OpenAI API:** ~$50+ (2 API calls per image: vision + embeddings)

**Total Cost for 1000 images:** ~$10 (GPT-4o + Nomic Vision)

## Files

- `FINDINGS.md` - Detailed vision model testing results
- `EMBEDDING_COMPARISON_REPORT.md` - Comprehensive embedding comparison
- `README.md` - Original testing documentation
- `requirements.txt` - Python dependencies

## Next Steps

1. ✅ Move research to `docs/research/vision-testing/`
2. ⏳ Update ADR-057 with implementation decisions
3. ⏳ Implement `VisionProvider` abstraction (GPT-4o, Claude, Ollama)
4. ⏳ Implement Nomic Vision embedding generation
5. ⏳ Add image ingestion to REST API
6. ⏳ Add visual similarity to query API
7. ⏳ Test with larger datasets (100+ images)

## References

- ADR-057: Multimodal Image Ingestion
- ADR-043: VRAM Resource Management
- Nomic Vision: https://huggingface.co/nomic-ai/nomic-embed-vision-v1.5
- OpenAI Vision API: https://platform.openai.com/docs/guides/vision
