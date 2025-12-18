# ADR-082 & ADR-083 Implementation Checklist

Combined implementation tracking for User Scoping (ADR-082) and Artifact Persistence (ADR-083).

## Phase 1: Schema Foundation (ADR-082)

### Database Migration
- [x] Create migration file `034_user_scoping_groups.sql`
- [x] Create `kg_auth.groups` table
- [x] Create `kg_auth.user_groups` table
- [x] Create `kg_auth.resource_grants` table
- [x] Insert system user (ID 1, username='system')
- [x] Insert `public` group (ID 1)
- [x] Insert `admins` group (ID 2)
- [x] Alter `kg_auth.users_id_seq` to restart at 1000
- [x] Create `kg_auth.groups_id_seq` starting at 1000
- [x] Update operator admin creation to use new sequence (no changes needed - uses sequence)
- [x] Fix migration 020 to create system user (ID 1) and admin user (ID 1000)

### Permission Resolution
- [x] Extend `has_access()` function to check:
  - [x] Direct user grants
  - [x] Group grants (new ADR-082)
  - [x] Public group grants (implicit membership)
- [x] Add indexes for grant lookups
- [ ] Test permission resolution order

### Default Group Memberships
- [x] Add admin user (ID 1000) to admins group in migration 034
- [x] Update operator `configure.py` to add new admins to admins group
- [x] Update API `POST /users` to add admin-role users to admins group

## Phase 2: Artifact Schema (ADR-083)

### Database Migration
- [x] Create migration file `035_artifact_persistence.sql`
- [x] Create `kg_api.query_definitions` table
- [x] Create `kg_api.artifacts` table
- [x] Add indexes for artifact queries
- [x] Add constraint for inline_result OR garage_key

### Garage Integration
- [x] Create `ArtifactStorageService` class
- [x] Implement `store()` and `prepare_for_storage()` methods
- [x] Implement `get()` and `get_by_id()` methods
- [x] Route small (<10KB) to inline, large to Garage via `prepare_for_storage()`
- [x] Key structure: `artifacts/{artifact_type}/{artifact_id}.json`
- [x] Add factory function `get_artifact_storage()` and exports

## Phase 3a: Core Artifact API + CLI Validation

### Artifact API Endpoints (ADR-083)
- [x] `GET /artifacts` - List artifacts (metadata only)
- [x] `GET /artifacts/{id}` - Get artifact metadata
- [x] `GET /artifacts/{id}/payload` - Get artifact payload (inline or Garage)
- [x] `POST /artifacts` - Create artifact
- [x] `DELETE /artifacts/{id}` - Delete artifact

### CLI Commands (validation)
- [x] `kg artifact list` - List user's artifacts
- [x] `kg artifact show <id>` - Show artifact metadata
- [x] `kg artifact payload <id>` - Get artifact payload
- [x] `kg artifact create` - Create test artifact (for validation)
- [x] `kg artifact delete <id>` - Delete artifact

## Phase 3b: Grants & Groups API

### Grant Management (ADR-082)
- [x] `POST /grants` - Create grant
- [x] `GET /resources/{type}/{id}/grants` - List grants for resource
- [x] `DELETE /grants/{id}` - Revoke grant
- [x] `POST /groups` - Create group
- [x] `GET /groups` - List groups
- [x] `GET /groups/{id}/members` - List group members
- [x] `POST /groups/{id}/members` - Add member
- [x] `DELETE /groups/{id}/members/{user_id}` - Remove member

### CLI Commands (validation)
- [x] `kg group list` - List groups
- [x] `kg group members <id>` - List group members
- [x] `kg group create` - Create group
- [x] `kg group add-member` - Add member to group
- [x] `kg group remove-member` - Remove member from group

## Phase 3c: Query Definitions API

### Query Definitions (ADR-083)
- [x] `GET /query-definitions` - List definitions
- [x] `GET /query-definitions/{id}` - Get definition by ID
- [x] `POST /query-definitions` - Save definition
- [x] `PUT /query-definitions/{id}` - Update definition
- [x] `DELETE /query-definitions/{id}` - Delete definition
- [ ] `POST /artifacts/{id}/regenerate` - Re-run computation from definition (deferred to Phase 4)

### CLI Commands (validation)
- [x] `kg query-def list` - List query definitions
- [x] `kg query-def show <id>` - Show definition details
- [x] `kg query-def create` - Create definition
- [x] `kg query-def delete <id>` - Delete definition

## Code Review Fixes (Post Phase 3)

Issues identified in code review of commits ac658a3b..ebdd1b86.

### Major Issues (Required before merge)

- [x] **#1: Grant ownership verification** (`api/api/routes/grants.py`)
  - Added `verify_resource_ownership()` helper function
  - Checks resource tables by type to get owner_id
  - Allows resource owners to create/revoke grants
  - Admins can manage all grants

- [x] **#2: System resource NULL handling** (`api/api/routes/grants.py`)
  - Policy: NULL owner_id treated as system-owned (SYSTEM_USER_ID = 1)
  - Only admins can manage grants for system resources
  - Consistent with Unix-style ID ranges (1-999 = system)

### Minor Issues (Recommended before merge)

- [x] **#3: Garage deletion error logging** (`api/api/routes/artifacts.py`)
  - Added try/except with logger.warning for Garage delete failures
  - References maintenance job for orphan cleanup

- [x] **#4: Composite index for artifact queries** (`schema/migrations/035_artifact_persistence.sql`)
  - Added `idx_artifacts_owner_repr (owner_id, representation, created_at DESC)`

- [x] **#5: Double JSON serialization** (`api/api/lib/garage/artifact_storage.py`)
  - Documented as acceptable trade-off in docstring
  - ~1-2ms overhead for small payloads is negligible
  - Large payloads only serialize once (to Garage)

- [x] **#6: Public group members endpoint** (`api/api/routes/grants.py`)
  - Added `include_implicit` query parameter
  - With `include_implicit=true`, returns all users as public group members
  - Added `implicit_membership` field to response model

---

## Phase 4: Async Job Integration (ADR-083)

### Job Queue Changes
- [x] Add `artifact_id` column to jobs (Migration 036)
- [x] Update `job_queue.update_job()` to support artifact_id field
- [x] Note: `user_id` column already exists (Migration 020)

### Worker Artifact Helper
- [x] Create `artifact_helper.py` module
- [x] Implement `create_job_artifact()` function
- [x] Implement `get_job_user_id()` helper

### Projection Worker Integration
- [x] Add `create_artifact` flag to job_data
- [x] Create artifact on completion when flag is set
- [x] Link artifact to job via artifact_id
- [x] Include artifact_id in job result

### Polarity Analysis Async Job
- [x] Create `polarity_worker.py` with artifact creation support
- [x] Add `/polarity-axis/jobs` endpoint to queries.py
- [x] Update CLI `kg polarity analyze --save-artifact` flag
- [x] Register polarity worker in main.py

### Artifact Regeneration
- [x] Add `POST /artifacts/{id}/regenerate` endpoint
- [x] Support regeneration for polarity_analysis and projection types
- [x] Trigger async job with stored parameters

### Artifact Cleanup Worker
- [x] Create `artifact_cleanup_worker.py`
- [x] Create `ArtifactCleanupLauncher` in launchers/
- [x] Add scheduled job entry (daily at 2 AM)
- [x] Register worker in main.py

## Phase 5: Web Client (ADR-083)

### Zustand Store Refactor
- [ ] Create `useArtifactStore` (metadata only)
- [ ] Create `useQueryDefinitionStore`
- [ ] Implement `loadArtifacts()` action
- [ ] Implement `persistArtifact()` action

### LocalStorage Caching
- [ ] Implement `fetchArtifactPayload()` with cache
- [ ] Implement LRU eviction (50MB limit)
- [ ] Validate cache against `graph_epoch`

### Component Updates
- [ ] Update `PolarityExplorerWorkspace` to use artifacts
- [ ] Update `BlockEditorWorkspace` to use query_definitions
- [ ] Update `ReportWorkspace` to use artifacts
- [ ] Add stale/missing artifact UI states

### Migrate Existing Stores
- [ ] Migrate `polarityState` → artifacts
- [ ] Migrate `blockDiagramStore` → query_definitions
- [ ] Migrate `reportStore` → artifacts
- [ ] Provide migration utility for localStorage data

## Phase 6: CLI/MCP (ADR-083)

### CLI Commands
- [ ] `kg artifact list` - List user's artifacts
- [ ] `kg artifact show <id>` - Show artifact metadata
- [ ] `kg artifact payload <id>` - Get artifact payload
- [ ] `kg artifact delete <id>` - Delete artifact
- [ ] Update existing commands to optionally save as artifact

### MCP Tools
- [ ] Add artifact listing to MCP
- [ ] Add artifact recall to MCP
- [ ] Enable AI agents to reuse stored analyses

## Phase 7: Cleanup & Maintenance

### Scheduled Jobs
- [x] Create `artifact_cleanup_worker.py`
- [x] Delete expired artifacts (past `expires_at`)
- [ ] Delete orphaned Garage objects (future enhancement)
- [x] Schedule daily at 2 AM

### Monitoring
- [ ] Add metrics for artifact storage usage
- [ ] Add metrics for cache hit/miss rates
- [ ] Add alerts for Garage storage growth

---

## Dependencies

```
Phase 1 (Schema) ─┬─► Phase 2 (Artifacts)
                  │
                  └─► Phase 3 (API) ─► Phase 4 (Jobs)
                                    │
                                    └─► Phase 5 (Web)
                                    │
                                    └─► Phase 6 (CLI/MCP)

Phase 7 (Cleanup) can start after Phase 4
```

## Notes

- Fresh deployment, no migration concerns for existing users
- Graph epoch = `graph_change_counter` from Migration 033
- Terminology: Use `graph_epoch` consistently in new code

## Related Files

- ADR-082: `docs/architecture/ADR-082-user-scoping-artifact-ownership.md`
- ADR-083: `docs/architecture/ADR-083-artifact-persistence-pattern.md`
- Existing projection storage: `api/api/lib/garage/projection_storage.py`
- Existing auth schema: `schema/00_baseline.sql` (kg_auth.*)
- Graph change counter: Migration 033
