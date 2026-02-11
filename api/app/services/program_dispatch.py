"""
GraphProgram operation dispatch (ADR-500 Phase 3).

Executes CypherOp and ApiOp operations against the source graph H,
returning results as WorkingGraph (nodes + links).

CypherOp: Runs query via AGEClient._execute_cypher(), maps AGE result rows.
ApiOp: Calls internal service functions directly (no HTTP), maps to WorkingGraph.
"""

import logging
from typing import Any, Dict, List, Optional

from api.app.models.program import (
    CypherOp,
    ApiOp,
    WorkingGraph,
    RawNode,
    RawLink,
)

logger = logging.getLogger(__name__)


class DispatchContext:
    """Shared resources for a single program execution."""

    def __init__(self, client):
        self.client = client
        self._provider = None

    @property
    def provider(self):
        """Lazy-load AI provider (only needed for ApiOp search endpoints)."""
        if self._provider is None:
            from api.app.lib.ai_providers import get_provider
            self._provider = get_provider()
        return self._provider


# ---------------------------------------------------------------------------
# CypherOp dispatch
# ---------------------------------------------------------------------------

def dispatch_cypher(ctx: DispatchContext, op: CypherOp) -> WorkingGraph:
    """Execute CypherOp and map AGE results to WorkingGraph."""
    from api.app.services.cypher_guard import check_cypher_safety

    # Defense-in-depth: re-check safety at execution time even though
    # the validator already checked during notarization (programs could
    # be stored and executed much later, or a future caller could skip
    # the validation gate).
    issues = check_cypher_safety(op.query)
    if issues:
        msgs = "; ".join(i.message for i in issues)
        raise ValueError(f"Cypher safety check failed: {msgs}")

    query = op.query

    # Apply limit if set and query doesn't already have one
    if op.limit and 'LIMIT' not in query.upper():
        query = f"{query} LIMIT {op.limit}"

    records = ctx.client._execute_cypher(query)
    return _parse_age_results(records)


def _parse_age_results(records: List[Dict[str, Any]]) -> WorkingGraph:
    """Parse AGE result rows into nodes and links.

    Replicates the parsing pattern from routes/queries.py (execute_cypher_query).
    Handles dict values (nodes/edges) and list values (paths).
    """
    nodes_map: Dict[str, RawNode] = {}
    links: List[RawLink] = []
    # Map AGE internal IDs to concept_ids for link endpoint translation
    age_id_to_concept_id: Dict[str, str] = {}

    for record in records:
        for _key, value in record.items():
            if isinstance(value, dict):
                _process_age_value(value, nodes_map, links, age_id_to_concept_id)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, dict):
                        _process_age_value(item, nodes_map, links, age_id_to_concept_id)

    # Translate link endpoints from AGE IDs to concept_ids
    resolved_links = _resolve_link_endpoints(links, age_id_to_concept_id)

    return WorkingGraph(
        nodes=list(nodes_map.values()),
        links=resolved_links,
    )


def _process_age_value(
    value: Dict[str, Any],
    nodes_map: Dict[str, RawNode],
    links: List[RawLink],
    age_id_to_concept_id: Dict[str, str],
) -> None:
    """Process a single AGE result value (node or relationship)."""
    # Check for relationship (has start_id/end_id)
    start_id = value.get('start_id') or value.get('start')
    end_id = value.get('end_id') or value.get('end')

    if start_id and end_id:
        rel_type = value.get('label', value.get('type', 'RELATED'))
        props = value.get('properties', {})
        links.append(RawLink(
            from_id=str(start_id),
            to_id=str(end_id),
            relationship_type=rel_type,
            category=props.get('category'),
            confidence=props.get('confidence'),
            properties={k: v for k, v in props.items()
                        if k not in ('category', 'confidence')},
        ))
    elif 'id' in value:
        # Node
        node_id = str(value['id'])
        if node_id not in nodes_map:
            props = value.get('properties', {})
            props.pop('embedding', None)
            concept_id = props.get('concept_id', node_id)
            label = props.get('label') or value.get('label', node_id)

            nodes_map[concept_id] = RawNode(
                concept_id=concept_id,
                label=label,
                ontology=props.get('ontology'),
                description=props.get('description'),
                properties={k: v for k, v in props.items()
                            if k not in ('concept_id', 'label', 'ontology',
                                         'description', 'embedding')},
            )
            age_id_to_concept_id[node_id] = concept_id


def _resolve_link_endpoints(
    links: List[RawLink],
    age_id_to_concept_id: Dict[str, str],
) -> List[RawLink]:
    """Translate AGE internal IDs in link endpoints to concept_ids.

    Discards links whose endpoints can't be resolved (dangling).
    """
    resolved = []
    for link in links:
        from_cid = age_id_to_concept_id.get(link.from_id)
        to_cid = age_id_to_concept_id.get(link.to_id)
        if from_cid is None or to_cid is None:
            continue  # discard dangling
        resolved.append(RawLink(
            from_id=from_cid,
            to_id=to_cid,
            relationship_type=link.relationship_type,
            category=link.category,
            confidence=link.confidence,
            properties=link.properties,
        ))
    return resolved


# ---------------------------------------------------------------------------
# ApiOp dispatch
# ---------------------------------------------------------------------------

_API_HANDLERS: Dict[str, Any] = {}  # populated below


def dispatch_api(ctx: DispatchContext, op: ApiOp) -> WorkingGraph:
    """Dispatch ApiOp to internal service function."""
    handler = _API_HANDLERS.get(op.endpoint)
    if handler is None:
        raise ValueError(f"Unknown API endpoint: {op.endpoint}")
    return handler(ctx, op.params)


def _dispatch_search_concepts(ctx: DispatchContext, params: Dict[str, Any]) -> WorkingGraph:
    """Vector search -> concept nodes."""
    embedding_result = ctx.provider.generate_embedding(params['query'], purpose="query")
    if isinstance(embedding_result, dict):
        embedding = embedding_result['embedding']
    else:
        embedding = embedding_result

    matches = ctx.client.vector_search(
        embedding,
        threshold=params.get('min_similarity', 0.7),
        top_k=params.get('limit', 10),
    )

    nodes = []
    for m in matches:
        if m.get('similarity', 0) < params.get('min_similarity', 0.7):
            continue
        nodes.append(RawNode(
            concept_id=m['concept_id'],
            label=m.get('label', ''),
            ontology=m.get('ontology'),
            description=m.get('description'),
        ))

    return WorkingGraph(nodes=nodes, links=[])


def _dispatch_search_sources(ctx: DispatchContext, params: Dict[str, Any]) -> WorkingGraph:
    """Source search -> concept nodes extracted from matched sources."""
    import numpy as np
    from api.app.routes.queries import _search_source_embeddings_by_similarity

    embedding_result = ctx.provider.generate_embedding(params['query'], purpose="query")
    if isinstance(embedding_result, dict):
        embedding = embedding_result['embedding']
    else:
        embedding = embedding_result

    query_embedding = np.array(embedding)
    source_matches = _search_source_embeddings_by_similarity(
        query_embedding=query_embedding,
        min_similarity=params.get('min_similarity', 0.7),
        limit=params.get('limit', 10),
    )

    if not source_matches:
        return WorkingGraph(nodes=[], links=[])

    # Fetch concepts linked to matched sources
    source_ids = list(source_matches.keys())
    concepts_by_source = ctx.client.graph.match_concepts_for_sources_batch(source_ids)

    # Deduplicate concepts across sources
    seen: Dict[str, RawNode] = {}
    for _source_id, concepts in concepts_by_source.items():
        for c in concepts:
            cid = c.get('concept_id', '')
            if cid and cid not in seen:
                seen[cid] = RawNode(
                    concept_id=cid,
                    label=c.get('label', ''),
                    ontology=c.get('ontology'),
                    description=c.get('description'),
                )

    return WorkingGraph(nodes=list(seen.values()), links=[])


def _dispatch_concepts_details(ctx: DispatchContext, params: Dict[str, Any]) -> WorkingGraph:
    """Concept detail -> single node + its relationships."""
    concept_id = params['concept_id']

    # Fetch concept node
    rows = ctx.client._execute_cypher(
        "MATCH (c:Concept {concept_id: $cid}) RETURN c",
        params={"cid": concept_id},
    )
    if not rows:
        return WorkingGraph(nodes=[], links=[])

    result = _parse_age_results(rows)

    # Fetch relationships
    rel_rows = ctx.client._execute_cypher(
        "MATCH (c:Concept {concept_id: $cid})-[r]->(t:Concept) "
        "RETURN c, r, t",
        params={"cid": concept_id},
    )
    if rel_rows:
        rel_result = _parse_age_results(rel_rows)
        # Merge into result
        existing_ids = {n.concept_id for n in result.nodes}
        for node in rel_result.nodes:
            if node.concept_id not in existing_ids:
                result.nodes.append(node)
                existing_ids.add(node.concept_id)
        result.links.extend(rel_result.links)

    return result


def _dispatch_concepts_related(ctx: DispatchContext, params: Dict[str, Any]) -> WorkingGraph:
    """Neighborhood exploration -> concept nodes."""
    results = ctx.client.graph.neighborhood(
        concept_id=params['concept_id'],
        max_depth=params.get('max_depth', 2),
        relationship_types=params.get('relationship_types'),
    )

    nodes = [
        RawNode(
            concept_id=r['concept_id'],
            label=r.get('label', ''),
        )
        for r in results
    ]
    return WorkingGraph(nodes=nodes, links=[])


def _dispatch_concepts_batch(ctx: DispatchContext, params: Dict[str, Any]) -> WorkingGraph:
    """Batch concept fetch -> concept nodes."""
    concept_ids = params['concept_ids']
    if not concept_ids:
        return WorkingGraph(nodes=[], links=[])

    rows = ctx.client._execute_cypher(
        "MATCH (c:Concept) WHERE c.concept_id IN $cids RETURN c",
        params={"cids": concept_ids},
    )
    return _parse_age_results(rows)


def _dispatch_vocabulary_status(ctx: DispatchContext, params: Dict[str, Any]) -> WorkingGraph:
    """Vocabulary epistemic status -> synthetic nodes."""
    where_clauses = []
    query_params: Dict[str, Any] = {}

    if params.get('status_filter'):
        where_clauses.append("v.epistemic_status = $status")
        query_params['status'] = params['status_filter']
    if params.get('relationship_type'):
        where_clauses.append("v.name = $name")
        query_params['name'] = params['relationship_type']

    where = " AND ".join(where_clauses) if where_clauses else None
    vocab_types = ctx.client.facade.match_vocab_types(
        where=where,
        params=query_params if query_params else None,
        limit=1000,
    )

    nodes = []
    for vt in vocab_types:
        v_props = vt.get('v', {}).get('properties', {})
        name = v_props.get('name', '')
        nodes.append(RawNode(
            concept_id=f"vocab:{name}",
            label=name,
            properties={
                'epistemic_status': v_props.get('epistemic_status'),
                'category': v_props.get('category'),
                'is_active': v_props.get('is_active'),
            },
        ))

    return WorkingGraph(nodes=nodes, links=[])


# Register handlers
_API_HANDLERS = {
    '/search/concepts': _dispatch_search_concepts,
    '/search/sources': _dispatch_search_sources,
    '/concepts/details': _dispatch_concepts_details,
    '/concepts/related': _dispatch_concepts_related,
    '/concepts/batch': _dispatch_concepts_batch,
    '/vocabulary/status': _dispatch_vocabulary_status,
}
