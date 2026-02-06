"""
Cypher safety guard for query endpoints (ADR-500 Phase 2a).

Reusable safety checks extracted from the GraphProgram validator. Guards
user-submitted Cypher against write operations and unbounded traversals
before it reaches the database.

This module is the runtime gate; the validator is the notarization-time gate.
Both use the same underlying checks so the rules stay in sync.

    from api.app.services.cypher_guard import check_cypher_safety

    issues = check_cypher_safety(query)
    if issues:
        raise HTTPException(400, detail=...)

Zero platform dependencies: pure Python only. Shares constants and logic
with ``program_validator.py``.

@verified 0000000
"""

from typing import List

from api.app.services.program_validator import (
    ValidationIssue,
    _sanitize_cypher,
    _check_cypher_safety as _validator_check_cypher,
)


def check_cypher_safety(query: str) -> List[ValidationIssue]:
    """
    Check a raw Cypher query for write keywords and unbounded paths.

    Delegates to the same V010-V016 and V030 checks used by the GraphProgram
    validator, using statement index -1 (not part of a program).

    Args:
        query: Raw Cypher query string from user input.

    Returns:
        List of ValidationIssue objects. Empty list means the query is safe.

    @verified 0000000
    """
    return _validator_check_cypher(query, index=-1)
