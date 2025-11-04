# PDF to Image Ingestion & Vision Model Testing

This use case provides tooling for converting PDFs to images and testing vision model quality before ingesting into the knowledge graph system.

## Purpose

1. **PDF to Images**: Simple converter for preparing PDFs for multimodal ingestion
2. **Vision Model Testing**: Scratch space for evaluating Granite Vision 3.3 2B quality
3. **Quality Verification**: Assess description accuracy and performance before production use

## Prerequisites

### System Dependencies

```bash
# Install poppler-utils (required for PDF conversion)
sudo apt install poppler-utils  # Debian/Ubuntu
# or
brew install poppler  # macOS
```

### Python Dependencies

```bash
# Install from requirements.txt
pip install -r requirements.txt

# Or install individually:
pip install pdf2image ollama Pillow
```

### Ollama Setup

Make sure Ollama is running with Granite Vision model:

```bash
# Check Ollama status
docker ps | grep ollama

# Verify Granite Vision model is available
docker exec kg-ollama ollama list | grep granite3.3-vision
```

## Quick Start

### 1. Convert PDF to Images

```bash
# Basic conversion (300 DPI, default)
python convert.py document.pdf

# Custom output directory
python convert.py document.pdf /path/to/output

# Higher quality (larger files)
python convert.py document.pdf --dpi 600

# Lower quality (smaller files, faster)
python convert.py document.pdf --dpi 150
```

**Output**: Ordered PNG files `page-001.png`, `page-002.png`, etc.

### 2. Test Vision Model Quality

```bash
# Test single image
python test_vision.py page-001.png

# Save description to file
python test_vision.py page-001.png --save-description

# Use custom prompt
python test_vision.py page-001.png --prompt "Extract all text and describe the layout"
```

**Output**: Markdown description + performance metrics

## Workflow Example

### End-to-End Testing

```bash
# 1. Convert PDF to images
python convert.py /path/to/document.pdf

# 2. Test vision model on sample pages
python test_vision.py document_images/page-001.png --save-description
python test_vision.py document_images/page-010.png --save-description
python test_vision.py document_images/page-050.png --save-description

# 3. Review descriptions and evaluate quality
cat document_images/page-001.txt
cat document_images/page-010.txt
cat document_images/page-050.txt

# 4. If quality is good, prepare for batch ingestion
# (Future: integrate with kg ingest image command)
```

## DPI Recommendations

| DPI | Use Case | File Size | Quality |
|-----|----------|-----------|---------|
| 150 | Quick preview, testing | Small (~50-100 KB) | Basic |
| 300 | Standard ingestion (recommended) | Medium (~200-400 KB) | Good |
| 600 | High-quality archival | Large (~1-2 MB) | Excellent |

**Default**: 300 DPI strikes a good balance between quality and file size.

## Testing Notes

### What to Look For

When evaluating Granite Vision descriptions:

1. **Text Accuracy**: Does it capture all visible text verbatim?
2. **Structure Recognition**: Does it identify headings, lists, tables?
3. **Visual Elements**: Does it describe diagrams, charts, images?
4. **Relationships**: Does it explain how elements relate to each other?
5. **Layout**: Does it capture the organization and flow?

### Performance Metrics

Expected performance on typical presentation slides (300 DPI):

- **Image size**: ~200-400 KB per page
- **Processing time**: 5-15 seconds per image
- **Description length**: 500-2000 characters

### Quality Assessment

**Good description** (ready for ingestion):
- Captures all text accurately
- Identifies visual structure (headings, bullets)
- Describes diagrams and charts meaningfully
- Maintains logical flow

**Poor description** (needs adjustment):
- Missing or incorrect text
- Ignores visual structure
- Generic diagram descriptions ("there is a box")
- No logical organization

## Common Issues

### PDF Conversion Errors

**Error**: `pdf2image: command not found`
**Fix**: Install poppler-utils system dependency

**Error**: Permission denied
**Fix**: Make script executable: `chmod +x convert.py`

### Vision Model Errors

**Error**: Connection refused to Ollama
**Fix**: Start Ollama container: `docker start kg-ollama`

**Error**: Model not found
**Fix**: Pull model: `docker exec kg-ollama ollama pull ibm/granite3.3-vision:2b`

**Error**: Out of memory
**Fix**: Reduce image DPI or use smaller batch sizes

## File Organization

```
pdf-to-images/
├── convert.py              # PDF to images converter
├── test_vision.py          # Vision model quality tester
├── requirements.txt        # Python dependencies
├── README.md              # This file
├── .gitignore             # Ignore large files
└── [scratch space]        # Your PDFs, images, test outputs (gitignored)
```

## Integration with Knowledge Graph

Once you've verified vision model quality:

1. **Future CLI**: `kg ingest image page-001.png -o "My Ontology"`
2. **Future Batch**: `kg ingest images document_images/ -o "My Ontology"`
3. **Future API**: POST `/ingest/image` with image bytes

## Example Test Data

Test with the EPOM (Enterprise Product Operating Model) presentation:

```bash
# 1. Convert EPOM PDF to images
python convert.py "/home/aaron/Projects/ai/data/etfm/Enterprise Product Operating Model.pdf"

# 2. Test vision model on sample slides
python test_vision.py "Enterprise Product Operating Model_images/page-001.png" --save-description
python test_vision.py "Enterprise Product Operating Model_images/page-010.png" --save-description

# 3. Review quality
cat "Enterprise Product Operating Model_images/page-001.txt"
```

## Next Steps

After verifying vision model quality:

1. **Document findings**: Note description quality, performance, issues
2. **Decide approach**: Local (Granite) vs Cloud (GPT-4o/Claude)
3. **Implement ingestion**: Build image ingestion into main pipeline
4. **Create API routes**: `/ingest/image` endpoint
5. **Add CLI commands**: `kg ingest image` command
6. **Test end-to-end**: Full pipeline from PDF to concept graph

## License

This tooling is part of the Knowledge Graph System (Apache 2.0).

**Dependencies**:
- pdf2image: MIT License
- poppler-utils: GPL (external tool, not linked)
- ollama: MIT License
- Pillow: HPND License (PIL Software License)
