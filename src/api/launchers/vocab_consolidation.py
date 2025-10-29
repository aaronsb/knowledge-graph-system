"""
Vocabulary Consolidation Launcher (ADR-050).

Automatically consolidate vocabulary based on hysteresis curve to prevent
thrashing and maintain optimal vocabulary spread.
"""

from .base import JobLauncher
from src.api.lib.age_client import AGEClient
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class VocabConsolidationLauncher(JobLauncher):
    """
    Automatically consolidate vocabulary based on hysteresis thresholds.

    Schedule: Every 12 hours (cron: "0 */12 * * *")
    Condition: Does vocab spread exceed consolidation threshold with hysteresis?
    Worker: vocab_consolidate_worker
    Pattern: Polling (checks often, runs rarely)

    Hysteresis Logic:
    - Upper threshold: 20% inactive types → consolidate
    - Lower threshold: 10% inactive types → don't consolidate (prevent thrashing)
    - Gray zone (10-20%): Use previous state to avoid flip-flopping

    Example flow:
    1. Scheduler fires every 12 hours
    2. check_conditions() calculates inactive_ratio = inactive_types / active_types
    3. If inactive_ratio > 20%: return True (consolidate)
    4. If inactive_ratio < 10%: return False (don't consolidate)
    5. If 10% < ratio < 20%: maintain previous state (hysteresis)
    6. Worker consolidates similar/redundant vocabulary types
    """

    # Hysteresis thresholds (configurable via future enhancement)
    UPPER_THRESHOLD = 0.20  # 20% - trigger consolidation
    LOWER_THRESHOLD = 0.10  # 10% - prevent thrashing
    MIN_ACTIVE_TYPES = 50    # Minimum active types before considering consolidation

    def check_conditions(self) -> bool:
        """
        Check if vocabulary spread exceeds consolidation threshold with hysteresis.

        Returns:
            True if consolidation needed, False otherwise
        """
        try:
            client = AGEClient()

            # Query vocabulary statistics using facade
            # Complex aggregation requires execute_raw() but with namespace safety (ADR-048)
            query = """
                MATCH (v:VocabType)
                RETURN
                    COUNT(v) AS total_types,
                    SUM(CASE WHEN v.is_active = true THEN 1 ELSE 0 END) AS active_types,
                    SUM(CASE WHEN v.is_active = false THEN 1 ELSE 0 END) AS inactive_types
            """

            results = client.facade.execute_raw(query, namespace="vocabulary")

            if not results:
                logger.warning("VocabConsolidationLauncher: No vocabulary stats found")
                return False

            row = results[0]
            total_types = int(row.get('total_types', 0))
            active_types = int(row.get('active_types', 0))
            inactive_types = int(row.get('inactive_types', 0))

            logger.debug(
                f"VocabConsolidationLauncher stats: "
                f"total={total_types}, active={active_types}, inactive={inactive_types}"
            )

            # Don't consolidate if not enough active types yet
            if active_types < self.MIN_ACTIVE_TYPES:
                logger.info(
                    f"⏭️  VocabConsolidationLauncher: Too few active types "
                    f"({active_types} < {self.MIN_ACTIVE_TYPES}), skipping"
                )
                return False

            # Calculate inactive ratio
            inactive_ratio = inactive_types / active_types

            # Hysteresis decision logic
            if inactive_ratio > self.UPPER_THRESHOLD:
                # Upper threshold exceeded: consolidate
                logger.info(
                    f"✓ VocabConsolidationLauncher: Consolidation threshold exceeded - "
                    f"{inactive_types}/{active_types} = {inactive_ratio:.1%} > {self.UPPER_THRESHOLD:.0%}"
                )
                return True

            elif inactive_ratio < self.LOWER_THRESHOLD:
                # Lower threshold: prevent thrashing
                logger.debug(
                    f"⏭️  VocabConsolidationLauncher: Below lower threshold - "
                    f"{inactive_types}/{active_types} = {inactive_ratio:.1%} < {self.LOWER_THRESHOLD:.0%} "
                    f"(hysteresis)"
                )
                return False

            else:
                # Gray zone (10-20%): maintain previous state
                # Since we don't track previous state yet, default to not consolidating
                # This errs on the side of caution (fewer consolidations)
                logger.info(
                    f"⏭️  VocabConsolidationLauncher: In hysteresis zone - "
                    f"{inactive_types}/{active_types} = {inactive_ratio:.1%} "
                    f"({self.LOWER_THRESHOLD:.0%} - {self.UPPER_THRESHOLD:.0%}), defaulting to skip"
                )
                return False

        except Exception as e:
            # Let exceptions bubble up so scheduler can retry
            logger.error(f"VocabConsolidationLauncher condition check failed: {e}")
            raise

    def prepare_job_data(self) -> Dict:
        """
        Prepare data for vocab consolidation worker.

        Reads target size and aggressiveness profile from vocab config.

        Returns:
            Dict with operation parameters
        """
        client = AGEClient()

        try:
            # Read vocab_max from config (target size)
            target_query = """
                SELECT value FROM kg_api.vocabulary_config
                WHERE key = 'vocab_max'
            """
            target_result = client._execute_sql(target_query)
            target_size = int(target_result[0]['value']) if target_result else 90

            # Read active aggressiveness profile
            profile_query = """
                SELECT value FROM kg_api.vocabulary_config
                WHERE key = 'aggressiveness_profile'
            """
            profile_result = client._execute_sql(profile_query)
            profile_name = profile_result[0]['value'] if profile_result else "aggressive"

            logger.info(
                f"VocabConsolidationLauncher: Using target_size={target_size} "
                f"from config, profile={profile_name}"
            )

            return {
                "operation": "consolidate",
                "auto_mode": True,
                "strategy": "hysteresis",
                "upper_threshold": self.UPPER_THRESHOLD,
                "lower_threshold": self.LOWER_THRESHOLD,
                "target_size": target_size,
                "aggressiveness_profile": profile_name,
                "description": f"Scheduled vocabulary consolidation (target: {target_size}, profile: {profile_name})"
            }
        finally:
            client.close()

    def get_job_type(self) -> str:
        """
        Return job type for worker registry.

        Returns:
            "vocab_consolidate" (must be registered as worker)
        """
        return "vocab_consolidate"
