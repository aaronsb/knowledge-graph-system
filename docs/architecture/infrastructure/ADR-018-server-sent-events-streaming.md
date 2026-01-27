---
status: Draft
date: 2025-10-09
deciders:
  - aaronsb
  - claude
---

# ADR-018: Server-Sent Events for Real-Time Progress Streaming

**Status**: Proposed
**Date**: 2025-10-09
**Deciders**: Development Team
**Related**: ADR-015 (Backup/Restore Streaming), ADR-014 (Job Queue System)

## Overview

Picture yourself waiting for a large file to download. You want to know how it's going - is it 10% done? 50%? Stuck? The worst experience is when your browser just shows a spinning wheel with no indication of progress. Now imagine that same frustrating experience, but for a 5-minute knowledge graph ingestion process. You'd be sitting there wondering: "Is it working? How much longer? Should I cancel and try again?"

We had exactly this problem. Our server could see beautiful progress bars internally, watching as it processed documents chunk by chunk, but the user's terminal only saw updates every few seconds when it polled "are we done yet?" It's like checking your mailbox every 5 minutes instead of having the mail carrier knock on your door when they arrive.

Server-Sent Events solve this by opening a continuous connection where the server can push updates the moment something happens. Process a chunk? User sees it instantly. Hit an error? User knows right away. It's like streaming vs. downloading - instead of asking "what's the status?" over and over, the server just tells you when things change. This creates a responsive experience where users feel connected to what's happening, and it sets up the foundation for real-time features in future web dashboards.

---

## Context

After implementing ADR-015 Phase 2 (backup/restore with progress tracking), we discovered that progress updates are limited by polling architecture:

### Current Architecture
- **Client polls** `/jobs/{job_id}` every 2 seconds
- **Server logs** show beautiful animated progress bars (Python `Console.progress()`)
- **Client sees** only sparse manual updates (20%, 90%, 100%)
- **Problem**: Rich server-side progress never reaches client

### Example Gap
```python
# Server logs (not visible to client):
Importing concepts...
Concepts: ████████████████████████████████████████ 100.0% (114/114)
Importing sources...
Sources: ████████████████████████████████████████ 100.0% (18/18)

# Client sees (via polling):
→ GET /jobs/{job_id} - {"stage": "restoring_concepts", "percent": 20}
[2 seconds later]
→ GET /jobs/{job_id} - {"stage": "restoring_relationships", "percent": 90}
```

### Why This Matters Now
The CLI is establishing **API interaction patterns** that will be reused in future GUI applications. Those applications will need:
- Live dashboard updates
- Real-time ingestion statistics
- Multi-user notifications
- Streaming search results
- Graph visualization updates

Solving this now creates the foundation for all future real-time features.

## Decision

**Implement Server-Sent Events (SSE) for streaming job progress and future real-time updates.**

Add streaming endpoints alongside existing polling endpoints:
- `/jobs/{job_id}/stream` - Real-time job progress (SSE)
- `/jobs/{job_id}` - Job status snapshot (polling fallback)

## Alternatives Considered

### Option 1: Enhanced Polling (Rejected)
Add progress callback to `DataImporter.import_backup()` that updates job state every 10 items.

**Rejected because:**
- Still 2-second latency minimum
- Increased database writes (every 10 items)
- Doesn't solve the architectural problem
- Scales poorly for high-frequency updates

### Option 2: WebSockets (Rejected)
Full-duplex bidirectional communication.

**Rejected because:**
- Overkill for unidirectional progress updates
- More complex connection management
- Doesn't work through all proxies/firewalls
- Higher implementation complexity
- Node.js WebSocket client adds dependencies

### Option 3: Server-Sent Events (Selected)
HTTP-based unidirectional event streaming from server to client.

**Selected because:**
- ✅ Simple HTTP protocol (works everywhere polling works)
- ✅ Built-in reconnection and event ID tracking
- ✅ Low latency (<500ms updates possible)
- ✅ Graceful degradation to polling
- ✅ Establishes pattern for future real-time features
- ✅ Widely supported (EventSource API in browsers, `eventsource` npm for Node.js)

## Implementation

### Phase 1: Core SSE Infrastructure

#### Server (FastAPI)
```python
# src/api/routes/jobs.py

@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str):
    """
    Stream real-time job progress updates via Server-Sent Events.

    Events sent:
    - progress: Job progress updates (stage, percent, items)
    - completed: Job completed successfully
    - failed: Job failed with error
    - keepalive: Connection keepalive (every 30s)

    Auto-closes stream when job reaches terminal state.
    """
    async def event_generator():
        last_progress = None

        while True:
            job = job_queue.get_job(job_id)

            if not job:
                yield f"event: error\ndata: {json.dumps({'error': 'Job not found'})}\n\n"
                break

            # Send progress if changed
            current_progress = job.get('progress')
            if current_progress != last_progress:
                yield f"event: progress\ndata: {json.dumps(current_progress)}\n\n"
                last_progress = current_progress

            # Send terminal events
            if job['status'] == 'completed':
                yield f"event: completed\ndata: {json.dumps(job['result'])}\n\n"
                break
            elif job['status'] == 'failed':
                yield f"event: failed\ndata: {json.dumps({'error': job['error']})}\n\n"
                break

            await asyncio.sleep(0.5)  # 500ms update interval

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
```

#### Client (TypeScript)
```typescript
// client/src/lib/job-stream.ts

import EventSource from 'eventsource';

export interface JobProgressCallback {
  onProgress?: (progress: JobProgress) => void;
  onCompleted?: (result: JobResult) => void;
  onFailed?: (error: string) => void;
  onError?: (error: Error) => void;
}

export class JobProgressStream {
  private eventSource: EventSource | null = null;

  constructor(
    private baseUrl: string,
    private jobId: string,
    private callbacks: JobProgressCallback
  ) {}

  start(): void {
    const url = `${this.baseUrl}/jobs/${this.jobId}/stream`;
    this.eventSource = new EventSource(url);

    this.eventSource.addEventListener('progress', (event) => {
      const progress = JSON.parse(event.data);
      this.callbacks.onProgress?.(progress);
    });

    this.eventSource.addEventListener('completed', (event) => {
      const result = JSON.parse(event.data);
      this.callbacks.onCompleted?.(result);
      this.close();
    });

    this.eventSource.addEventListener('failed', (event) => {
      const error = JSON.parse(event.data);
      this.callbacks.onFailed?.(error.error);
      this.close();
    });

    this.eventSource.onerror = (error) => {
      this.callbacks.onError?.(error);
      // Auto-reconnect handled by EventSource
    };
  }

  close(): void {
    this.eventSource?.close();
    this.eventSource = null;
  }
}
```

#### CLI Usage
```typescript
// client/src/cli/admin.ts

const stream = new JobProgressStream(baseUrl, jobId, {
  onProgress: (progress) => {
    // Update ora spinner with real-time progress
    spinner.text = formatProgress(progress);
  },
  onCompleted: (result) => {
    spinner.succeed('Restore completed!');
    displayResults(result);
  },
  onFailed: (error) => {
    spinner.fail(`Restore failed: ${error}`);
  }
});

stream.start();
```

#### Graceful Fallback
```typescript
// client/src/lib/job-tracker.ts

export async function trackJob(jobId: string, callbacks: JobProgressCallback) {
  // Try SSE first
  if (supportsSSE()) {
    const stream = new JobProgressStream(baseUrl, jobId, callbacks);
    stream.start();
    return;
  }

  // Fallback to polling
  return pollJob(jobId, callbacks.onProgress, 2000);
}
```

### Phase 2: Progress Callback Integration

Update `DataImporter.import_backup()` to emit progress:

```python
# src/lib/serialization.py

@staticmethod
def import_backup(
    client: AGEClient,
    backup_data: Dict[str, Any],
    overwrite_existing: bool = False,
    progress_callback: Optional[Callable[[str, int, int, float], None]] = None
) -> Dict[str, int]:
    """
    Import backup data with optional progress tracking.

    progress_callback(stage, current, total, percent) called every N items
    """
    data = backup_data["data"]

    # Concepts
    for i, concept in enumerate(data["concepts"]):
        # ... import logic ...

        if progress_callback and (i + 1) % 10 == 0:
            progress_callback("concepts", i + 1, len(data["concepts"]),
                            (i + 1) / len(data["concepts"]) * 100)

    # Same for sources, instances, relationships...
```

Restore worker uses callback:

```python
# src/api/workers/restore_worker.py

def _execute_restore(...):
    def progress_callback(stage: str, current: int, total: int, percent: float):
        job_queue.update_job(job_id, {
            "progress": {
                "stage": f"restoring_{stage}",
                "percent": int(percent),
                "items_total": total,
                "items_processed": current,
                "message": f"Restoring {stage}: {current}/{total}"
            }
        })

    stats = DataImporter.import_backup(
        client, backup_data,
        overwrite_existing=overwrite,
        progress_callback=progress_callback
    )
```

### Phase 3: Extended Streaming Endpoints

Once pattern established, add:

```python
# Future endpoints using same pattern
@router.get("/database/stats/stream")  # Live database metrics
@router.get("/ingestion/{job_id}/stream")  # Real-time concept extraction
@router.get("/notifications/stream")  # System-wide events
@router.get("/search/{query_id}/stream")  # Streaming search results
```

## Consequences

### Positive

1. **Real-Time UX**: Sub-second progress updates visible to client
2. **Scalable Pattern**: Foundation for all future real-time features
3. **Reduced Load**: Less polling traffic (1 connection vs N requests)
4. **Better Feedback**: Users see granular progress (every 10 items)
5. **Future-Ready**: GUI applications get real-time updates for free
6. **Standard Protocol**: SSE is widely supported, battle-tested
7. **Debugging**: Easier to debug with `curl` (see events in real-time)

### Negative

1. **Connection Management**: Long-lived HTTP connections (requires proxy config)
2. **Client Dependency**: Need `eventsource` npm package for Node.js
3. **State Tracking**: Server must track active streams
4. **Error Handling**: Need reconnection logic (auto-handled by EventSource)
5. **Testing**: More complex integration tests
6. **Documentation**: Need to document SSE vs polling trade-offs

### Neutral

1. **Backward Compatibility**: Polling endpoints remain for fallback
2. **Infrastructure**: Most modern proxies/load balancers support SSE
3. **Resource Usage**: One SSE connection ≈ one poll every 500ms

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Proxy buffering breaks SSE | High | Add `X-Accel-Buffering: no` header, document nginx config |
| Client doesn't support SSE | Medium | Automatic fallback to polling |
| Memory leak from abandoned streams | Medium | Server-side timeout (5min), client cleanup on unmount |
| Reconnection storms | Low | Exponential backoff in EventSource (built-in) |
| Testing complexity | Medium | Add SSE testing utilities, document patterns |

## Success Metrics

- ✅ Progress updates visible within 500ms
- ✅ CLI shows item-level progress (concepts, sources, instances, relationships)
- ✅ Graceful fallback to polling if SSE fails
- ✅ Pattern documented for future GUI implementation
- ✅ No regression in polling-based clients

## Timeline

- **Phase 1**: Core SSE infrastructure (1-2 days)
  - Server streaming endpoint
  - Client EventSource wrapper
  - CLI integration with fallback
- **Phase 2**: Progress callback integration (1 day)
  - Update DataImporter
  - Wire to restore worker
  - Test end-to-end
- **Phase 3**: Documentation & examples (1 day)
  - API documentation
  - Client usage examples
  - Testing guide

## References

- [Server-Sent Events Specification](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
- [EventSource API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/EventSource)
- [eventsource npm package](https://www.npmjs.com/package/eventsource)
- ADR-014: Job Queue System
- ADR-015: Backup/Restore Streaming

## Future Considerations

### Multi-Client Broadcasting
For future GUI features like shared dashboards:
```python
# Broadcast to multiple clients watching same job
@router.get("/jobs/{job_id}/stream")
async def stream_job_progress(job_id: str):
    # Subscribe to job updates via pub/sub pattern
    subscription = job_notifier.subscribe(job_id)
    # ...
```

### Event Filtering
Allow clients to filter events:
```
GET /jobs/{job_id}/stream?events=progress,completed
```

### Event History
Allow clients to catch up from specific event:
```
GET /jobs/{job_id}/stream?last-event-id=42
```

## Notes

- SSE is unidirectional (server→client). Client commands use standard REST POST/PUT.
- EventSource auto-reconnects with exponential backoff. No manual reconnection needed.
- SSE works over HTTP/1.1 and HTTP/2. No special protocol upgrade required.
- Consider rate limiting: 1 SSE connection per client per job maximum.
