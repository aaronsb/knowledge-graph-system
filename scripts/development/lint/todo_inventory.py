#!/usr/bin/env python3
"""
TODO Inventory & Entropic AI Laziness Detector (SLOPSCAN 9000)

Scans the project for two categories of technical debt:

  1. Traditional markers: TODO, FIXME, HACK, XXX
  2. Agent antipatterns (--slop): truncated output, placeholder stubs,
     rubber-stamp approvals, dummy credentials, and AI attribution noise
     left behind by less refined coding agents.

Reports location, marker type, age (via git blame), and text for every
finding. The SLOPSCAN 9000 mode acts as a thermodynamic entropy detector
for AI-generated code — because the second law of thermodynamics applies
to codebases too, and agents that leave "... rest of the code" comments
are simply accelerating heat death.

Usage:
    python3 scripts/development/lint/todo_inventory.py              # summary
    python3 scripts/development/lint/todo_inventory.py -v           # list every marker
    python3 scripts/development/lint/todo_inventory.py --age        # include git blame age
    python3 scripts/development/lint/todo_inventory.py --json       # machine-readable output
    python3 scripts/development/lint/todo_inventory.py --slop       # include agent antipatterns
    python3 scripts/development/lint/todo_inventory.py --slop-only  # ONLY agent antipatterns
"""

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Traditional markers — the word followed by optional colon and text
# ---------------------------------------------------------------------------
MARKER_RE = re.compile(
    r'\b(TODO|FIXME|HACK|XXX)\b\s*:?\s*(.*)',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Agent antipatterns ("slop") — patterns that suggest an AI agent truncated,
# stubbed, or hand-waved code rather than writing it.
#
# Each entry: (compiled_regex, marker_name, description)
# The regex matches the ENTIRE line (after stripping comment prefixes).
# ---------------------------------------------------------------------------
SLOP_PATTERNS: List[tuple] = [
    # --- Truncation: agent stopped generating and left a breadcrumb ---
    # Must be full phrases to avoid matching JS spread (...existing) or
    # legitimate code (...remaining). These patterns are comment-shaped.
    (re.compile(
        r'\.{2,}\s*'
        r'(rest of (the )?(code|implementation|file|function|method|class)'
        r'|remaining (code|implementation|handlers?|methods?|functions?|logic)'
        r'|same (as|pattern) (above|before|below)'
        r'|similar (to|pattern) (above|before|below)'
        r'|continue(s| with)?( the| as)? (same|above|before|previous)'
        r'|and so on|etc\.?\s*$'
        r'|more (of the same|handlers?|methods?|routes?)'
        r'|code here'
        r'|as before'
        r'|unchanged)',
        re.IGNORECASE,
    ), 'TRUNCATED', 'Ellipsis with continuation hint — likely truncated output'),

    (re.compile(
        r'(stays?|remains?|keep|left)\s+(the\s+)?same\s*$',
        re.IGNORECASE,
    ), 'TRUNCATED', 'Vague "stays the same" — may hide omitted code'),

    # --- Stubs: agent wrote a function signature but no body ---
    (re.compile(
        r'(add|put|write|insert|place)\s+(your|the|actual|real)\s+'
        r'(code|implementation|logic)',
        re.IGNORECASE,
    ), 'STUB', 'Placeholder inviting someone else to write the code'),

    (re.compile(
        r'implement(ation)?\s+(this|here|goes here|me)',
        re.IGNORECASE,
    ), 'STUB', 'Bare "implement this" stub'),

    # --- Attribution / provenance noise ---
    (re.compile(
        r'(generated|created|written|authored|produced)\s+by\s+'
        r'(chatgpt|gpt-?\d|copilot|claude|gemini|bard|ai\b|llm\b'
        r'|openai|anthropic|cursor|codeium|tabnine)',
        re.IGNORECASE,
    ), 'ATTRIB', 'AI tool attribution comment'),

    # --- Dummy / example values left in production code ---
    # Tight matches only — actual dummy credentials or nonsense strings.
    # Avoids: "placeholder" (React attrs), "abc123" (hash examples),
    # "example.com" (RFC 2606 reserved domain, used legitimately in docs).
    (re.compile(
        r'(lorem ipsum|changeme|password123|hunter2|s3cr3t'
        r'|replace.?me|CHANGETHIS)',
        re.IGNORECASE,
    ), 'DUMMY', 'Dummy credential or nonsense value'),

    # --- Rubber-stamp reviews / non-actionable approval noise ---
    (re.compile(
        r'^\s*LGTM\s*$',
        re.IGNORECASE,
    ), 'LGTM', 'Rubber-stamp approval comment left in code'),
]

# File extensions where SLOP scanning applies (skip .md — prose is fine)
SLOP_CODE_EXTENSIONS = {
    '.py', '.ts', '.tsx', '.js', '.jsx', '.rs',
    '.sh', '.bash', '.zsh',
    '.yml', '.yaml', '.toml', '.ini', '.cfg',
    '.html', '.css', '.scss',
    '.sql', '.cypher',
}

# Directories always skipped (vendor, build artifacts, caches)
SKIP_DIRS = {
    '.git', 'node_modules', '__pycache__', '.venv', 'venv',
    'dist', 'build', '.cache', '.tox', 'htmlcov', '.mypy_cache',
    '.pytest_cache', 'site', '.next', '.nuxt', 'target',
    'site-packages', '.egg-info',
    'examples',  # archived conversation logs, not project source
}

# File extensions to scan (empty = scan everything not skipped)
TEXT_EXTENSIONS = {
    '.py', '.ts', '.tsx', '.js', '.jsx', '.rs',
    '.md', '.txt', '.rst',
    '.sh', '.bash', '.zsh',
    '.yml', '.yaml', '.toml', '.ini', '.cfg', '.conf',
    '.html', '.css', '.scss',
    '.sql', '.cypher',
    '.dockerfile', '.env',
    '.json',  # occasionally has comments in jsonc
}

# Files with no extension that are still text
TEXT_FILENAMES = {
    'Makefile', 'Dockerfile', 'Containerfile',
    'Justfile', 'Rakefile', 'Gemfile',
    '.gitignore', '.dockerignore', '.editorconfig',
}


@dataclass
class TodoItem:
    """A single marker found in source code."""
    file: str
    line: int
    marker: str       # TODO, FIXME, HACK, XXX, TRUNCATED, STUB, ATTRIB, DUMMY
    text: str         # the text after the marker / matched line
    category: str = 'todo'   # 'todo' or 'slop'
    age_days: Optional[int] = None
    author: Optional[str] = None
    date: Optional[str] = None

# Marker types in each category, for display ordering
TODO_MARKERS = ('TODO', 'FIXME', 'HACK', 'XXX')
SLOP_MARKERS = ('TRUNCATED', 'STUB', 'ATTRIB', 'DUMMY', 'LGTM')


def _should_scan(path: Path) -> bool:
    """Decide whether a file should be scanned."""
    # Skip directories in SKIP_DIRS at any depth
    for part in path.parts:
        if part in SKIP_DIRS:
            return False

    if path.is_dir():
        return False

    # Check extension or known filename
    if path.suffix.lower() in TEXT_EXTENSIONS:
        return True
    if path.name in TEXT_FILENAMES:
        return True

    return False


def _strip_comment_prefix(line: str) -> str:
    """Strip common comment prefixes to get the semantic content."""
    s = line.strip()
    # Multi-line comment bodies: * leading, or /** / */
    for prefix in ('//', '#', '--', '/*', '/**', '*/', '*', '<!--', '"""', "'''"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    return s.strip()


def scan_file(file_path: Path, include_slop: bool = False) -> List[TodoItem]:
    """Scan a single file for TODO markers and optionally agent antipatterns."""
    # Don't scan ourselves — we contain marker strings in regex/docs
    if file_path.resolve() == Path(__file__).resolve():
        return []

    items = []
    try:
        text = file_path.read_text(encoding='utf-8', errors='replace')
    except (OSError, UnicodeDecodeError):
        return items

    is_code_file = file_path.suffix.lower() in SLOP_CODE_EXTENSIONS

    for line_num, line in enumerate(text.splitlines(), start=1):
        # Traditional TODO/FIXME/HACK/XXX markers
        match = MARKER_RE.search(line)
        if match:
            marker = match.group(1).upper()
            todo_text = match.group(2).strip()
            # Trim trailing comment closers
            for suffix in ('*/', '-->', '#}', '%}'):
                if todo_text.endswith(suffix):
                    todo_text = todo_text[:-len(suffix)].rstrip()
            items.append(TodoItem(
                file=str(file_path),
                line=line_num,
                marker=marker,
                text=todo_text,
                category='todo',
            ))

        # Agent antipattern detection (code files only)
        if include_slop and is_code_file:
            stripped = _strip_comment_prefix(line)
            if not stripped:
                continue
            for pattern, marker_name, _desc in SLOP_PATTERNS:
                if pattern.search(stripped):
                    # Avoid double-counting lines already caught as TODO
                    if match:
                        break
                    items.append(TodoItem(
                        file=str(file_path),
                        line=line_num,
                        marker=marker_name,
                        text=stripped[:120],
                        category='slop',
                    ))
                    break  # one hit per line

    return items


def scan_directory(root: Path, include_slop: bool = False) -> List[TodoItem]:
    """Walk a directory tree and collect all TODO markers."""
    items = []
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped directories in-place
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]

        for fname in filenames:
            fpath = Path(dirpath) / fname
            if _should_scan(fpath):
                items.extend(scan_file(fpath, include_slop=include_slop))
    return items


def enrich_with_git_blame(items: List[TodoItem], root: Path) -> None:
    """Add age/author via git blame (batch per file for efficiency)."""
    by_file: Dict[str, List[TodoItem]] = {}
    for item in items:
        by_file.setdefault(item.file, []).append(item)

    now = datetime.now(timezone.utc)

    for file_path, file_items in by_file.items():
        try:
            # Sort by line number — blame -L needs min,max range
            file_items.sort(key=lambda i: i.line)
            # Use porcelain format for reliable parsing
            result = subprocess.run(
                ['git', 'blame', '--porcelain', '-L',
                 f'{file_items[0].line},{file_items[-1].line}',
                 '--', file_path],
                capture_output=True, text=True, timeout=10,
                cwd=str(root),
            )
            if result.returncode != 0:
                continue

            # Porcelain only emits author/time on the FIRST occurrence of each
            # commit hash. Cache per commit, then look up per line.
            commit_info: Dict[str, Tuple[str, int]] = {}  # hash -> (author, epoch)
            line_commit: Dict[int, str] = {}  # final-line -> commit hash
            current_hash = None

            for pline in result.stdout.splitlines():
                if pline.startswith('\t'):
                    continue  # content line, skip
                parts = pline.split()
                if len(parts) >= 3 and len(parts[0]) == 40 and parts[2].isdigit():
                    # Commit header: <40-char hash> <orig> <final> [<count>]
                    current_hash = parts[0]
                    line_commit[int(parts[2])] = current_hash
                    commit_info.setdefault(current_hash, ('?', 0))
                elif pline.startswith('author ') and current_hash:
                    author = pline[7:]
                    _, epoch = commit_info[current_hash]
                    commit_info[current_hash] = (author, epoch)
                elif pline.startswith('author-time ') and current_hash:
                    try:
                        epoch = int(pline[12:])
                        author, _ = commit_info[current_hash]
                        commit_info[current_hash] = (author, epoch)
                    except ValueError:
                        pass

            # Apply to items
            for item in file_items:
                chash = line_commit.get(item.line)
                if chash and chash in commit_info:
                    author, epoch = commit_info[chash]
                    item.author = author
                    if epoch > 0:
                        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
                        item.date = dt.strftime('%Y-%m-%d')
                        item.age_days = (now - dt).days

        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue


def print_report(items: List[TodoItem], verbose: bool = False, show_age: bool = False) -> None:
    """Print a human-readable report."""
    if not items:
        print("No markers found.")
        return

    todo_items = [i for i in items if i.category == 'todo']
    slop_items = [i for i in items if i.category == 'slop']

    # Group by marker type
    by_marker: Dict[str, List[TodoItem]] = {}
    for item in items:
        by_marker.setdefault(item.marker, []).append(item)

    # --- TODO section ---
    if todo_items:
        print(f"\n{'='*60}")
        print(f"  TODO Inventory: {len(todo_items)} markers")
        print(f"{'='*60}\n")

        for marker in TODO_MARKERS:
            count = len(by_marker.get(marker, []))
            if count > 0:
                print(f"  {marker:8s}  {count}")
        print()

    # --- Slop section ---
    if slop_items:
        print(f"{'='*60}")
        print(f"  (O) SLOPSCAN 9000: {len(slop_items)} antipatterns detected")
        print(f"{'='*60}\n")

        for marker in SLOP_MARKERS:
            count = len(by_marker.get(marker, []))
            if count > 0:
                # Look up description from SLOP_PATTERNS
                desc = marker
                for _, name, d in SLOP_PATTERNS:
                    if name == marker:
                        desc = d
                        break
                print(f"  {marker:12s}  {count:3d}  ({desc})")
        print()

    # --- Verbose listing ---
    if verbose:
        by_file: Dict[str, List[TodoItem]] = {}
        for item in items:
            by_file.setdefault(item.file, []).append(item)

        for file_path in sorted(by_file):
            file_items = by_file[file_path]
            print(f"  {file_path} ({len(file_items)})")
            for item in sorted(file_items, key=lambda i: i.line):
                age_str = ''
                if show_age and item.age_days is not None:
                    age_str = f"  ({item.age_days}d ago, {item.author})"
                text_preview = item.text[:80] + ('...' if len(item.text) > 80 else '')
                badge = f"[{item.marker}]" if item.category == 'slop' else item.marker
                print(f"    :{item.line:<5d} {badge:14s} {text_preview}{age_str}")
            print()

    # Age summary (if available)
    aged = [it for it in items if it.age_days is not None]
    if aged:
        oldest = max(aged, key=lambda i: i.age_days)
        newest = min(aged, key=lambda i: i.age_days)
        avg_age = sum(i.age_days for i in aged) // len(aged)

        print(f"  Age: oldest {oldest.age_days}d ({oldest.file}:{oldest.line})")
        print(f"       newest {newest.age_days}d ({newest.file}:{newest.line})")
        print(f"       average {avg_age}d")
        print()

    # Top files by count
    by_file_count = {}
    for item in items:
        by_file_count[item.file] = by_file_count.get(item.file, 0) + 1
    top_files = sorted(by_file_count.items(), key=lambda x: -x[1])[:10]

    if len(top_files) > 1:
        print("  Top files:")
        for fpath, count in top_files:
            print(f"    {count:4d}  {fpath}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description=(
            'Scan project for TODO/FIXME/HACK/XXX markers and (optionally) '
            'AI agent antipatterns — the SLOPSCAN 9000.'
        ),
    )
    parser.add_argument(
        'paths', nargs='*', default=['.'],
        help='Paths to scan (default: current directory)',
    )
    parser.add_argument(
        '-v', '--verbose', action='store_true',
        help='List every marker with file:line',
    )
    parser.add_argument(
        '--age', action='store_true',
        help='Include git blame age for each marker (slower)',
    )
    parser.add_argument(
        '--json', action='store_true', dest='json_output',
        help='Output as JSON (for CI integration)',
    )
    parser.add_argument(
        '--marker', action='append', default=None,
        help='Filter to specific marker types (e.g. --marker TODO --marker TRUNCATED)',
    )
    parser.add_argument(
        '--slop', action='store_true',
        help='Include SLOPSCAN 9000: detect agent antipatterns (truncation, stubs, etc.)',
    )
    parser.add_argument(
        '--slop-only', action='store_true',
        help='Run ONLY the agent antipattern scan, skip traditional TODO markers',
    )
    parser.add_argument(
        '--fail-over', type=int, default=None, metavar='N',
        help='Exit non-zero if total marker count exceeds N',
    )

    args = parser.parse_args()

    include_slop = args.slop or args.slop_only
    all_items: List[TodoItem] = []
    root = Path('.').resolve()

    for path_str in args.paths:
        path = Path(path_str)
        if not path.exists():
            print(f"Error: Path does not exist: {path}", file=sys.stderr)
            sys.exit(1)
        if path.is_file():
            all_items.extend(scan_file(path, include_slop=include_slop))
        else:
            all_items.extend(scan_directory(path, include_slop=include_slop))

    # Filter by category
    if args.slop_only:
        all_items = [it for it in all_items if it.category == 'slop']

    # Filter by marker type
    if args.marker:
        allowed = {m.upper() for m in args.marker}
        all_items = [it for it in all_items if it.marker in allowed]

    # Enrich with git blame
    if args.age:
        enrich_with_git_blame(all_items, root)

    # Output
    if args.json_output:
        print(json.dumps([asdict(it) for it in all_items], indent=2))
    else:
        print_report(all_items, verbose=args.verbose, show_age=args.age)

    # Threshold check
    if args.fail_over is not None and len(all_items) > args.fail_over:
        print(f"FAIL: {len(all_items)} markers exceed threshold of {args.fail_over}",
              file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
