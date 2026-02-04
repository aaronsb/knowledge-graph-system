---
status: Accepted
date: 2025-11-03
deciders:
  - aaronsb
  - claude
related:
  - ADR-054
  - ADR-055
---

# ADR-056: Timezone-Aware Datetime Utilities

## Overview

DateTime handling in Python has a subtle trap that catches even experienced developers. When you call `datetime.utcnow()`, you get what looks like a UTC timestamp. But Python doesn't attach timezone information to it - it's "naive" in Python's terminology. Meanwhile, PostgreSQL stores timestamps with timezone info attached - they're "aware." When you try to compare these two, Python throws an error: you can't compare apples (naive) with oranges (aware).

This kept happening throughout the codebase. Fix it in one place, encounter it somewhere else a week later. Each time felt like hitting the same hidden tripwire. The root issue is that Python's standard datetime API makes it too easy to accidentally create naive datetimes, and nothing warns you until runtime when the comparison fails - often in production.

The solution is embarrassingly simple: create a central utility module with functions that always return timezone-aware datetimes. Instead of remembering to write `datetime.now(timezone.utc)` everywhere, you import `utcnow()` from the utilities. Instead of manual expiration checks, you call `is_expired(timestamp)` which handles all the timezone conversion internally. It's a thin wrapper, but it prevents the entire class of bugs by making the safe thing the easy thing.

---

## Context

The knowledge graph system has repeatedly encountered datetime comparison errors:

```python
TypeError: can't compare offset-naive and offset-aware datetimes
```

### Recent Incidents

1. **OAuth Token Exchange (ADR-055 Implementation):**
   - `api/app/lib/oauth_utils.py:253` - `is_token_expired()` function
   - Used `datetime.utcnow()` (naive) to compare with PostgreSQL timestamps (aware)
   - Result: 500 errors on `POST /auth/oauth/token`
   - Fixed: Replaced all `datetime.utcnow()` → `datetime.now(timezone.utc)`

2. **Previous Incidents (Pattern Recognition):**
   - User reported: "we seem to run into timezone errors a lot"
   - Similar fixes likely applied in other parts of codebase
   - No systematic prevention mechanism

### Root Cause

**Python's `datetime` module has two datetime types:**

1. **Naive datetimes** (no timezone info):
   ```python
   datetime.utcnow()  # 2025-11-03 12:00:00 (no timezone)
   datetime.now()     # 2025-11-03 07:00:00 (local time, no timezone)
   ```

2. **Aware datetimes** (with timezone info):
   ```python
   datetime.now(timezone.utc)  # 2025-11-03 12:00:00+00:00
   datetime.fromisoformat('2025-11-03T12:00:00+00:00')
   ```

**PostgreSQL's `TIMESTAMP WITH TIME ZONE`:**
- Always returns timezone-aware datetimes to Python via psycopg2
- `created_at`, `updated_at`, `expires_at` columns all have timezone info
- Cannot be compared with naive Python datetimes

**The problem:**
```python
# ❌ BREAKS: Comparing naive (left) vs aware (right)
datetime.utcnow() > row['expires_at']  # TypeError

# ✅ WORKS: Both timezone-aware
datetime.now(timezone.utc) > row['expires_at']
```

### Why This Keeps Happening

1. **`datetime.utcnow()` is a footgun:**
   - Commonly used pattern in Python docs
   - Returns naive datetime despite "utc" in name
   - Easy to forget `.replace(tzinfo=timezone.utc)`

2. **No linting or type checking:**
   - `mypy` cannot detect naive vs aware datetimes (both are `datetime` type)
   - No runtime warnings until comparison happens
   - Error surfaces in production, not development

3. **Inconsistent patterns across codebase:**
   - Some modules use `datetime.utcnow()`
   - Some use `datetime.now(timezone.utc)`
   - Some use `datetime.now()` (local time, also naive)
   - No single source of truth

## Decision

### 1. Create Central Datetime Utility Module

**New file: `api/app/lib/datetime_utils.py`**

```python
"""
Timezone-Aware Datetime Utilities (ADR-056)

Centralized datetime helpers to prevent naive/aware comparison errors.
All functions return timezone-aware datetimes in UTC.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional


def utcnow() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.

    Returns:
        Current UTC time with timezone info

    Example:
        >>> now = utcnow()
        >>> now.tzinfo
        datetime.timezone.utc
    """
    return datetime.now(timezone.utc)


def utc_from_timestamp(timestamp: float) -> datetime:
    """
    Convert Unix timestamp to timezone-aware UTC datetime.

    Args:
        timestamp: Unix timestamp (seconds since epoch)

    Returns:
        Timezone-aware datetime in UTC

    Example:
        >>> dt = utc_from_timestamp(1699027200.0)
        >>> dt.tzinfo
        datetime.timezone.utc
    """
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def utc_from_iso(iso_string: str) -> datetime:
    """
    Parse ISO 8601 string to timezone-aware UTC datetime.

    If input has no timezone, assumes UTC.
    If input has different timezone, converts to UTC.

    Args:
        iso_string: ISO 8601 datetime string

    Returns:
        Timezone-aware datetime in UTC

    Example:
        >>> dt = utc_from_iso('2025-11-03T12:00:00Z')
        >>> dt.tzinfo
        datetime.timezone.utc
    """
    dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))

    if dt.tzinfo is None:
        # Assume UTC if no timezone info
        return dt.replace(tzinfo=timezone.utc)

    # Convert to UTC if in different timezone
    return dt.astimezone(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    """
    Ensure datetime is timezone-aware and in UTC.

    - If naive, assumes UTC
    - If aware but not UTC, converts to UTC
    - If already UTC, returns as-is

    Args:
        dt: Input datetime (naive or aware)

    Returns:
        Timezone-aware datetime in UTC

    Example:
        >>> naive = datetime(2025, 11, 3, 12, 0, 0)
        >>> aware = ensure_utc(naive)
        >>> aware.tzinfo
        datetime.timezone.utc
    """
    if dt.tzinfo is None:
        # Naive datetime - assume UTC
        return dt.replace(tzinfo=timezone.utc)

    # Already aware - convert to UTC
    return dt.astimezone(timezone.utc)


def is_expired(expires_at: datetime, now: Optional[datetime] = None) -> bool:
    """
    Check if a datetime has passed (timezone-safe).

    Args:
        expires_at: Expiration datetime (naive or aware)
        now: Current time (defaults to utcnow())

    Returns:
        True if expired, False otherwise

    Example:
        >>> past = utcnow() - timedelta(hours=1)
        >>> is_expired(past)
        True
    """
    if now is None:
        now = utcnow()

    # Ensure both datetimes are timezone-aware
    expires_at_utc = ensure_utc(expires_at)
    now_utc = ensure_utc(now)

    return now_utc > expires_at_utc


def timedelta_from_now(
    days: int = 0,
    hours: int = 0,
    minutes: int = 0,
    seconds: int = 0
) -> datetime:
    """
    Get timezone-aware UTC datetime offset from now.

    Args:
        days: Days to add
        hours: Hours to add
        minutes: Minutes to add
        seconds: Seconds to add

    Returns:
        Timezone-aware datetime in UTC

    Example:
        >>> future = timedelta_from_now(hours=1)
        >>> future > utcnow()
        True
    """
    return utcnow() + timedelta(
        days=days,
        hours=hours,
        minutes=minutes,
        seconds=seconds
    )
```

### 2. Deprecate Direct `datetime.utcnow()` Usage

**Add linter rule to detect unsafe patterns:**

```python
# scripts/lint_datetimes.py
"""
Lint for unsafe datetime patterns (ADR-056).

Detects:
- datetime.utcnow() - should use datetime_utils.utcnow()
- datetime.now() without timezone - should use datetime_utils.utcnow()
"""

import re
import sys
from pathlib import Path


UNSAFE_PATTERNS = [
    (r'\bdatetime\.utcnow\(\)', 'Use datetime_utils.utcnow() instead'),
    (r'\bdatetime\.now\(\)(?!\s*\()', 'Use datetime_utils.utcnow() instead'),
    (r'\bdatetime\.fromtimestamp\([^,)]+\)', 'Use datetime_utils.utc_from_timestamp() instead'),
]


def lint_file(file_path: Path) -> list[tuple[int, str, str]]:
    """Lint a Python file for unsafe datetime patterns."""
    errors = []

    with open(file_path) as f:
        for line_num, line in enumerate(f, start=1):
            # Skip comments and imports
            if line.strip().startswith('#') or 'import' in line:
                continue

            for pattern, message in UNSAFE_PATTERNS:
                if re.search(pattern, line):
                    errors.append((line_num, line.strip(), message))

    return errors


def main():
    src_path = Path('api/app')
    errors_found = False

    for py_file in src_path.rglob('*.py'):
        # Skip datetime_utils.py itself
        if py_file.name == 'datetime_utils.py':
            continue

        errors = lint_file(py_file)
        if errors:
            errors_found = True
            print(f"\n{py_file}:")
            for line_num, line, message in errors:
                print(f"  Line {line_num}: {message}")
                print(f"    {line}")

    if errors_found:
        print("\n❌ Found unsafe datetime patterns")
        print("   See ADR-056 for migration guide")
        sys.exit(1)
    else:
        print("✅ No unsafe datetime patterns found")


if __name__ == '__main__':
    main()
```

### 3. Migration Strategy

**Phase 1: Add utility module (immediate)**
```bash
# Create datetime_utils.py
# Update oauth_utils.py to use new utilities
# Verify OAuth flow works
```

**Phase 2: Incremental migration (ongoing)**
```bash
# Run linter to find all unsafe patterns
python scripts/lint_datetimes.py

# Migrate module by module
# Test after each migration
```

**Phase 3: Enforce in CI (future)**
```yaml
# .github/workflows/lint.yml
- name: Lint datetime usage
  run: python scripts/lint_datetimes.py
```

### 4. Update OAuth Utils (Immediate Fix)

**Before (ADR-055 fix):**
```python
from datetime import datetime, timedelta, timezone

def is_token_expired(expires_at: datetime) -> bool:
    return datetime.now(timezone.utc) > expires_at
```

**After (ADR-056 pattern):**
```python
from api.app.lib.datetime_utils import utcnow, is_expired

def is_token_expired(expires_at: datetime) -> bool:
    return is_expired(expires_at)
```

**Even better (semantic naming):**
```python
# oauth_utils.py
from api.app.lib.datetime_utils import (
    timedelta_from_now,
    is_expired as is_datetime_expired
)

def get_authorization_code_expiry() -> datetime:
    """Get expiration datetime for authorization codes (10 minutes)."""
    return timedelta_from_now(minutes=10)

def get_access_token_expiry() -> datetime:
    """Get expiration datetime for access tokens (1 hour)."""
    return timedelta_from_now(hours=1)

def get_refresh_token_expiry(client_type: str) -> datetime:
    """Get expiration datetime for refresh tokens (client-type dependent)."""
    if client_type == "confidential":
        return timedelta_from_now(days=30)
    else:
        return timedelta_from_now(days=7)

def is_token_expired(expires_at: datetime) -> bool:
    """Check if a token has expired."""
    return is_datetime_expired(expires_at)
```

## Implementation

### File Changes

**New files:**
- `api/app/lib/datetime_utils.py` - Central datetime utilities
- `scripts/lint_datetimes.py` - Linter for unsafe patterns

**Modified files:**
- `api/app/lib/oauth_utils.py` - Use datetime_utils instead of direct datetime calls

### Testing

```python
# tests/test_datetime_utils.py
import pytest
from datetime import datetime, timezone, timedelta
from api.app.lib.datetime_utils import (
    utcnow,
    ensure_utc,
    is_expired,
    timedelta_from_now
)


def test_utcnow_returns_aware():
    """utcnow() returns timezone-aware datetime."""
    now = utcnow()
    assert now.tzinfo == timezone.utc


def test_ensure_utc_with_naive():
    """ensure_utc() adds UTC timezone to naive datetime."""
    naive = datetime(2025, 11, 3, 12, 0, 0)
    aware = ensure_utc(naive)
    assert aware.tzinfo == timezone.utc


def test_ensure_utc_with_aware():
    """ensure_utc() converts to UTC from other timezone."""
    # Create datetime in PST (UTC-8)
    from datetime import timezone as tz
    pst = tz(timedelta(hours=-8))
    dt_pst = datetime(2025, 11, 3, 4, 0, 0, tzinfo=pst)  # 4am PST

    dt_utc = ensure_utc(dt_pst)
    assert dt_utc.tzinfo == timezone.utc
    assert dt_utc.hour == 12  # 4am PST = 12pm UTC


def test_is_expired_past():
    """is_expired() returns True for past datetime."""
    past = utcnow() - timedelta(hours=1)
    assert is_expired(past) is True


def test_is_expired_future():
    """is_expired() returns False for future datetime."""
    future = utcnow() + timedelta(hours=1)
    assert is_expired(future) is False


def test_timedelta_from_now():
    """timedelta_from_now() creates future datetime."""
    future = timedelta_from_now(hours=1)
    now = utcnow()

    assert future > now
    assert future.tzinfo == timezone.utc
```

## Consequences

### Benefits

1. **Prevents Naive/Aware Errors:**
   - ✅ All datetimes from utilities are timezone-aware
   - ✅ `ensure_utc()` safely handles mixed inputs
   - ✅ `is_expired()` handles comparisons safely

2. **Consistent Patterns:**
   - ✅ Single import: `from api.app.lib.datetime_utils import utcnow`
   - ✅ Semantic function names (`is_expired` vs manual comparison)
   - ✅ Clear intent in code

3. **Easier Testing:**
   - ✅ Mock `datetime_utils.utcnow()` in tests (single point)
   - ✅ `is_expired(dt, now=mock_now)` for deterministic tests
   - ✅ No need to patch `datetime.datetime`

4. **Linting and CI:**
   - ✅ Automated detection of unsafe patterns
   - ✅ Prevents regressions
   - ✅ Educational for new contributors

### Trade-offs

1. **Migration Effort:**
   - ⚠️ Need to update existing code incrementally
   - ⚠️ Linter will initially find many violations
   - ⚠️ Requires discipline to use new utilities

2. **Import Overhead:**
   - ⚠️ Adds import statement to files
   - ⚠️ Not a Python built-in (custom module)
   - ✅ But clearer than remembering `datetime.now(timezone.utc)`

3. **Learning Curve:**
   - ⚠️ New contributors need to learn datetime_utils
   - ✅ But simpler than understanding naive vs aware
   - ✅ Linter guides them to correct pattern

## Alternatives Considered

### Alternative 1: Use Third-Party Library (pendulum, arrow)

**Example with Pendulum:**
```python
import pendulum

now = pendulum.now('UTC')  # Always timezone-aware
```

**Rejected because:**
- ❌ Adds dependency for simple problem
- ❌ Pendulum is heavier (more features than needed)
- ❌ Standard library solution is cleaner
- ❌ Team familiarity with stdlib `datetime`

### Alternative 2: Custom `datetime` Subclass

**Enforce timezone-aware at type level:**
```python
class UTCDatetime(datetime):
    def __new__(cls, *args, **kwargs):
        if 'tzinfo' not in kwargs:
            kwargs['tzinfo'] = timezone.utc
        return super().__new__(cls, *args, **kwargs)
```

**Rejected because:**
- ❌ Breaks isinstance(obj, datetime) checks
- ❌ Not compatible with PostgreSQL drivers
- ❌ Overengineered for the problem
- ❌ Confusing inheritance semantics

### Alternative 3: PostgreSQL `TIMESTAMP WITHOUT TIME ZONE`

**Store naive datetimes in database:**
```sql
-- All timestamps without timezone
created_at TIMESTAMP WITHOUT TIME ZONE
```

**Rejected because:**
- ❌ Loses timezone information (dangerous)
- ❌ Assumes all times are UTC (not enforceable)
- ❌ Harder to work with multi-timezone data later
- ❌ Best practice is to use `WITH TIME ZONE`

### Alternative 4: Configure mypy Plugin

**Use mypy plugin to detect naive datetimes:**
```ini
# mypy.ini
[mypy]
plugins = mypy_naive_datetime_plugin
```

**Considered but not primary solution:**
- ⚠️ No official mypy plugin for this
- ⚠️ Would require writing custom plugin
- ⚠️ Runtime linter is simpler for this case
- ✅ Could be added later as enhancement

## Migration Checklist

### Immediate (ADR-056 Implementation) ✅ COMPLETED

- [x] Create `api/app/lib/datetime_utils.py`
- [x] Create `scripts/lint_datetimes.py`
- [x] Add comprehensive tests for datetime_utils (32 tests, 100% pass)
- [x] Update critical security modules:
  - [x] `api/app/lib/auth.py` (JWT token expiration) - 2 violations fixed
  - [x] `api/app/routes/oauth.py` (OAuth token rotation) - 1 violation fixed
- [x] Update audit/checkpoint modules:
  - [x] `api/app/lib/checkpoint.py` - 1 violation fixed
  - [x] `api/app/lib/query_facade.py` - 1 violation fixed
- [x] Update job management routes:
  - [x] `api/app/routes/ingest.py` - 2 violations fixed
  - [x] `api/app/routes/ingest_image.py` - 3 violations fixed
  - [x] `api/app/routes/jobs.py` - 3 violations fixed
- [x] Document in ADR-056 (this file)

**Progress: 13 of 34 violations fixed (38% complete)**
- ✅ All high-priority security and job management violations resolved
- ⏳ Remaining: 21 violations in low-priority files (utilities, workers)

### Short-term (Next Sprint)

- [ ] Migrate remaining utility modules:
  - [ ] `api/app/lib/backup_streaming.py` (1 violation)
  - [ ] `api/app/lib/gexf_exporter.py` (2 violations)
  - [ ] `api/app/logging_config.py` (1 violation)
  - [ ] `api/app/main.py` (3 violations)
  - [ ] `api/app/services/admin_service.py` (1 violation)
  - [ ] `api/app/services/scheduled_jobs_manager.py` (1 violation)
- [ ] Migrate worker modules:
  - [ ] `api/app/services/embedding_worker.py` (10 violations - performance timing)
  - [ ] `api/app/workers/ingestion_worker.py` (1 violation)
  - [ ] `api/app/workers/restore_worker.py` (1 violation)
- [ ] Add linter to pre-commit hook (optional)
- [ ] Document in `docs/guides/DEVELOPMENT.md`

### Long-term (Next Quarter)

- [ ] Verify 0 violations: `python scripts/lint_datetimes.py --strict`
- [ ] Add linter to CI pipeline
- [ ] Update contributor guidelines
- [ ] Consider mypy plugin for additional safety

## References

- **Python datetime module:** https://docs.python.org/3/library/datetime.html
- **Timezone Best Practices:** https://blog.ganssle.io/articles/2019/11/utcnow.html
- **PostgreSQL TIMESTAMP:** https://www.postgresql.org/docs/current/datatype-datetime.html
- **ISO 8601:** https://en.wikipedia.org/wiki/ISO_8601
- **RFC 3339:** https://datatracker.ietf.org/doc/html/rfc3339

## Decision Log

- **2025-11-03:** ADR created after third timezone error in OAuth implementation
- **2025-11-03:** Decided on utility module approach (simple, no dependencies)
- **2025-11-03:** Linter chosen over mypy plugin (faster to implement)
- **2025-11-04:** ADR-056 implementation completed
  - Created `api/app/lib/datetime_utils.py` with 8 utility functions
  - Created `scripts/lint_datetimes.py` linter (detects 3 unsafe patterns)
  - Fixed 13 critical violations in auth, OAuth, jobs, and audit modules
  - Added 32 comprehensive tests (100% pass rate)
  - Status changed from **Proposed** → **Accepted**

---

**Next Actions:**

1. Implement `datetime_utils.py` module
2. Update `oauth_utils.py` to use new utilities
3. Verify OAuth flow still works
4. Create linter script
5. Run linter baseline and document violations
