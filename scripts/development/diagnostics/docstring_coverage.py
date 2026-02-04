#!/usr/bin/env python3
"""
Cross-language docstring coverage reporter.

Scans Python, TypeScript, and Rust source files to report documentation
coverage. Delegates to `interrogate` for Python (AST-based accuracy),
uses built-in regex scanners for TypeScript and Rust.

Usage:
    python3 scripts/development/diagnostics/docstring_coverage.py
    python3 scripts/development/diagnostics/docstring_coverage.py -v
    python3 scripts/development/diagnostics/docstring_coverage.py --fail-under 80
    python3 scripts/development/diagnostics/docstring_coverage.py --python-only
"""

import argparse
import ast
import os
import re
import shutil
import subprocess
import sys
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
# Python scanner (AST-based fallback when interrogate unavailable)
# ---------------------------------------------------------------------------

def _python_has_docstring(node: ast.AST) -> bool:
    """Check if an AST node (function/class) has a docstring."""
    if not hasattr(node, 'body') or not node.body:
        return False
    first = node.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
        return isinstance(first.value.value, str)
    return False


def scan_python_ast(file_path: str) -> FileResult:
    """Scan a Python file using the ast module for docstring coverage."""
    result = FileResult(path=file_path)
    try:
        source = Path(file_path).read_text(encoding='utf-8')
        tree = ast.parse(source, filename=file_path)
    except (SyntaxError, UnicodeDecodeError):
        return result

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip private helpers (single underscore, not dunder)
            if node.name.startswith('_') and not node.name.startswith('__'):
                continue
            kind = 'method' if _is_method(node, tree) else 'function'
            documented = _python_has_docstring(node)
            item = DocItem(
                file_path=file_path,
                line=node.lineno,
                name=node.name,
                kind=kind,
                documented=documented,
            )
            result.items.append(item)
            result.total += 1
            if documented:
                result.documented += 1

        elif isinstance(node, ast.ClassDef):
            documented = _python_has_docstring(node)
            item = DocItem(
                file_path=file_path,
                line=node.lineno,
                name=node.name,
                kind='class',
                documented=documented,
            )
            result.items.append(item)
            result.total += 1
            if documented:
                result.documented += 1

    return result


def _is_method(node: ast.AST, tree: ast.Module) -> bool:
    """Check if a function is a method (inside a class body)."""
    for parent in ast.walk(tree):
        if isinstance(parent, ast.ClassDef):
            if node in parent.body:
                return True
    return False


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


def scan_python(directories: List[str], project_root: str) -> LanguageResult:
    """Scan Python files for docstring coverage.

    Uses interrogate if available, falls back to AST-based scanning.
    """
    # Try interrogate first
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
        documented = _has_jsdoc_above(lines, i)

        item = DocItem(
            file_path=rel_path,
            line=i + 1,
            name=name,
            kind=kind,
            documented=documented,
        )
        result.items.append(item)
        result.total += 1
        if documented:
            result.documented += 1

    return result


def _has_jsdoc_above(lines: List[str], target_idx: int) -> bool:
    """Check if there's a JSDoc comment (/** ... */) above the target line.

    Scans backwards, skipping blank lines and decorators, looking for
    a line ending with */ within 30 lines.
    """
    scan_limit = max(0, target_idx - 30)

    for j in range(target_idx - 1, scan_limit - 1, -1):
        prev = lines[j].strip()

        # Skip blank lines
        if not prev:
            continue

        # Skip TypeScript decorators (@Something)
        if prev.startswith('@'):
            continue

        # Found end of JSDoc block
        if prev.endswith('*/'):
            return True

        # Found a single-line JSDoc: /** ... */
        if _JSDOC_START_RE.match(prev) and prev.endswith('*/'):
            return True

        # Hit a non-comment, non-blank line — no JSDoc
        return False

    return False


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

        # Track brace depth for #[cfg(test)] exclusion
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
        documented = _has_rust_doc_above(lines, i)

        item = DocItem(
            file_path=rel_path,
            line=i + 1,
            name=name,
            kind=kind,
            documented=documented,
        )
        result.items.append(item)
        result.total += 1
        if documented:
            result.documented += 1

    return result


def _has_rust_doc_above(lines: List[str], target_idx: int) -> bool:
    """Check if there's a /// doc comment above the target line.

    Skips #[...] attribute lines (derive macros, etc.) when looking
    for the doc comment.
    """
    scan_limit = max(0, target_idx - 30)

    for j in range(target_idx - 1, scan_limit - 1, -1):
        prev = lines[j].strip()

        # Skip blank lines
        if not prev:
            continue

        # Skip attribute macros (#[derive(...)], #[inline], etc.)
        if _RUST_ATTR_RE.match(prev):
            continue

        # Found doc comment
        if _RUST_DOC_RE.match(prev):
            return True

        # Hit a non-doc, non-attr line — no documentation
        return False

    return False


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
        '--no-color', action='store_true',
        help='Disable ANSI color output',
    )
    args = parser.parse_args()

    project_root = find_project_root()
    use_color = not args.no_color and sys.stdout.isatty()

    # If no --*-only flag is set, run all
    run_all = not (args.python_only or args.ts_only or args.rust_only)

    results: List[LanguageResult] = []

    if run_all or args.python_only:
        results.append(scan_python(['api/app'], project_root))

    if run_all or args.ts_only:
        results.append(scan_typescript(['web/src', 'cli/src'], project_root))

    if run_all or args.rust_only:
        results.append(scan_rust(
            ['graph-accel/core/src', 'graph-accel/ext/src'],
            project_root,
        ))

    print_results(results, verbose=args.verbose, use_color=use_color)

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
