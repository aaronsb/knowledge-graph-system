"""
Apache AGE client for knowledge graph operations.

AGEClient composes domain-specific mixins into a single class that
provides the full graph database API. This package structure enables:

1. Domain organization: Methods grouped by concern (ingestion, query,
   ontology, vocabulary) rather than one monolithic file.

2. Future acceleration: Individual mixins can be enhanced with
   graph_accel support (ADR-201) without touching unrelated domains.

Import interface is unchanged:
    from api.app.lib.age_client import AGEClient
"""

from .base import BaseMixin
from .ingestion import IngestionMixin
from .query import QueryMixin
from .grounding import GroundingMixin
from .ontology import OntologyMixin
from .ontology_scoring import OntologyScoringMixin
from .ontology_edges import OntologyEdgesMixin
from .rehydration import RehydrationMixin
from .vocabulary import VocabularyMixin


class AGEClient(
    VocabularyMixin,
    RehydrationMixin,
    OntologyEdgesMixin,
    OntologyScoringMixin,
    OntologyMixin,
    GroundingMixin,
    QueryMixin,
    IngestionMixin,
    BaseMixin,
):
    """Client for interacting with Apache AGE knowledge graph database.

    Composed from domain mixins:
    - BaseMixin: Connection pool, Cypher execution, AGE type parsing
    - IngestionMixin: Source/Concept/Instance CRUD, graph linking, document metadata
    - QueryMixin: Vector search, learned knowledge, query/graph/epoch facades
    - GroundingMixin: Polarity axis caching + grounding strength calculation (ADR-044)
    - OntologyMixin: Ontology node CRUD and lifecycle management
    - OntologyScoringMixin: Ontology scoring, analytics, and annealing mutations
    - OntologyEdgesMixin: Inter-ontology edges and proposal execution primitives
    - RehydrationMixin: Rebuild derived :Ontology/:DocumentMeta layers from Sources (issue #505)
    - VocabularyMixin: Relationship type config, CRUD, sync, merge, embeddings

    Facades attached lazily via properties on QueryMixin:
    - client.graph   → GraphFacade (topology + graph_accel)
    - client.epochs  → EpochFacade (ADR-203 epoch event log read-side)
    """
    pass


__all__ = ["AGEClient"]
