# source

> Auto-generated from MCP tool schema

### source

Retrieve original source content (text or image) for a source node (ADR-057).

For IMAGE sources: Returns the image for visual verification
For TEXT sources: Returns full_text content with metadata (document, paragraph, offsets)

Use when you need to:
- Verify extracted concepts against original source
- Get the full context of a text passage
- Retrieve images for visual analysis
- Check character offsets for highlighting

**Parameters:**

- `source_id` (`string`) **(required)** - Source ID from evidence or search results

---
