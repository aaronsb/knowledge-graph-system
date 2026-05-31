"""
Grounding strength + cache mixin (ADR-044, ADR-201 Phase 5f).

The grounding cluster is what turns each concept's incoming edges into a
single probabilistic-truth score (ADR-044): we project edge embeddings
onto a polarity axis derived from opposing vocabulary pairs
(SUPPORTS/CONTRADICTS, etc.). Pre-#278 this lived inside query.py
alongside vector search and learned-knowledge CRUD, growing the file past
1100 lines with no internal cohesion — the grounding code has no
dependency on the rest of QueryMixin, and the rest of QueryMixin has no
dependency on it. Splitting at this seam keeps each file under the
project's review threshold and lets future grounding changes land
without touching unrelated query paths.

## Two-tier cache (ADR-201 Phase 5f)

Tier 1 — Polarity axis: derived from vocabulary embeddings, shared
across all concepts. Invalidates when
vocabulary_embedding_generation_counter changes — bumped by any path
that updates the `embedding` column on relationship_vocabulary rows
(batch generation, add_edge_type inline path, regen). One axis
computation replaces N identical DB queries.

Tier 2 — Per-concept grounding: cached against graph generation. Each
concept's grounding depends only on its own incoming edges (no
cross-concept dependency), making independent caching safe. Invalidates
when graph_accel_invalidate() bumps the generation after ingestion,
edits, or vocabulary merges.

Analogy: like global-illumination probe caching in real-time rendering
— only recompute when the "frame" (generation) changes, and each "probe"
(concept) is independent.
"""

import json
import logging
import threading
from collections import defaultdict
from typing import List, Dict, Optional, Any, Tuple

import numpy as np
from psycopg2 import extras

from api.app.constants import BATCH_CHUNK_SIZE
from api.app.lib.freshness import (
    Budget,
    CollectionDerivation,
    read_committed_epoch,
    register_derivation,
)

logger = logging.getLogger(__name__)


# ---- Cache module-globals ----
#
# These intentionally live at module scope so they survive across
# AGEClient instances. Multiple FastAPI worker processes each get their
# own copy (no shared memory) — invalidation rides on the graph
# generation counter, which is shared via the database, so process-local
# caches stay coherent automatically.

_polarity_axis_cache_lock = threading.Lock()
_polarity_axis_cache: Optional[Tuple[int, np.ndarray]] = None  # (vocab_generation, axis_vector)

_grounding_cache_lock = threading.Lock()
_grounding_cache: Dict[Tuple[str, int], float] = {}  # (concept_id, graph_gen) → grounding_strength
_grounding_cache_generation: Optional[int] = None  # tracks which graph generation the cache covers


def _parse_embedding(emb_json) -> Optional[np.ndarray]:
    """Parse embedding from various storage formats (JSONB, list, str)."""
    if isinstance(emb_json, str):
        return np.array(json.loads(emb_json), dtype=float)
    elif isinstance(emb_json, list):
        return np.array(emb_json, dtype=float)
    elif isinstance(emb_json, dict):
        return np.array(list(emb_json.values()), dtype=float)
    else:
        try:
            return np.array(list(emb_json), dtype=float)
        except Exception:
            return None


def _parse_confidence(value) -> float:
    """Parse edge confidence from AGE result (may be float, str, dict, or None)."""
    if value is None:
        return 1.0
    if isinstance(value, dict):
        return float(value.get('confidence', 1.0))
    return float(value)


class GroundingMixin:
    """
    Grounding strength calculation + two-tier caching.

    Expects from sibling mixins / base:
    - self.pool (BaseMixin) — psycopg2 ThreadedConnectionPool
    - self.graph_name (BaseMixin) — AGE graph name
    - self._execute_cypher (BaseMixin) — Cypher executor
    """

    def _get_vocab_embedding_generation(self, cur) -> int:
        """Read vocabulary_embedding_generation_counter from graph_metrics.

        Migration 069 introduced this counter as the polarity-axis cache key.
        Distinct from vocabulary_change_counter: that one tracks row
        membership (add/remove/categorize), this one tracks embedding
        contents. The polarity axis is built from embedding vectors, so
        it's the embedding-generation counter that should drive
        invalidation — not membership.
        """
        try:
            cur.execute(
                "SELECT counter FROM graph_metrics "
                "WHERE metric_name = 'vocabulary_embedding_generation_counter'"
            )
            row = cur.fetchone()
            return int(row['counter']) if row else 0
        except Exception:
            return 0

    def _get_polarity_axis(self, cur) -> Optional[np.ndarray]:
        """Get cached polarity axis, recomputing if vocab embeddings changed.

        The polarity axis is derived from vocabulary embeddings for opposing
        relationship pairs (SUPPORTS/CONTRADICTS, etc.). It's shared across
        all concepts — only the per-concept edge projections differ.

        Cached against graph_metrics.vocabulary_embedding_generation_counter
        (migration 069). Invalidates when embeddings are generated or
        regenerated — including via `kg admin embedding regenerate` and
        the inline path in age_client/vocabulary.py:add_edge_type. The
        previous key (vocabulary_change_counter, membership) didn't move
        on embedding-content changes, requiring a process restart to
        invalidate after `kg admin embedding regenerate --type vocabulary`.
        """
        global _polarity_axis_cache

        vocab_gen = self._get_vocab_embedding_generation(cur)

        with _polarity_axis_cache_lock:
            if _polarity_axis_cache is not None:
                cached_gen, cached_axis = _polarity_axis_cache
                if cached_gen == vocab_gen:
                    return cached_axis

        # Cache miss — recompute from vocabulary embeddings
        POLARITY_PAIRS = [
            ("SUPPORTS", "CONTRADICTS"),
            ("VALIDATES", "REFUTES"),
            ("CONFIRMS", "DISPROVES"),
            ("REINFORCES", "OPPOSES"),
            ("ENABLES", "PREVENTS"),
        ]

        all_pair_terms = set()
        for positive, negative in POLARITY_PAIRS:
            all_pair_terms.add(positive)
            all_pair_terms.add(negative)

        terms_list = ','.join([f"'{t}'" for t in all_pair_terms])
        cur.execute(f"""
            SELECT relationship_type, embedding
            FROM kg_api.relationship_vocabulary
            WHERE relationship_type IN ({terms_list})
              AND embedding IS NOT NULL
        """)

        pair_embeddings = {}
        for row in cur.fetchall():
            emb_array = _parse_embedding(row['embedding'])
            if emb_array is not None:
                pair_embeddings[row['relationship_type']] = emb_array

        difference_vectors = []
        for positive, negative in POLARITY_PAIRS:
            if positive in pair_embeddings and negative in pair_embeddings:
                difference_vectors.append(
                    pair_embeddings[positive] - pair_embeddings[negative]
                )

        if not difference_vectors:
            logger.warning("No polarity pairs available for axis calculation (need embeddings)")
            return None

        polarity_axis = np.mean(difference_vectors, axis=0)
        axis_magnitude = np.linalg.norm(polarity_axis)
        if axis_magnitude == 0:
            logger.warning("Polarity axis has zero magnitude")
            return None

        polarity_axis = polarity_axis / axis_magnitude
        logger.info(
            f"Polarity axis computed from {len(difference_vectors)} pairs "
            f"(vocab generation {vocab_gen})"
        )

        with _polarity_axis_cache_lock:
            _polarity_axis_cache = (vocab_gen, polarity_axis)

        return polarity_axis

    def calculate_grounding_strength_semantic(
        self,
        concept_id: str,
        include_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None
    ) -> float:
        """
        Calculate grounding strength using polarity axis projection (ADR-044).
        @verified 53b820d5

        Computes one number per concept that says how much its incoming
        edges lean toward support-like vs contradict-like semantics. The
        polarity axis is built from opposing relationship-type pairs
        (SUPPORTS/CONTRADICTS, ENABLES/PREVENTS, etc.); each edge's
        embedding is dot-product-projected onto this axis, confidence-
        weighted, and averaged.

        ## Two-tier cache (ADR-201 Phase 5f)

        Tier 1 — Polarity axis (vocabulary-level): derived from
        relationship-type embeddings, shared across every concept. Cached
        against graph_metrics.vocabulary_embedding_generation_counter
        (migration 069). Invalidates only when embeddings are generated
        or regenerated — including regen via `kg admin embedding regenerate`.
        One axis computation amortizes across the entire concept space.

        Tier 2 — Per-concept grounding: cached against
        graph_accel.generation. A concept's grounding depends only on its
        own incoming edges (no cross-concept coupling), so per-key caching
        is sound. The whole tier-2 cache is wiped when the generation
        bumps — every concept potentially has new edges so we don't try to
        be clever about which entries survive.

        Warm-cache short-circuit (#278): if `_grounding_cache_generation`
        is set and `(concept_id, _grounding_cache_generation)` is already
        in the cache, this method returns without acquiring a pool
        connection. Soundness: the warm path never re-reads the generation,
        so the staleness window is bounded by the next cold-path call in
        this process — not by wall-clock time. A workload that repeatedly
        hits the same hot concepts can keep serving cached values from
        before a graph mutation until something else takes the cold path
        and re-reads the generation. This is the intended trade-off for
        read-heavy steady-state workloads; callers that need linearizable
        freshness should call `include_grounding=False` to bypass the
        cache entirely, or rely on cache eviction triggered by other
        endpoint hits.

        Args:
            concept_id: Target concept to calculate grounding for.
            include_types: Optional whitelist of relationship types to
                consider in the projection. Cached values include all
                types; filtering happens during projection.
            exclude_types: Optional blacklist of relationship types.

        Returns:
            Grounding strength float in approximately [-1.0, 1.0]:
            - Positive = Edge types align with support-like semantics
            - Zero = Edge types are neutral, balanced, or absent
            - Negative = Edge types align with contradict-like semantics

            On any DB error during cold-path computation, returns 0.0
            and logs the failure — callers cannot distinguish "computed
            as 0.0" from "failed and defaulted." See calculate_grounding_strength_batch's
            #281 chunk-recovery comment for the same trade-off at scale.

        References:
            - ADR-044: Probabilistic Truth Convergence
            - ADR-045: Unified Embedding Generation
        """
        global _grounding_cache, _grounding_cache_generation

        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                # ---- Tier 2 cache check: per-concept grounding ----
                # ADR-207 D2: read the canonical freshness clock (the committed-
                # epoch tick) on EVERY call. The previous connection-free warm-
                # path short-circuit skipped this re-read, leaving staleness
                # unbounded in wall-clock time (#422). The cache still saves the
                # expensive edge fetch + projection — it just no longer skips the
                # clock read. graph_gen here is the universal tick, not
                # graph_accel.generation (which co-advances with it as a
                # sub-counter, ADR-207 D1).
                graph_gen = read_committed_epoch(cur)

                # Evict entire cache if graph generation changed
                with _grounding_cache_lock:
                    if _grounding_cache_generation != graph_gen:
                        if _grounding_cache:
                            logger.info(
                                f"Grounding cache invalidated: generation "
                                f"{_grounding_cache_generation} → {graph_gen} "
                                f"({len(_grounding_cache)} entries evicted)"
                            )
                        _grounding_cache.clear()
                        _grounding_cache_generation = graph_gen

                    cache_key = (concept_id, graph_gen)
                    if cache_key in _grounding_cache:
                        return _grounding_cache[cache_key]

                # ---- Tier 1: get or compute polarity axis ----
                polarity_axis = self._get_polarity_axis(cur)
                if polarity_axis is None:
                    return 0.0

                # ---- Per-concept: fetch incoming edges ----
                cypher_edges_query = f"""
                    MATCH (c:Concept {{concept_id: '{concept_id}'}})<-[r]-(source)
                    RETURN type(r) as rel_type, r.confidence as confidence
                """
                edge_results = self._execute_cypher(cypher_edges_query)

                if not edge_results:
                    with _grounding_cache_lock:
                        _grounding_cache[cache_key] = 0.0
                    return 0.0

                # Filter relationship types
                rel_types = set(edge['rel_type'] for edge in edge_results)
                if include_types:
                    rel_types = rel_types & set(include_types)
                if exclude_types:
                    rel_types = rel_types - set(exclude_types)
                if not rel_types:
                    with _grounding_cache_lock:
                        _grounding_cache[cache_key] = 0.0
                    return 0.0

                # Fetch vocabulary embeddings for these edge types
                types_list = ','.join([f"'{t}'" for t in rel_types])
                cur.execute(f"""
                    SELECT relationship_type, embedding
                    FROM kg_api.relationship_vocabulary
                    WHERE relationship_type IN ({types_list})
                      AND embedding IS NOT NULL
                """)
                vocab_embeddings = {
                    row['relationship_type']: row['embedding']
                    for row in cur.fetchall()
                }

                # Project each edge onto polarity axis
                total_polarity = 0.0
                total_confidence = 0.0
                edge_count = 0

                for edge in edge_results:
                    rel_type = edge['rel_type']
                    if rel_type not in vocab_embeddings:
                        continue

                    edge_emb = _parse_embedding(vocab_embeddings[rel_type])
                    if edge_emb is None:
                        continue

                    confidence = _parse_confidence(edge.get('confidence'))
                    polarity_projection = np.dot(edge_emb, polarity_axis)
                    total_polarity += confidence * float(polarity_projection)
                    total_confidence += confidence
                    edge_count += 1

                if total_confidence == 0:
                    with _grounding_cache_lock:
                        _grounding_cache[cache_key] = 0.0
                    return 0.0

                grounding_strength = float(total_polarity / total_confidence)
                logger.debug(
                    f"Grounding for {concept_id}: {grounding_strength:.3f} "
                    f"(from {edge_count} edges)"
                )

                with _grounding_cache_lock:
                    _grounding_cache[cache_key] = grounding_strength

                return grounding_strength

        except Exception as e:
            logger.error(f"Error calculating grounding strength for {concept_id}: {e}")
            return 0.0
        finally:
            self.pool.putconn(conn)

    def calculate_grounding_strength_batch(
        self,
        concept_ids: List[str],
        include_types: Optional[List[str]] = None,
        exclude_types: Optional[List[str]] = None
    ) -> Dict[str, float]:
        """
        Batch-compute grounding strength for multiple concepts (ADR-201 Phase 5f).

        Amortized version of calculate_grounding_strength_semantic(). On cache
        miss, replaces 2N DB round-trips (N Cypher edge queries + N SQL vocab
        queries) with 2 queries per chunk of BATCH_CHUNK_SIZE concepts:
          1. One batch Cypher: incoming edges for chunk concepts
          2. One SQL: vocabulary embeddings for all unique relationship types

        The per-concept computation (dot product against polarity axis) then
        runs in pure Python with no further DB access.

        Cache interaction:
            Uses the same _grounding_cache global as the per-concept method.
            For each concept_id: if (concept_id, graph_gen) is in cache, the
            cached value is used (no DB hit). Only cache misses trigger the
            batch queries. Each computed result is written back to the cache,
            so subsequent per-concept calls for any concept in this batch
            will return instantly from cache.

        Connection management:
            Misses are processed in chunks of BATCH_CHUNK_SIZE. Each chunk
            gets its own pool connection, runs 2 queries, and returns it.
            This keeps IN-clause lists small for AGE's query planner and
            releases connections between chunks so concurrent requests
            aren't starved.

        Args:
            concept_ids: Concept IDs to compute grounding for.
            include_types: Optional whitelist of relationship types.
            exclude_types: Optional blacklist of relationship types.

        Returns:
            Dict mapping concept_id -> grounding_strength float.
            Missing or failed concepts default to 0.0.
        """
        global _grounding_cache, _grounding_cache_generation

        if not concept_ids:
            return {}

        result = {cid: 0.0 for cid in concept_ids}

        # --- Cache check + polarity axis (one connection) ---
        # ADR-207 D2: read the canonical freshness clock on EVERY call. An
        # earlier connection-free "Phase 0" warm-cache short-circuit served the
        # whole batch from cache WITHOUT re-reading the generation, leaving
        # staleness unbounded in wall-clock time (#422). The single clock read +
        # connection per batch is cheap and amortizes across all concept_ids; the
        # cache still saves the expensive per-concept edge fetch + projection.
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                graph_gen = read_committed_epoch(cur)

                misses = []
                with _grounding_cache_lock:
                    if _grounding_cache_generation != graph_gen:
                        if _grounding_cache:
                            logger.info(
                                f"Grounding cache invalidated: generation "
                                f"{_grounding_cache_generation} → {graph_gen} "
                                f"({len(_grounding_cache)} entries evicted)"
                            )
                        _grounding_cache.clear()
                        _grounding_cache_generation = graph_gen

                    for cid in concept_ids:
                        cache_key = (cid, graph_gen)
                        if cache_key in _grounding_cache:
                            result[cid] = _grounding_cache[cache_key]
                        else:
                            misses.append(cid)

                if not misses:
                    logger.debug(
                        f"Grounding batch: all {len(concept_ids)} concepts "
                        f"served from cache"
                    )
                    return result

                polarity_axis = self._get_polarity_axis(cur)
                if polarity_axis is None:
                    with _grounding_cache_lock:
                        for cid in misses:
                            _grounding_cache[(cid, graph_gen)] = 0.0
                    return result
        finally:
            self.pool.putconn(conn)

        # --- Phase 2: process misses in chunks ---
        # Each chunk gets its own connection, keeping IN-clause lists
        # small and releasing connections between chunks. Per-chunk failures
        # are logged and isolated (#281): the failing chunk's concepts default
        # to 0.0 in the result (matching per-concept failure behavior at
        # calculate_grounding_strength_semantic line 772), but earlier and
        # later chunks' computed results survive and are cached.
        total_edges = 0
        failed_chunks: List[List[str]] = []
        for i in range(0, len(misses), BATCH_CHUNK_SIZE):
            chunk = misses[i:i + BATCH_CHUNK_SIZE]
            conn = self.pool.getconn()
            try:
                with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                    # Batch Cypher: incoming edges for this chunk
                    ids_str = ','.join([f"'{cid}'" for cid in chunk])
                    batch_edges_sql = f"""
                        SELECT * FROM ag_catalog.cypher(
                            '{self.graph_name}', $$
                            MATCH (c:Concept)<-[r]-(source)
                            WHERE c.concept_id IN [{ids_str}]
                            RETURN c.concept_id as concept_id,
                                   type(r) as rel_type,
                                   r.confidence as confidence
                        $$) AS (concept_id agtype, rel_type agtype,
                                confidence agtype)
                    """
                    cur.execute(batch_edges_sql)
                    chunk_edges = cur.fetchall()
                    total_edges += len(chunk_edges)

                    # Group edges by concept, collect unique rel types
                    edges_by_concept = defaultdict(list)
                    rel_types_needed = set()
                    for row in chunk_edges:
                        cid = str(row['concept_id']).strip('"')
                        rel_type = str(row['rel_type']).strip('"')
                        conf_str = (
                            str(row['confidence'])
                            if row['confidence'] else "1.0"
                        )
                        try:
                            confidence = float(conf_str.strip('"'))
                        except (ValueError, AttributeError):
                            confidence = 1.0
                        edges_by_concept[cid].append({
                            'rel_type': rel_type,
                            'confidence': confidence
                        })
                        rel_types_needed.add(rel_type)

                    # Apply type filters
                    if include_types:
                        rel_types_needed &= set(include_types)
                    if exclude_types:
                        rel_types_needed -= set(exclude_types)

                    # Batch SQL: vocabulary embeddings for this chunk's
                    # rel types
                    vocab_embeddings = {}
                    if rel_types_needed:
                        types_list = ','.join(
                            [f"'{t}'" for t in rel_types_needed]
                        )
                        cur.execute(f"""
                            SELECT relationship_type, embedding
                            FROM kg_api.relationship_vocabulary
                            WHERE relationship_type IN ({types_list})
                              AND embedding IS NOT NULL
                        """)
                        vocab_embeddings = {
                            row['relationship_type']: _parse_embedding(
                                row['embedding']
                            )
                            for row in cur.fetchall()
                        }
                        vocab_embeddings = {
                            k: v for k, v in vocab_embeddings.items()
                            if v is not None
                        }

                    # Per-concept dot products (pure CPU, no DB)
                    for cid in chunk:
                        edges = edges_by_concept.get(cid, [])
                        if not edges:
                            grounding = 0.0
                        else:
                            total_polarity = 0.0
                            total_confidence = 0.0
                            for edge in edges:
                                rel_type = edge['rel_type']
                                if (include_types
                                        and rel_type not in include_types):
                                    continue
                                if (exclude_types
                                        and rel_type in exclude_types):
                                    continue
                                emb = vocab_embeddings.get(rel_type)
                                if emb is None:
                                    continue
                                confidence = edge['confidence']
                                proj = np.dot(emb, polarity_axis)
                                total_polarity += confidence * float(proj)
                                total_confidence += confidence

                            grounding = (
                                float(total_polarity / total_confidence)
                                if total_confidence > 0
                                else 0.0
                            )

                        result[cid] = grounding
                        with _grounding_cache_lock:
                            _grounding_cache[(cid, graph_gen)] = grounding

            except Exception as e:
                # ADR-201 Phase 5f #281: per-chunk failure isolation.
                # Earlier chunks already wrote their results to _grounding_cache
                # and the result dict above, so they survive this chunk's
                # failure. The failing chunk's concept_ids stay at their
                # initial 0.0 default — same value the per-concept method
                # returns on error, so callers can't tell the difference
                # between "computed as 0.0" and "failed and defaulted."
                # Concept IDs are logged so operators can dig into transient
                # batch failures without losing the whole response.
                logger.warning(
                    f"Batch grounding chunk failed ({len(chunk)} concepts "
                    f"affected, defaulting to 0.0): {e}. "
                    f"Failed concept_ids: {chunk}"
                )
                failed_chunks.append(chunk)
            finally:
                self.pool.putconn(conn)

        successful_chunks = (
            (len(misses) + BATCH_CHUNK_SIZE - 1) // BATCH_CHUNK_SIZE
            - len(failed_chunks)
        )
        logger.debug(
            f"Grounding batch: {len(concept_ids)} concepts, "
            f"{len(concept_ids) - len(misses)} cached, "
            f"{len(misses)} computed in {successful_chunks} chunks "
            f"({len(failed_chunks)} chunks failed, {total_edges} edges total)"
        )

        return result


# ---------------------------------------------------------------------------
# ADR-207 freshness-contract registration
#
# The grounding cluster is TWO derivations on two different clocks (ADR-207 D3),
# so they register separately rather than being forced behind one interface. The
# on-read detection and cache live in GroundingMixin above; these objects expose
# each tier to the freshness registry — for the conformance test (CI catches a
# tier that forgets the contract) and the operator surface (list / show
# freshness / reconcile). Each is constructed with an AGEClient for its clock
# read; the cache state itself is process-global (above).
# ---------------------------------------------------------------------------


@register_derivation
class GroundingCacheDerivation(CollectionDerivation):
    """Tier 2 — per-concept grounding cache (ADR-207 CollectionDerivation).

    Whole-tier stamp: one generation covers every cached concept, and reconcile
    clears the lot (a graph mutation may have changed any concept's edges). Its
    clock is the **universal committed-epoch tick** — #386 makes that advance for
    every mutation kind, so the tier invalidates on ingestion, edits, and
    annealing alike. graph_accel.generation co-advances with the tick as a
    sub-counter (ADR-207 D1); this derivation reads the tick, not the sub-counter.
    """

    name = "grounding_cache"
    budget = Budget.strict()

    def __init__(self, client):
        """Store the AGE client for the clock read; cache state is module-global."""
        self.client = client

    def version_stamp(self):
        """The committed-epoch tick the cache was last filled at (None if cold)."""
        return _grounding_cache_generation

    def current_version(self) -> int:
        """The canonical clock now: the committed-epoch tick."""
        conn = self.client.pool.getconn()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                v = read_committed_epoch(cur)
            conn.rollback()
            return v
        finally:
            self.client.pool.putconn(conn)

    def reconcile(self) -> None:
        """Invalidate the whole tier; it refills lazily on the next read."""
        global _grounding_cache, _grounding_cache_generation
        with _grounding_cache_lock:
            _grounding_cache.clear()
            _grounding_cache_generation = None


@register_derivation
class PolarityAxisDerivation(CollectionDerivation):
    """Tier 1 — polarity-axis cache (ADR-207 CollectionDerivation).

    Distinct clock from the graph tick: the axis is derived from VOCABULARY
    embeddings, so its source-of-truth is `vocabulary_embedding_generation_counter`
    (migration 069) — a declared sub-counter that changes only on embedding
    (re)generation, far more rarely than the graph. Tracking the graph tick here
    would needlessly recompute the axis on every concept edit.
    """

    name = "polarity_axis"
    budget = Budget.strict()

    def __init__(self, client):
        """Store the AGE client for the clock read; cache state is module-global."""
        self.client = client

    def version_stamp(self):
        """The vocab-embedding generation the axis was built at (None if cold)."""
        cached = _polarity_axis_cache
        return cached[0] if cached is not None else None

    def current_version(self) -> int:
        """The polarity axis's clock: vocabulary_embedding_generation_counter."""
        conn = self.client.pool.getconn()
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT counter FROM graph_metrics "
                    "WHERE metric_name = 'vocabulary_embedding_generation_counter'"
                )
                row = cur.fetchone()
                v = int(row["counter"]) if row else 0
            conn.rollback()
            return v
        finally:
            self.client.pool.putconn(conn)

    def reconcile(self) -> None:
        """Invalidate the axis; it recomputes lazily on the next grounding call."""
        global _polarity_axis_cache
        with _polarity_axis_cache_lock:
            _polarity_axis_cache = None
