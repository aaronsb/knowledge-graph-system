# Continuation Notes for Context Compaction Recovery

**Last Updated:** 2025-11-17
**Commit:** af28d5b
**Branch:** feature/vocabulary-based-appears

## What We Just Accomplished

We implemented **counter-based staleness tracking for cached epistemic status** (ADR-065 Phase 2 enhancement). The system now:

1. Tracks vocabulary changes via incrementing counters (not timestamps)
2. Caches epistemic status in VocabType nodes instead of recalculating
3. Detects when cache is stale via counter delta
4. Automatically resets staleness after re-measurement

### Key Design Decisions

**Why counters instead of timestamps?**
- Delta = current_counter - last_measured_counter tells us HOW MANY changes occurred
- Independent of time - if no changes, no measurement needed regardless of time elapsed
- Enables threshold-based triggering (e.g., remeasure when delta >= 10)
- User emphasized: "the principle value is knowing the delta of change (counter) not the datetime"

**Why cache epistemic status?**
- Vocabulary grows much slower than concepts (user insight)
- Re-sampling 100 edges per type every query is wasteful
- Store results in VocabType.epistemic_status, VocabType.epistemic_stats
- Only re-measure when vocabulary actually changes (detected via counter delta)

**Why EMERGING classification?**
- All concepts in newly ingested knowledge base have weak grounding (0.0-0.3)
- Old threshold (CONTESTED: 0.2-0.8) missed most types (fell into UNCLASSIFIED)
- New EMERGING classification (0.0-0.15) captures developing evidence
- Lowered CONTESTED to 0.15 to catch more mixed-grounding types

## Current State

### Database

**Tables:**
- `graph_metrics` - 18 BIGINT counters tracking vocabulary/concept/ingestion changes
  - `vocabulary_change_counter` - PRIMARY staleness indicator
  - `epistemic_measurement_counter` - Tracks measurement runs
  - `concept_creation_counter`, etc. - Additional tracking

**VocabType Nodes:**
- `epistemic_status` - EMERGING, CONTESTED, AFFIRMATIVE, etc.
- `epistemic_stats` - JSON with avg_grounding, std, min, max, measured_concepts, sampled_edges, total_edges
- `epistemic_measured_at` - Timestamp of last measurement
- `epistemic_rationale` - Human-readable explanation

**Concept Nodes:**
- `grounding_strength` - Calculated via polarity axis projection (ADR-044)
- ALL 1100 concepts now have grounding calculated (run: operator/admin/calculate_concept_grounding.py)

### Services

**VocabularyMetricsService** (`api/api/services/vocabulary_metrics_service.py`)
```python
metrics = VocabularyMetricsService(db_connection)

# Increment on vocabulary changes
metrics.increment_vocabulary_change()  # Any create/delete/consolidate
metrics.increment_vocabulary_creation()
metrics.increment_vocabulary_deletion()
metrics.increment_vocabulary_consolidation()

# Check staleness
delta = metrics.get_counter_delta('vocabulary_change_counter')
if metrics.should_remeasure(threshold=10):
    # Trigger re-measurement

# After measurement
metrics.mark_measurement_complete('vocabulary_change_counter')  # Resets delta to 0
metrics.increment_epistemic_measurement()
```

**EpistemicStatusService** (`api/api/services/epistemic_status_service.py`)
- Moved from operator scripts to proper API service
- `measure_all_vocabulary(sample_size=100, store=True)` - Main measurement function
- Automatically integrates with VocabularyMetricsService:
  - Increments epistemic_measurement_counter after measurement
  - Marks vocabulary_change_counter complete (resets delta to 0)
- Stores results to VocabType nodes (cached)

### API Endpoints

**GET /vocabulary/epistemic-status** (list)
- **Reads from cached VocabType nodes** (not recalculating!)
- Returns: `last_measurement_at`, `vocabulary_changes_since_measurement` (delta)
- Filter by status: `?status_filter=EMERGING`

**GET /vocabulary/epistemic-status/{type}** (show)
- **Reads from cached VocabType node** (not recalculating!)
- Returns: `vocabulary_changes_since_measurement` (delta)

**GET /database/stats**
- Returns: `metrics` field with all counter data
- Includes: counter, last_measured_counter, delta for each metric

**POST /vocabulary/epistemic-status/measure**
- Triggers measurement (same as `kg vocab epistemic-status measure`)
- Updates VocabType cache
- Updates counters

### CLI Commands

**Working:**
- `kg vocab epistemic-status measure` - Trigger measurement, update cache, update counters
- `kg vocab epistemic-status list [--status EMERGING]` - List types (from cache)
- `kg vocab epistemic-status show SUPPORTS` - Show details (from cache)
- `kg db stats` - Database statistics

**Data Flow:**
```
Manual: kg vocab epistemic-status measure
                ↓
        EpistemicStatusService.measure_all_vocabulary()
                ↓
        1. Calculate grounding stats (sample 100 edges per type)
        2. Classify epistemic status
        3. Store to VocabType nodes (CACHE)
        4. Increment epistemic_measurement_counter
        5. Mark vocabulary_change_counter complete (delta=0)

Query:  kg vocab epistemic-status list
                ↓
        Read from VocabType nodes (CACHE - no recalculation!)
                ↓
        Get vocabulary_change_counter delta
                ↓
        Display: Last Measurement + Staleness Delta
```

### Current Measurements (As of 2025-11-17 6:25 PM)

**Epistemic Status Distribution:**
- INSUFFICIENT_DATA: 75 types (< 3 measurements)
- EMERGING: 21 types (0.0-0.15 avg grounding) ← NEW!
- UNCLASSIFIED: 13 types (-0.5 to 0.0 liminal)
- CONTESTED: 3 types (0.15-0.8 mixed grounding) ← Improved from 1!

**Example Types:**
- SUPPORTS: CONTESTED (0.174 avg, 100/126 edges measured)
- REQUIRES: EMERGING (0.031 avg)
- ENABLES: CONTESTED (0.218 avg)

**Counters:**
- epistemic_measurement_counter: 1
- vocabulary_change_counter: 2 (delta = 0 after measurement)

## What Still Needs To Be Done

### Priority 1: CLI Display Formatting

**Problem:** CLI still shows per-type "MEASURED AT" column, but all types measured together

**Solution:** Add single header with global measurement info

**Files to modify:**
- `cli/src/cli/vocabulary.ts` (lines 1125-1192 for list, 1195-1240 for show)

**Desired output for `kg vocab epistemic-status list`:**
```
📊 Epistemic Status

Last Measurement: 11/17/2025, 6:25 PM
Staleness: 0 vocabulary changes since measurement (fresh)
          ↑ Or: "5 vocabulary changes since measurement (consider re-measuring)"

Total Types: 112

─────────────────────────────────────────────────────────────────────
TYPE                      STATUS               AVG GROUNDING    SAMPLED
─────────────────────────────────────────────────────────────────────
SUPPORTS                  CONTESTED                    0.174        100
REQUIRES                  EMERGING                     0.031          0
...
```

**Remove:** "MEASURED AT" column (redundant - all measured together)
**Add:** Staleness header at top

**API already returns:** `last_measurement_at`, `vocabulary_changes_since_measurement`

### Priority 2: MCP Server Formatters

**Files to modify:**
- `cli/src/mcp/formatters.ts` - Update `formatEpistemicStatusList()` and `formatEpistemicStatusDetails()`

**Add staleness context** to both list and show formatters

### Priority 3: kg db stats Display

**File to modify:**
- `cli/src/cli/database.ts` - Add metrics section

**Desired output addition:**
```
📊 Database Statistics

Nodes
  Concepts: 1100
  Sources: 200
  ...

Relationships
  Total: 5630
  ...

Graph Metrics                               ← NEW SECTION
  Vocabulary Changes: 5 (delta: 5)
  Epistemic Measurements: 2
  Concept Creations: 1100
  Document Ingestions: 20
```

**API already returns:** `metrics` field in DatabaseStatsResponse

### Priority 4: Background Worker Job

**Create new file:** `api/api/workers/epistemic_status_worker.py`

**Logic:**
```python
async def epistemic_status_worker():
    """Periodic worker to check staleness and trigger re-measurement"""
    while True:
        await asyncio.sleep(600)  # Check every 10 minutes

        metrics_service = VocabularyMetricsService(db_conn)

        # Check if re-measurement needed
        if metrics_service.should_remeasure(threshold=10):
            logger.info("Vocabulary changed by 10+, triggering re-measurement")

            epistemic_service = EpistemicStatusService(age_client)
            epistemic_service.measure_all_vocabulary(
                sample_size=100,
                store=True
            )
            # Counters automatically updated by measure_all_vocabulary
```

**Integration point:** `api/api/main.py` - Add to startup tasks

**User quote:** "we can always manually trigger that sampling process 'kg vocab epistemic-status measure' in addition to the job, but they both run the same worker on the api server, and both would update the data cache, and update the counter stats"

### Priority 5: Hook Integration for Counter Increments

**When vocabulary changes occur**, increment counters:

**VocabularyManager methods to update:**
- `create_vocabulary_type()` → `metrics.increment_vocabulary_creation()` + `metrics.increment_vocabulary_change()`
- `delete_vocabulary_type()` → `metrics.increment_vocabulary_deletion()` + `metrics.increment_vocabulary_change()`
- `consolidate_synonyms()` → `metrics.increment_vocabulary_consolidation()` + `metrics.increment_vocabulary_change()`

**When concept/relationship creation occurs:**
- Ingestion pipeline → `metrics.increment_concept_creation()`, `metrics.increment_relationship_creation()`
- Job completion → `metrics.increment_document_ingestion()`

## Important Context for AI Continuation

### Philosophy

**Bounded Locality + Satisficing (from EpistemicStatusService docstring):**
- Grounding calculated at query time with limited recursion depth
- Perfect knowledge requires infinite computation (Gödel incompleteness)
- We satisfice: sample edges, calculate bounded grounding, estimate patterns
- Each run is a "measurement" - results are temporal, observer-dependent

**Counter-based Staleness:**
- Principle value is the DELTA (how many changes), not the datetime
- Enables threshold-based triggering independent of time
- If delta = 0, cache is fresh regardless of how old timestamp is
- If delta >= threshold, cache is stale and needs refresh

### Testing/Verification Commands

```bash
# Check current staleness
docker exec knowledge-graph-postgres psql -U admin -d knowledge_graph -c "
  SELECT metric_name, counter, last_measured_counter,
         (counter - last_measured_counter) as delta
  FROM graph_metrics
  WHERE metric_name IN ('vocabulary_change_counter', 'epistemic_measurement_counter');
"

# Check epistemic status cache
docker exec kg-operator python -c "
from api.api.lib.age_client import AGEClient
client = AGEClient()
query = '''
  MATCH (v:VocabType {name: \"SUPPORTS\"})
  RETURN v.epistemic_status, v.epistemic_measured_at
'''
print(client._execute_cypher(query))
"

# Trigger measurement
kg vocab epistemic-status measure

# Verify delta reset to 0
# (Run first query again)
```

### Common Issues & Solutions

**Issue:** CLI shows old cached data from before latest measurement
**Cause:** API endpoint was recalculating instead of reading cached VocabType nodes
**Solution:** ✅ Fixed! Endpoints now use `client.facade.match_vocab_types()` to read cache

**Issue:** Epistemic status shows INSUFFICIENT_DATA despite many edges
**Cause:** Grounding not calculated for concepts
**Solution:** ✅ Fixed! Run `operator/admin/calculate_concept_grounding.py` (all 1100 done)

**Issue:** Counter delta not resetting after measurement
**Cause:** Missing `metrics_service.mark_measurement_complete()` call
**Solution:** ✅ Fixed! Integrated into `measure_all_vocabulary()`

## Files Modified (Commit af28d5b)

**New Services:**
- `api/api/services/epistemic_status_service.py` - Main measurement logic
- `api/api/services/vocabulary_metrics_service.py` - Counter management

**New Migration:**
- `schema/migrations/025_graph_metrics_table.sql` - Graph metrics table

**New Script:**
- `operator/admin/calculate_concept_grounding.py` - Batch grounding calculation

**Modified API:**
- `api/api/models/database.py` - Added MetricCounter, metrics to DatabaseStatsResponse
- `api/api/models/vocabulary.py` - Added staleness fields to responses
- `api/api/routes/database.py` - Fetch and return metrics
- `api/api/routes/vocabulary.py` - Fetch and return staleness

**Deleted:**
- `operator/admin/calculate_vocab_epistemic_status.py` - Replaced by service
- `operator/admin/test_epistemic_status_queries.py` - Moved to test suite

## Next Session Checklist

When resuming work on this feature:

1. [ ] Read this document
2. [ ] Check current staleness: `kg vocab epistemic-status list` - Does it show staleness header?
3. [ ] If not, implement CLI formatter updates (Priority 1)
4. [ ] Test measurement: `kg vocab epistemic-status measure`
5. [ ] Verify counter reset: Check delta = 0
6. [ ] Implement remaining priorities (2-5)
7. [ ] Test end-to-end workflow:
   - Create new vocabulary type → counter increments
   - Check staleness increases
   - Trigger re-measurement (manual or automatic)
   - Verify cache updated, counters reset

## Related ADRs & Docs

- **ADR-065:** Vocabulary-Based Provenance Relationships (Phase 2 = epistemic status)
- **ADR-044:** Polarity Axis Projection (grounding calculation method)
- **ADR-048:** Query Safety via GraphQueryFacade
- **ADR-061:** Operator Architecture
- **Migration 025:** Graph Metrics Table
- **Guide:** `docs/guides/EPISTEMIC-STATUS-FILTERING.md`

---

**Remember:** The foundation is solid. API works, counters work, cache works. Just needs display formatting!
