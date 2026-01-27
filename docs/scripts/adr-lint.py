#!/usr/bin/env python3
"""
ADR Frontmatter Linter

Scans Architecture Decision Records for frontmatter consistency and reports issues.
Uses YAML frontmatter format (compatible with Obsidian, FUSE, etc.)

Usage:
    ./adr-lint.py                    # Report issues
    ./adr-lint.py --fix              # Fix issues in place
    ./adr-lint.py --check            # Exit 1 if issues found (CI mode)
    ./adr-lint.py path/to/ADR.md     # Check specific file

Valid frontmatter format (YAML):
    ---
    status: Draft | Proposed | Accepted | Superseded | Deprecated
    date: YYYY-MM-DD
    deciders: Comma-separated list or Team Name
    related:
      - ADR-NNN
      - ADR-NNN
    ---

    # ADR-NNN: Title
"""

import argparse
import re
import sys
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
import yaml

# Valid status values
VALID_STATUSES = {'Draft', 'Proposed', 'Accepted', 'Superseded', 'Deprecated'}

# Status normalization map (the kaleidoscope of acceptance)
STATUS_NORMALIZE = {
    'implemented': 'Accepted',
    'complete': 'Accepted',
    'complete ✅': 'Accepted',
    'implemented ✅': 'Accepted',
    'implemented ✅ - all phases complete': 'Accepted',
    'implemented ✅ - fully integrated': 'Accepted',
    'accepted - partially implemented': 'Accepted',
    'in progress': 'Proposed',
    'planning complete - ready for implementation': 'Proposed',
    'implementation guide': None,  # Not an ADR status
    'implementation plan': None,
    'reference data': None,
}

# Patterns for old markdown-style frontmatter
TITLE_PATTERN = re.compile(r'^# ADR-(\d+): (.+)$')
OLD_STATUS_PATTERN = re.compile(r'^\*\*Status:\*\*\s*(.+)$')
OLD_DATE_PATTERN = re.compile(r'^\*\*Date:\*\*\s*(\d{4}-\d{2}-\d{2})$')
OLD_UPDATED_PATTERN = re.compile(r'^\*\*Updated:\*\*\s*(\d{4}-\d{2}-\d{2})$')
OLD_DECIDERS_PATTERN = re.compile(r'^\*\*Deciders:\*\*\s*(.+)$')
OLD_RELATED_PATTERN = re.compile(r'^\*\*Related(?: ADRs)?:\*\*\s*(.*)$')
OLD_TAGS_PATTERN = re.compile(r'^\*\*Tags:\*\*\s*(.*)$')
RELATED_ITEM_PATTERN = re.compile(r'^-\s*(ADR-\d+)')


@dataclass
class Issue:
    line: int
    message: str
    severity: str = 'warning'  # 'error' or 'warning'


@dataclass
class ADRInfo:
    path: Path
    number: Optional[int] = None
    title: Optional[str] = None
    status: Optional[str] = None
    date: Optional[str] = None
    updated: Optional[str] = None
    deciders: Optional[str] = None
    related: list = field(default_factory=list)
    has_yaml_frontmatter: bool = False
    has_old_frontmatter: bool = False
    issues: list = field(default_factory=list)
    raw_content: str = ""


def normalize_status(status: str) -> str:
    """Normalize a status value to standard form."""
    status_lower = status.lower()

    # Check direct mapping
    if status_lower in STATUS_NORMALIZE:
        normalized = STATUS_NORMALIZE[status_lower]
        return normalized if normalized else status

    # Check for "Superseded by" pattern
    if status_lower.startswith('superseded'):
        return 'Superseded'

    # Check for parenthetical notes like "Accepted (Phase 1)"
    base_status = status.split('(')[0].strip()
    if base_status in VALID_STATUSES:
        return base_status

    return status


def parse_yaml_frontmatter(content: str) -> tuple[dict, int, int]:
    """Parse YAML frontmatter from content. Returns (data, start_line, end_line)."""
    lines = content.split('\n')

    if not lines or lines[0].strip() != '---':
        return {}, 0, 0

    # Find closing ---
    end_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == '---':
            end_idx = i
            break

    if end_idx is None:
        return {}, 0, 0

    yaml_content = '\n'.join(lines[1:end_idx])
    try:
        data = yaml.safe_load(yaml_content) or {}
        return data, 1, end_idx + 1
    except yaml.YAMLError:
        return {}, 0, 0


def parse_old_frontmatter(content: str) -> tuple[dict, list, int]:
    """Parse old markdown-style frontmatter. Returns (data, related_items, end_line)."""
    lines = content.split('\n')
    data = {}
    related = []
    end_line = 0
    in_related = False

    for i, line in enumerate(lines):
        # Stop at section break or ## heading
        if line.strip() == '---' or line.startswith('## '):
            end_line = i
            break

        # Title
        match = TITLE_PATTERN.match(line)
        if match:
            data['number'] = int(match.group(1))
            data['title'] = match.group(2)
            continue

        # Status
        match = OLD_STATUS_PATTERN.match(line)
        if match:
            data['status'] = match.group(1).strip()
            in_related = False
            continue

        # Date
        match = OLD_DATE_PATTERN.match(line)
        if match:
            data['date'] = match.group(1)
            in_related = False
            continue

        # Updated
        match = OLD_UPDATED_PATTERN.match(line)
        if match:
            data['updated'] = match.group(1)
            in_related = False
            continue

        # Deciders
        match = OLD_DECIDERS_PATTERN.match(line)
        if match:
            data['deciders'] = match.group(1).strip()
            in_related = False
            continue

        # Related header
        match = OLD_RELATED_PATTERN.match(line)
        if match:
            in_related = True
            # Check for inline related (e.g., "**Related:** ADR-001, ADR-002")
            inline = match.group(1).strip()
            if inline:
                related.extend(re.findall(r'ADR-\d+', inline))
            continue

        # Related items
        if in_related:
            match = RELATED_ITEM_PATTERN.match(line)
            if match:
                related.append(match.group(1))
                continue
            elif line.strip() and not line.startswith('-'):
                in_related = False

        # Tags (just note, don't preserve)
        if OLD_TAGS_PATTERN.match(line):
            in_related = False
            continue

    return data, related, end_line


def lint_adr(path: Path) -> ADRInfo:
    """Lint a single ADR file and return info with issues."""
    info = ADRInfo(path=path)

    try:
        content = path.read_text()
        info.raw_content = content
    except Exception as e:
        info.issues.append(Issue(0, f"Cannot read file: {e}", 'error'))
        return info

    lines = content.split('\n')

    # Check for YAML frontmatter
    yaml_data, yaml_start, yaml_end = parse_yaml_frontmatter(content)

    if yaml_data:
        info.has_yaml_frontmatter = True
        info.status = yaml_data.get('status')
        info.date = yaml_data.get('date')
        info.updated = yaml_data.get('updated')
        info.deciders = yaml_data.get('deciders')
        info.related = yaml_data.get('related', [])

        # Find title after frontmatter
        for i, line in enumerate(lines[yaml_end:], yaml_end + 1):
            match = TITLE_PATTERN.match(line)
            if match:
                info.number = int(match.group(1))
                info.title = match.group(2)
                break
    else:
        # Parse old-style frontmatter
        old_data, related, _ = parse_old_frontmatter(content)

        if old_data:
            info.has_old_frontmatter = True
            info.number = old_data.get('number')
            info.title = old_data.get('title')
            info.status = old_data.get('status')
            info.date = old_data.get('date')
            info.updated = old_data.get('updated')
            info.deciders = old_data.get('deciders')
            info.related = related

            info.issues.append(Issue(
                0,
                "Uses old markdown frontmatter format. Run with --fix to convert to YAML.",
                'warning'
            ))

    # Validate fields
    if not info.number or not info.title:
        info.issues.append(Issue(1, "Invalid or missing title. Expected '# ADR-NNN: Title'", 'error'))

    if not info.status:
        info.issues.append(Issue(0, "Missing status field", 'error'))
    elif info.status:
        normalized = normalize_status(info.status)
        if normalized != info.status:
            info.issues.append(Issue(
                0,
                f"Non-standard status '{info.status}' → should be '{normalized}'",
                'warning'
            ))
        base_status = normalized.split('(')[0].strip()
        if base_status not in VALID_STATUSES and STATUS_NORMALIZE.get(info.status.lower()) is None:
            info.issues.append(Issue(
                0,
                f"'{info.status}' is not a valid ADR status. Consider moving file to docs/guides/",
                'error'
            ))

    if not info.date:
        info.issues.append(Issue(0, "Missing date field", 'error'))

    if not info.deciders:
        info.issues.append(Issue(0, "Missing deciders field", 'warning'))

    # Check filename matches ADR number
    if info.number:
        expected_prefix = f"ADR-{info.number:03d}"
        if not path.name.startswith(expected_prefix):
            info.issues.append(Issue(
                0,
                f"Filename '{path.name}' doesn't match ADR number {info.number}",
                'warning'
            ))

    return info


def generate_yaml_frontmatter(info: ADRInfo) -> str:
    """Generate YAML frontmatter from ADRInfo."""
    lines = ['---']

    # Status (normalized)
    status = normalize_status(info.status) if info.status else 'Draft'
    lines.append(f'status: {status}')

    # Date
    if info.date:
        lines.append(f'date: {info.date}')

    # Updated (only if different from date)
    if info.updated and info.updated != info.date:
        lines.append(f'updated: {info.updated}')

    # Deciders
    if info.deciders:
        lines.append(f'deciders: {info.deciders}')

    # Related ADRs
    if info.related:
        lines.append('related:')
        for rel in info.related:
            lines.append(f'  - {rel}')

    lines.append('---')
    return '\n'.join(lines)


def convert_to_yaml_frontmatter(info: ADRInfo) -> str:
    """Convert an ADR from old format to YAML frontmatter."""
    content = info.raw_content
    lines = content.split('\n')

    # Find the title line
    title_line_idx = None
    for i, line in enumerate(lines):
        if TITLE_PATTERN.match(line):
            title_line_idx = i
            break

    if title_line_idx is None:
        return content  # Can't convert without title

    # Find where old frontmatter ends (--- or ## or empty space after metadata)
    body_start_idx = title_line_idx + 1
    for i, line in enumerate(lines[title_line_idx + 1:], title_line_idx + 1):
        stripped = line.strip()
        # Skip blank lines and metadata lines
        if not stripped:
            continue
        if stripped == '---':
            body_start_idx = i + 1
            break
        if stripped.startswith('## '):
            body_start_idx = i
            break
        if stripped.startswith('**') and ':**' in stripped:
            continue  # Old frontmatter line
        if stripped.startswith('-') and 'ADR-' in stripped:
            continue  # Related item
        # Non-metadata content found
        body_start_idx = i
        break

    # Generate new content
    yaml_frontmatter = generate_yaml_frontmatter(info)
    title_line = lines[title_line_idx]
    body = '\n'.join(lines[body_start_idx:])

    return f"{yaml_frontmatter}\n\n{title_line}\n\n{body.lstrip()}"


def fix_adr(adr: ADRInfo) -> bool:
    """Apply fixes to an ADR file. Returns True if changes were made."""
    if not adr.has_old_frontmatter:
        return False  # Already has YAML or unfixable

    try:
        new_content = convert_to_yaml_frontmatter(adr)
        if new_content != adr.raw_content:
            adr.path.write_text(new_content)
            rel_path = adr.path.relative_to(Path.cwd()) if adr.path.is_relative_to(Path.cwd()) else adr.path
            print(f"  Converted: {rel_path}")
            return True
    except Exception as e:
        print(f"  Error fixing {adr.path}: {e}")

    return False


def find_adrs(root: Path) -> list[Path]:
    """Find all ADR files under the given root."""
    return sorted(root.rglob("ADR-*.md"))


def print_report(adrs: list[ADRInfo], verbose: bool = False):
    """Print a report of all ADRs and their issues."""
    total_errors = 0
    total_warnings = 0

    # Status summary
    status_counts: dict[str, int] = {}
    format_counts = {'yaml': 0, 'old': 0, 'unknown': 0}

    for adr in adrs:
        status = normalize_status(adr.status) if adr.status else 'Unknown'
        status_counts[status] = status_counts.get(status, 0) + 1

        if adr.has_yaml_frontmatter:
            format_counts['yaml'] += 1
        elif adr.has_old_frontmatter:
            format_counts['old'] += 1
        else:
            format_counts['unknown'] += 1

    print(f"\n{'='*60}")
    print(f"ADR Frontmatter Lint Report")
    print(f"{'='*60}")
    print(f"\nScanned: {len(adrs)} ADRs")
    print(f"\nFormat distribution:")
    print(f"  YAML frontmatter: {format_counts['yaml']}")
    print(f"  Old markdown style: {format_counts['old']}")
    print(f"  Unknown/broken: {format_counts['unknown']}")
    print(f"\nStatus distribution:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")

    # Issues by file
    files_with_issues = [adr for adr in adrs if adr.issues]

    if files_with_issues:
        print(f"\n{'-'*60}")
        print(f"Issues found in {len(files_with_issues)} files:")
        print(f"{'-'*60}")

        for adr in files_with_issues:
            rel_path = adr.path.relative_to(Path.cwd()) if adr.path.is_relative_to(Path.cwd()) else adr.path
            print(f"\n{rel_path}")

            for issue in adr.issues:
                icon = '❌' if issue.severity == 'error' else '⚠️'
                line_info = f"line {issue.line}: " if issue.line > 0 else ""
                print(f"  {icon} {line_info}{issue.message}")

                if issue.severity == 'error':
                    total_errors += 1
                else:
                    total_warnings += 1

    print(f"\n{'='*60}")
    print(f"Summary: {total_errors} errors, {total_warnings} warnings")
    print(f"{'='*60}\n")

    return total_errors, total_warnings


def main():
    parser = argparse.ArgumentParser(description='Lint ADR frontmatter for consistency')
    parser.add_argument('paths', nargs='*', help='Specific ADR files to check')
    parser.add_argument('--fix', action='store_true', help='Convert old format to YAML frontmatter')
    parser.add_argument('--check', action='store_true', help='Exit 1 if issues found (CI mode)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()

    # Find ADRs
    if args.paths:
        adr_paths = [Path(p) for p in args.paths]
    else:
        docs_root = Path(__file__).parent.parent
        adr_paths = find_adrs(docs_root / 'architecture')

    if not adr_paths:
        print("No ADR files found.")
        return 0

    # Lint all ADRs
    adrs = [lint_adr(path) for path in adr_paths]

    # Print report
    errors, warnings = print_report(adrs, args.verbose)

    # Fix mode
    if args.fix:
        print("Converting old frontmatter to YAML...")
        fixed_count = sum(1 for adr in adrs if fix_adr(adr))
        print(f"Converted {fixed_count} files.")

    # CI mode
    if args.check and errors > 0:
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
