# Web Workspaces Implementation Plan

**Branch:** `feature/web-workspaces`
**Created:** 2025-12-07
**Status:** In Progress

## Overview

Implement the placeholder workspaces in the web UI: Ingest, Jobs, and Preferences. The API endpoints already exist and are tested via the CLI - this is purely frontend work.

## Progress Tracking

- [x] **Phase 1: Shared Foundation** (completed 2025-12-07)
- [x] **Phase 2: IngestWorkspace** (completed 2025-12-07)
- [x] **Phase 3: JobsWorkspace** (completed 2025-12-07)
- [ ] **Phase 4: PreferencesWorkspace**

---

## Phase 1: Shared Foundation

### Types
- [x] `web/src/types/jobs.ts` - Job types (JobStatus, JobProgress, JobResult, etc.)
- [x] `web/src/types/ingest.ts` - Ingest types (IngestRequest, IngestResponse, DuplicateJobResponse)

### API Client Methods (`web/src/api/client.ts`)
- [x] `ingestFile(file, options)` - Multipart file upload
- [x] `ingestText(text, options)` - Raw text ingestion
- [x] `listJobs(filters)` - List jobs with status/user filters
- [x] `getJob(jobId)` - Get job status and details
- [x] `approveJob(jobId)` - Approve job for processing
- [x] `cancelJob(jobId)` - Cancel a job
- [x] `streamJobProgress(jobId, callbacks)` - SSE streaming with polling fallback
- [x] `pollJobUntilComplete(jobId, callbacks)` - Polling fallback
- [x] `listOntologies()` - Get available ontologies for selector

### Common Components (`web/src/components/workspaces/common/`)
- [x] `StatusBadge.tsx` - Consistent job status display (icons + colors)
- [x] `CostDisplay.tsx` - Format cost estimates ($0.15 - $0.25)
- [x] `ProgressIndicator.tsx` - Reusable progress bar with percentage
- [x] `index.ts` - Re-exports for easy importing

---

## Phase 2: IngestWorkspace

**Location:** `web/src/components/ingest/`

### Components
- [x] `IngestWorkspace.tsx` - Main workspace (all-in-one implementation)

### Features
- [x] Drag-and-drop file upload
- [x] Manual file picker fallback
- [x] Ontology selection (existing or new)
- [x] Chunking options (target words, overlap)
- [x] Processing mode (serial/parallel)
- [x] Force re-ingest option
- [x] Duplicate detection handling
- [x] Cost estimate before approval
- [x] Real-time progress tracking (SSE with polling fallback)
- [x] Success/error feedback

### State Management
- [x] Local component state (simpler than Zustand for single-component use)

---

## Phase 3: JobsWorkspace

**Location:** `web/src/components/jobs/`

### Components
- [x] `JobsWorkspace.tsx` - Main workspace (all-in-one implementation)

### Features
- [x] Job list with filtering
- [x] Filter by status (all, pending, processing, completed, failed, cancelled)
- [x] Real-time status updates (auto-refresh when active jobs present)
- [x] Job detail view with:
  - Metadata (ID, type, timestamps, duration)
  - Pre-ingestion analysis (file stats, cost estimate, warnings)
  - Progress indicator (chunks, concepts, relationships)
  - Results (stats, actual cost)
  - Error messages (if failed)
- [x] Approve action (for awaiting_approval jobs)
- [x] Cancel action (with confirmation)
- [x] Responsive layout (list-only on mobile, split view on desktop)
- [x] Polling-based updates (3s interval for active jobs)

### State Management
- [x] Local component state (simpler than Zustand for single-component use)

---

## Phase 4: PreferencesWorkspace

**Location:** `web/src/components/preferences/`

### Existing (already implemented)
- [x] Theme selection (Light/Dark/System)

### Components to Add
- [ ] `SearchPreferences.tsx` - Search result display options
- [ ] `IngestDefaults.tsx` - Default ingest settings
- [ ] `DisplayPreferences.tsx` - UI display options

### Features
- [ ] Search preferences:
  - [ ] Show evidence quotes in results
  - [ ] Show images inline
  - [ ] Default result limit
- [ ] Ingest defaults:
  - [ ] Auto-approve new jobs
  - [ ] Default ontology
  - [ ] Default chunk size
- [ ] Display preferences:
  - [ ] Compact vs expanded views
  - [ ] Animation settings

### State Management
- [ ] Enhance `web/src/store/preferencesStore.ts` (or themeStore)
- [ ] localStorage persistence

---

## API Endpoints Reference

All endpoints already exist and work via CLI:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/ingest` | POST | File upload (multipart) |
| `/ingest/text` | POST | Raw text ingestion |
| `/jobs` | GET | List jobs with filters |
| `/jobs/{id}` | GET | Get job status |
| `/jobs/{id}/approve` | POST | Approve job |
| `/jobs/{id}` | DELETE | Cancel job |
| `/jobs/{id}/stream` | GET | SSE progress stream |
| `/ontology/` | GET | List ontologies |

---

## Design Patterns

### Follow existing patterns from:
- `web/src/explorers/common/` - Shared panel components
- `web/src/components/polarity/` - Complex workspace example
- `web/src/store/graphStore.ts` - Zustand store pattern
- `web/src/hooks/useGraphData.ts` - React Query hooks

### UI Consistency
- Use existing Tailwind classes and color scheme
- Match panel styling from explorers
- Use same icon library (Lucide React)
- Consistent spacing and typography

---

## Notes

- **No API changes needed** - All endpoints tested via CLI
- **Client-side preferences** - localStorage for now, DB persistence later
- **SSE with fallback** - Use EventSource for real-time, poll if unavailable
- **Type reuse** - Reference CLI types but create web-specific versions

---

## Session Log

### 2025-12-07
- Created feature branch `feature/web-workspaces`
- Created this plan document
- Researched existing web UI structure and CLI implementations
- **Phase 1 completed:**
  - Created `web/src/types/jobs.ts` with full job lifecycle types
  - Created `web/src/types/ingest.ts` with ingest request/response types
  - Added ingest methods to API client (ingestFile, ingestText, listOntologies)
  - Added job methods to API client (getJob, listJobs, approveJob, cancelJob)
  - Added SSE streaming (streamJobProgress) and polling fallback (pollJobUntilComplete)
  - Created common components: StatusBadge, CostDisplay, ProgressIndicator
  - All components use theme-aware Tailwind classes (dark: variants)
- **Phase 2 completed:**
  - Implemented IngestWorkspace with drag-drop file upload
  - Ontology selector with create-new option
  - Advanced options (chunking, processing mode, auto-approve)
  - Duplicate detection and force re-ingest
  - Real-time job progress monitoring
  - Success/error state handling
- **Phase 3 completed:**
  - Implemented JobsWorkspace with job list and detail view
  - Status filter tabs (All, Pending, Processing, Completed, Failed, Cancelled)
  - Auto-refresh for active jobs (3s polling interval)
  - Job detail panel with full metadata, analysis, progress, results
  - Approve/cancel actions with loading states
  - Responsive split-view layout
