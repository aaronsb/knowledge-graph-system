# ADR-049: Rate Limiting and Per-Provider Concurrency Management

**Status:** Accepted
**Date:** 2025-10-28
**Deciders:** Development Team
**Related:** ADR-041 (AI Extraction Provider Configuration), ADR-042 (Local LLM Inference)

## Context

Users experiencing 429 rate limit errors when running multiple concurrent ingestion jobs:

**Observed Issues:**
- Multiple workers (4 concurrent jobs) hitting API providers simultaneously
- SDK default retry count (2 attempts) insufficient for concurrent workloads
- No coordination between workers → synchronized retry storms
- Different providers have different rate limits (OpenAI vs Anthropic vs Ollama)
- Local providers (Ollama) have GPU/CPU resource constraints

**Real-World Scenario:**
```
Worker 1: [Call OpenAI] → 429 → retry 1s → 429 → retry 2s → FAIL
Worker 2: [Call OpenAI] → 429 → retry 1s → 429 → retry 2s → FAIL
Worker 3: [Call OpenAI] → 429 → retry 1s → 429 → retry 2s → FAIL
Worker 4: [Call OpenAI] → 429 → retry 1s → 429 → retry 2s → FAIL

Result: All 4 workers fail despite having capacity for retries
```

## Decision

Implement comprehensive rate limiting with three layers:

### 1. SDK-Level Retry (Exponential Backoff)
Configure built-in retry mechanisms in provider SDKs:
- **OpenAI SDK:** `max_retries=8` (default was 2)
- **Anthropic SDK:** `max_retries=8` (default was 2)
- **Ollama (raw HTTP):** Custom retry wrapper with `max_retries=3`

**Retry Pattern:** Exponential backoff with jitter
```
Attempt 1: immediate
Attempt 2: ~1s delay
Attempt 3: ~2s delay
Attempt 4: ~4s delay
Attempt 5: ~8s delay
Attempt 6: ~16s delay
Attempt 7: ~32s delay
Attempt 8: ~64s delay
Total: ~127 seconds of retry window
```

### 2. Per-Provider Concurrency Limiting (Semaphores)
Thread-safe semaphores limit simultaneous API calls per provider:

**Default Limits:**
- **OpenAI:** 8 concurrent requests (higher API tier limits)
- **Anthropic:** 4 concurrent requests (moderate API limits)
- **Ollama:** 1 concurrent request (single GPU/CPU bottleneck)
- **Mock:** 100 concurrent requests (testing - no real limits)

**Implementation:**
```python
# Thread-safe singleton semaphore per provider
semaphore = get_provider_semaphore("openai")  # limit=8

# Acquire before API call
with semaphore:
    response = client.chat.completions.create(...)
```

**Benefit:** Prevents worker collision even with 4+ jobs running
```
4 Workers with OpenAI (limit=8):
Worker 1: [Acquire] → Call API → [Release]
Worker 2: [Acquire] → Call API → [Release]
Worker 3: [Acquire] → Call API → [Release]
Worker 4: [Acquire] → Call API → [Release]

All proceed smoothly - no contention at limit=8
```

### 3. Configuration System (Database-First)
Following ADR-041 pattern, configuration stored in database with environment fallbacks:

**Precedence:**
1. **Primary:** `ai_extraction_config` table columns
   - `max_concurrent_requests` (per-provider limit)
   - `max_retries` (exponential backoff attempts)
2. **Fallback:** Environment variables
   - `{PROVIDER}_MAX_CONCURRENT` (e.g., `OPENAI_MAX_CONCURRENT`)
   - `{PROVIDER}_MAX_RETRIES` (e.g., `OPENAI_MAX_RETRIES`)
3. **Default:** Hardcoded per provider

**Schema Migration 018:**
```sql
ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN max_concurrent_requests INTEGER DEFAULT 4
    CHECK (max_concurrent_requests >= 1 AND max_concurrent_requests <= 100);

ALTER TABLE kg_api.ai_extraction_config
ADD COLUMN max_retries INTEGER DEFAULT 8
    CHECK (max_retries >= 0 AND max_retries <= 20);
```

### 4. Safety Bounds
Enforce reasonable limits to prevent misconfiguration:

**Minimum:** 1 concurrent request
- Falls back to serial processing if undefined/invalid
- Logs warning: "Defaulting to 1 for safety"

**Maximum:** 32 concurrent requests (configurable via `MAX_CONCURRENT_THREADS`)
- Caps per-provider limits to prevent resource exhaustion
- Logs warning: "Capping at 32 to prevent resource exhaustion"

**Rationale:**
- Prevents accidental configuration of 1000 concurrent requests
- Protects against API cost explosions
- Ensures system stability under misconfiguration

## Consequences

### Positive

**Eliminates Rate Limit Failures:**
- 8 retries with exponential backoff provides ~127s retry window
- Most rate limits reset within 60 seconds
- Semaphores prevent worker collision

**Optimizes Resource Usage:**
- Ollama (1 concurrent) prevents GPU thrashing
- Cloud providers (8 concurrent) maximize throughput
- Configurable limits adapt to different API tiers

**Database-Driven Configuration:**
- Hot-reloadable without API restart
- Consistent with ADR-041 pattern
- API endpoints for runtime changes

**Safety and Observability:**
- Bounds checking prevents misconfiguration
- Clear logging at each retry attempt
- Warnings for fallback configurations

### Negative

**Added Complexity:**
- New rate_limiter module (258 lines)
- Schema migration required
- Configuration precedence to understand

**Serialization Overhead:**
- Ollama (1 concurrent) may bottleneck on multi-job ingestion
- Semaphore acquisition adds microseconds latency
- Trade-off: stability over maximum speed

**Migration Dependency:**
- Existing installations must run migration 018
- No automatic migration on API startup
- Requires manual `./scripts/database/migrate-db.sh`

## Implementation

### Rate Limiter Module
`src/api/lib/rate_limiter.py`:
- `get_provider_concurrency_limit()` - Load from DB/env/defaults
- `get_provider_max_retries()` - Load from DB/env/defaults
- `get_provider_semaphore()` - Thread-safe singleton
- `exponential_backoff_retry()` - Decorator for retry logic
- `_is_rate_limit_error()` - Detect 429/rate limit exceptions

### Provider Integration
**OpenAI (`src/api/lib/ai_providers.py`):**
```python
max_retries = get_provider_max_retries("openai")
self.client = OpenAI(
    api_key=self.api_key,
    max_retries=max_retries,
    timeout=120.0
)
```

**Anthropic (`src/api/lib/ai_providers.py`):**
```python
max_retries = get_provider_max_retries("anthropic")
self.client = Anthropic(
    api_key=self.api_key,
    max_retries=max_retries,
    timeout=120.0
)
```

**Ollama (`src/api/lib/ai_providers.py`):**
```python
@exponential_backoff_retry(max_retries=3, base_delay=0.5)
def _make_request():
    resp = self.session.post(...)
    resp.raise_for_status()
    return resp

response = _make_request()
```

### API Exposure
**Models (`src/api/models/extraction.py`):**
- Added `max_concurrent_requests` to request/response models
- Added `max_retries` to request/response models

**Endpoints:**
- `GET /extraction/config` - Public summary (includes limits)
- `GET /admin/extraction/config` - Full details (includes limits)
- `POST /admin/extraction/config` - Update configuration

### Configuration Priority

**NOT respecting DEVELOPMENT_MODE:**
Unlike ADR-041 (provider/model selection), rate limiting loads database-first regardless of `DEVELOPMENT_MODE`:

```python
# Always tries database first
try:
    # Load from kg_api.ai_extraction_config
    config = load_from_database()
except:
    # Fall back to environment
    config = load_from_env()
```

**Rationale:**
- Rate limits are operational constraints, not development settings
- Production systems should use database configuration
- Environment variables serve as emergency fallback
- Simpler logic than DEVELOPMENT_MODE branching

## Alternatives Considered

### Option A: Global Token Bucket Rate Limiter
**Description:** Pre-emptive rate limiting using token bucket algorithm

**Pros:**
- Prevents 429 errors before they happen
- Smooth traffic distribution
- Industry standard for high-throughput systems

**Cons:**
- Complex implementation (token refill, rate tracking)
- Requires knowing exact rate limits per provider
- Adds latency to every API call
- Overkill for 4-worker scenario

**Decision:** Rejected - Exponential backoff simpler and sufficient for current scale

### Option B: Reduce Worker Count to 2
**Description:** Lower `MAX_CONCURRENT_JOBS` from 4 to 2

**Pros:**
- Dead simple - no code changes
- Reduces rate limit pressure by 50%

**Cons:**
- Halves ingestion throughput
- Doesn't address root cause
- Doesn't scale as usage grows

**Decision:** Rejected - Doesn't solve the problem, just hides it

### Option C: Queue with Circuit Breaker
**Description:** Job queue with circuit breaker pattern for degraded providers

**Pros:**
- Protects against cascading failures
- Automatic fallback to slow mode
- Enterprise-grade reliability

**Cons:**
- Significant complexity (state machine, health checks)
- Requires distributed state management
- Premature optimization for current scale

**Decision:** Rejected - Consider for future at higher scale

### Option D: Separate Queue Per Provider
**Description:** Maintain separate job queues for each provider type

**Pros:**
- Complete isolation between providers
- Prevents one provider from blocking others

**Cons:**
- Requires queue multiplexing logic
- Complicates job scheduling
- Doesn't address within-provider rate limits

**Decision:** Rejected - Semaphores provide equivalent isolation with less complexity

## Testing Strategy

### Unit Tests
- `test_rate_limiter.py` - Semaphore behavior, retry logic
- `test_exponential_backoff` - Timing verification
- `test_concurrency_limits` - Thread safety

### Integration Tests
```bash
# 1. Test with multiple workers
kg ingest directory -o "Test" -r --depth 2 ingest_source/

# 2. Monitor logs for retry behavior
tail -f logs/api_*.log | grep -i "rate limit\|retry"

# 3. Verify configuration loading
curl http://localhost:8000/admin/extraction/config
```

### Load Testing (Future)
- Simulate 10+ concurrent jobs
- Verify no 429 failures with defaults
- Test configuration changes without restart

## Monitoring

**Key Metrics:**
- Rate limit hit rate (429 errors per hour)
- Retry success rate (recovered after N attempts)
- Semaphore contention (workers waiting for slots)
- Average retry delay (exponential backoff effectiveness)

**Log Examples:**
```
# Success
INFO: OpenAI client configured with max_retries=8
INFO: Created concurrency semaphore for provider 'openai' with limit=8
INFO: Rate limit recovered after 2 retries (function: extract_concepts)

# Rate limit hit
WARNING: Rate limit hit (attempt 2/9), backing off for 1.2s (function: extract_concepts): 429 Too Many Requests

# Safety warnings
WARNING: Provider 'ollama' concurrency limit not configured. Defaulting to 1 for safety.
WARNING: Provider 'openai' concurrency limit (100) exceeds maximum (32). Capping at 32.
```

## Future Enhancements

### Phase 2: Token Bucket Pre-emption
Add token bucket rate limiter to prevent 429 errors proactively:
```python
class TokenBucket:
    def __init__(self, rate_per_minute=60):
        self.rate = rate_per_minute
        self.tokens = rate_per_minute
        self.last_update = time.time()
```

### Phase 3: Auto-Tuning
Monitor 429 error rate and automatically adjust concurrency:
```python
if error_429_rate > 5%:
    reduce_concurrency(provider, factor=0.8)
elif error_429_rate < 1% and latency_acceptable:
    increase_concurrency(provider, factor=1.2)
```

### Phase 4: Per-Endpoint Limits
Different limits for different operations:
- Extraction: 8 concurrent (expensive)
- Embeddings: 16 concurrent (cheaper)
- Translation: 4 concurrent (moderate)

## Provider HTTP Error Codes

### OpenAI API Errors

| Code | Error Type | Cause | Retry Strategy |
|------|-----------|-------|----------------|
| **401** | Invalid Authentication | Invalid API key or requesting organization | ❌ Do not retry - Fix credentials |
| **401** | Incorrect API key provided | The requesting API key is not correct | ❌ Do not retry - Fix API key |
| **401** | Not member of organization | Account is not part of an organization | ❌ Do not retry - Contact support |
| **401** | IP not authorized | Request IP does not match configured allowlist | ❌ Do not retry - Update IP allowlist |
| **403** | Country/region not supported | Accessing API from unsupported location | ❌ Do not retry - Use VPN/proxy |
| **429** | Rate limit reached for requests | Sending requests too quickly | ✅ **Retry with exponential backoff** |
| **429** | Quota exceeded | Run out of credits or hit monthly spend limit | ❌ Do not retry - Buy more credits |
| **500** | Server error | Issue on OpenAI's servers | ✅ Retry after brief wait |
| **503** | Engine overloaded | High traffic on OpenAI servers | ✅ Retry after brief wait |
| **503** | Slow Down | Sudden increase in request rate impacting reliability | ✅ Retry with reduced rate |

**Key Insight:** Only retry 429 (rate limit), 500 (server error), and 503 (overload/slow down) errors. All 401/403 errors indicate permanent configuration issues.

### Anthropic API Errors

| Code | Error Type | Cause | Retry Strategy |
|------|-----------|-------|----------------|
| **400** | invalid_request_error | Issue with format/content of request | ❌ Do not retry - Fix request |
| **401** | authentication_error | Issue with API key | ❌ Do not retry - Fix API key |
| **403** | permission_error | API key lacks permission for resource | ❌ Do not retry - Fix permissions |
| **404** | not_found_error | Requested resource not found | ❌ Do not retry - Fix resource path |
| **413** | request_too_large | Request exceeds maximum size (32 MB standard, 256 MB batch, 500 MB files) | ❌ Do not retry - Reduce request size |
| **429** | rate_limit_error | Account hit rate limit or acceleration limit | ✅ **Retry with exponential backoff** |
| **500** | api_error | Unexpected internal error | ✅ Retry after brief wait |
| **529** | overloaded_error | API temporarily overloaded (high traffic) | ✅ Retry after brief wait |

**Key Insight:** Only retry 429 (rate limit), 500 (internal error), and 529 (overload) errors. All 4XX errors (except 429) indicate permanent request issues.

**Special Notes:**
- Anthropic's 529 errors occur during high traffic across all users
- Sharp usage increases may trigger 429 acceleration limits - ramp up gradually
- When streaming, errors can occur after 200 response (non-standard error handling)
- Every Anthropic response includes `request_id` header for support tracking

### Request Size Limits (Anthropic)

| Endpoint Type | Maximum Size |
|---------------|--------------|
| Messages API | 32 MB |
| Token Counting API | 32 MB |
| Batch API | 256 MB |
| Files API | 500 MB |

Exceeding these limits returns **413 request_too_large** from Cloudflare before reaching API servers.

### Ollama API Errors

| Code | Error Type | Cause | Retry Strategy |
|------|-----------|-------|----------------|
| **200** | Success | Request completed successfully | ✅ N/A - Success |
| **400** | Bad Request | Missing parameters, invalid JSON, etc. | ❌ Do not retry - Fix request |
| **404** | Not Found | Model doesn't exist | ❌ Do not retry - Use valid model |
| **429** | Too Many Requests | Rate limit exceeded (local/cloud) | ✅ **Retry with exponential backoff** |
| **500** | Internal Server Error | Ollama server encountered an error | ✅ Retry after brief wait |
| **502** | Bad Gateway | Cloud model cannot be reached (remote inference) | ✅ Retry after brief wait |

**Key Insight:** Ollama supports both local and cloud models. 502 errors occur when cloud models (e.g., remote API backends) are unreachable.

**Special Notes:**
- **Streaming errors:** Errors can occur mid-stream after 200 response (returns error object in `application/x-ndjson` format)
- **Error format:** JSON with `error` property: `{"error": "the model failed to generate a response"}`
- **Local inference:** 429 errors less common (single GPU bottleneck, not API rate limits)
- **Cloud models:** 502 errors indicate network/upstream issues, retry appropriate

### Retry Logic Implementation

Our rate limiter (`src/api/lib/rate_limiter.py`) detects retryable errors:

```python
def _is_rate_limit_error(e: Exception) -> bool:
    """
    Detect rate limit and retryable errors.

    Returns True for:
    - OpenAI: 429, 500, 503
    - Anthropic: 429, 500, 529
    - Ollama: 429, 500, 502
    - All: Connection errors, timeouts
    """
    # Check HTTP status codes
    if hasattr(e, 'status_code'):
        return e.status_code in [429, 500, 502, 503, 529]

    # Check exception type names
    error_type = type(e).__name__
    return 'RateLimit' in error_type or 'Overload' in error_type or 'Gateway' in error_type
```

**Retryable Errors (Exponential Backoff):**
- **429** - Rate limit exceeded (all providers)
- **500** - Internal server error (all providers)
- **502** - Bad gateway (Ollama cloud models)
- **503** - Service unavailable (OpenAI)
- **529** - Overloaded (Anthropic)

**Non-Retryable Errors (Fail Fast):**
- **400** - Bad request (malformed input)
- **401** - Authentication error (invalid API key)
- **403** - Permission error (insufficient permissions)
- **404** - Not found (invalid resource/model)
- **413** - Request too large (exceeds size limits)

These errors indicate configuration or request problems that won't resolve with retries.

## References

- **OpenAI Cookbook:** [How to handle rate limits](https://cookbook.openai.com/examples/how_to_handle_rate_limits)
- **Industry Standard:** Exponential backoff with jitter
- **ADR-041:** AI Extraction Provider Configuration (database-first pattern)
- **Migration 018:** `schema/migrations/018_add_rate_limiting_config.sql`
- **Implementation:** `src/api/lib/rate_limiter.py`
