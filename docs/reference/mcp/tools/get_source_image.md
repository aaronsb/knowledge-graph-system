# get_source_image

> Auto-generated from MCP tool schema

### get_source_image

Retrieve the original image for a source node (ADR-057). Use this when concept evidence has image metadata (has_image=true, image_uri set). Returns base64-encoded image data. **Use Case:** Visual verification of extracted concepts - compare image to extracted descriptions to check if anything was missed. This enables a refinement loop: view image → create new description → upsert → concepts get associated with image.

**Parameters:**

- `source_id` (`string`) **(required)** - Source ID from concept instance (found in evidence with has_image=true)

---
