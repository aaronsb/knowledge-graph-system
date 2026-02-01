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
from .ontology import OntologyMixin
from .ontology_scoring import OntologyScoringMixin
from .ontology_edges import OntologyEdgesMixin
from .vocabulary import VocabularyMixin


class AGEClient(
    VocabularyMixin,
    OntologyEdgesMixin,
    OntologyScoringMixin,
    OntologyMixin,
    QueryMixin,
    IngestionMixin,
    BaseMixin,
):
    """Client for interacting with Apache AGE knowledge graph database.

    Composed from domain mixins:
    - BaseMixin: Connection pool, Cypher execution, AGE type parsing
    - IngestionMixin: Source/Concept/Instance CRUD, graph linking, document metadata
    - QueryMixin: Vector search, learned knowledge, grounding strength, query facade
    - OntologyMixin: Ontology node CRUD and lifecycle management
    - OntologyScoringMixin: Ontology scoring, analytics, and annealing mutations
    - OntologyEdgesMixin: Inter-ontology edges and proposal execution primitives
    - VocabularyMixin: Relationship type config, CRUD, sync, merge, embeddings
    """
    pass


__all__ = ["AGEClient"]
