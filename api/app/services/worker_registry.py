"""
Worker registry — single source of truth for job type → worker function mappings.

Extracted from main.py per #344. Each entry declares:
- job_type: the string stored in kg_api.jobs.job_type
- worker_func: the callable that executes the job
- lane: which worker lane claims this type (ADR-100)

The registry is static and explicit — no auto-discovery.
"""

from typing import Callable, NamedTuple

from ..workers.ingestion_worker import run_ingestion_worker
from ..workers.restore_worker import run_restore_worker
from ..workers.vocab_refresh_worker import run_vocab_refresh_worker
from ..workers.vocab_consolidate_worker import run_vocab_consolidate_worker
from ..workers.epistemic_remeasurement_worker import run_epistemic_remeasurement_worker
from ..workers.source_embedding_worker import run_source_embedding_worker
from ..workers.projection_worker import run_projection_worker
from ..workers.polarity_worker import run_polarity_worker
from ..workers.artifact_cleanup_worker import run_artifact_cleanup_worker
from ..workers.annealing_worker import run_annealing_worker
from ..workers.proposal_execution_worker import run_proposal_execution_worker


class WorkerEntry(NamedTuple):
    """A registered worker with its lane affinity."""
    func: Callable
    lane: str


# fmt: off
WORKER_REGISTRY: dict[str, WorkerEntry] = {
    # --- interactive lane: user-initiated, latency-sensitive ---
    "ingestion":               WorkerEntry(run_ingestion_worker,               "interactive"),
    "ingest_image":            WorkerEntry(run_ingestion_worker,               "interactive"),  # ADR-057
    "polarity":                WorkerEntry(run_polarity_worker,                "interactive"),  # ADR-070+083

    # --- maintenance lane: background, can wait ---
    "projection":              WorkerEntry(run_projection_worker,              "maintenance"),  # ADR-078
    "vocab_refresh":           WorkerEntry(run_vocab_refresh_worker,           "maintenance"),  # ADR-050
    "epistemic_remeasurement": WorkerEntry(run_epistemic_remeasurement_worker, "maintenance"),  # ADR-065
    "ontology_annealing":      WorkerEntry(run_annealing_worker,              "maintenance"),  # ADR-200
    "proposal_execution":      WorkerEntry(run_proposal_execution_worker,     "maintenance"),  # ADR-200

    # --- system lane: infrastructure housekeeping ---
    "restore":                 WorkerEntry(run_restore_worker,                 "system"),
    "vocab_consolidate":       WorkerEntry(run_vocab_consolidate_worker,       "system"),       # ADR-050
    "artifact_cleanup":        WorkerEntry(run_artifact_cleanup_worker,        "system"),       # ADR-083
    "source_embedding":        WorkerEntry(run_source_embedding_worker,        "system"),       # ADR-068
}
# fmt: on


def register_all_workers(queue) -> None:
    """Register all worker functions with the job queue.  @verified (new)"""
    for job_type, entry in WORKER_REGISTRY.items():
        queue.register_worker(job_type, entry.func)


def get_job_types_for_lane(lane: str) -> list[str]:
    """Return job types assigned to a lane.  @verified (new)"""
    return [jt for jt, entry in WORKER_REGISTRY.items() if entry.lane == lane]


def get_all_job_types() -> list[str]:
    """Return all registered job type names.  @verified (new)"""
    return list(WORKER_REGISTRY.keys())
