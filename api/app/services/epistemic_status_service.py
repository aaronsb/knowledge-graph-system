"""
Epistemic Status Service

Measures epistemic status for vocabulary types by sampling edges and calculating
grounding dynamically (ADR-065 Phase 2).

Philosophy (Bounded Locality + Satisficing):
- Grounding is calculated at query time with limited recursion depth
- Perfect knowledge requires infinite computation (Gödel incompleteness)
- We satisfice: sample edges, calculate bounded grounding, estimate patterns
- Each run is a "measurement" - results are temporal, observer-dependent

Epistemic Status Classifications (Grounding-Based):
- WELL_GROUNDED: Consistently high grounding (avg > 0.8) - well-established
- MIXED_GROUNDING: Mixed grounding (0.15 <= avg <= 0.8) - variable validation
- WEAK_GROUNDING: Weak positive grounding (0.0 < avg < 0.15) - emerging evidence
- POORLY_GROUNDED: Weak negative grounding (-0.5 <= avg <= 0.0) - uncertain
- CONTRADICTED: Strong negative grounding (avg < -0.5) - refuted
- HISTORICAL: Explicitly temporal vocabulary (detected by name)
- INSUFFICIENT_DATA: < 3 successful measurements
"""

import logging
import random
from datetime import datetime
from statistics import mean, stdev
from typing import Dict, List, Tuple, Optional

from api.app.lib.age_client import AGEClient
from api.app.services.vocabulary_metrics_service import VocabularyMetricsService

logger = logging.getLogger(__name__)


class EpistemicStatusService:
    """Service for measuring and classifying epistemic status of vocabulary types"""

    def __init__(self, age_client: AGEClient):
        self.client = age_client

    def classify_epistemic_status(
        self,
        vocab_type: str,
        grounding_stats: Dict
    ) -> Tuple[str, str]:
        """
        Classify epistemic status based on measured grounding patterns.

        Note: This is a MEASUREMENT, not a classification. Results are temporal
        and observer-dependent (sample-based, bounded calculation).

        Args:
            vocab_type: Vocabulary relationship type
            grounding_stats: Statistics from calculate_grounding_stats()

        Returns:
            (status, rationale) tuple
        """
        avg_grounding = grounding_stats.get('avg_grounding', 0.0)
        measured = grounding_stats.get('measured_concepts', 0)
        sampled = grounding_stats.get('sampled_edges', 0)
        total = grounding_stats.get('total_edges', 0)

        # Historical detection (name-based heuristic)
        historical_markers = [
            'WAS', 'WERE', 'HAD', 'HISTORICAL', 'FORMER', 'PREVIOUS',
            'PAST', 'ANCIENT', 'ORIGINALLY'
        ]
        if any(marker in vocab_type.upper() for marker in historical_markers):
            return (
                "HISTORICAL",
                f"Temporal marker detected in name: {vocab_type}"
            )

        # Insufficient measurement
        if measured < 3:
            return (
                "INSUFFICIENT_DATA",
                f"Only {measured} successful measurements from {sampled} sampled edges (total: {total})"
            )

        # Well-Grounded: Consistently high grounding
        if avg_grounding > 0.8:
            return (
                "WELL_GROUNDED",
                f"High avg grounding ({avg_grounding:.3f}) from {measured} measurements ({sampled}/{total} edges sampled)"
            )

        # Mixed Grounding: Variable validation (lowered threshold from 0.2 to 0.15)
        if 0.15 <= avg_grounding <= 0.8:
            return (
                "MIXED_GROUNDING",
                f"Mixed grounding ({avg_grounding:.3f}) from {measured} measurements ({sampled}/{total} edges sampled)"
            )

        # Weak Grounding: Weak positive grounding (emerging evidence)
        if 0.0 < avg_grounding < 0.15:
            return (
                "WEAK_GROUNDING",
                f"Weak positive grounding ({avg_grounding:.3f}) from {measured} measurements ({sampled}/{total} edges sampled) - developing evidence"
            )

        # Contradicted: Strong negative grounding (refuted)
        if avg_grounding < -0.5:
            return (
                "CONTRADICTED",
                f"Strong negative grounding ({avg_grounding:.3f}) from {measured} measurements ({sampled}/{total} edges sampled)"
            )

        # Poorly Grounded: Weak negative grounding (uncertain, liminal zone -0.5 to 0.0)
        return (
            "POORLY_GROUNDED",
            f"Weak negative grounding ({avg_grounding:.3f}) from {measured} measurements ({sampled}/{total} edges sampled)"
        )

    def calculate_grounding_stats(
        self,
        vocab_type: str,
        sample_size: int = 100
    ) -> Dict:
        """
        Measure grounding statistics for a vocabulary type by sampling edges.

        Philosophy: We don't analyze ALL edges (computationally expensive, mostly churn).
        Instead, we sample N edges and calculate grounding dynamically for target concepts.

        Args:
            vocab_type: Vocabulary relationship type to analyze
            sample_size: Maximum number of edges to sample

        Returns:
            Dictionary with grounding statistics
        """
        try:
            # Get all edges of this type and their target concepts
            query = f"""
                MATCH (c1:Concept)-[r:{vocab_type}]->(c2:Concept)
                RETURN c2.concept_id as target_id
            """

            results = self.client._execute_cypher(query)
            total_edges = len(results) if results else 0

            if total_edges == 0:
                return self._empty_stats()

            # Sample edges (or take all if fewer than sample_size)
            sample = results if total_edges <= sample_size else random.sample(results, sample_size)
            sampled_count = len(sample)

            # Batch-compute grounding for all sampled target concepts
            # (2 queries total instead of 2N sequential)
            target_ids = [
                row.get('target_id') for row in sample
                if row.get('target_id')
            ]
            try:
                grounding_map = self.client.calculate_grounding_strength_batch(
                    target_ids
                )
                grounding_values = [
                    float(g) for g in grounding_map.values()
                    if g is not None
                ]
            except Exception as e:
                logger.warning(
                    f"Batch grounding failed, falling back to per-concept: {e}"
                )
                grounding_values = []
                for target_id in target_ids:
                    try:
                        grounding = (
                            self.client.calculate_grounding_strength_semantic(
                                target_id
                            )
                        )
                        if grounding is not None:
                            grounding_values.append(float(grounding))
                    except Exception as inner_e:
                        logger.debug(
                            f"Skipping concept {target_id}: {inner_e}"
                        )

            if not grounding_values:
                return {
                    'total_edges': total_edges,
                    'sampled_edges': sampled_count,
                    'measured_concepts': 0,
                    'avg_grounding': 0.0,
                    'std_grounding': 0.0,
                    'max_grounding': 0.0,
                    'min_grounding': 0.0,
                    'grounding_distribution': [],
                    'measurement_timestamp': datetime.now().isoformat()
                }

            return {
                'total_edges': total_edges,
                'sampled_edges': sampled_count,
                'measured_concepts': len(grounding_values),
                'avg_grounding': mean(grounding_values),
                'std_grounding': stdev(grounding_values) if len(grounding_values) > 1 else 0.0,
                'max_grounding': max(grounding_values),
                'min_grounding': min(grounding_values),
                'grounding_distribution': grounding_values,
                'measurement_timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            logger.warning(f"Error measuring stats for {vocab_type}: {e}")
            return self._empty_stats()

    def get_all_vocab_types(self) -> List[str]:
        """Get all unique vocabulary relationship types from the graph."""
        query = """
            MATCH (v:VocabType)
            RETURN v.name as name
            ORDER BY v.name
        """

        try:
            results = self.client._execute_cypher(query)
            return [row['name'] for row in results if row.get('name')]
        except Exception as e:
            logger.error(f"Failed to fetch vocabulary types: {e}")
            return []

    def measure_all_vocabulary(
        self,
        sample_size: int = 100,
        store: bool = True
    ) -> Dict[str, Dict]:
        """
        Measure epistemic status for all vocabulary types.

        Integrates with graph_metrics table to track measurement completion
        and reset staleness counters.

        Args:
            sample_size: Number of edges to sample per type
            store: Whether to store results back to VocabType nodes

        Returns:
            Dictionary mapping vocab_type -> {status, rationale, stats}
        """
        vocab_types = self.get_all_vocab_types()
        results = {}

        logger.info(f"Measuring epistemic status for {len(vocab_types)} vocabulary types (sample_size={sample_size})")

        for vocab_type in vocab_types:
            # Calculate grounding statistics
            stats = self.calculate_grounding_stats(vocab_type, sample_size)

            # Classify epistemic status
            status, rationale = self.classify_epistemic_status(vocab_type, stats)

            results[vocab_type] = {
                'status': status,
                'rationale': rationale,
                'stats': stats
            }

            logger.debug(f"{vocab_type}: {status} - {rationale}")

        # Store results to graph if requested
        if store:
            self._store_results_to_graph(results)

            # Update graph metrics counters
            try:
                conn = self.client.pool.getconn()
                try:
                    metrics_service = VocabularyMetricsService(conn)

                    # Increment epistemic measurement counter
                    metrics_service.increment_epistemic_measurement()

                    # Mark vocabulary change counter measurement complete (reset delta to 0)
                    metrics_service.mark_measurement_complete('vocabulary_change_counter')

                    logger.info("Updated graph metrics counters after epistemic status measurement")
                except Exception as metrics_error:
                    logger.warning(f"Failed to update graph metrics: {metrics_error}")
                finally:
                    self.client.pool.putconn(conn)
            except Exception as e:
                logger.warning(f"Failed to get database connection for metrics update: {e}")

        return results

    def _store_results_to_graph(self, results: Dict[str, Dict]) -> None:
        """Store epistemic status results to VocabType nodes."""
        stored_count = 0

        for vocab_type, data in results.items():
            try:
                # Update VocabType node with epistemic_status and stats
                update_query = """
                    MATCH (v:VocabType {name: $vocab_type})
                    SET v.epistemic_status = $status,
                        v.epistemic_rationale = $rationale,
                        v.epistemic_measured_at = $timestamp,
                        v.epistemic_stats = $stats
                    RETURN v.name as name
                """

                params = {
                    'vocab_type': vocab_type,
                    'status': data['status'],
                    'rationale': data['rationale'],
                    'timestamp': data['stats']['measurement_timestamp'],
                    'stats': data['stats']
                }

                result = self.client._execute_cypher(update_query, params)
                if result:
                    stored_count += 1

            except Exception as e:
                logger.warning(f"Failed to store epistemic status for {vocab_type}: {e}")

        logger.info(f"✅ Stored {stored_count}/{len(results)} epistemic statuses to VocabType nodes")

    def _empty_stats(self) -> Dict:
        """Return empty statistics dictionary."""
        return {
            'total_edges': 0,
            'sampled_edges': 0,
            'measured_concepts': 0,
            'avg_grounding': 0.0,
            'std_grounding': 0.0,
            'max_grounding': 0.0,
            'min_grounding': 0.0,
            'grounding_distribution': [],
            'measurement_timestamp': datetime.now().isoformat()
        }
