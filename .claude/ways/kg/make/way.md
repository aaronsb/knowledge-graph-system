---
match: regex
pattern: \bmake\b|makefile|run.*(test|suite|lint)|docstring.?coverage|scan.?for.*(antipattern|slop)|\bpytest\b|python3?\s.*pytest|PYTHONPATH|\.?/?venv|pip\s+install|npm\s+(test|run)|cargo\s+(test|pgrx)|docker\s+exec\s+kg-
commands: ^make\s|^pytest|^python3?\s|^PYTHONPATH|^docker exec kg-|^npm (test|run)|^cargo (test|pgrx)
scope: agent, subagent
---
# Make Targets Way

**Use `make <target>` from the project root instead of raw commands.**
Make handles container checks, paths, and flags. If no target covers
what you need, run the command directly — this isn't a cage.

| Instead of | Use |
|------------|-----|
| `pytest tests/` or `docker exec kg-api-dev pytest ...` | `make test` |
| `python3 -m pytest tests/unit/` | `make test-unit` |
| `python3 scripts/development/lint/...` | `make lint`, `make coverage`, `make slopscan` |
| `pip install ...` or `venv` | Everything runs in containers — no local Python env needed |

Run `make` with no arguments to see all targets.
