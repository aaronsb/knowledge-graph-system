"""
Concept matching engine for restore integration mode (ADR-102 §2).

Succeeds the legacy ``api/lib/restitching.py`` ``ConceptMatcher`` as the
``api/app`` integration-mode engine. NOTE: this is not a line-for-line port —
the legacy matcher used a single 0.85 threshold; this module implements the
project's **canonical two-tier policy** (``api/app/lib/ingestion.py:432-461``),
which is what ADR-102 §2 specifies for integration mode. It is the *matching
engine only*: given an external concept (carrying an embedding, and optionally a
label) it finds the best-matching existing concept in the target graph by cosine
similarity. It performs no LLM calls, generates no embeddings, and is not wired
into any worker, route, or service — that wiring is Phase 4 of ADR-102.

The matching policy mirrors the canonical ingestion path
(``api/app/lib/ingestion.py``), with one deliberate refinement: ingestion
inspects only the top candidate, whereas this engine walks candidates best-first
so a label-boosted match just below a non-matching top hit is not missed:

- **Strict tier (>= 0.85):** any candidate at or above this cosine similarity is
  an unconditional match.
- **Label-boosted tier (>= 0.75):** a candidate in ``[0.75, 0.85)`` matches only
  when its label is equal to, or a substring containment of, the incoming
  concept's label (case-insensitive, whitespace-normalized).

Differences from the legacy version (see "Adaptation notes" in the ADR-102
Track C report):

- Uses the ``api/app`` :class:`~api.app.lib.age_client.AGEClient` and its
  :meth:`vector_search` rather than the legacy ``AGEConnection`` +
  hand-rolled full-scan loop.
- Does NOT generate embeddings from a label (the legacy code called
  ``conn.generate_embedding``). A concept with no embedding cannot be matched by
  similarity here; embedding rehydration is a separate ADR-102 §6 concern that
  must run before integration matching.
- Carries only the matching engine — the restitch-plan / execute-restitch /
  console-printing surface of the legacy class is intentionally omitted.
"""

import logging
from typing import Any, Dict, Optional

from api.app.lib.age_client import AGEClient

logger = logging.getLogger(__name__)

# Canonical two-tier matching thresholds (mirrors api/app/lib/ingestion.py).
STRICT_THRESHOLD = 0.85
LABEL_BOOST_THRESHOLD = 0.75


def _labels_match(incoming_label: Optional[str], candidate_label: Optional[str]) -> bool:
    """Decide whether two labels are similar enough to boost a borderline match.

    Normalizes both labels (lowercase, stripped) and returns True when they are
    identical or one contains the other — the same rule used by the canonical
    ingestion matcher's label-boost tier.

    Args:
        incoming_label: Label of the external/incoming concept (may be None).
        candidate_label: Label of the existing candidate concept (may be None).

    Returns:
        True if the labels are considered a match for boosting purposes.

    @verified 72ba3d3b
    """
    if not incoming_label or not candidate_label:
        return False
    norm_incoming = incoming_label.lower().strip()
    norm_candidate = candidate_label.lower().strip()
    if not norm_incoming or not norm_candidate:
        return False
    return (
        norm_incoming == norm_candidate
        or norm_incoming in norm_candidate
        or norm_candidate in norm_incoming
    )


class ConceptMatcher:
    """Match external concepts to existing target concepts by cosine similarity.

    This is the ADR-102 integration-mode matching engine. It wraps an
    :class:`~api.app.lib.age_client.AGEClient` and uses its ``vector_search``
    (cosine similarity over concept embeddings) to find the best existing
    concept for an incoming external concept, applying the project's canonical
    two-tier thresholds (strict 0.85 / label-boosted 0.75).

    The matcher is read-only with respect to the graph: it never writes,
    creates placeholders, or calls an LLM/embedding service. Concepts that do
    not meet the threshold return ``None`` (the caller's integration logic then
    falls through to adjacent-mode behaviour — out of scope here).

    Args:
        client: The ``api/app`` AGEClient used for Cypher / vector search.
        strict_threshold: Unconditional-match cosine threshold (default 0.85).
        label_boost_threshold: Lower threshold below which a label match is
            also required (default 0.75).

    @verified 72ba3d3b
    """

    def __init__(
        self,
        client: AGEClient,
        strict_threshold: float = STRICT_THRESHOLD,
        label_boost_threshold: float = LABEL_BOOST_THRESHOLD,
    ):
        """Initialize the matcher with an AGEClient and matching thresholds.

        Args:
            client: AGEClient for graph access (vector search).
            strict_threshold: Cosine similarity at/above which any candidate
                matches unconditionally.
            label_boost_threshold: Lower cosine similarity bound; candidates in
                ``[label_boost_threshold, strict_threshold)`` match only if
                their label matches the incoming label.

        Raises:
            ValueError: If thresholds are out of range or inverted.

        @verified 72ba3d3b
        """
        if not 0.0 <= label_boost_threshold <= strict_threshold <= 1.0:
            raise ValueError(
                "Thresholds must satisfy 0.0 <= label_boost_threshold "
                f"<= strict_threshold <= 1.0 (got label={label_boost_threshold}, "
                f"strict={strict_threshold})"
            )
        self.client = client
        self.strict_threshold = strict_threshold
        self.label_boost_threshold = label_boost_threshold

    def match_concept_in_database(
        self,
        external_concept: Dict[str, Any],
        top_k: int = 5,
    ) -> Optional[Dict[str, Any]]:
        """Find the best-matching existing concept for an external concept.

        Given an external concept dict carrying an ``embedding`` (and optionally
        a ``label``), search the target graph for the most similar existing
        concept above threshold using the canonical two-tier policy:

        1. Search candidates at the (lower) label-boost threshold via
           ``client.vector_search``.
        2. Walk candidates best-first; accept the first whose similarity is
           ``>= strict_threshold``, or whose similarity is
           ``>= label_boost_threshold`` *and* whose label matches the incoming
           concept's label.

        This method does not generate embeddings: a concept without an
        ``embedding`` key cannot be matched and returns ``None``. (Per ADR-102
        §6, embedding rehydration must run before integration matching.)

        Args:
            external_concept: Incoming concept metadata. Recognized keys:
                ``embedding`` (List[float], required for matching) and
                ``label`` (str, used for the label-boost tier).
            top_k: Maximum candidates to retrieve from the vector search.

        Returns:
            A dict ``{"concept_id", "label", "similarity"}`` for the best match,
            or ``None`` if no candidate meets the matching policy.

        @verified 72ba3d3b
        """
        embedding = external_concept.get("embedding")
        if not embedding:
            # No embedding → cannot perform similarity matching. Label-only
            # matching is intentionally unsupported (no embedding generation).
            label = external_concept.get("label")
            if label:
                logger.debug(
                    "ConceptMatcher: concept '%s' has no embedding; cannot "
                    "match by similarity (embedding rehydration required)",
                    label,
                )
            return None

        incoming_label = external_concept.get("label")

        # Retrieve candidates at the lower threshold so label-boosted matches
        # in [0.75, 0.85) are visible. vector_search returns results sorted by
        # similarity descending.
        try:
            candidates = self.client.vector_search(
                embedding=embedding,
                threshold=self.label_boost_threshold,
                top_k=top_k,
            )
        except Exception as e:
            logger.warning("ConceptMatcher: vector search failed: %s", e)
            return None

        if not candidates:
            return None

        for candidate in candidates:
            similarity = candidate["similarity"]
            candidate_label = candidate.get("label")

            if similarity >= self.strict_threshold:
                matched = True
            elif similarity >= self.label_boost_threshold and _labels_match(
                incoming_label, candidate_label
            ):
                matched = True
                logger.info(
                    "ConceptMatcher: label-boosted match '%s' -> '%s' at %.1f%%",
                    incoming_label,
                    candidate_label,
                    similarity * 100,
                )
            else:
                matched = False

            if matched:
                return {
                    "concept_id": candidate["concept_id"],
                    "label": candidate_label,
                    "similarity": similarity,
                }

        return None


__all__ = ["ConceptMatcher", "STRICT_THRESHOLD", "LABEL_BOOST_THRESHOLD"]
