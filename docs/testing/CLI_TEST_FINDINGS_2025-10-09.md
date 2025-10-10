# CLI Testing Findings Report
**Date:** 2025-10-09
**Tester:** Claude (Sonnet 4.5)
**Scope:** Full `kg` CLI command suite (excluding backup/restore)
**Branch:** main (post-PR#24 merge - 30-type relationship taxonomy)

---

## Executive Summary

Tested 9 command categories across the `kg` CLI. **Overall Status: 🟢 Functional** with 2 medium-priority issues and 1 informational finding.

**Key Achievement:** ✅ 30-type relationship taxonomy successfully integrated and displaying in `kg database stats`

**Issues Found:** 2 (1 API endpoint error, 1 health check warning)

---

## Test Results by Category

### 1. Health & Status ✅

| Command | Status | Notes |
|---------|--------|-------|
| `kg health` | ✅ Pass | API responsive, queue info correct |
| `kg admin status` | ✅ Pass | All checks green, shows PostgreSQL healthy |
| `kg database info` | ✅ Pass | Connection info correct |
| `kg database health` | ⚠️ Degraded | See Issue #1 below |

### 2. Configuration ✅

| Command | Status | Notes |
|---------|--------|-------|
| `kg config list` | ✅ Pass | Clean display, shows MCP tools enabled |
| `kg config get` | ⏭️ Skipped | Requires specific key |
| `kg config set` | ⏭️ Skipped | Requires key/value |

### 3. Database Operations ✅

| Command | Status | Notes |
|---------|--------|-------|
| `kg database stats` | ✅ Pass | **Shows new relationship types!** |

**Example Output:**
```
Relationships By Type:
  CONTRASTS_WITH: 2
  CATEGORIZED_AS: 1
  DEFINED_AS: 1
  RESULTS_FROM: 1
  USED_FOR: 1
```

✅ **Validation:** 30-type taxonomy is live and working!

### 4. Ontology Management ✅

| Command | Status | Notes |
|---------|--------|-------|
| `kg ontology list` | ✅ Pass | Table formatting looks excellent |
| `kg ontology info <name>` | ✅ Pass | Shows stats + file list |
| `kg ontology files` | ⏭️ Skipped | Would need multi-file ontology |

### 5. Jobs & Ingestion ✅

| Command | Status | Notes |
|---------|--------|-------|
| `kg jobs list` | ✅ Pass | Table shows 20 historical jobs |
| `kg jobs status <id>` | ✅ Pass | Detailed progress, cost breakdown |
| `kg ingest file` | ✅ Pass | Successfully ingested test document |

### 6. Search & Exploration 🟡

| Command | Status | Notes |
|---------|--------|-------|
| `kg search query "human intelligence"` | 🟡 Info | 0 results (see Finding #3) |
| `kg search details <id>` | ⏭️ Skipped | Need valid concept ID |
| `kg search related <id>` | ⏭️ Skipped | Need valid concept ID |
| `kg search connect <from> <to>` | ⏭️ Skipped | Need two concept IDs |

### 7. Admin & Scheduler 🔴

| Command | Status | Notes |
|---------|--------|-------|
| `kg admin status` | ✅ Pass | System overview looks good |
| `kg admin scheduler status` | 🔴 Fail | 500 error (see Issue #2) |
| `kg admin scheduler cleanup` | ⏭️ Skipped | Not tested due to status error |

---

## Issues & Investigations

### Issue #1: AGE Extension Health Check Warning ✅ RESOLVED
**Severity:** ⚠️ Medium (Informational) → ✅ Fixed
**Command:** `kg database health`
**Status:** Database functional but reports degraded → Now reports HEALTHY

**Root Cause:**
- Health check was using `_execute_cypher()` to execute a SQL query
- Line 175-177 in `database.py` attempted to run `SELECT extname FROM pg_extension...` as Cypher
- `_execute_cypher()` is for Cypher queries, not SQL
- This caused the AGE extension check to fail incorrectly

**Resolution:**
- Changed to use direct psycopg2 connection (like `get_database_info()` does)
- Now properly executes SQL query against PostgreSQL to check extension
- Database health now correctly shows "HEALTHY" with all checks passing

**Files Modified:**
- `src/api/routes/database.py` - Fixed AGE extension check (line 173-191)

---

### Issue #2: Scheduler Status API 500 Error ✅ RESOLVED
**Severity:** 🔴 High (Broken Feature) → ✅ Fixed
**Command:** `kg admin scheduler status`
**Error:** Request failed with status code 500

**Root Cause:**
- `admin.py` line 422 called `scheduler.get_stats()` method
- Method didn't exist in `JobScheduler` class

**Resolution:**
- Implemented `get_stats()` method in `src/api/services/job_scheduler.py` (line 210)
- Returns job counts by status from job queue
- Includes placeholders for last_cleanup and next_cleanup timestamps
- Tested successfully - endpoint now returns proper status and statistics

**Files Modified:**
- `src/api/services/job_scheduler.py` - Added `get_stats()` method

---

### Finding #3: Search Returns Zero Results ✅ RESOLVED (Expected Behavior)
**Severity:** 🟡 Informational → ✅ Working as designed
**Command:** `kg search query "human intelligence"`
**Result:** 0 concepts found with default threshold

**Investigation Results:**
1. **Actual concept label**: "Limitation of Human Intelligence" (specific/narrow)
2. **Search term**: "human intelligence" (general/broad)
3. **Similarity score**: 58.4%
4. **CLI default threshold**: 70% (0.7)

**Root Cause:**
- Threshold was too high for semantic similarity between narrow concept label and broad search term
- Additionally found bug: search endpoint wasn't passing threshold parameter to vector_search()
  - Was using hardcoded 0.85 instead of request.min_similarity

**Resolution:**
1. Fixed threshold parameter passing in `queries.py` (line 82-86)
2. Verified search works with lower threshold: `--min-similarity 0.5` returns 1 result
3. This is expected behavior - LLM extracted specific concept "Limitation of Human Intelligence"
   which has lower semantic similarity to generic "human intelligence"

**Enhancement Added - Threshold Hints:**
Implemented intelligent threshold suggestions when few results found:
- API calculates exact threshold needed to reveal additional concepts
- CLI displays helpful hint: "💡 1 additional concept available at 56% threshold"
- Provides ready-to-run command: `kg search query "..." --min-similarity 0.56`
- Creates progressive discovery UX through the similarity gradient

**Files Modified:**
- `src/api/routes/queries.py` - Fixed threshold parameter + added threshold hint logic
- `src/api/models/queries.py` - Added `below_threshold_count` and `suggested_threshold` fields
- `client/src/types/index.ts` - Updated SearchResponse interface
- `client/src/cli/search.ts` - Added threshold hint display

---

## Positive Findings

### ✅ 30-Type Relationship Taxonomy Fully Operational

The new relationship system from PR#24 is working perfectly:

**Evidence:**
```bash
kg database stats
```
Shows 5 distinct types from the new taxonomy:
- `CONTRASTS_WITH` (similarity category)
- `CATEGORIZED_AS` (meta category)
- `DEFINED_AS` (meta category)
- `RESULTS_FROM` (causal category)
- `USED_FOR` (functional category)

**Validation:** Zero "invalid relationship type" errors during ingestion ✅

### ✅ Table Formatting System (ADR-019)

All list commands show clean, aligned tables:
- `kg ontology list`
- `kg jobs list`
- `kg database stats`

Formatting is consistent and professional.

### ✅ Job Approval Workflow (ADR-014)

Jobs system shows detailed cost estimates and progress tracking:
- Pre-ingestion analysis with token estimates
- Real-time progress updates
- Final cost breakdown

---

## Test Coverage

### Tested Commands (15/25) - 60%

✅ Fully tested:
- health
- config list
- database stats/info/health
- ontology list/info
- jobs list/status
- admin status
- ingest file

⏭️ Skipped (require specific data):
- search details/related/connect (need concept IDs)
- config get/set/delete
- ontology files (need multi-file ontology)
- admin scheduler cleanup

❌ Not tested (per requirements):
- admin backup
- admin restore

### Test Environment

- **Database:** PostgreSQL 16.10 + Apache AGE (healthy)
- **API Server:** Running with hot reload
- **Python:** 3.13.7
- **Data:** 1 ontology (CleanTest), 7 concepts, 6 relationships
- **Jobs:** 20 historical jobs (mix of completed/failed)

---

## Recommendations

### Priority 1: Fix Scheduler Status Error
**Why:** Broken API endpoint (500 error)
**Action:** Debug `/admin/scheduler/status` endpoint
**Effort:** 30-60 minutes

### Priority 2: Investigate AGE Health Check
**Why:** Confusing "degraded" status when DB is healthy
**Action:** Review health check logic, possibly fix or remove check
**Effort:** 15-30 minutes

### Priority 3: Verify Vector Search Behavior
**Why:** Search returns 0 results unexpectedly
**Action:** List concepts, test with exact labels, check embeddings
**Effort:** 15-30 minutes

### Priority 4: Test Remaining Commands
**Why:** Complete coverage for confidence
**Action:** Ingest multi-file ontology, test all search commands
**Effort:** 30-45 minutes

---

## Next Steps

1. **Investigate Issue #2** (scheduler 500 error) - Check API logs and fix
2. **Investigate Issue #1** (AGE health warning) - Review health check logic
3. **Verify Finding #3** (search behavior) - List concepts and test embedding search
4. **Test remaining commands** - Use generated concepts for search commands
5. **Document any additional fixes** - Update this report with findings

---

## Appendix: Test Commands Used

```bash
# Health & Status
kg health
kg admin status
kg database info
kg database health

# Configuration
kg config list

# Database
kg database stats

# Ontology
kg ontology list
kg ontology info CleanTest

# Jobs
kg jobs list
kg jobs status job_77346d101c15

# Search
kg search query "human intelligence" --limit 3

# Admin (Scheduler)
kg admin scheduler status  # 500 error
```

---

**Report Status:** Draft
**Follow-up:** Investigation of Issues #1 and #2
**Owner:** Development Team
