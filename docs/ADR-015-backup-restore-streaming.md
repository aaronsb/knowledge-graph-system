# ADR-015: Backup/Restore Streaming Architecture

**Status:** Accepted
**Date:** 2025-10-08
**Deciders:** System Architecture
**Related:** ADR-012 (API Server), ADR-013 (Unified Client)

## Context

The current backup/restore implementation has architectural issues that violate client-server separation:

**Current Problems:**
1. **Server-side storage:** Backups created in `./backups` on API server
2. **Filename-based restore:** Client sends filename, expects server-side file
3. **No client-side backups:** Users don't have local copies
4. **Poor separation:** Client can't manage its own backups
5. **No progress feedback:** Large backups have no upload/download indication
6. **Memory concerns:** Loading entire backups into memory for processing

**POC Legacy:**
The original POC had excellent backup/restore UX with progress bars and detailed feedback during restore operations. We need to preserve this quality while implementing proper architecture.

## Decision

Implement **client-side backup storage with streaming upload/download**:

### Architecture Pattern

```
Backup Flow (Download):
Client                          API Server
  |                                |
  |------ POST /admin/backup ----->|
  |       (type, ontology)          |
  |                                 |--- Create backup in memory/temp
  |                                 |--- Stream JSON data (chunked)
  |<----- Stream backup data -------|
  |       + progress updates        |
  |                                 |--- Delete temp file
  |--- Save to local directory      |
  |    (~/.local/share/kg/backups)  |
  |--- Show download progress       |

Restore Flow (Upload):
Client                          API Server
  |                                |
  |--- Read backup from local       |
  |                                |
  |------ POST /admin/restore ----->|
  |       (multipart upload)        |
  |       Stream file chunks        |
  |                                 |--- Save to temp (/tmp/restore_<uuid>)
  |<----- Upload progress ---------|--- Run integrity checks
  |                                 |--- Restore with progress updates
  |<----- Poll restore status ----->|
  |       (nodes, relationships)    |
  |                                 |--- Delete temp file
  |<----- Complete ----------------|
```

### Key Principles

1. **Client-Side Storage**
   - All backups stored in configured directory (`backup_dir` from config)
   - Default: `~/.local/share/kg/backups`
   - User has full control over backup location
   - Backups survive API server restarts/migrations

2. **Streaming Transfer**
   - Use HTTP chunked transfer encoding
   - No loading entire backup into memory
   - Progress feedback during transfer
   - Support for large backups (100+ MB)

3. **Ephemeral Server Files**
   - Server never stores backups permanently
   - Temp files only during active operation
   - UUID-based temp filenames to avoid conflicts
   - Mandatory cleanup on completion/error

4. **Integrity Checks**
   - Separate module for backup validation
   - Run before restore starts
   - Check format, completeness, external deps
   - Report warnings/issues to user

5. **Progress Tracking**
   - Download/upload progress bars
   - Restore progress (nodes, relationships)
   - Match POC quality (detailed feedback)
   - Poll-based status updates

## Implementation

### Phase 1: Backup Download (Priority: High)

**Client Changes:**
```typescript
// client/src/api/client.ts
async createBackup(request: BackupRequest): Promise<void> {
  const response = await this.client.post('/admin/backup', request, {
    responseType: 'stream'
  });

  // Stream to configured directory with progress
  const config = getConfig();
  const backupPath = path.join(config.getBackupDir(), filename);

  // Show progress bar
  return streamToFile(response.data, backupPath, (progress) => {
    updateProgressBar(progress);
  });
}
```

**Server Changes:**
```python
# src/api/routes/admin.py
@router.post("/admin/backup")
async def create_backup(request: BackupRequest):
    # Create backup in memory or temp file
    backup_data = await create_backup_data(request)

    # Stream response
    return StreamingResponse(
        backup_generator(backup_data),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )
```

### Phase 2: Restore Upload (Priority: High)

**Client Changes:**
```typescript
// client/src/api/client.ts
async restoreBackup(request: RestoreRequest, filePath: string): Promise<RestoreResponse> {
  const form = new FormData();
  form.append('file', fs.createReadStream(filePath));
  form.append('username', request.username);
  form.append('password', request.password);

  const response = await this.client.post('/admin/restore', form, {
    headers: form.getHeaders(),
    onUploadProgress: (progressEvent) => {
      updateProgressBar(progressEvent);
    }
  });

  // Poll for restore progress
  return pollRestoreProgress(response.data.job_id);
}
```

**Server Changes:**
```python
# src/api/routes/admin.py
from fastapi import UploadFile

@router.post("/admin/restore")
async def restore_backup(
    file: UploadFile,
    username: str = Form(...),
    password: str = Form(...),
    overwrite: bool = Form(False)
):
    # Authenticate
    if not authenticate(username, password):
        raise HTTPException(401, "Authentication failed")

    # Save to temp location
    temp_path = f"/tmp/restore_{uuid.uuid4()}.json"
    with open(temp_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # Run integrity checks
        integrity = check_backup_integrity(temp_path)
        if not integrity.valid:
            return {"error": integrity.errors}

        # Perform restore with progress tracking
        job_id = enqueue_restore_job(temp_path, overwrite)
        return {"job_id": job_id, "status": "queued"}

    finally:
        # Cleanup happens in worker after restore completes
        pass
```

### Phase 3: Integrity Checks (Priority: Medium)

**Create separate module:**
```python
# src/api/services/integrity_check.py
class BackupIntegrity:
    valid: bool
    errors: List[str]
    warnings: List[str]
    external_deps: int

def check_backup_integrity(backup_path: str) -> BackupIntegrity:
    """
    Validate backup before restore.

    Checks:
    - JSON format validity
    - Required fields present
    - External concept references
    - Data consistency
    """
```

### Phase 4: Progress Tracking (Priority: Medium)

**Use existing job queue pattern:**
```python
# src/api/workers/restore_worker.py
def run_restore_worker(job_data: Dict, job_id: str, job_queue):
    # Update progress during restore
    job_queue.update_job(job_id, {
        "progress": {
            "stage": "restoring_nodes",
            "nodes_restored": 1250,
            "nodes_total": 5000,
            "percent": 25
        }
    })
```

**Client polls for updates:**
```typescript
// Match ingestion progress pattern
const finalJob = await client.pollJob(restoreJobId, (job) => {
  if (job.progress) {
    spinner.text = `Restoring... ${job.progress.percent}% ` +
                   `(${job.progress.nodes_restored}/${job.progress.nodes_total} nodes)`;
  }
});
```

### Phase 5: Temp File Cleanup (Priority: High)

**Cleanup strategy:**
```python
# src/api/workers/restore_worker.py
def run_restore_worker(job_data: Dict, job_id: str, job_queue):
    temp_path = job_data["temp_file"]

    try:
        # Perform restore
        result = restore_from_backup(temp_path)
        return result

    finally:
        # Always cleanup, even on error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
```

**Startup cleanup:**
```python
# src/api/main.py
@app.on_event("startup")
async def cleanup_old_temp_files():
    """Clean up abandoned restore files on startup"""
    temp_dir = "/tmp"
    for file in glob.glob(f"{temp_dir}/restore_*.json"):
        # Delete files older than 24 hours
        if is_older_than(file, hours=24):
            os.unlink(file)
```

## Consequences

### Positive

1. **Proper Separation**
   - Client manages backups locally
   - Server is stateless (no backup storage)
   - Users control backup location via config

2. **Better UX**
   - Progress bars for large operations
   - Local backup management (list, delete, organize)
   - No surprises (backups stored where user expects)

3. **Performance**
   - Streaming prevents memory exhaustion
   - Chunked transfer for large files
   - No artificial size limits

4. **Security**
   - Temp files cleaned up automatically
   - No persistent sensitive data on server
   - Authentication required for restore

5. **Reliability**
   - Backups survive API restarts
   - Client-side backup retention policies
   - Integrity checks before restore

### Negative

1. **Complexity**
   - Multipart upload handling required
   - Progress polling adds complexity
   - More error cases to handle

2. **Migration**
   - Existing server-side backups need migration
   - Users must copy backups to local directory
   - Breaking change for current users

3. **Network**
   - Large backups consume bandwidth
   - Upload time for restore operations
   - Requires stable connection for large files

### Neutral

1. **Storage Location**
   - Client-side storage is standard pattern
   - Aligns with other CLI tools (e.g., Docker, kubectl)
   - User has full control

## Alternatives Considered

### 1. Base64 Encoding

**Rejected:** 33% size overhead, memory allocation for encoding/decoding, no progress feedback

```python
# Would require loading entire backup into memory
backup_b64 = base64.b64encode(backup_json)
# 33% larger payload
```

### 2. Server-Side Storage Only

**Rejected:** Violates client-server separation, backups lost on server migration, user has no control

### 3. Both Client and Server Storage

**Rejected:** Unnecessary duplication, sync issues, unclear source of truth

### 4. External Storage (S3, etc.)

**Rejected:** Adds external dependency, complexity for single-user deployments, cost

## Migration Path

### For Existing Users

1. **Backward Compatibility Period:**
   - Keep server-side backup creation for 1 release
   - Add deprecation warning
   - Provide migration script

2. **Migration Script:**
   ```bash
   # scripts/migrate-backups.sh
   # Copy server backups to client directory
   cp ./backups/* ~/.local/share/kg/backups/
   ```

3. **Documentation:**
   - Update README with new backup location
   - Add migration guide
   - Update CLI help text

### Release Plan

**v0.2.0:** (Next Release)
- Phase 1: Backup download
- Phase 2: Restore upload
- Deprecation warnings on old approach

**v0.3.0:** (Following Release)
- Phase 3: Integrity checks
- Phase 4: Progress tracking
- Phase 5: Cleanup improvements

**v0.4.0:** (Future)
- Remove server-side backup storage
- Remove backward compatibility code

## References

- **ADR-012:** API Server Architecture (job queue pattern)
- **ADR-013:** Unified TypeScript Client (config management)
- **File:** `docs/BACKUP_RESTORE.md` (user guide, TODO)
- **File:** `client/src/cli/admin.ts` (implementation)
- **File:** `src/api/routes/admin.py` (API endpoints)

## Notes

**Progress Bar Quality:**
The POC backup tool had excellent progress feedback showing:
- Nodes being restored
- Relationships created
- Current operation stage
- Percentage complete

This quality should be maintained in the new implementation. Users appreciate seeing what's happening during long operations.

**Config Integration:**
The backup directory is already configurable via `kg config`:
```bash
kg config list  # Shows backup_dir
kg config set backup_dir /path/to/backups
```

This ADR formalizes using that configured directory as the authoritative backup location.
