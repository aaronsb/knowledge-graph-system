"""
Unit tests for concept-details relationships in both directions (#587)
and the shared ontology-membership predicate (#595 finding 6).

The AGE client is faked: it answers the outgoing and incoming edge queries
from fixed rows, so these tests pin how rows become ConceptRelationships,
not the Cypher engine.
"""

from api.app.lib.age_client.ontology import concept_in_ontology
from api.app.routes.queries import _fetch_concept_relationships


def _row(related_id, related_label, rel_type, **props):
    return {
        "related_id": related_id,
        "related_label": related_label,
        "rel_type": rel_type,
        "props": props,
        "vocab_category": "evidential",
        "vocab_epistemic_status": "WEAK_GROUNDING",
        "vocab_epistemic_stats": {"avg_grounding": 0.05},
    }


class FakeClient:
    """Returns outgoing rows for '(c...)-[r]->(related...)' and incoming rows
    for '(related...)-[r]->(c...)', recording the queries it saw."""

    def __init__(self, outgoing, incoming):
        self.outgoing, self.incoming, self.queries = outgoing, incoming, []

    def _execute_cypher(self, query, params=None, fetch_one=False):
        self.queries.append(query)
        assert params == {"cid": "c_target"}
        if "(related:Concept)-[r]->(c:Concept" in query:
            return self.incoming
        return self.outgoing


def test_incoming_edges_name_their_source_concept_and_provenance():
    client = FakeClient(
        outgoing=[_row("c_conflict", "Human-AI Conflict", "CAUSES", confidence=0.9, source="llm_extraction")],
        incoming=[_row("c_revised", "Revised transparency claim", "CRITIQUES",
                       confidence=0.6, source="api_creation", created_by=7)],
    )

    outgoing, incoming = _fetch_concept_relationships(client, "c_target", "Concealment")

    assert [(r.to_id, r.to_label, r.rel_type) for r in outgoing] == [("c_conflict", "Human-AI Conflict", "CAUSES")]
    assert outgoing[0].from_id is None

    (edge,) = incoming
    assert (edge.from_id, edge.from_label) == ("c_revised", "Revised transparency claim")
    assert (edge.to_id, edge.to_label) == ("c_target", "Concealment")
    assert (edge.rel_type, edge.confidence, edge.source) == ("CRITIQUES", 0.6, "api_creation")
    assert edge.created_by == "7"
    assert (edge.category, edge.avg_grounding, edge.epistemic_status) == ("evidential", 0.05, "WEAK_GROUNDING")


def test_incoming_query_excludes_self_loops_and_outgoing_does_not():
    client = FakeClient(outgoing=[], incoming=[])
    _fetch_concept_relationships(client, "c_target", "Concealment")

    outgoing_query, incoming_query = client.queries
    assert "related.concept_id <> c.concept_id" in incoming_query
    assert "related.concept_id <> c.concept_id" not in outgoing_query


def test_unlabeled_concept_falls_back_to_its_id():
    client = FakeClient(outgoing=[], incoming=[_row("c_other", "Other", "SUPPORTS")])
    _, (edge,) = _fetch_concept_relationships(client, "c_target", None)
    assert edge.to_label == "c_target"


def test_membership_predicate_covers_both_membership_models():
    assert concept_in_ontology("c", "$ontology") == (
        "(c.ontology = $ontology OR "
        "EXISTS((c)-[:APPEARS]->(:Source)-[:SCOPED_BY]->(:Ontology {name: $ontology})))"
    )
    assert concept_in_ontology("t", "'ai-moats'") == (
        "(t.ontology = 'ai-moats' OR "
        "EXISTS((t)-[:APPEARS]->(:Source)-[:SCOPED_BY]->(:Ontology {name: 'ai-moats'})))"
    )
