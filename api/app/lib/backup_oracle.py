"""
Adapter to the offline backup-object oracle (ADR-102).

The single source of truth for kg-backup/2 *spec* validation is the standalone
``scripts/development/lint/lint_backup.py`` — a stdlib-only oracle with no
api-package dependency, so it doubles as a CI/test gate and loads standalone by
path (ADR-102 Track D / P6c). This module loads that oracle by path and exposes
a thin :func:`validate_backup_object`, so the API (``POST /admin/backup/verify``)
runs the *same* checks server-side — no reimplementation, no cross-language drift.

The oracle file is shipped into the API image (see ``api/Dockerfile``:
``COPY scripts/development/lint/``) and is present at the repo root in dev.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Dict

# Candidate locations for the standalone oracle, in priority order: resolved
# relative to this file (api/app/lib -> repo root), the container path, then cwd.
_ORACLE_PATH_CANDIDATES = [
    Path(__file__).resolve().parents[3] / "scripts" / "development" / "lint" / "lint_backup.py",
    Path("/app/scripts/development/lint/lint_backup.py"),
    Path.cwd() / "scripts" / "development" / "lint" / "lint_backup.py",
]

_oracle = None  # lazily-loaded module, cached after first load


def _load_oracle():
    """Load (once) the standalone ``lint_backup`` module by file path.

    Mirrors the importlib-by-path loading the pytest suites use, so the API runs
    the exact same oracle. Raises FileNotFoundError if the file is absent (e.g.
    an API image built without the ``COPY scripts/development/lint/`` line).
    """
    global _oracle
    if _oracle is not None:
        return _oracle
    for path in _ORACLE_PATH_CANDIDATES:
        if path.is_file():
            spec = importlib.util.spec_from_file_location("kg_backup_oracle", str(path))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _oracle = module
            return _oracle
    raise FileNotFoundError(
        "offline backup oracle (lint_backup.py) not found; looked in: "
        + ", ".join(str(p) for p in _ORACLE_PATH_CANDIDATES)
    )


def validate_backup_object(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Run the offline oracle on a parsed kg-backup/2 object; return a JSON report.

    Returns ``{ok, format_version, errors, warnings, notices, issues}`` where
    ``issues`` is the full ordered list of ``{severity, code, message, location}``
    and the severity buckets are convenience filters of that list.
    """
    oracle = _load_oracle()
    result = oracle.validate_backup(obj)
    issues = [
        {"severity": i.severity, "code": i.code, "message": i.message, "location": i.location}
        for i in result.issues
    ]
    return {
        "ok": result.ok,
        "format_version": result.format_version,
        "errors": [i for i in issues if i["severity"] == "ERROR"],
        "warnings": [i for i in issues if i["severity"] == "WARNING"],
        "notices": [i for i in issues if i["severity"] == "NOTICE"],
        "issues": issues,
    }
