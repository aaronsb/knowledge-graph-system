# Docstring Coverage

`scripts/development/lint/docstring_coverage.py` measures docstring coverage and tracks freshness across Python, TypeScript, and Rust source files in Kappa Graph. Run it from anywhere inside the repository — it finds the project root automatically.

## Run the tool

```bash
# Coverage report (all languages)
python3 scripts/development/lint/docstring_coverage.py

# Verbose — show each undocumented item with file:line
python3 scripts/development/lint/docstring_coverage.py -v

# Staleness analysis — compare @verified tags against git history
python3 scripts/development/lint/docstring_coverage.py --staleness

# CI gate — fail if coverage drops below threshold
python3 scripts/development/lint/docstring_coverage.py --fail-under 80
```

Install `interrogate` for more accurate Python coverage; the tool falls back to `ast.parse()` when it is absent:

```bash
pip install interrogate
```

## What it scans

| Language   | Directories                                          | Scanner |
|------------|------------------------------------------------------|---------|
| Python     | `api/app/`, `fuse/kg_fuse/`                          | `interrogate` (AST) or built-in `ast` fallback |
| TypeScript | `web/src/`, `cli/src/`                               | Built-in regex |
| Rust       | `graph-accel/core/src/`, `graph-accel/ext/src/`      | Built-in regex |

### Documentable items

| Language   | Items                                                                              | Doc style   |
|------------|------------------------------------------------------------------------------------|-------------|
| Python     | `def`, `async def`, `class` (public + module-level)                                | `"""..."""` |
| TypeScript | `export function`, `export const`, `export class`, `export interface`, `export type` | `/** ... */` |
| Rust       | `pub fn`, `pub struct`, `pub enum`, `pub trait`, `pub type`, `pub const`            | `///` |

### Exclusions

- Python: `__init__.py`, test files, private helpers (`_name`)
- TypeScript: `*.test.ts`, `*.spec.ts`, `*.d.ts`, re-exports
- Rust: `#[cfg(test)]` modules, benchmark crate

## Staleness tracking

### The problem

Docstrings drift from reality. Code changes; docstrings do not. Without a mechanism to detect this, documentation silently becomes misleading.

### Three dates, no extra state

For each documented item, the tool knows three things:

1. **Docstring date** — the commit hash stamped in the `@verified` tag
2. **File last commit** — from `git log`
3. **Current date** — when you run the check

This produces a tristate:

| Status       | Meaning |
|--------------|---------|
| **current**  | `@verified` commit matches or postdates the file's last commit |
| **stale**    | File was modified after the `@verified` commit (with drift in days) |
| **unverified** | No `@verified` tag — docstring exists but freshness is unknown |

No hashing, no sidecar files, no derived state. Git is the database.

### Adding @verified tags

When you write or review a docstring, stamp it with the current short commit hash. The tag format is the same across all three languages:

Get the current short hash:

```bash
git log -1 --format=%h
```

**Python:**
```python
def calculate_grounding(concept_id: str) -> float:
    """Calculate grounding strength for a concept.

    Uses the two-tier cache (vocabulary + per-concept) to avoid
    redundant graph queries.

    @verified a1b2c3f
    """
```

**TypeScript:**
```typescript
/**
 * Execute a saved query by replaying its Cypher statements.
 *
 * @verified a1b2c3f
 */
export function executeSavedQuery(query: QueryDefinition): void {
```

**Rust:**
```rust
/// Perform BFS neighborhood traversal from a concept node.
///
/// @verified a1b2c3f
pub fn neighborhood(start: &str, max_depth: usize) -> Vec<Edge> {
```

### Reading the staleness report

```
=== Staleness Report ===

  api/app/lib/graph_facade.py  (last commit: today)
    GraphFacade                              ✓ current       @verified a1b2c3f
    neighborhood                             ⚠ stale         @verified 77e2876 — 12d drift
    find_path                                · unverified
```

- **current** — the docstring was verified at or after the file's last change.
- **stale (Nd drift)** — the file changed N days after the `@verified` commit; the docstring may no longer be accurate.
- **unverified** — no `@verified` tag; the docstring might be fine, but nobody has confirmed it.

### Incremental workflow

The staleness report acts as a self-maintaining todo list:

1. Run `--staleness`
2. Stale items surface automatically — code changed, docstring did not
3. Review the docstring against the current code
4. If accurate, update the `@verified` hash to the current commit
5. If inaccurate, fix the docstring and stamp it

For agent-assisted docstring passes, this gives a natural priority queue: missing docstrings first, then stale ones, then unverified for spot-checking.

## CLI reference

```
usage: docstring_coverage.py [-h] [-v] [--fail-under FAIL_UNDER]
                             [--python-only] [--ts-only] [--rust-only]
                             [--staleness] [--no-color] [--json]

options:
  -v, --verbose         Show each undocumented item with file:line
  --fail-under N        Exit non-zero if overall coverage < N%
  --python-only         Run only Python scan
  --ts-only             Run only TypeScript scan
  --rust-only           Run only Rust scan
  --staleness           Analyze docstring freshness via @verified tags
  --no-color            Disable ANSI color output
  --json                Output as JSON (for CI or piping to other tools)
```

`--staleness` forces the Python scanner to use AST mode, bypassing `interrogate`, because staleness analysis requires reading docstring content that `interrogate` does not expose. `--json` implies `--staleness`.

## Architecture

```
docstring_coverage.py
├── Shared
│   └── _extract_verified(doc_text)       ← single @verified regex for all languages
├── Python scanner
│   ├── interrogate (subprocess)          ← preferred, AST-based
│   └── ast.parse fallback                ← extracts docstring text for @verified
├── TypeScript scanner
│   └── _extract_jsdoc_above(lines, i)    ← returns JSDoc text or None
├── Rust scanner
│   └── _extract_rust_doc_above(lines, i) ← returns /// text or None
├── Git helpers
│   ├── _git_file_last_commit(path)       ← one call per file
│   └── _git_commit_timestamp(hash)       ← one call per unique @verified hash
└── Staleness analysis
    ├── compute_staleness(results)        ← batch resolve, build entries
    └── print_staleness_report(entries)   ← tristate report
```

Each language scanner follows the same pattern: extract the full doc comment text (language-specific parsing), pass it to `_extract_verified()` (shared regex), store the result on `DocItem.verified_commit`. This keeps the `@verified` tag format consistent across languages while letting each scanner handle its own doc comment syntax.
