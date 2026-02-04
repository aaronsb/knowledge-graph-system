#!/usr/bin/env python3
"""
Lint for unsafe datetime patterns (ADR-056).

This linter detects potentially unsafe datetime usage that could lead to
naive/aware comparison errors.

Detects:
- datetime.utcnow() - deprecated, use datetime_utils.utcnow()
- datetime.now() without timezone - naive, use datetime_utils.utcnow()
- datetime.fromtimestamp() without tz - naive, use datetime_utils.utc_from_timestamp()

Usage:
    python scripts/lint_datetimes.py              # Lint all files
    python scripts/lint_datetimes.py --verbose    # Show all violations
    python scripts/lint_datetimes.py --strict     # Exit 1 on any violations

Exit codes:
    0 - No violations found
    1 - Violations found (only in --strict mode)

Related:
    ADR-056: Timezone-Aware Datetime Utilities
"""

import re
import sys
import argparse
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class Violation:
    """Represents a datetime linting violation."""
    file_path: Path
    line_num: int
    line_content: str
    pattern: str
    message: str


# Patterns to detect (pattern, user-friendly message)
UNSAFE_PATTERNS = [
    (
        r'\bdatetime\.utcnow\(\)',
        'Use datetime_utils.utcnow() instead of datetime.utcnow() (returns naive datetime)'
    ),
    (
        r'\bdatetime\.now\(\)(?!\s*\()',
        'Use datetime_utils.utcnow() instead of datetime.now() (returns naive local time)'
    ),
    (
        r'\bdatetime\.fromtimestamp\([^,)]+\)(?!\s*,\s*tz)',
        'Use datetime_utils.utc_from_timestamp() instead of datetime.fromtimestamp() without tz'
    ),
]


def should_skip_line(line: str) -> bool:
    """
    Check if a line should be skipped during linting.

    Args:
        line: Source code line

    Returns:
        True if line should be skipped
    """
    stripped = line.strip()

    # Skip comments
    if stripped.startswith('#'):
        return True

    # Skip import statements
    if 'import' in stripped and ('from' in stripped or 'import' in stripped):
        return True

    # Skip docstrings and multi-line strings
    if stripped.startswith('"""') or stripped.startswith("'''"):
        return True

    return False


def lint_file(file_path: Path) -> List[Violation]:
    """
    Lint a Python file for unsafe datetime patterns.

    Args:
        file_path: Path to Python file

    Returns:
        List of violations found
    """
    violations = []

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, start=1):
                # Skip comments and imports
                if should_skip_line(line):
                    continue

                # Check each unsafe pattern
                for pattern, message in UNSAFE_PATTERNS:
                    if re.search(pattern, line):
                        violations.append(Violation(
                            file_path=file_path,
                            line_num=line_num,
                            line_content=line.strip(),
                            pattern=pattern,
                            message=message
                        ))

    except Exception as e:
        print(f"⚠️  Error reading {file_path}: {e}", file=sys.stderr)

    return violations


def lint_directory(src_path: Path, exclude_files: List[str] = None) -> List[Violation]:
    """
    Lint all Python files in a directory recursively.

    Args:
        src_path: Root directory to scan
        exclude_files: List of filenames to exclude

    Returns:
        List of all violations found
    """
    exclude_files = exclude_files or []
    all_violations = []

    for py_file in src_path.rglob('*.py'):
        # Skip excluded files
        if py_file.name in exclude_files:
            continue

        violations = lint_file(py_file)
        all_violations.extend(violations)

    return all_violations


def format_violation_report(violations: List[Violation], verbose: bool = False) -> str:
    """
    Format violations into a human-readable report.

    Args:
        violations: List of violations
        verbose: If True, include line content

    Returns:
        Formatted report string
    """
    if not violations:
        return "✅ No unsafe datetime patterns found"

    # Group violations by file
    violations_by_file = {}
    for v in violations:
        if v.file_path not in violations_by_file:
            violations_by_file[v.file_path] = []
        violations_by_file[v.file_path].append(v)

    # Build report
    lines = []
    lines.append(f"\n❌ Found {len(violations)} unsafe datetime pattern(s) in {len(violations_by_file)} file(s)\n")

    for file_path in sorted(violations_by_file.keys()):
        file_violations = violations_by_file[file_path]
        lines.append(f"\n{file_path} ({len(file_violations)} violation(s)):")

        for v in file_violations:
            lines.append(f"  Line {v.line_num}: {v.message}")
            if verbose:
                lines.append(f"    {v.line_content}")

    lines.append("\n📖 See ADR-056 for migration guide:")
    lines.append("   docs/architecture/ADR-056-timezone-aware-datetime-utilities.md")
    lines.append("")

    return "\n".join(lines)


def main():
    """Main entry point for linter."""
    parser = argparse.ArgumentParser(
        description="Lint Python code for unsafe datetime patterns (ADR-056)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Show line content for each violation'
    )
    parser.add_argument(
        '--strict',
        action='store_true',
        help='Exit with code 1 if any violations found (useful for CI)'
    )
    parser.add_argument(
        '--path',
        type=Path,
        default=Path('api/app'),
        help='Path to lint (default: api/app)'
    )

    args = parser.parse_args()

    # Ensure path exists
    if not args.path.exists():
        print(f"❌ Path does not exist: {args.path}", file=sys.stderr)
        sys.exit(1)

    # Run linter
    print(f"🔍 Linting datetime usage in {args.path}...")

    violations = lint_directory(
        args.path,
        exclude_files=['datetime_utils.py']  # Don't lint the utility module itself
    )

    # Print report
    report = format_violation_report(violations, verbose=args.verbose)
    print(report)

    # Exit with appropriate code
    if args.strict and violations:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
