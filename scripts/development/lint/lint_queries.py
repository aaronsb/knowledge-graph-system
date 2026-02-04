#!/usr/bin/env python3
"""
Query Safety Linter - Detect unsafe Cypher queries

Scans Python files for execute_cypher calls and identifies queries that:
1. Use MATCH without explicit node labels (e.g., MATCH (n) instead of MATCH (n:Concept))
2. Use CREATE without explicit labels
3. Other unsafe patterns that could cause namespace collisions

Part of ADR-048: Vocabulary Metadata as First-Class Graph
"""

import re
import sys
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass


@dataclass
class UnsafeQuery:
    """Represents an unsafe query finding."""
    file_path: str
    line_number: int
    query_snippet: str
    issue: str
    severity: str  # 'error' or 'warning'


class QueryLinter:
    """Lints Cypher queries for namespace safety issues."""

    # Patterns for finding queries
    EXECUTE_CYPHER_PATTERN = re.compile(
        r'(?:_execute_cypher|execute_cypher)\s*\(\s*["\'](.+?)["\']',
        re.DOTALL
    )

    # Unsafe patterns
    UNSAFE_MATCH_PATTERN = re.compile(
        r'MATCH\s+\((\w+)\)(?![:\[])',  # MATCH (n) without :Label or [relationship]
        re.IGNORECASE
    )

    UNSAFE_CREATE_PATTERN = re.compile(
        r'CREATE\s+\((\w+)\)(?![:\[])',  # CREATE (n) without :Label
        re.IGNORECASE
    )

    UNSAFE_MERGE_PATTERN = re.compile(
        r'MERGE\s+\((\w+)\)(?![:\[])',  # MERGE (n) without :Label
        re.IGNORECASE
    )

    # Whitelist patterns (queries that are intentionally label-free)
    WHITELIST_PATTERNS = [
        r'MATCH\s+\(\)\s*RETURN',  # Empty node for counts
        r'MATCH\s+\(\w+\)\s*WHERE\s+id\(\w+\)',  # Match by ID
        r'MATCH\s+\(\w+\)\s*WHERE\s+\w+\.concept_id',  # Match by property (acceptable)
    ]

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.findings: List[UnsafeQuery] = []

    def lint_file(self, file_path: Path) -> List[UnsafeQuery]:
        """Lint a single Python file for unsafe queries."""
        findings = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            if self.verbose:
                print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
            return findings

        # Find all execute_cypher calls
        for match in self.EXECUTE_CYPHER_PATTERN.finditer(content):
            query = match.group(1)

            # Get line number
            line_number = content[:match.start()].count('\n') + 1

            # Skip if query is in whitelist
            if self._is_whitelisted(query):
                continue

            # Check for unsafe patterns
            findings.extend(self._check_query(file_path, line_number, query))

        return findings

    def _is_whitelisted(self, query: str) -> bool:
        """Check if query matches whitelist patterns."""
        for pattern in self.WHITELIST_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                return True
        return False

    def _check_query(self, file_path: Path, line_number: int, query: str) -> List[UnsafeQuery]:
        """Check a single query for unsafe patterns."""
        findings = []

        # Check for unsafe MATCH
        for match in self.UNSAFE_MATCH_PATTERN.finditer(query):
            var_name = match.group(1)
            findings.append(UnsafeQuery(
                file_path=str(file_path),
                line_number=line_number,
                query_snippet=self._get_snippet(query, match.start()),
                issue=f"MATCH ({var_name}) missing explicit label (should be MATCH ({var_name}:Concept) or similar)",
                severity='error'
            ))

        # Check for unsafe CREATE
        for match in self.UNSAFE_CREATE_PATTERN.finditer(query):
            var_name = match.group(1)
            findings.append(UnsafeQuery(
                file_path=str(file_path),
                line_number=line_number,
                query_snippet=self._get_snippet(query, match.start()),
                issue=f"CREATE ({var_name}) missing explicit label (should be CREATE ({var_name}:Concept) or similar)",
                severity='error'
            ))

        # Check for unsafe MERGE
        for match in self.UNSAFE_MERGE_PATTERN.finditer(query):
            var_name = match.group(1)
            findings.append(UnsafeQuery(
                file_path=str(file_path),
                line_number=line_number,
                query_snippet=self._get_snippet(query, match.start()),
                issue=f"MERGE ({var_name}) missing explicit label (should be MERGE ({var_name}:Concept) or similar)",
                severity='error'
            ))

        return findings

    def _get_snippet(self, query: str, position: int, context: int = 50) -> str:
        """Extract a snippet of the query around the issue."""
        start = max(0, position - context)
        end = min(len(query), position + context)
        snippet = query[start:end].strip()

        # Clean up whitespace
        snippet = re.sub(r'\s+', ' ', snippet)

        if start > 0:
            snippet = '...' + snippet
        if end < len(query):
            snippet = snippet + '...'

        return snippet

    def lint_directory(self, directory: Path, pattern: str = "**/*.py") -> List[UnsafeQuery]:
        """Lint all Python files in a directory."""
        findings = []

        for file_path in directory.glob(pattern):
            if self.verbose:
                print(f"Linting {file_path}...", file=sys.stderr)
            findings.extend(self.lint_file(file_path))

        return findings

    def print_report(self, findings: List[UnsafeQuery]) -> None:
        """Print a formatted report of findings."""
        if not findings:
            print("✓ No unsafe queries found!")
            return

        print(f"\n⚠️  Found {len(findings)} unsafe query pattern(s):\n")

        # Group by file
        by_file: Dict[str, List[UnsafeQuery]] = {}
        for finding in findings:
            by_file.setdefault(finding.file_path, []).append(finding)

        # Print grouped by file
        for file_path, file_findings in sorted(by_file.items()):
            print(f"📄 {file_path}")
            for finding in file_findings:
                severity_icon = "❌" if finding.severity == 'error' else "⚠️ "
                print(f"  {severity_icon} Line {finding.line_number}: {finding.issue}")
                print(f"     Query: {finding.query_snippet}")
                print()

        # Summary
        errors = sum(1 for f in findings if f.severity == 'error')
        warnings = sum(1 for f in findings if f.severity == 'warning')

        print(f"Summary: {errors} error(s), {warnings} warning(s)")
        print("\nRecommendation: Use GraphQueryFacade for namespace-safe queries.")
        print("See ADR-048: Vocabulary Metadata as First-Class Graph")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Lint Cypher queries for namespace safety issues"
    )
    parser.add_argument(
        'paths',
        nargs='*',
        default=['api/app'],
        help='Paths to lint (default: api/app)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose output'
    )
    parser.add_argument(
        '--fail-on-warning',
        action='store_true',
        help='Exit with error code on warnings (not just errors)'
    )

    args = parser.parse_args()

    linter = QueryLinter(verbose=args.verbose)
    all_findings = []

    # Lint all specified paths
    for path_str in args.paths:
        path = Path(path_str)

        if not path.exists():
            print(f"Error: Path does not exist: {path}", file=sys.stderr)
            sys.exit(1)

        if path.is_file():
            all_findings.extend(linter.lint_file(path))
        else:
            all_findings.extend(linter.lint_directory(path))

    # Print report
    linter.print_report(all_findings)

    # Exit with appropriate code
    errors = sum(1 for f in all_findings if f.severity == 'error')
    warnings = sum(1 for f in all_findings if f.severity == 'warning')

    if errors > 0:
        sys.exit(1)
    elif warnings > 0 and args.fail_on_warning:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
