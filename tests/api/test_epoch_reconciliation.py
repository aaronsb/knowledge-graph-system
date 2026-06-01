"""Live test for orphaned in_progress epoch reconciliation (issue #485).

reconcile_orphaned_epochs resolves in_progress graph_epochs whose owning job
(metadata->>'job_id') is no longer active to 'failed', unblocking the committed
watermark after a crash. Verifies the three cases against the live DB:
  - owning job FAILED (terminal)  → reconciled
  - owning job absent             → reconciled
  - owning job RUNNING (active)   → left alone (a live restore/ingestion in flight)

Uses an AGEClient pool shim (the repo's live-DB pattern; the job-queue singleton
isn't initialized in the test process). All test rows (epochs + jobs) are
namespaced and removed in a finally.
"""
import json
import uuid

import pytest

from api.app.lib.age_client import AGEClient
from api.app.services.job_scheduler import reconcile_orphaned_epochs

NS = "job_test485_"


class _PoolShim:
    """Adapts an AGEClient pool to the queue interface reconcile_orphaned_epochs uses."""
    def __init__(self, client):
        self._pool = client.pool

    def _get_connection(self):
        return self._pool.getconn()

    def _return_connection(self, conn):
        self._pool.putconn(conn)


@pytest.fixture()
def shim():
    client = AGEClient()
    try:
        yield _PoolShim(client)
    finally:
        client.close()


def _seed_job(shim, job_id, status):
    conn = shim._get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO kg_api.jobs (job_id, job_type, status, job_data, user_id) "
                "VALUES (%s, 'ingestion', %s, '{}'::jsonb, 1)",
                (job_id, status),
            )
        conn.commit()
    finally:
        shim._return_connection(conn)


def _seed_epoch(shim, job_id):
    conn = shim._get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO kg_api.graph_epochs (kind, actor, status, metadata) "
                "VALUES ('ingestion', 'test-485', 'in_progress', %s::jsonb) RETURNING event_id",
                (json.dumps({"job_id": job_id}),),
            )
            eid = cur.fetchone()[0]
        conn.commit()
        return eid
    finally:
        shim._return_connection(conn)


def _epoch_status(shim, event_id):
    conn = shim._get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM kg_api.graph_epochs WHERE event_id = %s", (event_id,))
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.commit()
        shim._return_connection(conn)


def _cleanup(shim, event_ids, job_ids):
    conn = shim._get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM kg_api.graph_epochs WHERE event_id = ANY(%s)", (list(event_ids),))
            cur.execute("DELETE FROM kg_api.jobs WHERE job_id = ANY(%s)", (list(job_ids),))
        conn.commit()
    finally:
        shim._return_connection(conn)


def test_reconcile_resolves_orphans_but_spares_active_jobs(shim):
    failed_job = f"{NS}failed_{uuid.uuid4().hex[:8]}"
    running_job = f"{NS}running_{uuid.uuid4().hex[:8]}"
    absent_job = f"{NS}absent_{uuid.uuid4().hex[:8]}"  # never inserted

    _seed_job(shim, failed_job, "failed")
    _seed_job(shim, running_job, "running")
    e_failed = _seed_epoch(shim, failed_job)
    e_running = _seed_epoch(shim, running_job)
    e_absent = _seed_epoch(shim, absent_job)

    try:
        reconciled = reconcile_orphaned_epochs(shim)

        # Orphans (failed + absent owning job) resolved; active (running) spared.
        assert e_failed in reconciled
        assert e_absent in reconciled
        assert e_running not in reconciled
        assert _epoch_status(shim, e_failed) == "failed"
        assert _epoch_status(shim, e_absent) == "failed"
        assert _epoch_status(shim, e_running) == "in_progress"
    finally:
        _cleanup(shim, [e_failed, e_running, e_absent], [failed_job, running_job])


@pytest.mark.parametrize("status,spared", [
    ("pending", True),
    ("awaiting_approval", True),   # review #486 M1: must be spared (pre-execution, live)
    ("approved", True),
    ("queued", True),             # review #486 M1: must be spared
    ("processing", True),
    ("completed", False),          # terminal → reconciled
    ("cancelled", False),          # terminal → reconciled
])
def test_reconcile_spares_all_non_terminal_statuses(shim, status, spared):
    """The sweep keys on the closed terminal set, so EVERY non-terminal job status
    protects its epoch — locks the M1 invariant against future status additions."""
    job_id = f"{NS}{status}_{uuid.uuid4().hex[:8]}"
    _seed_job(shim, job_id, status)
    eid = _seed_epoch(shim, job_id)
    try:
        reconcile_orphaned_epochs(shim)
        expected = "in_progress" if spared else "failed"
        assert _epoch_status(shim, eid) == expected
    finally:
        _cleanup(shim, [eid], [job_id])
