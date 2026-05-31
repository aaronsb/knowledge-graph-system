"""
Unit tests for global candidate-concept retrieval (#453).

The reasoner context is seeded with concepts most similar to the chunk (the
same global space the post-extraction merge uses), prioritised over the
ontology-adjacency seed and bounded by K. The embedding worker / DB boundary
is mocked (no network/DB).
"""

from unittest.mock import MagicMock, patch

from api.app.lib import ingestion as ing


class TestMergeContextConcepts:
    def test_candidates_come_first_then_existing(self):
        cand = [{"concept_id": "c1", "label": "A"}]
        existing = [{"concept_id": "e1", "label": "B"}]
        merged = ing._merge_context_concepts(cand, existing, limit=10)
        assert [m["concept_id"] for m in merged] == ["c1", "e1"]

    def test_dedup_by_concept_id_keeps_candidate(self):
        cand = [{"concept_id": "x", "label": "from-candidate"}]
        existing = [{"concept_id": "x", "label": "from-existing"},
                    {"concept_id": "y", "label": "Y"}]
        merged = ing._merge_context_concepts(cand, existing, limit=10)
        ids = [m["concept_id"] for m in merged]
        assert ids == ["x", "y"]
        assert merged[0]["label"] == "from-candidate"  # candidate wins the dup

    def test_bounded_by_limit(self):
        cand = [{"concept_id": f"c{i}", "label": str(i)} for i in range(50)]
        merged = ing._merge_context_concepts(cand, [], limit=30)
        assert len(merged) == 30

    def test_skips_entries_without_concept_id(self):
        merged = ing._merge_context_concepts(
            [{"label": "no-id"}], [{"concept_id": "ok", "label": "ok"}], limit=10)
        assert [m["concept_id"] for m in merged] == ["ok"]


class TestRetrieveCandidateConcepts:
    def test_maps_vector_search_results_to_id_label(self):
        client = MagicMock()
        client.vector_search.return_value = [
            {"concept_id": "c1", "label": "A", "description": "d", "similarity": 0.9},
            {"concept_id": "c2", "label": "B", "description": "d", "similarity": 0.7},
        ]
        worker = MagicMock()
        worker.generate_concept_embedding.return_value = {"embedding": [0.1, 0.2]}
        with patch.object(ing, "get_embedding_worker", return_value=worker):
            out = ing._retrieve_candidate_concepts(client, "some chunk", limit=5, threshold=0.5)
        assert out == [{"concept_id": "c1", "label": "A"},
                       {"concept_id": "c2", "label": "B"}]
        client.vector_search.assert_called_once_with(
            embedding=[0.1, 0.2], threshold=0.5, top_k=5)

    def test_returns_empty_when_worker_unavailable(self):
        with patch.object(ing, "get_embedding_worker", return_value=None):
            assert ing._retrieve_candidate_concepts(MagicMock(), "t") == []

    def test_degrades_to_empty_on_error(self):
        # Retrieval is an optimisation: any failure must not raise (would fail
        # the whole ingest), just yields no candidates.
        worker = MagicMock()
        worker.generate_concept_embedding.side_effect = Exception("embed down")
        with patch.object(ing, "get_embedding_worker", return_value=worker):
            assert ing._retrieve_candidate_concepts(MagicMock(), "t") == []
