# job

> Auto-generated from MCP tool schema

### job

Manage ingestion jobs: get status, list jobs, approve, or cancel. Use action parameter to specify operation.

**Parameters:**

- `action` (`string`) **(required)** - Operation: "status" (get job status), "list" (list jobs), "approve" (approve job), "cancel" (cancel job)
  - Allowed values: `status`, `list`, `approve`, `cancel`
- `job_id` (`string`) - Job ID (required for status, approve, cancel)
- `status` (`string`) - Filter by status for list (pending, awaiting_approval, running, completed, failed)
- `limit` (`number`) - Max jobs to return for list (default: 50)
  - Default: `50`

---
