#!/usr/bin/env python3
"""
Markdown link checker for docs/ — finds dead local references.

Scans every `.md` file under `docs/` (configurable) and resolves each
markdown link and image reference. A link is considered broken when:

  - It points at a relative path on disk that doesn't exist
  - It points at a path with an anchor fragment whose file half is missing
  - It uses a repo-absolute path (starts with `/`) that doesn't resolve
    under the project root

External links (http://, https://, mailto:, etc.) are reported by count
only — verifying them requires network and a different tool. Anchor
targets (`#some-heading`) are not verified inside the file; they would
need a Markdown parser that knows the project's heading-slug rules.

Usage:
    python3 scripts/development/lint/link_check.py
    python3 scripts/development/lint/link_check.py docs/architecture
    python3 scripts/development/lint/link_check.py --root docs --quiet
    python3 scripts/development/lint/link_check.py --fail-on-broken
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from urllib.parse import unquote, urlparse


# Matches `[text](target)` and `![alt](target)`. The target stops at the
# first space, closing paren, or quote — Markdown allows titles after a
# space (e.g. `[t](u "title")`) which we want to drop. Reference-style
# links and HTML <a href> tags are not handled; if they show up we'll add
# them.
LINK_RE = re.compile(r'!?\[[^\]]*?\]\(\s*([^\s\)\'"]+)')

# Schemes we treat as external (network or non-filesystem).
EXTERNAL_SCHEMES = {
    "http", "https", "ftp", "mailto", "tel", "data", "javascript",
}


@dataclass
class BrokenLink:
    """A markdown link whose local target could not be resolved on disk."""

    source: Path        # The .md file containing the link
    line_number: int    # 1-indexed line number of the occurrence
    raw_target: str     # Exactly what was inside the parentheses
    resolved: Path      # Where we looked for it on disk
    reason: str         # Short human-readable cause


@dataclass
class ScanReport:
    """Aggregate counts and details from a single scan run."""

    files_scanned: int = 0
    links_total: int = 0
    links_local: int = 0
    links_external: int = 0
    broken: List[BrokenLink] = None

    def __post_init__(self) -> None:
        if self.broken is None:
            self.broken = []


def _iter_markdown_files(root: Path) -> Iterable[Path]:
    """Yield every .md file under ``root`` in deterministic order."""
    yield from sorted(root.rglob("*.md"))


def _extract_links(md_path: Path) -> Iterable[Tuple[int, str]]:
    """Yield ``(line_number, raw_target)`` for every markdown link/image.

    Lines inside fenced code blocks are skipped — code samples often
    contain `[brackets](and parens)` that look like links but aren't.
    """
    in_fence = False
    for lineno, line in enumerate(md_path.read_text().splitlines(), start=1):
        stripped = line.lstrip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in LINK_RE.finditer(line):
            yield lineno, match.group(1)


def _is_external(target: str) -> bool:
    """True if the target is a URL with a network/non-fs scheme."""
    parsed = urlparse(target)
    return parsed.scheme.lower() in EXTERNAL_SCHEMES


def _resolve_local(source: Path, target: str, project_root: Path) -> Path:
    """Resolve ``target`` against ``source.parent`` (or project root if
    the target starts with ``/``). Strips any ``#fragment`` and decodes
    percent-encoded characters (e.g. ``%20``).
    """
    target_path = unquote(target.split("#", 1)[0])
    if not target_path:
        # Pure anchor link like `[x](#section)` — nothing to verify here.
        return source

    if target_path.startswith("/"):
        return (project_root / target_path.lstrip("/")).resolve()

    return (source.parent / target_path).resolve()


def scan(root: Path, project_root: Path) -> ScanReport:
    """Walk ``root``, parse every markdown file, classify each link, and
    return a :class:`ScanReport` listing any broken local references.
    """
    report = ScanReport()

    for md_path in _iter_markdown_files(root):
        report.files_scanned += 1

        for lineno, raw_target in _extract_links(md_path):
            report.links_total += 1

            if _is_external(raw_target):
                report.links_external += 1
                continue

            # Pure-fragment links (`#section`) point inside the same file.
            # We don't verify headings, so we don't count them as local
            # filesystem links either.
            if raw_target.startswith("#"):
                continue

            report.links_local += 1
            resolved = _resolve_local(md_path, raw_target, project_root)

            if not resolved.exists():
                report.broken.append(BrokenLink(
                    source=md_path,
                    line_number=lineno,
                    raw_target=raw_target,
                    resolved=resolved,
                    reason="path does not exist on disk",
                ))

    return report


def _format_report(report: ScanReport, project_root: Path, quiet: bool) -> str:
    """Render a short summary plus a per-broken-link detail block."""
    lines: List[str] = []
    lines.append(
        f"Scanned {report.files_scanned} markdown file(s) — "
        f"{report.links_total} link(s): "
        f"{report.links_local} local, {report.links_external} external"
    )

    if not report.broken:
        lines.append("✓ no broken local links")
        return "\n".join(lines)

    lines.append(f"✗ {len(report.broken)} broken local link(s):")
    lines.append("")
    for bl in report.broken:
        try:
            src_rel = bl.source.relative_to(project_root)
        except ValueError:
            src_rel = bl.source
        try:
            dst_rel = bl.resolved.relative_to(project_root)
        except ValueError:
            dst_rel = bl.resolved
        lines.append(f"  {src_rel}:{bl.line_number}")
        lines.append(f"    link    : {bl.raw_target}")
        lines.append(f"    resolved: {dst_rel}")
        lines.append(f"    reason  : {bl.reason}")
        if not quiet:
            lines.append("")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point. Returns 0 when no broken links found (or when
    ``--fail-on-broken`` is not set), 1 otherwise."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "paths",
        nargs="*",
        default=["docs"],
        help="One or more directories to scan (default: docs)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Project root for resolving repo-absolute paths (default: cwd)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress blank-line separators between broken-link entries",
    )
    parser.add_argument(
        "--fail-on-broken",
        action="store_true",
        help="Exit non-zero when broken links are found (CI mode)",
    )

    args = parser.parse_args(argv)
    project_root = args.root.resolve()

    total_broken = 0
    for raw_path in args.paths:
        path = (project_root / raw_path).resolve() if not Path(raw_path).is_absolute() else Path(raw_path).resolve()
        if not path.exists():
            print(f"error: {raw_path} does not exist", file=sys.stderr)
            return 2
        report = scan(path, project_root)
        print(_format_report(report, project_root, args.quiet))
        total_broken += len(report.broken)

    if args.fail_on_broken and total_broken > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
