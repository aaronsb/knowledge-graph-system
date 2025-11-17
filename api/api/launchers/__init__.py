"""
Job launchers for scheduled tasks (ADR-050).

Launchers are lightweight "sequencers" that:
1. Check if conditions are met to run a job
2. Prepare job_data for the worker
3. Enqueue job to existing job queue

The existing job queue handles execution, progress, approval, etc.
"""

from .base import JobLauncher
from .category_refresh import CategoryRefreshLauncher
from .vocab_consolidation import VocabConsolidationLauncher
from .epistemic_remeasurement import EpistemicRemeasurementLauncher

__all__ = [
    "JobLauncher",
    "CategoryRefreshLauncher",
    "VocabConsolidationLauncher",
    "EpistemicRemeasurementLauncher",
]
