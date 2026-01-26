# job

> Auto-generated from MCP tool schema

### job

Manage ingestion jobs: get status, list jobs, approve, cancel, delete, or cleanup. Use action parameter to specify operation.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "status" (get job status), "list" (list jobs), "approve" (approve job), "cancel" (cancel job), "delete" (permanently delete single job), "cleanup" (delete jobs matching filters)
  - Allowed values: `status`, `list`, `approve`, `cancel`, `delete`, `cleanup`
- `job_id` (`string`) - Job ID (required for status, approve, cancel, delete)
- `status` (`string`) - Filter by status for list/cleanup (pending, awaiting_approval, running, completed, failed)
- `limit` (`number`) - Max jobs to return for list (default: 50)
  - Default: `50`
- `force` (`boolean`) - Force delete even if job is processing (for delete action)
  - Default: `false`
- `system_only` (`boolean`) - Only delete system/scheduled jobs (for cleanup action)
  - Default: `false`
- `older_than` (`string`) - Delete jobs older than duration: 1h, 24h, 7d, 30d (for cleanup action)
- `job_type` (`string`) - Filter by job type for cleanup (ingestion, epistemic_remeasurement, projection, etc)
- `dry_run` (`boolean`) - Preview what would be deleted without deleting (for cleanup, default: true)
  - Default: `true`
- `confirm` (`boolean`) - Confirm deletion - set to true to actually delete (for cleanup action)
  - Default: `false`

---
