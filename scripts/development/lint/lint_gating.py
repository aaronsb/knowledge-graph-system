#!/usr/bin/env python3
"""
Gating Adoption Linter - Enforce session-aware capability gating in the web UI

Part of ADR-705 (Session Visibility and Declarative Capability Gating).

The gating primitives (sessionStatus, useCapability, <Gated>, <RequireCapability>)
only pay off if components actually use them; partial adoption re-introduces the
inconsistency the ADR removes. This linter makes adoption checkable:

  ERROR  - raw `isAuthenticated` reads from the auth store in components. This is
           how the original hand-rolled checks crept in; components should read
           `sessionStatus` / use `useCapability` instead. (Fails --check.)

  REPORT - adoption metrics: how many call sites use <Gated> / useCapability, so
           drift is visible over time. (Informational; never fails.)

Detecting every un-gated mutating control reliably from source is noisy and
error-prone, so this linter enforces the precise, unambiguous signal (raw
isAuthenticated reads) and *reports* the fuzzier adoption surface rather than
guessing at it.

Usage:
    python3 scripts/development/lint/lint_gating.py            # report + check
    python3 scripts/development/lint/lint_gating.py --check    # exit 1 on errors
    python3 scripts/development/lint/lint_gating.py -v         # list scanned files
"""

import re
import sys
from pathlib import Path
from typing import List
from dataclasses import dataclass

# Files allowed to reference `isAuthenticated` directly.
# The store defines and maintains the flag (kept for backward compat); the lint
# itself names it in patterns/messages.
ALLOWED_FILES = {
    "store/authStore.ts",
    "scripts/development/lint/lint_gating.py",
}

# A line that destructures isAuthenticated from the store, e.g.
#   const { user, isAuthenticated } = useAuthStore();
DESTRUCTURE_PATTERN = re.compile(r"useAuthStore\s*\([^)]*\)")
ISAUTH_NAME = re.compile(r"\bisAuthenticated\b")

# A line that accesses .isAuthenticated (selectors, getState, etc.), e.g.
#   useAuthStore((s) => s.isAuthenticated)   state.isAuthenticated
PROPERTY_ACCESS_PATTERN = re.compile(r"\.isAuthenticated\b")

GATED_USAGE = re.compile(r"<Gated[\s/>]")
CAPABILITY_USAGE = re.compile(r"\buseCapability\s*\(")


@dataclass
class Finding:
    """A raw isAuthenticated read that should move onto the sanctioned path."""
    file_path: str
    line_number: int
    line: str


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def is_allowed(rel_path: str) -> bool:
    return any(rel_path.endswith(allowed) for allowed in ALLOWED_FILES)


class GatingLinter:
    """Lints web UI source for gating adoption (ADR-705)."""

    def __init__(self, root: Path, verbose: bool = False):
        self.root = root
        self.verbose = verbose
        self.gated_count = 0
        self.capability_count = 0

    def lint_file(self, file_path: Path) -> List[Finding]:
        rel = _rel(file_path, self.root)
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except Exception as e:  # pragma: no cover
            print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
            return []

        # Don't count adoption inside the primitives' own definitions or in
        # comment lines (doc examples) — the metric should reflect consumers.
        is_definition = rel.endswith("components/auth/Gated.tsx") or rel.endswith(
            "hooks/useCapability.ts"
        )

        findings: List[Finding] = []
        for i, line in enumerate(lines, start=1):
            stripped = line.lstrip()
            is_comment = stripped.startswith(("*", "//", "/*"))

            # Adoption metrics (real consumer usages only)
            if not is_definition and not is_comment:
                self.gated_count += len(GATED_USAGE.findall(line))
                self.capability_count += len(CAPABILITY_USAGE.findall(line))

            if is_allowed(rel):
                continue

            destructured = (
                DESTRUCTURE_PATTERN.search(line) and ISAUTH_NAME.search(line)
            )
            accessed = PROPERTY_ACCESS_PATTERN.search(line)
            if destructured or accessed:
                findings.append(Finding(rel, i, line.strip()))

        return findings

    def lint_tree(self, directory: Path) -> List[Finding]:
        findings: List[Finding] = []
        for file_path in sorted(directory.rglob("*.ts*")):
            if file_path.suffix not in (".ts", ".tsx"):
                continue
            if "node_modules" in file_path.parts:
                continue
            if self.verbose:
                print(f"Scanning {_rel(file_path, self.root)}...", file=sys.stderr)
            findings.extend(self.lint_file(file_path))
        return findings

    def print_report(self, findings: List[Finding]) -> None:
        print("Gating adoption (ADR-705)")
        print("=" * 60)
        print(f"  <Gated> usages:       {self.gated_count}")
        print(f"  useCapability() uses: {self.capability_count}")
        print()

        if not findings:
            print("✓ No raw isAuthenticated reads in components.")
            return

        print(f"❌ Found {len(findings)} raw isAuthenticated read(s) — "
              f"use sessionStatus / useCapability instead:\n")
        for f in findings:
            print(f"📄 {f.file_path}:{f.line_number}")
            print(f"     {f.line}")
            print()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Lint web UI for session-aware capability gating adoption (ADR-705)"
    )
    parser.add_argument(
        "paths", nargs="*", default=["web/src"],
        help="Paths to scan (default: web/src)",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="List scanned files")
    parser.add_argument(
        "--check", action="store_true",
        help="Exit 1 if any raw isAuthenticated reads are found (CI mode)",
    )
    args = parser.parse_args()

    root = Path.cwd()
    linter = GatingLinter(root=root, verbose=args.verbose)
    all_findings: List[Finding] = []

    for path_str in args.paths:
        path = Path(path_str)
        if not path.exists():
            print(f"Error: Path does not exist: {path}", file=sys.stderr)
            sys.exit(2)
        if path.is_file():
            all_findings.extend(linter.lint_file(path))
        else:
            all_findings.extend(linter.lint_tree(path))

    linter.print_report(all_findings)

    if args.check and all_findings:
        sys.exit(1)


if __name__ == "__main__":
    main()
