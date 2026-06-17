---
id: 01.009.E
domain: infra
mode: explanation
---

# Scheduled Jobs

Kappa Graph runs background jobs on a timer to keep vocabulary, epistemic measurements, and ontology structure in sync as your graph evolves.

All jobs follow the same polling pattern: the schedule fires, the launcher checks a condition, and the job is enqueued only when work is actually needed. A skip is not a failure.

---

## How the polling pattern works

```
Schedule fires → check_conditions() → work needed?
                                       ├─ YES → enqueue job
                                       └─ NO  → skip (normal)
```

The schedule interval is a rate limit, not a precise execution time. "Every hour" means "not more often than every hour." Condition checks are cheap (~1 ms SQL query); the actual work runs only when the condition is met.

**Example — epistemic re-measurement:**

```
00:00 → delta = 5  → skip (< 10)
01:00 → delta = 5  → skip (< 10)
02:00 → delta = 7  → skip (< 10)
03:00 → delta = 12 → enqueue (>= 10)
04:00 → delta = 0  → skip (just reset)
```

If a launcher raises an exception (distinct from returning `False`), the scheduler retries up to five times before disabling the schedule. Disabling is logged as an error and requires manual re-enablement.

---

## Active scheduled jobs

### Category refresh — every 6 hours

| | |
|---|---|
| Cron | `0 */6 * * *` |
| Worker | `vocab_refresh_worker` |
| Launcher | `CategoryRefreshLauncher` |
| ADR | ADR-111 |

When the LLM discovers relationship types during ingestion, those types are marked `llm_generated`. This job checks for pending `llm_generated` entries and integrates them into the permanent vocabulary.

**Condition:** At least one vocabulary category contains entries with the `llm_generated` relationship type.

---

### Vocabulary consolidation — every 12 hours

| | |
|---|---|
| Cron | `0 */12 * * *` |
| Worker | `vocab_consolidate_worker` |
| Launcher | `VocabConsolidationLauncher` |
| ADR | ADR-111 |

As a graph evolves, some vocabulary types stop appearing in new extractions and become inactive. When the ratio of inactive-to-active types exceeds a threshold, this job consolidates them to keep the vocabulary manageable.

**Condition:** `inactive_types / active_types > 20%` and total active types ≥ 50.

**Hysteresis thresholds (prevent thrashing):**

| Ratio | Action |
|---|---|
| > 20% inactive | Consolidate |
| 10–20% inactive | Hold previous state (default: skip) |
| < 10% inactive | Skip |

The aggressiveness profile and target vocabulary size are read from `kg_api.vocabulary_config` at launch time.

---

### Epistemic re-measurement — every hour

| | |
|---|---|
| Cron | `0 * * * *` |
| Worker | `epistemic_remeasurement_worker` |
| Launcher | `EpistemicRemeasurementLauncher` |
| ADR | ADR-610 |

Epistemic status labels (`WELL_GROUNDED`, `MIXED_GROUNDING`, etc.) are computed by sampling relationship edges. This job refreshes those measurements when enough vocabulary changes have accumulated.

**Condition:** `vocabulary_change_counter` delta ≥ 10 (default). The counter increments on vocabulary modification and resets to 0 after a measurement run.

To change the threshold, edit `api/app/launchers/epistemic_remeasurement.py`, update the `threshold` parameter in `__init__()`, and restart the API container:

```bash
./operator.sh restart api
```

---

### Ontology annealing — every 6 hours and post-ingestion

| | |
|---|---|
| Cron | `0 */6 * * *` + post-ingestion trigger |
| Worker | `annealing_worker` |
| Launcher | `AnnealingLauncher` |
| ADR | ADR-200 |

As documents are ingested, some ontologies accumulate enough high-degree concepts to warrant splitting; others shrink below useful coherence and are candidates for dissolution. This job re-scores ontologies, generates proposals, and (in the default `autonomous` mode) executes them within the same cycle.

**Condition:** `current_epoch - last_annealing_epoch >= epoch_interval` (default: 5 epochs). The check and the epoch claim are atomic — concurrent triggers cannot both pass.

**Refractory gate:** Annealing defers while ingestion jobs are actively running, up to a maximum of 50 accumulated epochs, to avoid reorganizing a graph that is still being flooded with concepts.

**Automation modes:**

| Mode | Behavior |
|---|---|
| `autonomous` (default) | Proposals are auto-approved and executed in the same cycle |
| `hitl` | Proposals stay `pending` for review via the API before execution |

To switch modes:

```sql
UPDATE kg_api.annealing_options SET value = 'hitl' WHERE key = 'automation_level';
```

No restart is required — the launcher reads `kg_api.annealing_options` at each launch.

**Decision thresholds:**

| Candidate | Default threshold | Evaluated by |
|---|---|---|
| Demotion (dissolution) | `protection_score < 0.15` | LLM using mass, coherence, concept count, affinity targets |
| Promotion (new ontology) | `concept degree >= 10` | LLM using degree, top neighbors, ontology size, affinity targets |

The LLM can reject candidates that pass numeric thresholds. See ADR-200 for the full decision verb set (CLEAVE, DISSOLVE, MERGE, RENAME, NO\_ACTION, ESCALATE).

---

### Artifact cleanup — daily at 02:00

| | |
|---|---|
| Cron | `0 2 * * *` |
| Worker | `artifact_cleanup` |
| Launcher | `ArtifactCleanupLauncher` |
| ADR | ADR-116 |

Removes artifacts whose `expires_at` timestamp has passed.

**Condition:** At least one row in `kg_api.artifacts` has `expires_at < NOW()`.

---

## Viewing schedule status

```sql
SELECT name, schedule_cron, enabled, last_run, last_success, next_run
FROM kg_api.scheduled_jobs
ORDER BY name;
```

```
name                    | schedule_cron | enabled | last_run            | last_success        | next_run
------------------------+---------------+---------+---------------------+---------------------+---------------------
annealing               | 0 */6 * * *   | t       | 2026-06-14 12:00:00 | 2026-06-14 06:00:00 | 2026-06-14 18:00:00
artifact_cleanup        | 0 2 * * *     | t       | 2026-06-14 02:00:00 | 2026-06-14 02:00:00 | 2026-06-15 02:00:00
category_refresh        | 0 */6 * * *   | t       | 2026-06-14 12:00:00 | 2026-06-14 06:00:00 | 2026-06-14 18:00:00
epistemic_remeasurement | 0 * * * *     | t       | 2026-06-14 13:00:00 | 2026-06-14 11:00:00 | 2026-06-14 14:00:00
vocab_consolidation     | 0 */12 * * *  | t       | 2026-06-14 12:00:00 | 2026-06-13 00:00:00 | 2026-06-15 00:00:00
```

A high skip rate is normal. `last_success` advances only when conditions were met and work ran; prolonged gaps are expected during quiet periods.

## Viewing job history

```sql
SELECT job_id, job_type, status, created_at, completed_at
FROM kg_api.jobs
WHERE is_system_job = true
  AND job_source = 'scheduled_task'
ORDER BY created_at DESC
LIMIT 10;
```

---

## Managing schedules

### Trigger a job immediately (for testing)

Set `next_run` to the current time. The job will still check its condition and skip if the condition is not met.

```sql
UPDATE kg_api.scheduled_jobs
SET next_run = NOW()
WHERE name = 'epistemic_remeasurement';
```

### Disable a schedule

```sql
UPDATE kg_api.scheduled_jobs
SET enabled = false
WHERE name = 'vocab_consolidation';
```

### Re-enable after a failure

```sql
UPDATE kg_api.scheduled_jobs
SET enabled = true, retry_count = 0
WHERE name = 'category_refresh';
```

---

## Log messages

**Normal run:**
```
INFO: Schedule 'epistemic_remeasurement' is due, triggering launcher
INFO: EpistemicRemeasurementLauncher: Vocabulary change delta (12) >= threshold (10)
INFO: EpistemicRemeasurementLauncher: Enqueued job job_abc123
```

**Healthy skip:**
```
INFO: Schedule 'epistemic_remeasurement' is due, triggering launcher
INFO: EpistemicRemeasurementLauncher: Delta (5) below threshold (10)
INFO: Schedule 'epistemic_remeasurement' skipped (conditions not met)
```

**Failure with retry:**
```
ERROR: Schedule 'category_refresh' launcher failed: Database connection timeout
WARNING: Schedule 'category_refresh' failed (retry 1/5), retrying in 2 min
```

**Max retries exceeded:**
```
ERROR: Schedule 'category_refresh' max retries exceeded, disabling
```

---

## Troubleshooting

**Schedule disabled after max retries**
The launcher raised an exception (not a condition skip) five times consecutively. Check API logs for the underlying error, fix the root cause, then re-enable:

```sql
UPDATE kg_api.scheduled_jobs SET enabled = true, retry_count = 0 WHERE name = 'category_refresh';
```

**Jobs not running when conditions should be met**
Check in order:
1. `enabled = true` in `kg_api.scheduled_jobs`
2. `next_run` is in the past
3. The condition is actually met (inspect launcher logic against current data)
4. The scheduler loop is running (API logs should show a scheduler heartbeat every ~60 s)

**Duplicate jobs from one schedule**
Multiple API workers raced past the advisory lock. Verify the PostgreSQL advisory lock is operating correctly (see ADR-111). Logs should show only one worker acquiring the scheduler lock per minute.

---

## Related

- [ADR-111: Scheduled Jobs System](../architecture/infrastructure/ADR-111-scheduled-jobs-system.md)
- [ADR-610: Vocabulary-Based Provenance](../architecture/vocabulary-relationships/ADR-610-vocabulary-based-provenance-relationships.md)
- [ADR-200: Ontology Annealing](../architecture/database-schema/ADR-200-annealing-ontologies-self-organizing-knowledge-graph-structure.md)
- [Vocabulary Lifecycle](../explanation/vocabulary-lifecycle.md)
- [Filter by Epistemic Status](../how-to/epistemic-status.md)
