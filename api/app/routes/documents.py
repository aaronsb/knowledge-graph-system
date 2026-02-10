"""
Document search and retrieval API routes (ADR-084).

Provides endpoints for:
- Document-level semantic search (aggregates chunk matches)
- Document content retrieval from Garage
- Ontology document listing
"""

import base64
import logging
import os
from typing import List, Optional, Dict, Any
import numpy as np
import psycopg2

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from ..lib.age_client import AGEClient
from ..lib.garage import get_source_storage, get_image_storage
from ..lib.similarity_calculator import cosine_similarity
from ..dependencies.auth import get_current_active_user, CurrentUser, require_permission
from ..models.auth import UserInDB

router = APIRouter(prefix="/documents", tags=["documents"])
query_router = APIRouter(prefix="/query/documents", tags=["documents"])

logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================

class DocumentResource(BaseModel):
    """Resource reference for a document (garage key)."""
    type: str = Field(..., description="Resource type: 'document' or 'image'")
    garage_key: str = Field(..., description="Garage storage key")


class DocumentSearchResult(BaseModel):
    """Single document in search results."""
    document_id: str = Field(..., description="Document ID (content hash)")
    filename: str = Field(..., description="Original filename")
    ontology: str = Field(..., description="Ontology/document name")
    content_type: str = Field(..., description="Content type: 'document' or 'image'")
    best_similarity: float = Field(..., description="Highest chunk similarity score")
    source_count: int = Field(..., description="Number of source chunks")
    resources: List[DocumentResource] = Field(default_factory=list, description="Garage resource references")
    concept_ids: List[str] = Field(default_factory=list, description="Concept IDs extracted from this document")


class DocumentSearchRequest(BaseModel):
    """Request body for document search."""
    query: str = Field(..., min_length=1, description="Search query text")
    min_similarity: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum similarity threshold")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum results")
    ontology: Optional[str] = Field(default=None, description="Filter by ontology name")


class DocumentSearchResponse(BaseModel):
    """Response from document search."""
    documents: List[DocumentSearchResult] = Field(default_factory=list)
    returned: int = Field(..., description="Number of results returned")
    total_matches: int = Field(..., description="Total documents matching threshold")


class DocumentsByConceptsRequest(BaseModel):
    """Request body for finding documents by concept IDs (reverse lookup)."""
    concept_ids: List[str] = Field(..., min_length=1, max_length=500, description="Concept IDs to find documents for")
    limit: int = Field(default=50, ge=1, le=200, description="Maximum results")


class DocumentChunk(BaseModel):
    """A source chunk from a document."""
    source_id: str
    paragraph: int
    full_text: str
    char_offset_start: Optional[int] = None
    char_offset_end: Optional[int] = None


class DocumentContentResponse(BaseModel):
    """Response with full document content."""
    document_id: str
    content_type: str = Field(default="document", description="'document' or 'image'")
    content: Dict[str, Any] = Field(..., description="Document content (text or image+prose)")
    chunks: List[DocumentChunk] = Field(default_factory=list, description="Source chunks from ingestion")


class DocumentListItem(BaseModel):
    """Document metadata for listing."""
    document_id: str
    filename: str
    ontology: str
    content_type: str = Field(default="document")
    source_count: int
    concept_count: int


class DocumentListResponse(BaseModel):
    """Response from document listing."""
    documents: List[DocumentListItem] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class DocumentDeleteResponse(BaseModel):
    """Response from document deletion."""
    document_id: str
    deleted: bool
    sources_deleted: int
    orphaned_concepts_deleted: int


class DocumentConceptItem(BaseModel):
    """Concept extracted from a document."""
    concept_id: str
    name: str
    source_id: str = Field(..., description="Source chunk where concept appears")
    instance_count: int = Field(default=1, description="Number of instances in document")


class DocumentConceptsResponse(BaseModel):
    """Response with concepts for a document."""
    document_id: str
    filename: str
    concepts: List[DocumentConceptItem] = Field(default_factory=list)
    total: int


class BulkDocumentConceptsRequest(BaseModel):
    """Request for bulk document concepts lookup."""
    document_ids: List[str] = Field(..., min_length=1, max_length=100, description="Document IDs to fetch concepts for")


class BulkDocumentConcept(BaseModel):
    """Concept with label for bulk response (no per-source detail)."""
    concept_id: str
    label: str


class BulkDocumentConceptsResponse(BaseModel):
    """Response with concepts grouped by document."""
    documents: Dict[str, List[BulkDocumentConcept]] = Field(
        default_factory=dict,
        description="Map of document_id to its concepts"
    )


# ============================================================================
# Helper Functions
# ============================================================================

def _generate_query_embedding(query: str) -> np.ndarray:
    """Generate embedding for search query."""
    from ..lib.ai_providers import get_provider

    provider = get_provider()
    embedding_result = provider.generate_embedding(query)

    # Extract embedding vector
    if isinstance(embedding_result, dict):
        embedding = embedding_result['embedding']
    else:
        embedding = embedding_result

    # Validate embedding is non-empty
    if not embedding or len(embedding) == 0:
        logger.error("Generated embedding is empty")
        raise HTTPException(
            status_code=500,
            detail="Generated embedding is empty. Check embedding provider configuration."
        )

    return np.array(embedding, dtype=np.float32)


def _search_documents_by_similarity(
    query_embedding: np.ndarray,
    min_similarity: float,
    limit: int,
    ontology_filter: Optional[str] = None
) -> Dict[str, Dict]:
    """
    Search source embeddings and aggregate to source level.

    Returns dict mapping source_id to:
    {
        "best_similarity": float,
        "chunk_count": int
    }

    Source nodes link to DocumentMeta via the graph.
    """
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database=os.getenv("POSTGRES_DB", "knowledge_graph"),
        user=os.getenv("POSTGRES_USER", "admin"),
        password=os.getenv("POSTGRES_PASSWORD")
    )

    try:
        with conn.cursor() as cursor:
            # Fetch all source embeddings
            cursor.execute("""
                SELECT
                    se.source_id,
                    se.embedding
                FROM kg_api.source_embeddings se
                WHERE se.chunk_strategy = 'sentence'
            """)

            # Calculate similarities and group by source_id
            source_aggregates = {}
            for row in cursor.fetchall():
                source_id, embedding_bytes = row

                chunk_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)
                similarity = cosine_similarity(query_embedding, chunk_embedding)

                if similarity >= min_similarity:
                    if source_id not in source_aggregates:
                        source_aggregates[source_id] = {
                            'best_similarity': similarity,
                            'chunk_count': 1
                        }
                    else:
                        source_aggregates[source_id]['chunk_count'] += 1
                        if similarity > source_aggregates[source_id]['best_similarity']:
                            source_aggregates[source_id]['best_similarity'] = similarity

            return source_aggregates

    finally:
        conn.close()


def _get_document_metadata_for_sources(
    client: AGEClient,
    source_ids: List[str],
    ontology_filter: Optional[str] = None
) -> Dict[str, Dict]:
    """
    Fetch DocumentMeta nodes for given source IDs via graph traversal.

    Returns dict mapping source_id to document metadata.
    """
    if not source_ids:
        return {}

    # Build query: Source <- HAS_SOURCE - DocumentMeta
    params = {"source_ids": source_ids}

    if ontology_filter:
        params["ontology_pattern"] = f"(?i).*{ontology_filter}.*"
        query = """
        MATCH (d:DocumentMeta)-[:HAS_SOURCE]->(s:Source)
        WHERE s.source_id IN $source_ids AND d.ontology =~ $ontology_pattern
        RETURN s.source_id as source_id,
               d.document_id as document_id,
               d.filename as filename,
               d.ontology as ontology,
               d.content_type as content_type,
               d.garage_key as garage_key,
               d.storage_key as storage_key
        """
    else:
        query = """
        MATCH (d:DocumentMeta)-[:HAS_SOURCE]->(s:Source)
        WHERE s.source_id IN $source_ids
        RETURN s.source_id as source_id,
               d.document_id as document_id,
               d.filename as filename,
               d.ontology as ontology,
               d.content_type as content_type,
               d.garage_key as garage_key,
               d.storage_key as storage_key
        """

    results = client._execute_cypher(query, params=params)

    docs_by_source = {}
    for row in results:
        source_id = row.get('source_id')
        if source_id:
            docs_by_source[source_id] = row

    return docs_by_source


def _get_concepts_for_documents(client: AGEClient, document_ids: List[str]) -> Dict[str, List[str]]:
    """
    Get concept IDs for each document via Source nodes.

    Returns dict mapping document_id to list of concept_ids.
    """
    if not document_ids:
        return {}

    # Query: DocumentMeta -[:HAS_SOURCE]-> Source <-[:APPEARS]- Concept
    query = """
    MATCH (d:DocumentMeta)-[:HAS_SOURCE]->(s:Source)<-[:APPEARS]-(c:Concept)
    WHERE d.document_id IN $doc_ids
    RETURN d.document_id as document_id, collect(DISTINCT c.concept_id) as concept_ids
    """

    results = client._execute_cypher(query, params={"doc_ids": document_ids})

    concepts_by_doc = {}
    for row in results:
        doc_id = row.get('document_id')
        concept_ids = row.get('concept_ids', [])
        if doc_id:
            concepts_by_doc[doc_id] = concept_ids

    return concepts_by_doc


# ============================================================================
# Query Routes
# ============================================================================

@query_router.post("/search", response_model=DocumentSearchResponse)
async def search_documents(
    request: DocumentSearchRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Search documents using semantic similarity (ADR-084).

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `graph:read` permission

    Searches source embeddings and aggregates results to document level.
    Documents are ranked by their best matching chunk's similarity score.

    **Request Body:**
    ```json
    {
      "query": "recursive depth patterns",
      "min_similarity": 0.7,
      "limit": 20,
      "ontology": "optional-filter"
    }
    ```

    **Response:**
    ```json
    {
      "documents": [
        {
          "document_id": "sha256:abc123...",
          "filename": "algorithms.md",
          "ontology": "CS Research",
          "content_type": "document",
          "best_similarity": 0.92,
          "source_count": 5,
          "resources": [{"type": "document", "garage_key": "..."}],
          "concept_ids": ["c-123", "c-456"]
        }
      ],
      "returned": 20,
      "total_matches": 42
    }
    ```
    """
    try:
        # 1. Generate query embedding
        query_embedding = _generate_query_embedding(request.query)

        # 2. Search and aggregate to source level
        source_aggregates = _search_documents_by_similarity(
            query_embedding=query_embedding,
            min_similarity=request.min_similarity,
            limit=request.limit,
            ontology_filter=request.ontology
        )

        if not source_aggregates:
            return DocumentSearchResponse(
                documents=[],
                returned=0,
                total_matches=0
            )

        # 3. Look up DocumentMeta for each source_id via graph
        client = AGEClient()
        try:
            source_ids = list(source_aggregates.keys())
            docs_by_source = _get_document_metadata_for_sources(client, source_ids, request.ontology)

            # 4. Aggregate to document level
            # Multiple sources may belong to same document
            doc_aggregates: Dict[str, Dict] = {}
            for source_id, source_data in source_aggregates.items():
                doc_meta = docs_by_source.get(source_id)
                if not doc_meta:
                    # Source not linked to DocumentMeta (legacy data)
                    continue

                doc_id = doc_meta.get('document_id')
                if not doc_id:
                    continue

                if doc_id not in doc_aggregates:
                    doc_aggregates[doc_id] = {
                        'meta': doc_meta,
                        'best_similarity': source_data['best_similarity'],
                        'source_count': 1,
                        'source_ids': [source_id]
                    }
                else:
                    doc_aggregates[doc_id]['source_count'] += 1
                    doc_aggregates[doc_id]['source_ids'].append(source_id)
                    if source_data['best_similarity'] > doc_aggregates[doc_id]['best_similarity']:
                        doc_aggregates[doc_id]['best_similarity'] = source_data['best_similarity']

            total_matches = len(doc_aggregates)

            if not doc_aggregates:
                return DocumentSearchResponse(
                    documents=[],
                    returned=0,
                    total_matches=0
                )

            # 5. Sort by best_similarity, limit results
            sorted_doc_ids = sorted(
                doc_aggregates.keys(),
                key=lambda d: doc_aggregates[d]['best_similarity'],
                reverse=True
            )[:request.limit]

            # 6. Fetch concepts for documents
            concepts_by_doc = _get_concepts_for_documents(client, sorted_doc_ids)

            # 7. Build results
            results = []
            for doc_id in sorted_doc_ids:
                agg = doc_aggregates[doc_id]
                meta = agg['meta']

                # Build resources list
                resources = []
                if meta.get('garage_key'):
                    resources.append(DocumentResource(
                        type="document",
                        garage_key=meta['garage_key']
                    ))
                if meta.get('storage_key'):
                    resources.append(DocumentResource(
                        type="image",
                        garage_key=meta['storage_key']
                    ))

                results.append(DocumentSearchResult(
                    document_id=doc_id,
                    filename=meta.get('filename') or 'unknown',
                    ontology=meta.get('ontology') or 'unknown',
                    content_type=meta.get('content_type') or 'document',
                    best_similarity=round(agg['best_similarity'], 4),
                    source_count=agg['source_count'],
                    resources=resources,
                    concept_ids=concepts_by_doc.get(doc_id, [])
                ))

            return DocumentSearchResponse(
                documents=results,
                returned=len(results),
                total_matches=total_matches
            )

        finally:
            client.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Document search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@query_router.post("/by-concepts", response_model=DocumentSearchResponse)
async def find_documents_by_concepts(
    request: DocumentsByConceptsRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Find documents that contain the given concepts (reverse lookup).

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `graph:read` permission

    Traverses Concept → APPEARS → Source ← HAS_SOURCE ← DocumentMeta
    to find which documents contributed to the given concepts.
    Documents are ranked by number of matching concepts (most relevant first).
    """
    try:
        client = AGEClient()
        try:
            # 1. Find documents linked to these concepts via Source nodes
            # Group by document_id string (not node identity) to avoid
            # AGE returning duplicate rows for the same document.
            query = """
            MATCH (c:Concept)-[:APPEARS]->(s:Source)<-[:HAS_SOURCE]-(d:DocumentMeta)
            WHERE c.concept_id IN $concept_ids
            RETURN d.document_id as document_id,
                   d.filename as filename,
                   d.ontology as ontology,
                   d.content_type as content_type,
                   d.garage_key as garage_key,
                   d.storage_key as storage_key,
                   s.source_id as source_id,
                   c.concept_id as concept_id
            """

            results = client._execute_cypher(
                query,
                params={"concept_ids": request.concept_ids}
            )

            if not results:
                return DocumentSearchResponse(
                    documents=[],
                    returned=0,
                    total_matches=0
                )

            # 2. Aggregate in Python — deduplicate by document_id
            doc_aggregates: Dict[str, Dict] = {}
            for row in results:
                doc_id = row.get('document_id')
                if not doc_id:
                    continue

                if doc_id not in doc_aggregates:
                    doc_aggregates[doc_id] = {
                        'filename': row.get('filename') or 'unknown',
                        'ontology': row.get('ontology') or 'unknown',
                        'content_type': row.get('content_type') or 'document',
                        'garage_key': row.get('garage_key'),
                        'storage_key': row.get('storage_key'),
                        'source_ids': set(),
                        'concept_ids': set(),
                    }

                doc_aggregates[doc_id]['source_ids'].add(row.get('source_id'))
                doc_aggregates[doc_id]['concept_ids'].add(row.get('concept_id'))

            # 3. Sort by matching concept count, limit
            sorted_docs = sorted(
                doc_aggregates.items(),
                key=lambda item: len(item[1]['concept_ids']),
                reverse=True
            )[:request.limit]

            total_concept_count = len(request.concept_ids)

            # 4. Build results
            documents = []
            for doc_id, agg in sorted_docs:
                resources = []
                if agg.get('garage_key'):
                    resources.append(DocumentResource(
                        type="document",
                        garage_key=agg['garage_key']
                    ))
                if agg.get('storage_key'):
                    resources.append(DocumentResource(
                        type="image",
                        garage_key=agg['storage_key']
                    ))

                documents.append(DocumentSearchResult(
                    document_id=doc_id,
                    filename=agg['filename'],
                    ontology=agg['ontology'],
                    content_type=agg['content_type'],
                    best_similarity=len(agg['concept_ids']) / max(total_concept_count, 1),
                    source_count=len(agg['source_ids']),
                    resources=resources,
                    concept_ids=list(agg['concept_ids']),
                ))

            return DocumentSearchResponse(
                documents=documents,
                returned=len(documents),
                total_matches=len(doc_aggregates)
            )

        finally:
            client.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Find documents by concepts failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to find documents: {str(e)}")


# ============================================================================
# Document Routes
# ============================================================================

@router.get("/{document_id}/content", response_model=DocumentContentResponse)
async def get_document_content(
    document_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Retrieve full document content from Garage (ADR-084).

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `sources:read` permission

    Returns the original document plus all source chunks created during ingestion.

    **Response for text document:**
    ```json
    {
      "document_id": "sha256:abc123...",
      "content_type": "document",
      "content": {
        "document": "# Full markdown content...",
        "encoding": "utf-8"
      },
      "chunks": [
        {"source_id": "...", "paragraph": 0, "full_text": "..."}
      ]
    }
    ```

    **Response for image:**
    ```json
    {
      "document_id": "sha256:img456...",
      "content_type": "image",
      "content": {
        "image": "base64-encoded...",
        "prose": "Description of the image...",
        "encoding": "base64"
      },
      "chunks": [...]
    }
    ```
    """
    client = AGEClient()

    try:
        # 1. Get DocumentMeta node
        query = """
        MATCH (d:DocumentMeta {document_id: $doc_id})
        RETURN d.document_id as document_id,
               d.content_type as content_type,
               d.garage_key as garage_key,
               d.storage_key as storage_key,
               d.prose_key as prose_key
        """

        result = client._execute_cypher(
            query,
            params={"doc_id": document_id},
            fetch_one=True
        )

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Document not found: {document_id}"
            )

        content_type = result.get('content_type') or 'document'
        garage_key = result.get('garage_key')
        storage_key = result.get('storage_key')
        prose_key = result.get('prose_key')

        # 2. Fetch content based on type
        content = {}

        if content_type == 'image':
            # Fetch image + prose
            image_storage = get_image_storage()

            if storage_key:
                try:
                    image_bytes = image_storage.base.get_object(storage_key)
                    if image_bytes:
                        content['image'] = base64.b64encode(image_bytes).decode('utf-8')
                        content['encoding'] = 'base64'
                except Exception as e:
                    logger.warning(f"Failed to fetch image {storage_key}: {e}")

            if prose_key:
                try:
                    prose_bytes = image_storage.base.get_object(prose_key)
                    if prose_bytes:
                        content['prose'] = prose_bytes.decode('utf-8')
                except Exception as e:
                    logger.warning(f"Failed to fetch prose {prose_key}: {e}")

        else:
            # Fetch text document
            if garage_key:
                source_storage = get_source_storage()
                try:
                    doc_bytes = source_storage.get(garage_key)
                    if doc_bytes:
                        content['document'] = doc_bytes.decode('utf-8')
                        content['encoding'] = 'utf-8'
                except Exception as e:
                    logger.warning(f"Failed to fetch document {garage_key}: {e}")
                    content['document'] = None
                    content['error'] = str(e)

        # 3. Fetch source chunks (DISTINCT handles duplicate DocumentMeta nodes / edges)
        chunks_query = """
        MATCH (d:DocumentMeta {document_id: $doc_id})-[:HAS_SOURCE]->(s:Source)
        RETURN DISTINCT s.source_id as source_id,
               s.paragraph as paragraph,
               s.full_text as full_text,
               s.char_offset_start as char_offset_start,
               s.char_offset_end as char_offset_end
        ORDER BY s.paragraph
        """

        chunks_result = client._execute_cypher(chunks_query, params={"doc_id": document_id})

        chunks = [
            DocumentChunk(
                source_id=c['source_id'],
                paragraph=c.get('paragraph', 0),
                full_text=c.get('full_text', ''),
                char_offset_start=c.get('char_offset_start'),
                char_offset_end=c.get('char_offset_end')
            )
            for c in chunks_result
        ]

        return DocumentContentResponse(
            document_id=document_id,
            content_type=content_type,
            content=content,
            chunks=chunks
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document content: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve document: {str(e)}")
    finally:
        client.close()


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    ontology: Optional[str] = Query(None, description="Filter by ontology name"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Skip first N results"),
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    List documents with optional ontology filter (ADR-084).

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `sources:read` permission

    **Query Parameters:**
    - `ontology`: Filter by ontology name (case-insensitive partial match)
    - `limit`: Maximum results (default 50, max 200)
    - `offset`: Skip first N results for pagination

    **Response:**
    ```json
    {
      "documents": [
        {
          "document_id": "sha256:abc...",
          "filename": "notes.md",
          "ontology": "Research",
          "content_type": "document",
          "source_count": 5,
          "concept_count": 12
        }
      ],
      "total": 42,
      "limit": 50,
      "offset": 0
    }
    ```
    """
    client = AGEClient()

    try:
        # Build query with optional filter
        params = {"limit": limit, "offset": offset}

        if ontology:
            params["ontology_pattern"] = f"(?i).*{ontology}.*"
            # Main query with counts (aggregate by document_id to handle duplicate nodes)
            query = """
            MATCH (d:DocumentMeta)
            WHERE d.ontology =~ $ontology_pattern
            OPTIONAL MATCH (d)-[:HAS_SOURCE]->(s:Source)
            OPTIONAL MATCH (s)<-[:APPEARS_IN]-(c:Concept)
            WITH d.document_id as document_id, d.filename as filename,
                 d.ontology as ontology, d.content_type as content_type,
                 count(DISTINCT s) as source_count, count(DISTINCT c) as concept_count
            RETURN document_id, filename, ontology, content_type,
                   source_count, concept_count
            ORDER BY ontology, filename
            SKIP $offset LIMIT $limit
            """
            count_query = """
            MATCH (d:DocumentMeta)
            WHERE d.ontology =~ $ontology_pattern
            RETURN count(DISTINCT d.document_id) as total
            """
        else:
            query = """
            MATCH (d:DocumentMeta)
            OPTIONAL MATCH (d)-[:HAS_SOURCE]->(s:Source)
            OPTIONAL MATCH (s)<-[:APPEARS_IN]-(c:Concept)
            WITH d.document_id as document_id, d.filename as filename,
                 d.ontology as ontology, d.content_type as content_type,
                 count(DISTINCT s) as source_count, count(DISTINCT c) as concept_count
            RETURN document_id, filename, ontology, content_type,
                   source_count, concept_count
            ORDER BY ontology, filename
            SKIP $offset LIMIT $limit
            """
            count_query = """
            MATCH (d:DocumentMeta)
            RETURN count(DISTINCT d.document_id) as total
            """

        results = client._execute_cypher(query, params=params)
        count_result = client._execute_cypher(
            count_query,
            params={"ontology_pattern": params.get("ontology_pattern")} if ontology else {},
            fetch_one=True
        )

        documents = [
            DocumentListItem(
                document_id=r['document_id'],
                filename=r.get('filename') or 'unknown',
                ontology=r.get('ontology') or 'unknown',
                content_type=r.get('content_type') or 'document',
                source_count=r.get('source_count') or 0,
                concept_count=r.get('concept_count') or 0
            )
            for r in results
        ]

        return DocumentListResponse(
            documents=documents,
            total=count_result.get('total', 0) if count_result else 0,
            limit=limit,
            offset=offset
        )

    except Exception as e:
        logger.error(f"Failed to list documents: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")
    finally:
        client.close()


@router.get("/{document_id}/concepts", response_model=DocumentConceptsResponse)
async def get_document_concepts(
    document_id: str,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Get all concepts extracted from a document (ADR-084).

    **Authentication:** Requires valid OAuth token
    **Authorization:** Requires `graph:read` permission

    Returns concepts linked to the document via Source nodes,
    including concept names and the source chunks where they appear.

    **Response:**
    ```json
    {
      "document_id": "sha256:abc...",
      "filename": "notes.md",
      "concepts": [
        {
          "concept_id": "sha256:abc_chunk1_def",
          "name": "Machine Learning",
          "source_id": "sha256:abc_chunk1",
          "instance_count": 3
        }
      ],
      "total": 15
    }
    ```
    """
    client = AGEClient()

    try:
        # 1. Get document metadata
        doc_query = """
        MATCH (d:DocumentMeta {document_id: $doc_id})
        RETURN d.filename as filename
        """
        doc_result = client._execute_cypher(doc_query, params={"doc_id": document_id}, fetch_one=True)

        if not doc_result:
            raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

        filename = doc_result.get('filename') or 'unknown'

        # 2. Get concepts via DocumentMeta -> HAS_SOURCE -> Source <- APPEARS - Concept
        concepts_query = """
        MATCH (d:DocumentMeta {document_id: $doc_id})-[:HAS_SOURCE]->(s:Source)<-[:APPEARS]-(c:Concept)
        OPTIONAL MATCH (c)-[:EVIDENCED_BY]->(i:Instance)-[:FROM_SOURCE]->(s)
        WITH c, s, count(i) as instance_count
        RETURN c.concept_id as concept_id,
               c.label as name,
               s.source_id as source_id,
               instance_count
        ORDER BY instance_count DESC, c.label
        """

        results = client._execute_cypher(concepts_query, params={"doc_id": document_id})

        concepts = [
            DocumentConceptItem(
                concept_id=r['concept_id'],
                name=r.get('name') or r['concept_id'],
                source_id=r['source_id'],
                instance_count=r.get('instance_count') or 1
            )
            for r in results
        ]

        return DocumentConceptsResponse(
            document_id=document_id,
            filename=filename,
            concepts=concepts,
            total=len(concepts)
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document concepts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get concepts: {str(e)}")
    finally:
        client.close()


@router.post("/concepts/bulk", response_model=BulkDocumentConceptsResponse)
async def get_document_concepts_bulk(
    request: BulkDocumentConceptsRequest,
    current_user: UserInDB = Depends(get_current_active_user)
):
    """
    Bulk fetch concepts for multiple documents in a single query.

    Returns deduplicated concepts (concept_id + label) per document.
    Used by the Document Explorer to hydrate all documents from a saved query.
    """
    client = AGEClient()

    try:
        query = """
        MATCH (d:DocumentMeta)-[:HAS_SOURCE]->(s:Source)<-[:APPEARS]-(c:Concept)
        WHERE d.document_id IN $doc_ids
        RETURN d.document_id as document_id,
               c.concept_id as concept_id,
               c.label as label
        """

        results = client._execute_cypher(query, params={"doc_ids": request.document_ids})

        # Aggregate by document, deduplicate concepts per document
        docs: Dict[str, Dict[str, str]] = {}  # doc_id -> {concept_id: label}
        for row in results:
            doc_id = row.get('document_id')
            concept_id = row.get('concept_id')
            label = row.get('label')
            if doc_id and concept_id:
                if doc_id not in docs:
                    docs[doc_id] = {}
                docs[doc_id][concept_id] = label or concept_id

        response_docs = {
            doc_id: [
                BulkDocumentConcept(concept_id=cid, label=lbl)
                for cid, lbl in concepts.items()
            ]
            for doc_id, concepts in docs.items()
        }

        return BulkDocumentConceptsResponse(documents=response_docs)

    except Exception as e:
        logger.error(f"Failed to get bulk document concepts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get bulk concepts: {str(e)}")
    finally:
        client.close()


# ============================================================================
# Document Deletion
# ============================================================================

@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    document_id: str,
    current_user: CurrentUser,
    _: None = Depends(require_permission("sources", "delete")),
):
    """Delete a document and cascade-remove orphaned concepts.

    Deletes all data associated with a single document:
    - Source nodes (chunks) linked via DocumentMeta
    - Instance nodes linked to those sources
    - source_embeddings records
    - Garage storage objects (source documents and images)
    - The DocumentMeta node itself
    - Orphaned Concept nodes (concepts with no remaining sources)

    Follows the same cascade pattern as DELETE /ontology/{name}
    but scoped to a single document.

    Authorization: Requires sources:delete permission.
    """
    from ..services.job_queue import get_job_queue

    client = AGEClient()
    queue = get_job_queue()
    try:
        # Find the DocumentMeta node and its sources
        doc_meta = client._execute_cypher("""
            MATCH (d:DocumentMeta {document_id: $document_id})
            RETURN d.document_id as document_id,
                   d.filename as filename,
                   d.ontology as ontology
        """, params={"document_id": document_id}, fetch_one=True)

        if not doc_meta:
            raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")

        ontology_name = doc_meta.get("ontology")
        filename = doc_meta.get("filename", document_id)
        logger.info(f"Deleting document '{filename}' (id={document_id}) from ontology '{ontology_name}'")

        # Capture source_ids before deletion
        source_ids_result = client._execute_cypher("""
            MATCH (d:DocumentMeta {document_id: $document_id})-[:HAS_SOURCE]->(s:Source)
            RETURN s.source_id as source_id, s.storage_key as storage_key
        """, params={"document_id": document_id})

        source_ids = [r["source_id"] for r in (source_ids_result or []) if r.get("source_id")]
        storage_keys = [r["storage_key"] for r in (source_ids_result or []) if r.get("storage_key")]

        # Clean up Garage storage objects
        try:
            # Delete images (via storage_key on Source nodes)
            if storage_keys:
                image_storage = get_image_storage()
                for key in storage_keys:
                    try:
                        image_storage.delete(key)
                    except Exception as e:
                        logger.warning(f"Failed to delete Garage image {key}: {e}")

            # Delete source documents
            try:
                source_storage = get_source_storage()
                for sid in source_ids:
                    try:
                        source_storage.delete(sid)
                    except Exception as e:
                        logger.warning(f"Failed to delete source doc {sid} from Garage: {e}")
            except Exception as e:
                logger.warning(f"Failed to initialize source storage: {e}")

        except Exception as e:
            logger.warning(f"Failed to initialize Garage for cleanup: {e}")

        # Delete Instance nodes linked to this document's sources
        client._execute_cypher("""
            MATCH (d:DocumentMeta {document_id: $document_id})-[:HAS_SOURCE]->(s:Source)
            MATCH (i:Instance)-[:FROM_SOURCE]->(s)
            DETACH DELETE i
        """, params={"document_id": document_id})

        # Delete Source nodes
        result = client._execute_cypher("""
            MATCH (d:DocumentMeta {document_id: $document_id})-[:HAS_SOURCE]->(s:Source)
            DETACH DELETE s
            RETURN count(s) as deleted_count
        """, params={"document_id": document_id}, fetch_one=True)

        sources_deleted = result["deleted_count"] if result else 0

        # Delete source_embeddings
        if source_ids:
            conn = None
            try:
                conn = client.pool.getconn()
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM kg_api.source_embeddings
                        WHERE source_id = ANY(%s)
                    """, (source_ids,))
                    conn.commit()
            except Exception as e:
                logger.warning(f"Failed to delete source embeddings: {e}")
            finally:
                if conn:
                    client.pool.putconn(conn)

        # Delete the DocumentMeta node
        client._execute_cypher("""
            MATCH (d:DocumentMeta {document_id: $document_id})
            DETACH DELETE d
        """, params={"document_id": document_id})

        # Clean up orphaned concepts (concepts with no remaining sources)
        orphaned_result = client._execute_cypher("""
            MATCH (c:Concept)
            OPTIONAL MATCH (c)-[:APPEARS]->(s:Source)
            WITH c, s
            WHERE s IS NULL
            DETACH DELETE c
            RETURN count(c) as orphaned_count
        """, fetch_one=True)

        orphaned_count = orphaned_result["orphaned_count"] if orphaned_result else 0

        # Delete job records for this document
        try:
            conn = None
            conn = client.pool.getconn()
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM kg_api.jobs
                    WHERE source_filename = %s AND ontology = %s
                """, (filename, ontology_name))
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to delete job records: {e}")
        finally:
            if conn:
                client.pool.putconn(conn)

        logger.info(
            f"Deleted document '{filename}': "
            f"{sources_deleted} sources, {orphaned_count} orphaned concepts"
        )

        # Refresh graph epoch so caches (FUSE, etc.) detect the change
        client.refresh_epoch()

        return DocumentDeleteResponse(
            document_id=document_id,
            deleted=True,
            sources_deleted=sources_deleted,
            orphaned_concepts_deleted=orphaned_count,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")
    finally:
        client.close()
