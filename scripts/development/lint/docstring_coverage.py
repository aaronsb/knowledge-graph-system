#!/usr/bin/env python3
"""
Cross-language docstring coverage and staleness reporter.

Scans Python, TypeScript, and Rust source files to report documentation
coverage. Delegates to `interrogate` for Python (AST-based accuracy),
uses built-in regex scanners for TypeScript and Rust.

Staleness tracking (--staleness): Each scanner extracts `@verified <hash>`
tags from docstrings. The tool compares the verified commit date against
the file's last commit date to produce a tristate:
  - current:    @verified commit >= file's last commit
  - stale:      @verified commit < file's last commit (with drift in days)
  - unverified: no @verified tag present

Usage:
    python3 scripts/development/lint/docstring_coverage.py
    python3 scripts/development/lint/docstring_coverage.py -v
    python3 scripts/development/lint/docstring_coverage.py --staleness
    python3 scripts/development/lint/docstring_coverage.py --fail-under 80
"""

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DocItem:
    """A single documentable item found in source code."""
    file_path: str
    line: int
    name: str
    kind: str  # 'function', 'class', 'method', 'interface', 'type', etc.
    documented: bool
    verified_commit: Optional[str] = None


@dataclass
class FileResult:
    """Coverage result for a single file."""
    path: str
    total: int = 0
    documented: int = 0
    items: List[DocItem] = field(default_factory=list)

    @property
    def percentage(self) -> float:
        return (self.documented / self.total * 100) if self.total > 0 else 100.0


@dataclass
class LanguageResult:
    """Aggregated coverage result for a language."""
    language: str
    files: List[FileResult] = field(default_factory=list)
    note: str = ""

    @property
    def total(self) -> int:
        return sum(f.total for f in self.files)

    @property
    def documented(self) -> int:
        return sum(f.documented for f in self.files)

    @property
    def percentage(self) -> float:
        return (self.documented / self.total * 100) if self.total > 0 else 100.0


# ---------------------------------------------------------------------------
# Shared: @verified tag extraction
# ---------------------------------------------------------------------------

# Matches @verified <short-or-full commit hash> in any doc comment style.
# Each language scanner extracts the raw doc text, then calls this regex.
_VERIFIED_RE = re.compile(r'@verified\s+([0-9a-f]{7,40})')


def _extract_verified(doc_text: Optional[str]) -> Optional[str]:
    """Extract commit hash from an @verified tag in doc comment text.

    This is the single extraction point used by all three language scanners,
    keeping the tag format consistent across Python, TypeScript, and Rust.
    """
    if not doc_text:
        return None
    m = _VERIFIED_RE.search(doc_text)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Python scanner (AST-based fallback when interrogate unavailable)
# ---------------------------------------------------------------------------

def _python_get_docstring(node: ast.AST) -> Optional[str]:
    """Extract the docstring text from an AST node, or None if absent."""
    if not hasattr(node, 'body') or not node.body:
        return None
    first = node.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
        if isinstance(first.value.value, str):
            return first.value.value
    return None


def scan_python_ast(file_path: str) -> FileResult:
    """Scan a Python file using the ast module for docstring coverage."""
    result = FileResult(path=file_path)
    try:
        source = Path(file_path).read_text(encoding='utf-8')
        tree = ast.parse(source, filename=file_path)
    except (SyntaxError, UnicodeDecodeError):
        return result

    class_children = _build_class_children(tree)

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip private helpers (single underscore, not dunder)
            if node.name.startswith('_') and not node.name.startswith('__'):
                continue
            kind = 'method' if id(node) in class_children else 'function'
            docstring = _python_get_docstring(node)
            item = DocItem(
                file_path=file_path,
                line=node.lineno,
                name=node.name,
                kind=kind,
                documented=docstring is not None,
                verified_commit=_extract_verified(docstring),
            )
            result.items.append(item)
            result.total += 1
            if item.documented:
                result.documented += 1

        elif isinstance(node, ast.ClassDef):
            docstring = _python_get_docstring(node)
            item = DocItem(
                file_path=file_path,
                line=node.lineno,
                name=node.name,
                kind='class',
                documented=docstring is not None,
                verified_commit=_extract_verified(docstring),
            )
            result.items.append(item)
            result.total += 1
            if item.documented:
                result.documented += 1

    return result


def _build_class_children(tree: ast.Module) -> set:
    """Build set of AST nodes that are direct children of a class body."""
    children = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                children.add(id(child))
    return children


def scan_python_interrogate(directories: List[str], project_root: str) -> Optional[LanguageResult]:
    """Try to run interrogate and parse its output.

    Returns None if interrogate is not installed.
    """
    if not shutil.which('interrogate'):
        return None

    result = LanguageResult(language="Python", note="(interrogate)")

    for directory in directories:
        abs_dir = os.path.join(project_root, directory)
        if not os.path.isdir(abs_dir):
            continue

        proc = subprocess.run(
            [
                'interrogate', '-v',
                '--fail-under', '0',
                '--ignore-init-module',
                '--ignore-init-method',
                '--ignore-semiprivate',
                '--ignore-private',
                '--ignore-magic',
                '--quiet',
                abs_dir,
            ],
            capture_output=True, text=True, cwd=project_root
        )

        # Parse interrogate verbose output — lines like:
        #   api/app/lib/graph_facade.py  (24/26)  92.3%
        # or the detailed per-item lines in -vv mode
        for line in proc.stdout.splitlines():
            # Match file summary lines: path (covered/total) pct%
            m = re.match(
                r'\s*([\w/._-]+\.py)\s+.*?(\d+)/(\d+)\s+.*?([\d.]+)%',
                line
            )
            if m:
                path = m.group(1)
                documented = int(m.group(2))
                total = int(m.group(3))
                if total > 0:
                    result.files.append(FileResult(
                        path=path,
                        total=total,
                        documented=documented,
                    ))

        # If interrogate's verbose mode didn't give per-file stats,
        # try to parse the summary line
        if not result.files:
            for line in proc.stdout.splitlines():
                m = re.match(r'.*?(\d+)/(\d+)\s+.*?([\d.]+)%', line)
                if m:
                    documented = int(m.group(1))
                    total = int(m.group(2))
                    if total > 0:
                        result.files.append(FileResult(
                            path=directory,
                            total=total,
                            documented=documented,
                        ))
                    break

    return result if result.files else None


def scan_python(directories: List[str], project_root: str, force_ast: bool = False) -> LanguageResult:
    """Scan Python files for docstring coverage.

    Uses interrogate if available, falls back to AST-based scanning.
    When force_ast is True, always uses AST (needed for --staleness,
    since interrogate doesn't expose docstring content).
    """
    # Try interrogate first (unless staleness needs docstring content)
    if not force_ast:
        interrogate_result = scan_python_interrogate(directories, project_root)
        if interrogate_result is not None:
            return interrogate_result

    # Fallback: AST-based scanning
    result = LanguageResult(language="Python", note="(ast fallback)")
    print(
        "  Note: install 'interrogate' for more accurate Python scanning: "
        "pip install interrogate",
        file=sys.stderr,
    )

    for directory in directories:
        abs_dir = os.path.join(project_root, directory)
        if not os.path.isdir(abs_dir):
            continue

        for root, _dirs, files in os.walk(abs_dir):
            # Skip test directories and __pycache__
            rel_root = os.path.relpath(root, project_root)
            if '/tests/' in rel_root or rel_root.startswith('tests/'):
                continue
            if '__pycache__' in rel_root:
                continue

            for fname in sorted(files):
                if not fname.endswith('.py'):
                    continue
                if fname == '__init__.py':
                    continue

                fpath = os.path.join(root, fname)
                rel_path = os.path.relpath(fpath, project_root)
                file_result = scan_python_ast(fpath)
                file_result.path = rel_path
                if file_result.total > 0:
                    result.files.append(file_result)

    return result


# ---------------------------------------------------------------------------
# TypeScript scanner (regex-based)
# ---------------------------------------------------------------------------

# Patterns for documentable TypeScript exports
_TS_EXPORT_RE = re.compile(
    r'^export\s+'
    r'(?:default\s+)?'
    r'(?:async\s+)?'
    r'(function|const|let|class|interface|type|enum)\s+'
    r'(\w+)',
)

# Re-export pattern (skip these)
_TS_REEXPORT_RE = re.compile(r'^export\s+\{.*\}\s+from\s+')

# JSDoc end marker
_JSDOC_END_RE = re.compile(r'\*/\s*$')

# JSDoc start marker
_JSDOC_START_RE = re.compile(r'^\s*/\*\*')


def scan_typescript_file(file_path: str, project_root: str) -> FileResult:
    """Scan a TypeScript file for JSDoc coverage on exported items."""
    rel_path = os.path.relpath(file_path, project_root)
    result = FileResult(path=rel_path)

    try:
        lines = Path(file_path).read_text(encoding='utf-8').splitlines()
    except (UnicodeDecodeError, OSError):
        return result

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Skip re-exports
        if _TS_REEXPORT_RE.match(stripped):
            continue

        m = _TS_EXPORT_RE.match(stripped)
        if not m:
            continue

        kind = m.group(1)
        name = m.group(2)

        # Look backwards for JSDoc comment ending with */
        jsdoc = _extract_jsdoc_above(lines, i)

        item = DocItem(
            file_path=rel_path,
            line=i + 1,
            name=name,
            kind=kind,
            documented=jsdoc is not None,
            verified_commit=_extract_verified(jsdoc),
        )
        result.items.append(item)
        result.total += 1
        if item.documented:
            result.documented += 1

    return result


def _extract_jsdoc_above(lines: List[str], target_idx: int) -> Optional[str]:
    """Extract JSDoc comment (/** ... */) above the target line.

    Scans backwards, skipping blank lines and decorators. Returns the
    JSDoc text content if found, None otherwise. Used by both the
    coverage check (is it None?) and @verified extraction.
    """
    scan_limit = max(0, target_idx - 30)

    # Step 1: find */ (end of JSDoc)
    end_idx = None
    for j in range(target_idx - 1, scan_limit - 1, -1):
        prev = lines[j].strip()
        if not prev:
            continue
        if prev.startswith('@'):
            continue
        if prev.endswith('*/'):
            end_idx = j
            break
        # Hit a non-comment, non-blank line — no JSDoc
        return None

    if end_idx is None:
        return None

    # Step 2: scan backwards from end to find /**
    for j in range(end_idx, scan_limit - 1, -1):
        if _JSDOC_START_RE.match(lines[j]):
            return '\n'.join(lines[j:end_idx + 1])

    return None


def scan_typescript(directories: List[str], project_root: str) -> LanguageResult:
    """Scan TypeScript files for JSDoc coverage on exported items."""
    result = LanguageResult(language="TypeScript")

    for directory in directories:
        abs_dir = os.path.join(project_root, directory)
        if not os.path.isdir(abs_dir):
            continue

        for root, _dirs, files in os.walk(abs_dir):
            rel_root = os.path.relpath(root, project_root)

            for fname in sorted(files):
                if not (fname.endswith('.ts') or fname.endswith('.tsx')):
                    continue
                # Skip test files
                if fname.endswith('.test.ts') or fname.endswith('.spec.ts'):
                    continue
                if fname.endswith('.test.tsx') or fname.endswith('.spec.tsx'):
                    continue
                # Skip declaration files
                if fname.endswith('.d.ts'):
                    continue

                fpath = os.path.join(root, fname)
                file_result = scan_typescript_file(fpath, project_root)
                if file_result.total > 0:
                    result.files.append(file_result)

    return result


# ---------------------------------------------------------------------------
# Rust scanner (regex-based)
# ---------------------------------------------------------------------------

# Patterns for documentable Rust public items
_RUST_PUB_RE = re.compile(
    r'^\s*pub(?:\([^)]*\))?\s+'
    r'(?:unsafe\s+)?'
    r'(?:async\s+)?'
    r'(fn|struct|enum|trait|type|const|static|mod)\s+'
    r'(\w+)',
)

# Doc comment
_RUST_DOC_RE = re.compile(r'^\s*///')

# Derive/attribute macro
_RUST_ATTR_RE = re.compile(r'^\s*#\[')

# cfg(test) module start
_RUST_CFG_TEST_RE = re.compile(r'#\[cfg\(test\)\]')


def scan_rust_file(file_path: str, project_root: str) -> FileResult:
    """Scan a Rust file for doc comment coverage on public items."""
    rel_path = os.path.relpath(file_path, project_root)
    result = FileResult(path=rel_path)

    try:
        lines = Path(file_path).read_text(encoding='utf-8').splitlines()
    except (UnicodeDecodeError, OSError):
        return result

    # Track whether we're inside a #[cfg(test)] module
    in_test_module = False
    brace_depth_at_test = 0
    brace_depth = 0

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Track brace depth for #[cfg(test)] exclusion.
        # Note: naive counting — braces in strings/comments could throw this
        # off, but in practice Rust test modules are straightforward.
        brace_depth += stripped.count('{') - stripped.count('}')

        if _RUST_CFG_TEST_RE.search(stripped):
            in_test_module = True
            brace_depth_at_test = brace_depth

        if in_test_module and brace_depth <= brace_depth_at_test and i > 0:
            # Exited the test module
            if brace_depth < brace_depth_at_test:
                in_test_module = False

        if in_test_module:
            continue

        m = _RUST_PUB_RE.match(line)
        if not m:
            continue

        kind = m.group(1)
        name = m.group(2)

        # Look backwards for /// doc comments, skipping #[...] attributes
        doc = _extract_rust_doc_above(lines, i)

        item = DocItem(
            file_path=rel_path,
            line=i + 1,
            name=name,
            kind=kind,
            documented=doc is not None,
            verified_commit=_extract_verified(doc),
        )
        result.items.append(item)
        result.total += 1
        if item.documented:
            result.documented += 1

    return result


def _extract_rust_doc_above(lines: List[str], target_idx: int) -> Optional[str]:
    """Extract /// doc comment block above the target line.

    Skips #[...] attribute lines. Returns the doc comment text if found,
    None otherwise. Used by both the coverage check and @verified extraction.
    """
    scan_limit = max(0, target_idx - 30)
    doc_lines = []

    for j in range(target_idx - 1, scan_limit - 1, -1):
        prev = lines[j].strip()
        if not prev:
            if doc_lines:
                break  # blank line after doc comments = end of block
            continue
        if _RUST_ATTR_RE.match(prev):
            continue
        if _RUST_DOC_RE.match(prev):
            doc_lines.append(prev)
            continue
        break

    if not doc_lines:
        return None

    doc_lines.reverse()
    return '\n'.join(doc_lines)


def scan_rust(directories: List[str], project_root: str) -> LanguageResult:
    """Scan Rust files for doc comment coverage on public items."""
    result = LanguageResult(language="Rust")

    for directory in directories:
        abs_dir = os.path.join(project_root, directory)
        if not os.path.isdir(abs_dir):
            continue

        for root, _dirs, files in os.walk(abs_dir):
            rel_root = os.path.relpath(root, project_root)

            # Skip benchmark directory
            if 'bench/' in rel_root or rel_root.endswith('bench'):
                continue

            for fname in sorted(files):
                if not fname.endswith('.rs'):
                    continue

                fpath = os.path.join(root, fname)
                file_result = scan_rust_file(fpath, project_root)
                if file_result.total > 0:
                    result.files.append(file_result)

    return result


# ---------------------------------------------------------------------------
# Git helpers (for --staleness)
# ---------------------------------------------------------------------------

def _git_file_last_commit(file_path: str, project_root: str) -> Tuple[Optional[str], Optional[int]]:
    """Get the most recent commit hash and unix timestamp for a file."""
    proc = subprocess.run(
        ['git', 'log', '-1', '--format=%H %ct', '--', file_path],
        capture_output=True, text=True, cwd=project_root,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        parts = proc.stdout.strip().split()
        if len(parts) == 2:
            return parts[0], int(parts[1])
    return None, None


def _git_commit_timestamp(commit_hash: str, project_root: str) -> Optional[int]:
    """Resolve a commit hash (full or short) to a unix timestamp."""
    proc = subprocess.run(
        ['git', 'show', '-s', '--format=%ct', commit_hash],
        capture_output=True, text=True, cwd=project_root,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        try:
            return int(proc.stdout.strip().splitlines()[0])
        except ValueError:
            pass
    return None


def _format_age(ts: Optional[int]) -> str:
    """Format a unix timestamp as a human-readable age string."""
    if ts is None:
        return "unknown"
    days = max(0, (int(time.time()) - ts) // 86400)
    if days == 0:
        return "today"
    elif days == 1:
        return "1d ago"
    else:
        return f"{days}d ago"


# ---------------------------------------------------------------------------
# Staleness analysis (--staleness)
# ---------------------------------------------------------------------------

@dataclass
class StalenessEntry:
    """Staleness analysis for a single documented item.

    Tristate: current (verified >= file last commit), stale (verified <
    file last commit), or unverified (no @verified tag).
    """
    item: DocItem
    file_last_commit: Optional[str] = None
    file_last_ts: Optional[int] = None
    verified_ts: Optional[int] = None

    @property
    def status(self) -> str:
        if not self.item.verified_commit:
            return 'unverified'
        if self.verified_ts is None:
            return 'unknown'
        if self.file_last_ts is None:
            return 'unknown'
        # Prefix match: @verified hash may be short (7 chars)
        v = self.item.verified_commit
        f = self.file_last_commit or ''
        if f.startswith(v) or v.startswith(f):
            return 'current'
        # Compare timestamps
        if self.verified_ts >= self.file_last_ts:
            return 'current'
        return 'stale'

    @property
    def drift_days(self) -> Optional[int]:
        if self.status != 'stale' or not self.verified_ts or not self.file_last_ts:
            return None
        return max(0, (self.file_last_ts - self.verified_ts) // 86400)


def compute_staleness(
    results: List[LanguageResult],
    project_root: str,
) -> List[StalenessEntry]:
    """Resolve git timestamps and compute staleness for all documented items."""
    entries: List[StalenessEntry] = []

    # Cache: file path -> (last_commit_hash, last_commit_ts)
    file_commits: dict = {}
    # Collect unique @verified hashes to batch-resolve
    verified_hashes: set = set()

    for lang_result in results:
        for fr in lang_result.files:
            if fr.path not in file_commits:
                file_commits[fr.path] = _git_file_last_commit(fr.path, project_root)
            for item in fr.items:
                if item.documented and item.verified_commit:
                    verified_hashes.add(item.verified_commit)

    # Resolve verified commit timestamps
    hash_timestamps: dict = {}
    for h in verified_hashes:
        ts = _git_commit_timestamp(h, project_root)
        if ts is not None:
            hash_timestamps[h] = ts

    # Build entries for all documented items
    for lang_result in results:
        for fr in lang_result.files:
            fc_hash, fc_ts = file_commits.get(fr.path, (None, None))
            for item in fr.items:
                if not item.documented:
                    continue
                entry = StalenessEntry(
                    item=item,
                    file_last_commit=fc_hash,
                    file_last_ts=fc_ts,
                    verified_ts=hash_timestamps.get(
                        item.verified_commit
                    ) if item.verified_commit else None,
                )
                entries.append(entry)

    return entries


def print_staleness_report(
    entries: List[StalenessEntry],
    use_color: bool = True,
) -> None:
    """Print the staleness report grouped by file."""
    bold = BOLD if use_color else ''
    dim = DIM if use_color else ''
    reset = RESET if use_color else ''
    green = GREEN if use_color else ''
    yellow = YELLOW if use_color else ''
    red = RED if use_color else ''

    # Group by file
    by_file: dict = {}
    for entry in entries:
        by_file.setdefault(entry.item.file_path, []).append(entry)

    print(f"\n{bold}=== Staleness Report ==={reset}")

    has_any_verified = any(e.item.verified_commit for e in entries)

    if not has_any_verified:
        print(f"\n  {dim}No @verified tags found in docstrings.{reset}")
        print(f"  {dim}Add '@verified <commit-hash>' to track docstring freshness.{reset}")
        print(f"  {dim}Example (Python):  @verified a1b2c3f{reset}")
        print(f"  {dim}Example (JSDoc):   @verified a1b2c3f{reset}")
        print(f"  {dim}Example (Rust):    @verified a1b2c3f{reset}")

    for file_path in sorted(by_file.keys()):
        file_entries = by_file[file_path]
        # Skip files with no verified tags (avoid noise)
        if not any(e.item.verified_commit for e in file_entries):
            continue

        fc_ts = file_entries[0].file_last_ts if file_entries else None
        age_str = _format_age(fc_ts)
        print(f"\n  {bold}{file_path}{reset}  {dim}(last commit: {age_str}){reset}")

        for entry in file_entries:
            status = entry.status
            name = entry.item.name
            if status == 'current':
                marker = f"{green}✓ current{reset}" if use_color else "  current"
                tag = f"@verified {entry.item.verified_commit}"
                print(f"    {name:<40s} {marker:<20s} {dim}{tag}{reset}")
            elif status == 'stale':
                drift = entry.drift_days
                drift_str = f" — {drift}d drift" if drift is not None else ""
                marker = f"{yellow}⚠ stale{reset}" if use_color else "! stale"
                tag = f"@verified {entry.item.verified_commit}{drift_str}"
                print(f"    {name:<40s} {marker:<20s} {dim}{tag}{reset}")
            elif status == 'unknown':
                marker = f"{red}? unknown{reset}" if use_color else "? unknown"
                tag = f"@verified {entry.item.verified_commit} (hash not found)"
                print(f"    {name:<40s} {marker:<20s} {dim}{tag}{reset}")
            else:
                marker = f"{dim}· unverified{reset}" if use_color else ". unverified"
                print(f"    {name:<40s} {marker}")

    # Summary counts
    current = sum(1 for e in entries if e.status == 'current')
    stale = sum(1 for e in entries if e.status == 'stale')
    unknown = sum(1 for e in entries if e.status == 'unknown')
    unverified = sum(1 for e in entries if e.status == 'unverified')
    total = len(entries)

    print(f"\n{bold}=== Staleness Summary ==={reset}")
    if total == 0:
        print("  No documented items found.")
        return

    if current:
        m = f"{green}✓{reset}" if use_color else " "
        print(f"  {m} Current:      {current:>4d}  ({current * 100 // total}%)")
    if stale:
        m = f"{yellow}⚠{reset}" if use_color else "!"
        print(f"  {m} Stale:        {stale:>4d}  ({stale * 100 // total}%)")
    if unknown:
        m = f"{red}?{reset}" if use_color else "?"
        print(f"  {m} Unknown hash: {unknown:>4d}  ({unknown * 100 // total}%)")
    if unverified:
        m = f"{dim}·{reset}" if use_color else "."
        print(f"  {m} Unverified:   {unverified:>4d}  ({unverified * 100 // total}%)")
    print(f"  {'Total documented:':<16s} {total:>4d}")


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

BOLD = '\033[1m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RED = '\033[31m'
DIM = '\033[2m'
RESET = '\033[0m'


def _color_pct(pct: float, use_color: bool) -> str:
    """Color a percentage value based on coverage level."""
    if not use_color:
        return f"{pct:.1f}%"
    if pct >= 90:
        return f"{GREEN}{pct:.1f}%{RESET}"
    elif pct >= 70:
        return f"{YELLOW}{pct:.1f}%{RESET}"
    else:
        return f"{RED}{pct:.1f}%{RESET}"


def print_results(
    results: List[LanguageResult],
    verbose: bool = False,
    use_color: bool = True,
) -> None:
    """Print the coverage report."""
    bold = BOLD if use_color else ''
    dim = DIM if use_color else ''
    reset = RESET if use_color else ''

    overall_total = 0
    overall_documented = 0

    for lang_result in results:
        if not lang_result.files:
            continue

        note = f" {lang_result.note}" if lang_result.note else ""
        print(f"\n{bold}=== {lang_result.language}{note} ==={reset}")

        # Per-file results
        for fr in sorted(lang_result.files, key=lambda f: f.path):
            pct = _color_pct(fr.percentage, use_color)
            count = f"{fr.documented}/{fr.total}"
            print(f"  {fr.path:<60s} {count:>8s}  ({pct})")

            if verbose:
                for item in fr.items:
                    if not item.documented:
                        marker = f"{RED}MISSING{reset}" if use_color else "MISSING"
                        print(
                            f"    {dim}{item.file_path}:{item.line}{reset}"
                            f"  {item.kind} {bold}{item.name}{reset}"
                            f"  [{marker}]"
                        )

        # Language total
        pct = _color_pct(lang_result.percentage, use_color)
        count = f"{lang_result.documented}/{lang_result.total}"
        print(f"  {'':60s} {'-' * 8}")
        print(f"  {lang_result.language + ' total:':<60s} {count:>8s}  ({pct})")

        overall_total += lang_result.total
        overall_documented += lang_result.documented

    # Summary
    print(f"\n{bold}=== Summary ==={reset}")
    for lang_result in results:
        if lang_result.total == 0:
            continue
        pct = _color_pct(lang_result.percentage, use_color)
        count = f"{lang_result.documented}/{lang_result.total}"
        print(f"  {lang_result.language + ':':<16s} {count:>8s}  ({pct})")

    overall_pct = (overall_documented / overall_total * 100) if overall_total > 0 else 100.0
    pct_str = _color_pct(overall_pct, use_color)
    count = f"{overall_documented}/{overall_total}"
    print(f"  {'Overall:':<16s} {count:>8s}  ({pct_str})")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def find_project_root() -> str:
    """Find the project root by looking for CLAUDE.md or .git."""
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / 'CLAUDE.md').exists() or (parent / '.git').exists():
            return str(parent)
    return str(cwd)


def results_to_json(
    results: List[LanguageResult],
    staleness_entries: Optional[List[StalenessEntry]] = None,
) -> dict:
    """Build a JSON-serializable dict of coverage and staleness data."""
    overall_total = sum(r.total for r in results)
    overall_documented = sum(r.documented for r in results)
    overall_pct = (overall_documented / overall_total * 100) if overall_total > 0 else 100.0

    languages = []
    for r in results:
        lang = {
            'language': r.language,
            'total': r.total,
            'documented': r.documented,
            'percentage': round(r.percentage, 1),
            'files': [],
        }
        if r.note:
            lang['note'] = r.note
        for f in r.files:
            fdata = {
                'path': f.path,
                'total': f.total,
                'documented': f.documented,
                'percentage': round(f.percentage, 1),
                'undocumented': [
                    {'name': it.name, 'kind': it.kind, 'line': it.line}
                    for it in f.items if not it.documented
                ],
            }
            lang['files'].append(fdata)
        languages.append(lang)

    out: dict = {
        'summary': {
            'total': overall_total,
            'documented': overall_documented,
            'percentage': round(overall_pct, 1),
        },
        'languages': languages,
    }

    if staleness_entries is not None:
        stale_list = []
        for entry in staleness_entries:
            if entry.status == 'stale':
                stale_list.append({
                    'file': entry.item.file_path,
                    'line': entry.item.line,
                    'name': entry.item.name,
                    'kind': entry.item.kind,
                    'drift_days': entry.drift_days,
                    'verified_commit': entry.item.verified_commit,
                    'file_last_commit': entry.file_last_commit,
                })

        current_count = sum(1 for e in staleness_entries if e.status == 'current')
        stale_count = sum(1 for e in staleness_entries if e.status == 'stale')
        unverified_count = sum(1 for e in staleness_entries if e.status == 'unverified')
        unknown_count = sum(1 for e in staleness_entries if e.status == 'unknown')

        out['staleness'] = {
            'current': current_count,
            'stale': stale_count,
            'unverified': unverified_count,
            'unknown': unknown_count,
            'stale_items': sorted(stale_list, key=lambda x: -(x.get('drift_days') or 0)),
        }

    return out


def main():
    parser = argparse.ArgumentParser(
        description='Cross-language docstring coverage reporter',
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='Show each undocumented item with file:line',
    )
    parser.add_argument(
        '--fail-under', type=float, default=0,
        help='Exit non-zero if overall coverage < N%%',
    )
    parser.add_argument('--python-only', action='store_true')
    parser.add_argument('--ts-only', action='store_true')
    parser.add_argument('--rust-only', action='store_true')
    parser.add_argument(
        '--staleness', action='store_true',
        help='Analyze docstring freshness using @verified tags and git history',
    )
    parser.add_argument(
        '--no-color', action='store_true',
        help='Disable ANSI color output',
    )
    parser.add_argument(
        '--json', action='store_true', dest='json_output',
        help='Output as JSON (for CI or piping to other tools)',
    )
    args = parser.parse_args()

    project_root = find_project_root()
    use_color = not args.no_color and sys.stdout.isatty()

    # If no --*-only flag is set, run all
    run_all = not (args.python_only or args.ts_only or args.rust_only)

    results: List[LanguageResult] = []

    # JSON mode implies staleness scan (it includes both)
    force_staleness = args.staleness or args.json_output

    if run_all or args.python_only:
        results.append(scan_python(
            ['api/app', 'fuse/kg_fuse'], project_root, force_ast=force_staleness,
        ))

    if run_all or args.ts_only:
        results.append(scan_typescript(['web/src', 'cli/src'], project_root))

    if run_all or args.rust_only:
        results.append(scan_rust(
            ['graph-accel/core/src', 'graph-accel/ext/src'],
            project_root,
        ))

    # Staleness analysis
    staleness_entries = None
    if force_staleness:
        staleness_entries = compute_staleness(results, project_root)

    # Output
    if args.json_output:
        print(json.dumps(results_to_json(results, staleness_entries), indent=2))
    else:
        print_results(results, verbose=args.verbose, use_color=use_color)
        if args.staleness and staleness_entries is not None:
            print_staleness_report(staleness_entries, use_color=use_color)

    # Exit code
    overall_total = sum(r.total for r in results)
    overall_documented = sum(r.documented for r in results)
    overall_pct = (overall_documented / overall_total * 100) if overall_total > 0 else 100.0

    if args.fail_under > 0 and overall_pct < args.fail_under:
        print(
            f"\nFAILED: coverage {overall_pct:.1f}% < "
            f"threshold {args.fail_under:.1f}%",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == '__main__':
    main()
