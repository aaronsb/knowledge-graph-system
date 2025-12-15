"""
Source retrieval API routes.

Provides endpoints for retrieving source content, including:
- Images from Garage (ADR-057)
- Original documents from Garage (ADR-081)
"""

import logging
import os
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import Response
from typing import Optional

from ..lib.age_client import AGEClient
from ..lib.garage_client import get_garage_client
from ..lib.garage import get_source_storage
from ..dependencies.auth import get_current_active_user
from ..models.auth import UserInDB

router = APIRouter(prefix="/sources", tags=["sources"])

logger = logging.getLogger(__name__)


@router.get(
    "/{source_id}/image",
    summary="Retrieve image from source (ADR-057)",
    responses={
        200: {
            "content": {
                "image/jpeg": {},
                "image/png": {},
                "image/gif": {},
                "image/webp": {},
                "image/bmp": {}
            },
            "description": "Image binary data"
        },
        404: {"description": "Source not found or not an image source"},
        500: {"description": "Failed to retrieve image from storage"}
    }
)
async def get_source_image(
    source_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Retrieve the original image for an image source.

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `sources:read` permission

    **Workflow:**
    1. Look up Source node in graph by source_id
    2. Verify it's an image source (content_type='image')
    3. Get storage key from Source node
    4. Download image from Garage storage
    5. Return image with appropriate Content-Type header

    **Args:**
    - `source_id`: Source ID from search results or concept details

    **Returns:**
    - Image binary data with correct MIME type header

    **Example:**
    ```bash
    curl -H "Authorization: Bearer $TOKEN" \\
      http://localhost:8000/api/sources/src_abc123/image \\
      -o image.jpg
    ```

    **Access Control:**
    - Requires authentication (any authenticated user can retrieve images)
    - Future: Add ontology-based access control (ADR-028)
    """
    age_client = AGEClient()

    # Step 1: Look up Source node
    try:
        query = """
        MATCH (s:Source {source_id: $source_id})
        RETURN s.content_type as content_type,
               s.storage_key as storage_key
        """

        result = age_client._execute_cypher(
            query,
            params={"source_id": source_id},
            fetch_one=True
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Source not found: {source_id}"
            )

        content_type = result.get("content_type")
        storage_key = result.get("storage_key")

        logger.info(f"Found source {source_id}: content_type={content_type}, storage_key={storage_key}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to lookup source {source_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database lookup failed: {str(e)}"
        )

    # Step 2: Verify it's an image source
    if content_type != "image":
        raise HTTPException(
            status_code=400,
            detail=f"Source {source_id} is not an image (content_type='{content_type}')"
        )

    if not storage_key:
        raise HTTPException(
            status_code=404,
            detail=f"Source {source_id} has no MinIO object key (image may have been deleted)"
        )

    # Step 3: Download image from Garage
    try:
        garage_client = get_garage_client()
        image_bytes = garage_client.download_image(storage_key)

        logger.info(f"Retrieved image for {source_id}: {len(image_bytes)} bytes")

    except Exception as e:
        logger.error(f"Failed to download image from MinIO: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Image retrieval failed: {str(e)}"
        )

    # Step 4: Detect content type from file extension
    content_type_map = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
        '.bmp': 'image/bmp'
    }

    # Extract extension from storage_key
    import os
    ext = os.path.splitext(storage_key)[1].lower()
    mime_type = content_type_map.get(ext, 'image/jpeg')

    # Step 5: Return image with appropriate headers
    return Response(
        content=image_bytes,
        media_type=mime_type,
        headers={
            "Content-Disposition": f"inline; filename={source_id}{ext}",
            "Cache-Control": "public, max-age=31536000"  # Cache for 1 year (images are immutable)
        }
    )


@router.get(
    "/{source_id}/document",
    summary="Retrieve original document from Garage (ADR-081)",
    responses={
        200: {
            "content": {
                "text/plain": {},
                "text/markdown": {},
                "application/octet-stream": {}
            },
            "description": "Original document content"
        },
        404: {"description": "Source not found or no garage_key"},
        500: {"description": "Failed to retrieve document from storage"}
    }
)
async def get_source_document(
    source_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Retrieve the original source document from Garage storage.

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `sources:read` permission

    **Workflow:**
    1. Look up Source node in graph by source_id
    2. Get garage_key from Source node (ADR-081)
    3. Download document from Garage storage
    4. Return document with appropriate Content-Type header

    **Args:**
    - `source_id`: Source ID from search results or concept details

    **Returns:**
    - Original document content with correct MIME type header

    **Example:**
    ```bash
    # Save to file
    curl -H "Authorization: Bearer $TOKEN" \\
      http://localhost:8000/api/sources/sha256:abc123_chunk1/document \\
      -o original.txt

    # Pipe to stdout
    curl -s -H "Authorization: Bearer $TOKEN" \\
      http://localhost:8000/api/sources/sha256:abc123_chunk1/document
    ```

    **Note:** This returns the ORIGINAL document stored before chunking,
    not the chunk text. Use `GET /sources/{source_id}` for chunk metadata.
    """
    age_client = AGEClient()

    # Step 1: Look up Source node
    try:
        query = """
        MATCH (s:Source {source_id: $source_id})
        RETURN s.garage_key as garage_key,
               s.content_type as content_type
        """

        result = age_client._execute_cypher(
            query,
            params={"source_id": source_id},
            fetch_one=True
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Source not found: {source_id}"
            )

        garage_key = result.get("garage_key")
        content_type = result.get("content_type")

        logger.info(f"Found source {source_id}: garage_key={garage_key}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to lookup source {source_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database lookup failed: {str(e)}"
        )

    # Step 2: Verify garage_key exists
    if not garage_key:
        raise HTTPException(
            status_code=404,
            detail=f"Source {source_id} has no garage_key (document may predate ADR-081)"
        )

    # Step 3: Download document from Garage
    try:
        source_storage = get_source_storage()
        document_bytes = source_storage.get(garage_key)

        if document_bytes is None:
            raise HTTPException(
                status_code=404,
                detail=f"Document not found in Garage: {garage_key}"
            )

        logger.info(f"Retrieved document for {source_id}: {len(document_bytes)} bytes")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download document from Garage: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Document retrieval failed: {str(e)}"
        )

    # Step 4: Detect content type from file extension
    content_type_map = {
        '.txt': 'text/plain',
        '.md': 'text/markdown',
        '.markdown': 'text/markdown',
        '.json': 'application/json',
        '.html': 'text/html',
        '.htm': 'text/html'
    }

    ext = os.path.splitext(garage_key)[1].lower()
    mime_type = content_type_map.get(ext, 'application/octet-stream')

    # Extract filename from garage_key for Content-Disposition
    filename = os.path.basename(garage_key)

    # Step 5: Return document with appropriate headers
    return Response(
        content=document_bytes,
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
            "Cache-Control": "public, max-age=31536000"  # Cache for 1 year (documents are immutable)
        }
    )


@router.get(
    "/{source_id}",
    summary="Get source metadata and content",
)
async def get_source(
    source_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Retrieve source metadata and content (prose for images, text for documents).

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `sources:read` permission

    **Returns:**
    ```json
    {
      "source_id": "src_abc123",
      "document": "Architecture Diagrams",
      "paragraph": 1,
      "full_text": "Flowchart showing...",
      "content_type": "image",
      "storage_key": "Architecture_Diagrams/src_abc123.jpg",
      "has_visual_embedding": true,
      "has_text_embedding": true
    }
    ```

    **Note:** For images, `full_text` contains the prose description, not the binary image.
    Use `GET /sources/{source_id}/image` to retrieve the actual image.
    """
    age_client = AGEClient()

    try:
        query = """
        MATCH (s:Source {source_id: $source_id})
        RETURN s.source_id as source_id,
               s.document as document,
               s.paragraph as paragraph,
               s.full_text as full_text,
               s.file_path as file_path,
               s.content_type as content_type,
               s.storage_key as storage_key,
               s.garage_key as garage_key,
               s.content_hash as content_hash,
               s.char_offset_start as char_offset_start,
               s.char_offset_end as char_offset_end,
               s.chunk_index as chunk_index,
               s.visual_embedding IS NOT NULL as has_visual_embedding,
               s.embedding IS NOT NULL as has_text_embedding
        """

        result = age_client._execute_cypher(
            query,
            params={"source_id": source_id},
            fetch_one=True
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Source not found: {source_id}"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get source {source_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve source: {str(e)}"
        )
