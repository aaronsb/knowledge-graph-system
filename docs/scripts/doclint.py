#!/usr/bin/env python3
"""
doclint — graph-aware linter for the documentation catalog.

Extends the ADR linter's approach (`docs/scripts/adr lint`) from ADRs to the
whole `docs/` tree, treating docs and ADRs as a single *decision graph*: nodes
are records, edges are `related`/`supersedes` references. See ADR-908
(documentation catalog) and ADR-900 (numbering domain system).

It checks three things:

1. Frontmatter validity — every catalog page carries a well-formed
   `id`/`domain`/`mode`, and the ID's domain digit + mode letter agree with the
   `domain`/`mode` fields. Domains come from `adr.yaml` (single source of truth).
2. Reference graph — every `related`/`supersedes` target resolves (no dangling
   reference), no supersede cycles, and no catalog page is orphaned from the
   mkdocs nav.
3. Coverage matrix — which `(domain, mode)` cells hold pages, surfacing gaps.

Catalog pages (docs/ outside architecture/) are ENFORCED: their issues are
errors. ADRs (docs/architecture/) WARN by default; `--enforce-adrs` promotes
them to errors once the ADR frontmatter sweep lands.

Usage:
    doclint.py [--check] [--enforce-adrs] [--quiet]

    --check         exit 1 if any errors (CI mode)
    --enforce-adrs  treat ADR issues as errors, not warnings
    --quiet         suppress the coverage matrix and per-file OK lines
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required (pip install pyyaml).", file=sys.stderr)
    sys.exit(1)

DOCS = Path(__file__).resolve().parent.parent          # docs/
REPO = DOCS.parent
ADR_YAML = DOCS / "architecture" / "adr.yaml"
MKDOCS_YML = REPO / "mkdocs.yml"

# Retired-range guard (ADR-900): scan these trees for references into the
# retired pre-domain number range and fail the build.
RETIRED_SCAN_DIRS = ["docs", "specs", "api", "cli", "fuse", "schema",
                     "web/src", "operator", "scripts"]
RETIRED_SCAN_EXTS = {".md", ".py", ".ts", ".tsx", ".js", ".mjs", ".rs",
                     ".sh", ".yml", ".yaml", ".json"}
RETIRED_SKIP_PARTS = {"node_modules", "dist", "site", ".git"}
# Files that define the retired range and may legitimately name it.
RETIRED_EXEMPT_NAMES = {"adr.yaml"}
RETIRED_EXEMPT_PREFIXES = ("ADR-900-",)
RETIRED_ALLOW_MARKER = "doclint-allow-retired"
ADR_ANYREF_RE = re.compile(r"\bADR-0*(\d+)(\.\d+)?\b")

MODE_LETTER = {
    "tutorial": "T", "how-to": "H", "reference": "R",
    "explanation": "E",
}
LETTER_MODE = {v: k for k, v in MODE_LETTER.items()}

ID_RE = re.compile(r"^(\d{2})\.(\d{3})\.([A-Z])$")
ADR_REF_RE = re.compile(r"^ADR-(\d+(?:\.\d+)?)$")
ADR_FILE_RE = re.compile(r"^ADR-(\d+(?:\.\d+)?)")

# Catalog pages live in docs/ but not these subtrees. Generated per-item stubs
# under reference/{cli,mcp,fuse}/ are excluded from the published site
# (mkdocs.yml exclude_docs) and are not catalog pages.
SKIP_DIR_PARTS = {"architecture", "security"}
SKIP_PREFIXES = ("reference/cli/", "reference/mcp/", "reference/fuse/")


# ============================================================================
# Config
# ============================================================================

def load_domain_digits() -> dict:
    """Map domain key -> leading digit, derived from adr.yaml ranges."""
    with open(ADR_YAML) as f:
        cfg = yaml.safe_load(f)
    digits = {}
    for key, dcfg in cfg.get("domains", {}).items():
        lo = dcfg["range"][0]
        digits[key] = lo // 100
    return digits


# ============================================================================
# Parsing
# ============================================================================

@dataclass
class Node:
    """A record in the decision graph (a catalog page or an ADR)."""
    kind: str                       # 'doc' | 'adr'
    key: str                        # catalog id ('4.O.01') or 'ADR-411'
    path: Path
    rel: str                        # display path, relative to repo root
    domain: str = None
    mode: str = None
    refs: list = field(default_factory=list)   # (field_name, target_string)
    issues: list = field(default_factory=list)  # (severity, message)


def parse_frontmatter(path: Path) -> dict:
    """Return the YAML frontmatter as a dict, or {} if absent/empty."""
    text = path.read_text()
    if not text.startswith("---"):
        return {}
    lines = text.split("\n")
    end = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return {}
    try:
        return yaml.safe_load("\n".join(lines[1:end])) or {}
    except yaml.YAMLError:
        return {}


def _as_ref_list(value) -> list:
    """Coerce a related/supersedes frontmatter value into a list of strings."""
    if not value:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def iter_catalog_pages():
    """Yield catalog page paths (docs/ outside architecture/ and security/)."""
    for p in sorted(DOCS.rglob("*.md")):
        parts = set(p.relative_to(DOCS).parts)
        if parts & SKIP_DIR_PARTS:
            continue
        rel = str(p.relative_to(DOCS))
        if rel.startswith(SKIP_PREFIXES):
            continue
        yield p


def iter_adrs():
    """Yield ADR file paths under docs/architecture/."""
    yield from sorted((DOCS / "architecture").rglob("ADR-*.md"))


# ============================================================================
# Building the graph
# ============================================================================

def build_doc_node(path: Path, digits: dict) -> Node:
    """Parse a catalog page and validate its frontmatter into a Node."""
    rel = str(path.relative_to(DOCS.parent))
    fm = parse_frontmatter(path)
    node = Node(kind="doc", key=fm.get("id") or f"?{rel}", path=path, rel=rel)

    cid, domain, mode = fm.get("id"), fm.get("domain"), fm.get("mode")
    node.domain, node.mode = domain, mode

    if not fm:
        node.issues.append(("error", "missing frontmatter (need id/domain/mode)"))
        return node

    for fname in ("id", "domain", "mode"):
        if not fm.get(fname):
            node.issues.append(("error", f"missing frontmatter key: {fname}"))

    if domain and domain not in digits:
        node.issues.append(("error", f"unknown domain: {domain} (see adr.yaml)"))
    if mode and mode not in MODE_LETTER:
        node.issues.append(
            ("error", f"unknown mode: {mode} (valid: {', '.join(MODE_LETTER)})"))

    if cid:
        m = ID_RE.match(cid)
        if not m:
            node.issues.append(("error", f"malformed id: {cid} (want <DD>.<NNN>.<POLE>)"))
        else:
            band, _serial, letter = m.group(1), m.group(2), m.group(3)
            if domain in digits and int(band) != digits[domain]:
                node.issues.append(
                    ("error",
                     f"id domain band {band} != domain '{domain}' (expected {digits[domain]:02d})"))
            if mode in MODE_LETTER and letter != MODE_LETTER[mode]:
                node.issues.append(
                    ("error",
                     f"id pole {letter} != mode '{mode}' (expected {MODE_LETTER[mode]})"))

    node.refs += [("related", r) for r in _as_ref_list(fm.get("related"))]
    node.refs += [("supersedes", r) for r in _as_ref_list(fm.get("supersedes"))]
    return node


def build_adr_node(path: Path) -> Node:
    """Parse an ADR into a Node (key from filename, refs from frontmatter)."""
    rel = str(path.relative_to(DOCS.parent))
    m = ADR_FILE_RE.match(path.name)
    key = f"ADR-{m.group(1)}" if m else path.stem
    fm = parse_frontmatter(path)
    node = Node(kind="adr", key=key, path=path, rel=rel)
    node.refs += [("related", r) for r in _as_ref_list(fm.get("related"))]
    node.refs += [("supersedes", r) for r in _as_ref_list(fm.get("supersedes"))]
    return node


# ============================================================================
# Graph checks
# ============================================================================

def collect_nav_pages() -> set:
    """Return the set of doc paths (relative to docs/) referenced by mkdocs nav."""
    class _Loader(yaml.SafeLoader):
        pass

    _Loader.add_multi_constructor(
        "tag:yaml.org,2002:python/", lambda loader, suffix, node: None)
    with open(MKDOCS_YML) as f:
        cfg = yaml.load(f, Loader=_Loader)

    pages = set()

    def walk(node):
        if isinstance(node, str):
            if node.endswith(".md"):
                pages.add(node)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(cfg.get("nav", []))
    return pages


def check_references(nodes: list):
    """Flag related/supersedes targets that resolve to no known node.

    Decimal-ADR convention (ADR-900): a decision may be split into parts
    (ADR-603.1, ADR-603.2). A bare base reference (`ADR-603`) is the family
    identifier and is satisfied by any of its parts — references cite the
    decision, not a specific part. An exact part reference (`ADR-603.2`) must
    match exactly.
    """
    keys = {n.key for n in nodes}
    base_parts = set()
    for k in keys:
        m = re.match(r"^(ADR-\d+)\.\d+$", k)
        if m:
            base_parts.add(m.group(1))

    for node in nodes:
        for fname, target in node.refs:
            t = target.strip()
            if not (ADR_REF_RE.match(t) or ID_RE.match(t)):
                continue   # prose `amends:` and other non-refs are not edges
            if t in keys:
                continue
            if "." not in t and t in base_parts:
                continue   # base reference satisfied by a part (ADR-603 -> ADR-603.1)
            node.issues.append(
                ("error", f"dangling {fname} reference: {t} (no such record)"))


def check_retired_refs(lo: int, hi: int):
    """Scan docs + source for references into the retired number range (ADR-900).

    Returns a list of (relpath, lineno, ref). The files that define the range
    (this ADR, adr.yaml) are exempt, as is any line carrying the allow-marker.
    """
    hits = []
    for d in RETIRED_SCAN_DIRS:
        base = REPO / d
        if not base.exists():
            continue
        for f in base.rglob("*"):
            if not f.is_file() or f.suffix not in RETIRED_SCAN_EXTS:
                continue
            if RETIRED_SKIP_PARTS & set(f.parts):
                continue
            if f.name in RETIRED_EXEMPT_NAMES or f.name.startswith(RETIRED_EXEMPT_PREFIXES):
                continue
            try:
                text = f.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            if "ADR-" not in text:
                continue
            rel = str(f.relative_to(REPO))
            for ln, line in enumerate(text.split("\n"), 1):
                if RETIRED_ALLOW_MARKER in line:
                    continue
                for m in ADR_ANYREF_RE.finditer(line):
                    if lo <= int(m.group(1)) <= hi:
                        hits.append((rel, ln, m.group(0)))
    return hits


def check_supersede_cycles(nodes: list):
    """Detect cycles in the supersedes relation."""
    edges = {}
    for n in nodes:
        edges.setdefault(n.key, [])
        for fname, target in n.refs:
            if fname == "supersedes":
                edges[n.key].append(target.strip())

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {k: WHITE for k in edges}
    by_key = {n.key: n for n in nodes}

    def visit(k, stack):
        color[k] = GRAY
        for nxt in edges.get(k, []):
            if nxt not in color:
                continue
            if color[nxt] == GRAY:
                cycle = " -> ".join(stack + [nxt])
                if k in by_key:
                    by_key[k].issues.append(("error", f"supersede cycle: {cycle}"))
            elif color[nxt] == WHITE:
                visit(nxt, stack + [nxt])
        color[k] = BLACK

    for k in edges:
        if color[k] == WHITE:
            visit(k, [k])


def check_orphans(doc_nodes: list, nav_pages: set):
    """Flag catalog pages on disk that the mkdocs nav never references."""
    for n in doc_nodes:
        rel_to_docs = str(n.path.relative_to(DOCS))
        if rel_to_docs not in nav_pages:
            n.issues.append(("warning", "orphan: not referenced by mkdocs nav"))


def check_duplicate_ids(doc_nodes: list):
    """Flag any catalog id shared by more than one page.

    Serials are scoped to a domain (not domain x mode), so the id is the page's
    stable handle and must be unique. A collision is a real clash to resolve,
    not a coincidence — two pages cannot carry the same part number.
    """
    by_id = {}
    for n in doc_nodes:
        if n.key and not n.key.startswith("?"):
            by_id.setdefault(n.key, []).append(n)
    for cid, group in by_id.items():
        if len(group) > 1:
            for n in group:
                mates = ", ".join(sorted(g.rel for g in group if g is not n))
                n.issues.append(("error", f"duplicate catalog id {cid} (also on: {mates})"))


# ============================================================================
# Coverage
# ============================================================================

def print_coverage(doc_nodes: list, digits: dict):
    """Print a domain x mode matrix of catalog page counts."""
    modes = list(MODE_LETTER)
    grid = {}
    for n in doc_nodes:
        if n.domain and n.mode:
            grid[(n.domain, n.mode)] = grid.get((n.domain, n.mode), 0) + 1

    domains = sorted(digits, key=lambda d: digits[d])
    header = f"{'domain':9} " + " ".join(f"{MODE_LETTER[m]:>3}" for m in modes) + "   tot"
    print("\nCoverage matrix (catalog pages per domain x mode):")
    print(header)
    print("-" * len(header))
    for d in domains:
        cells = [grid.get((d, m), 0) for m in modes]
        row = f"{d:9} " + " ".join(f"{c or '.':>3}" for c in cells)
        print(f"{row}   {sum(cells):>3}")
    total = sum(grid.values())
    print("-" * len(header))
    print(f"{'total':9} " + " ".join(
        f"{sum(grid.get((d, m), 0) for d in domains):>3}" for m in modes)
        + f"   {total:>3}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Graph-aware documentation catalog linter.")
    parser.add_argument("--check", action="store_true", help="exit 1 on errors (CI mode)")
    parser.add_argument("--enforce-adrs", action="store_true",
                        help="treat ADR issues as errors, not warnings")
    parser.add_argument("--quiet", action="store_true",
                        help="suppress coverage matrix and OK lines")
    args = parser.parse_args()

    digits = load_domain_digits()
    nav_pages = collect_nav_pages()
    with open(ADR_YAML) as f:
        retired_lo, retired_hi = (int(x) for x in
                                  yaml.safe_load(f).get("legacy", {}).get("range", [1, 99]))

    doc_nodes = [build_doc_node(p, digits) for p in iter_catalog_pages()]
    adr_nodes = [build_adr_node(p) for p in iter_adrs()]
    all_nodes = doc_nodes + adr_nodes

    check_references(all_nodes)
    check_supersede_cycles(all_nodes)
    check_orphans(doc_nodes, nav_pages)
    check_duplicate_ids(doc_nodes)

    # ADR issues are warnings unless --enforce-adrs; doc issues are always errors.
    def effective(node, severity):
        if node.kind == "adr" and not args.enforce_adrs and severity == "error":
            return "warning"
        return severity

    errors = warnings = 0
    flagged = [n for n in all_nodes if n.issues]
    for node in sorted(flagged, key=lambda n: n.rel):
        print(f"\n{node.rel}  [{node.key}]")
        for severity, msg in node.issues:
            sev = effective(node, severity)
            icon = "ERROR" if sev == "error" else "warn "
            print(f"  {icon}  {msg}")
            if sev == "error":
                errors += 1
            else:
                warnings += 1

    # Retired-range guard: references into the vacated pre-domain range (ADR-900).
    retired_hits = check_retired_refs(retired_lo, retired_hi)
    if retired_hits:
        print(f"\nRetired-range references (ADR-{retired_lo}..{retired_hi} are "
              f"renumbered; see ADR-900):")
        for rel, ln, ref in sorted(retired_hits):
            print(f"  ERROR  {rel}:{ln}  {ref}")
        errors += len(retired_hits)

    if not args.quiet:
        print_coverage(doc_nodes, digits)

    print(f"\n{'='*60}")
    print(f"Scanned {len(doc_nodes)} catalog pages + {len(adr_nodes)} ADRs")
    print(f"Summary: {errors} errors, {warnings} warnings")
    print(f"{'='*60}")

    if args.check and errors > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
