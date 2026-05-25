"""
Regression guard: workers must not reach past the GraphQueryFacade for graph
queries.

The GraphQueryFacade (ADR-048) is the namespace-safe entry point for all
Cypher executed against Apache AGE. Workers that reach for the raw escape
hatch (`facade.execute_raw(...)`) or bypass the facade entirely
(`age_client._execute_cypher(...)`) lose audit trail, namespace safety, and
the typed DSL surface that the facade is meant to enforce. See PR #413
(closes #355) for the migration that drove this guard.

Scope: only Cypher escape hatches are checked. Raw psycopg2 access to
``kg_api.*`` relational tables (job queue, proposals, artifact metadata,
embedding storage) is out of scope — the facade is a *graph* DSL, not an
ORM, and relational reads/writes against the kg_api schema have no facade
equivalent.

Allowlist policy: any new entry must come with a documented reason inline,
and ideally a path back to the facade (or an ADR explaining why it stays
raw). The bar to add an exception is the same as the bar to introduce a
new `execute_raw` call — high.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Tuple

import pytest


WORKERS_DIR = Path(__file__).resolve().parents[3] / "api" / "app" / "workers"

# Files whose direct ``_execute_cypher`` usage is intentional and not
# migratable. Each entry must explain why.
EXECUTE_CYPHER_ALLOWLIST: Dict[str, str] = {
    "restore_worker.py": (
        "Privileged dataset-authority worker. _clear_database issues "
        "DETACH DELETE against Concept/Source/Instance labels as part of a "
        "full-restore teardown. No parameter substitution, no user input — "
        "a facade method would not add safety, and restore needs full "
        "authority over the graph."
    ),
}


def _iter_worker_files() -> List[Path]:
    """Yield every worker .py file (skipping __init__) in lexical order."""
    return sorted(
        p for p in WORKERS_DIR.glob("*.py")
        if p.name != "__init__.py"
    )


def _find_pattern(path: Path, pattern: str) -> List[Tuple[int, str]]:
    """Return ``(line_number, line)`` pairs where ``pattern`` appears verbatim."""
    matches: List[Tuple[int, str]] = []
    for lineno, line in enumerate(path.read_text().splitlines(), start=1):
        if pattern in line:
            matches.append((lineno, line.rstrip()))
    return matches


# Build parametrize IDs from the file basename so a failure points at the
# exact worker.
_WORKER_PARAMS = [pytest.param(p, id=p.name) for p in _iter_worker_files()]


@pytest.mark.parametrize("worker_path", _WORKER_PARAMS)
def test_worker_does_not_use_facade_execute_raw(worker_path: Path) -> None:
    """No worker may call ``facade.execute_raw(...)`` — the raw escape hatch
    logs a WARNING on every invocation and bypasses the typed DSL.

    To extend the facade with a new shape, add a typed method to
    ``GraphQueryFacade`` and route the worker through it. See PR #413 for
    examples (``count_sources``, ``update_source_properties``,
    ``get_vocab_type_stats``).
    """
    matches = _find_pattern(worker_path, "facade.execute_raw(")
    assert not matches, (
        f"{worker_path.name} contains {len(matches)} facade.execute_raw "
        f"call(s) — promote to a typed GraphQueryFacade method instead.\n"
        + "\n".join(f"  L{lineno}: {line}" for lineno, line in matches)
    )


@pytest.mark.parametrize("worker_path", _WORKER_PARAMS)
def test_worker_does_not_call_execute_cypher_directly(worker_path: Path) -> None:
    """No worker may call ``age_client._execute_cypher(...)`` — that bypasses
    the facade audit log and namespace safety entirely.

    The single allowed exception is ``restore_worker.py`` (see
    ``EXECUTE_CYPHER_ALLOWLIST`` for the rationale). Adding a new exception
    requires the same care as adding a new ``execute_raw`` call.
    """
    matches = _find_pattern(worker_path, "._execute_cypher(")

    if worker_path.name in EXECUTE_CYPHER_ALLOWLIST:
        # Allowlisted: confirm the file still uses it (otherwise the entry
        # is stale and should be removed) but don't fail.
        assert matches, (
            f"{worker_path.name} is in EXECUTE_CYPHER_ALLOWLIST but no "
            "_execute_cypher calls remain — remove the allowlist entry."
        )
        return

    assert not matches, (
        f"{worker_path.name} bypasses the facade with {len(matches)} "
        f"_execute_cypher call(s). Either route through GraphQueryFacade or, "
        f"if this worker has a defensible reason to bypass it, add an entry "
        f"to EXECUTE_CYPHER_ALLOWLIST with the rationale.\n"
        + "\n".join(f"  L{lineno}: {line}" for lineno, line in matches)
    )
