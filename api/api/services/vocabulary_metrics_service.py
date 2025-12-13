"""
Vocabulary Metrics Service

Tracks graph change counters to trigger periodic epistemic status measurement.

Philosophy:
- Vocabulary epistemic status can be cached (unlike node grounding)
- Only re-measure when vocabulary changes (create/delete/consolidate)
- Use change counters, not datetimes, to detect staleness
- Delta = current_counter - last_measured_counter indicates staleness

Counter Types:
  GRAPH STRUCTURE (auto-incremented by database triggers - Migration 033):
  - graph_change_counter: ANY graph modification
  - concept_creation/deletion_counter: Concept changes
  - relationship_creation/deletion_counter: Edge changes
  - vocabulary_change/creation/deletion_counter: VocabType/VocabCategory changes

  ACTIVITY (application-incremented via this service):
  - document_ingestion_counter: Documents ingested
  - epistemic_measurement_counter: Measurements completed
  - vocabulary_consolidation_counter: Vocabulary merges (application-level)

Usage:
    metrics = VocabularyMetricsService(db_connection)

    # Activity counters (application must call these)
    metrics.increment_document_ingestion()
    metrics.increment_epistemic_measurement()
    metrics.increment_vocabulary_consolidation()

    # Check if re-measurement needed
    if metrics.should_remeasure(threshold=10):
        measure_epistemic_status()
        metrics.mark_measurement_complete()

Note: Graph structure counters (concept_creation, relationship_creation, etc.)
are now automatically incremented by database triggers. Do NOT call increment
methods for these - they would cause double-counting.
"""

import logging
from typing import Dict, Optional
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class VocabularyMetricsService:
    """Service for tracking graph change counters and detecting staleness"""

    def __init__(self, db_connection):
        """
        Initialize metrics service.

        Args:
            db_connection: PostgreSQL database connection
        """
        self.conn = db_connection

    def increment_counter(self, metric_name: str) -> bool:
        """
        Increment a specific counter.

        Args:
            metric_name: Name of counter to increment

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT increment_counter(%s)", (metric_name,))
                self.conn.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to increment counter {metric_name}: {e}")
            self.conn.rollback()
            return False

    # =========================================================================
    # ACTIVITY COUNTERS (application must call these - not trigger-based)
    # =========================================================================

    def increment_vocabulary_consolidation(self) -> bool:
        """
        Increment vocabulary_consolidation_counter.

        Call this when vocabulary types are merged/consolidated.
        This is an application-level operation, not a simple graph change.
        """
        return self.increment_counter('vocabulary_consolidation_counter')

    def increment_document_ingestion(self) -> bool:
        """
        Increment document_ingestion_counter.

        Call this when a document is successfully ingested.
        """
        return self.increment_counter('document_ingestion_counter')

    def increment_epistemic_measurement(self) -> bool:
        """
        Increment epistemic_measurement_counter.

        Call this when epistemic status measurement completes.
        """
        return self.increment_counter('epistemic_measurement_counter')

    # =========================================================================
    # DEPRECATED: Graph structure counters are now trigger-based (Migration 033)
    # These methods are kept for backwards compatibility but should NOT be called.
    # The database triggers handle these automatically.
    # =========================================================================

    def _deprecated_increment_vocabulary_change(self) -> bool:
        """DEPRECATED: Now handled by database trigger on VocabType/VocabCategory"""
        logger.warning("increment_vocabulary_change() is deprecated - triggers handle this automatically")
        return True  # No-op, triggers handle it

    def _deprecated_increment_concept_creation(self) -> bool:
        """DEPRECATED: Now handled by database trigger on Concept table"""
        logger.warning("increment_concept_creation() is deprecated - triggers handle this automatically")
        return True  # No-op, triggers handle it

    def _deprecated_increment_relationship_creation(self) -> bool:
        """DEPRECATED: Now handled by database trigger on edge tables"""
        logger.warning("increment_relationship_creation() is deprecated - triggers handle this automatically")
        return True  # No-op, triggers handle it

    def get_counter_delta(self, metric_name: str) -> int:
        """
        Get delta between current counter and last measured counter.

        Args:
            metric_name: Name of counter to check

        Returns:
            Delta value (0 if no changes since last measurement)
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT get_counter_delta(%s)", (metric_name,))
                result = cur.fetchone()
                return int(result[0]) if result else 0
        except Exception as e:
            logger.error(f"Failed to get counter delta for {metric_name}: {e}")
            return 0

    def get_all_metrics(self) -> Dict[str, Dict]:
        """
        Get all metric counters and their deltas.

        Returns:
            Dictionary mapping metric_name -> {counter, last_measured, delta, updated_at}
        """
        try:
            with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        metric_name,
                        counter,
                        last_measured_counter,
                        last_measured_at,
                        updated_at,
                        (counter - last_measured_counter) as delta
                    FROM graph_metrics
                    ORDER BY metric_name
                """)
                results = cur.fetchall()

                return {
                    row['metric_name']: {
                        'counter': row['counter'],
                        'last_measured': row['last_measured_counter'],
                        'delta': row['delta'],
                        'last_measured_at': row['last_measured_at'],
                        'updated_at': row['updated_at']
                    }
                    for row in results
                }
        except Exception as e:
            logger.error(f"Failed to get all metrics: {e}")
            return {}

    def should_remeasure(self, threshold: int = 10) -> bool:
        """
        Check if epistemic status should be re-measured based on vocabulary changes.

        Args:
            threshold: Minimum delta to trigger re-measurement (default: 10 changes)

        Returns:
            True if vocabulary_change_counter delta >= threshold
        """
        delta = self.get_counter_delta('vocabulary_change_counter')
        should_measure = delta >= threshold

        if should_measure:
            logger.info(f"Vocabulary change delta ({delta}) >= threshold ({threshold}) - triggering re-measurement")
        else:
            logger.debug(f"Vocabulary change delta ({delta}) < threshold ({threshold}) - no re-measurement needed")

        return should_measure

    def mark_measurement_complete(self, metric_name: str = 'vocabulary_change_counter') -> bool:
        """
        Mark epistemic status measurement complete (resets delta to 0).

        Args:
            metric_name: Counter to mark complete (default: vocabulary_change_counter)

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT mark_measurement_complete(%s)", (metric_name,))
                self.conn.commit()
                logger.info(f"Marked {metric_name} measurement complete")
                return True
        except Exception as e:
            logger.error(f"Failed to mark measurement complete for {metric_name}: {e}")
            self.conn.rollback()
            return False

    def reset_counter(self, metric_name: str) -> bool:
        """
        Reset counter to 0 (operator maintenance task).

        Args:
            metric_name: Counter to reset

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT reset_counter(%s)", (metric_name,))
                self.conn.commit()
                logger.warning(f"Reset counter: {metric_name}")
                return True
        except Exception as e:
            logger.error(f"Failed to reset counter {metric_name}: {e}")
            self.conn.rollback()
            return False

    def get_staleness_info(self) -> Dict:
        """
        Get comprehensive staleness information for dashboard/monitoring.

        Returns:
            Dictionary with staleness metrics and recommendations
        """
        vocab_delta = self.get_counter_delta('vocabulary_change_counter')
        concept_delta = self.get_counter_delta('concept_creation_counter')
        relationship_delta = self.get_counter_delta('relationship_creation_counter')

        metrics = self.get_all_metrics()
        vocab_metrics = metrics.get('vocabulary_change_counter', {})

        # Determine urgency
        if vocab_delta >= 50:
            urgency = "high"
            recommendation = "Re-measure epistemic status immediately"
        elif vocab_delta >= 20:
            urgency = "medium"
            recommendation = "Re-measure epistemic status soon"
        elif vocab_delta >= 10:
            urgency = "low"
            recommendation = "Re-measure epistemic status when convenient"
        else:
            urgency = "none"
            recommendation = "No re-measurement needed"

        return {
            'vocabulary_changes_since_last_measurement': vocab_delta,
            'concept_creations_since_last_measurement': concept_delta,
            'relationship_creations_since_last_measurement': relationship_delta,
            'last_measurement_at': vocab_metrics.get('last_measured_at'),
            'urgency': urgency,
            'recommendation': recommendation,
            'all_metrics': metrics
        }
