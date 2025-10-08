# TODO: Backup/Restore Streaming Architecture

## Current State (Incomplete)
- ✅ Client lists backups from configured local directory
- ❌ `kg admin backup` creates backup on server (client should download it)
- ❌ `kg admin restore` sends filename (should stream file data)
- ❌ No file upload/download progress indicators
- ❌ Server doesn't clean up temp files

## Target Architecture

### Backup Flow (Download from Server)
```
Client                          API Server
  |                                |
  |------ POST /admin/backup ----->|
  |       (type, ontology)          |
  |                                 |--- Create backup in memory/temp
  |                                 |--- Stream backup data
  |<----- Stream backup JSON -------|
  |       (chunked transfer)        |
  |                                 |--- Delete temp file
  |--- Save to local directory      |
  |    (~/.local/share/kg/backups)  |
  |                                 |
  |--- Show progress bar            |
```

**Client Changes:**
1. `kg admin backup` downloads backup data from API
2. Stream to configured directory with progress bar
3. Save with timestamp filename

**Server Changes:**
1. Stream backup data instead of saving to ./backups
2. No server-side backup storage (ephemeral)
3. Clean up any temp files immediately

### Restore Flow (Upload to Server)
```
Client                          API Server
  |                                |
  |--- Read backup from local dir  |
  |                                |
  |------ POST /admin/restore ----->|
  |       (multipart file upload)   |
  |       Stream file chunks        |
  |                                 |--- Save to temp location
  |                                 |--- Run integrity checks
  |<----- Upload progress ---------|    (separate module)
  |                                 |
  |------ Poll restore status ----->|--- Restore with progress
  |<----- Progress updates ---------|    - Nodes restored
  |       (% complete, stats)       |    - Relationships created
  |                                 |    - Prune/stitch/defer
  |                                 |
  |<----- Restore complete ---------|
  |                                 |--- Delete temp file
```

**Client Changes:**
1. `kg admin restore` reads backup from configured directory (or --path)
2. Stream file to API with multipart upload
3. Show upload progress bar
4. Poll restore status with progress display
5. Show same rich progress as POC backup tool had

**Server Changes:**
1. Accept multipart file upload in `/admin/restore`
2. Save to temp location (e.g., `/tmp/restore_<uuid>.json`)
3. Run integrity checks (separate module)
4. Stream restore progress updates
5. Support prune/stitch/defer operations
6. Delete temp file after completion (success or failure)

## Implementation Tasks

### Phase 1: Backup Download (Priority: High)
- [ ] Update API `/admin/backup` to stream JSON data
- [ ] Update client `backup` command to download and save
- [ ] Add download progress bar
- [ ] Remove server-side ./backups directory creation

### Phase 2: Restore Upload (Priority: High)
- [ ] Update API `/admin/restore` to accept multipart upload
- [ ] Add file upload handling (express-fileupload or multer)
- [ ] Save to temp location with UUID filename
- [ ] Update client `restore` command to upload file
- [ ] Add upload progress bar

### Phase 3: Integrity Checks (Priority: Medium)
- [ ] Create separate integrity check module
- [ ] Check backup format validity
- [ ] Check for external dependencies
- [ ] Assess completeness
- [ ] Return warnings/issues before restore

### Phase 4: Progress Tracking (Priority: Medium)
- [ ] Add restore progress tracking to job queue
- [ ] Stream progress updates during restore
- [ ] Client polls and displays progress
- [ ] Show nodes restored, relationships created, etc.
- [ ] Match POC backup tool progress display quality

### Phase 5: Cleanup (Priority: High)
- [ ] Ensure temp files deleted on success
- [ ] Ensure temp files deleted on failure
- [ ] Ensure temp files deleted on API restart
- [ ] Add temp file expiration (cleanup old uploads)

## Memory & Performance Considerations

**Streaming Benefits:**
- No need to load entire backup into memory
- Chunked transfer encoding for large files
- Progress feedback without memory overhead

**File Size Limits:**
- Configure max upload size (e.g., 500MB)
- Stream processing for large backups
- Disk space checks before restore

**Temp File Management:**
- UUID-based filenames to avoid conflicts
- Cleanup on process exit
- Periodic cleanup of abandoned files (>24h old)

## Progress Display Examples

### Backup Progress
```
💾 Creating backup...
  Collecting data...              [████████████████] 100%
  Writing backup...               [████████----] 75%

  Downloaded: 15.3 MB

✓ Backup saved: backup_20251008_123045.json
```

### Restore Progress
```
📥 Uploading backup...
  Upload progress...              [████████████████] 100%
  Uploaded: 15.3 MB

🔍 Running integrity checks...
  ✓ Format valid
  ✓ No external dependencies

🔄 Restoring database...
  Nodes restored...               [████████----] 2,547 / 3,200
  Relationships created...        [████████----] 5,124 / 6,890
  Progress: 78% complete

✓ Restore complete!
```

## Security Considerations

**Authentication:**
- Restore requires username/password (already implemented)
- Consider API key for backup downloads (Phase 2)

**Validation:**
- Verify backup format before processing
- Sanitize filenames to prevent path traversal
- Limit upload size to prevent DoS

**Cleanup:**
- Always delete temp files (even on error)
- Don't leave sensitive data in /tmp

## Related Files

**Client:**
- `client/src/cli/admin.ts` - Backup/restore commands
- `client/src/api/client.ts` - API methods

**Server:**
- `src/api/routes/admin.py` - Backup/restore endpoints
- `src/api/services/backup_service.py` - TODO: Create
- `src/api/services/integrity_check.py` - TODO: Create
- `src/api/workers/restore_worker.py` - TODO: Create

## Decision: Streaming vs. Base64

**Rejected: Base64 encoding**
- 33% size overhead
- Memory allocation for encoding/decoding
- No progress feedback during transfer

**Chosen: Multipart file upload + streaming**
- Native HTTP chunked transfer
- Progress tracking built-in
- No memory overhead
- Standard patterns (multer/express-fileupload)
