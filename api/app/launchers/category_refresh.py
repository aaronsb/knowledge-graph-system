"""
Category Refresh Launcher (ADR-050).

Automatically refresh vocabulary categories with llm_generated entries.
Checks every 6 hours (configured in kg_api.scheduled_jobs) but only runs
when llm_generated categories actually exist.
"""

from .base import JobLauncher
from api.app.lib.age_client import AGEClient
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class CategoryRefreshLauncher(JobLauncher):
    """
    Automatically refresh vocabulary categories with llm_generated entries.

    Schedule: Every 6 hours (cron: "0 */6 * * *")
    Condition: Are there categories with "llm_generated" relationship types?
    Worker: vocab_refresh_worker
    Pattern: Polling (checks often, runs rarely)

    Example flow:
    1. Scheduler fires every 6 hours
    2. check_conditions() queries for llm_generated categories
    3. If found: enqueue vocab_refresh job
    4. If not found: skip (return None, not a failure)
    5. Worker re-integrates llm_generated types into base vocabulary
    """

    def check_conditions(self) -> bool:
        """
        Check if any categories have llm_generated entries.

        Returns:
            True if llm_generated categories exist, False otherwise
        """
        try:
            client = AGEClient()

            # Query for categories with llm_generated relationship types using facade
            # This ensures namespace safety and audit logging (ADR-048)
            results = client.facade.match_vocab_categories(
                where="c.name IS NOT NULL"
            )

            # Check if any category has 'llm_generated' in its relationship_types
            for row in results:
                # Facade returns {c: {...}} format
                category = row.get('c', {})
                if not category:
                    continue

                category_name = category.get('name')
                relationship_types = category.get('relationship_types', [])

                # Parse agtype to Python list if needed
                if isinstance(relationship_types, str):
                    import json
                    try:
                        relationship_types = json.loads(relationship_types)
                    except:
                        continue

                if isinstance(relationship_types, list) and 'llm_generated' in relationship_types:
                    logger.info(
                        f"✓ CategoryRefreshLauncher: Found category '{category_name}' "
                        f"with llm_generated entries"
                    )
                    return True

            # No llm_generated categories found
            logger.debug("CategoryRefreshLauncher: No llm_generated categories found")
            return False

        except Exception as e:
            # Let exceptions bubble up so scheduler can retry
            logger.error(f"CategoryRefreshLauncher condition check failed: {e}")
            raise

    def prepare_job_data(self) -> Dict:
        """
        Prepare data for vocab refresh worker.

        Returns:
            Dict with operation parameters
        """
        return {
            "operation": "refresh_categories",
            "auto_mode": True,
            "filter": "llm_generated",
            "description": "Scheduled category refresh (llm_generated → base vocabulary)"
        }

    def get_job_type(self) -> str:
        """
        Return job type for worker registry.

        Returns:
            "vocab_refresh" (must be registered as worker)
        """
        return "vocab_refresh"
