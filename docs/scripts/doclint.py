#!/usr/bin/env python3
"""
doclint — graph-aware linter for the documentation catalog.

Extends the ADR linter (`docs/scripts/adr lint`) from ADRs to the whole `docs/`
tree, treating docs and ADRs as a single *decision graph*: nodes are records,
edges are `related`/`supersedes` references. See your project's
documentation-catalog decision record for the model; this tool was generalized
from the knowledge-graph-system reference implementation.

It checks:

1. Frontmatter validity — every catalog page carries a well-formed
   `id`/`domain`/`mode`; the id's domain band and mode pole agree with the
   `domain`/`mode` fields. Domains come from `adr.yaml` (single source of truth).
2. Reference graph — every `related`/`supersedes` target resolves (no dangling
   reference), no supersede cycles, and (when a site nav exists) no catalog page
   is orphaned from it.
3. Coverage matrix — which `(domain, mode)` cells hold pages, surfacing gaps.

Portability (this is the canonical, multi-repo tool, not a single project's copy):

- **Catalog membership is opt-in.** A `docs/` page is a catalog node only if it
  declares catalog frontmatter (`id`/`domain`/`mode`). Un-declared prose is
  ignored, so a repo can adopt the catalog gradually instead of all-at-once.
- **mkdocs nav is optional.** No `mkdocs.yml` → the orphan check is skipped.
- **The retired-range guard is opt-in.** Set `legacy: {retired: true}` in
  `adr.yaml` to fail on references into a vacated pre-domain range. Set
  `legacy: {defining_adr: ADR-NNN}` to exempt the ADR that vacated the range (it
  names retired numbers legitimately). Repos still using their legacy range leave
  both off (default).
- **Project root is discovered** (git, then walking up for
  `docs/architecture/adr.yaml`), so the script works whether it is a symlink
  into the ways corpus (agent-ways dogfooding) or a vendored copy in a project.

Usage:
    doclint [--check] [--enforce-adrs] [--quiet]

    --check         exit 1 if any errors (CI mode)
    --enforce-adrs  treat ADR issues as errors, not warnings
    --quiet         suppress the coverage matrix
"""

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required (pip install pyyaml).", file=sys.stderr)
    sys.exit(1)


# ============================================================================
# Project root discovery (works under symlink or vendored copy)
# ============================================================================

def get_project_root() -> Path:
    """Find the project root via git, then by walking up to docs/architecture/."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            root = Path(result.stdout.strip())
            if (root / "docs" / "architecture" / "adr.yaml").exists():
                return root
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    candidate = Path.cwd()
    for _ in range(10):
        if (candidate / "docs" / "architecture" / "adr.yaml").exists():
            return candidate
        if candidate.parent == candidate:
            break
        candidate = candidate.parent
    return Path.cwd()


REPO = get_project_root()
DOCS = REPO / "docs"
ADR_YAML = DOCS / "architecture" / "adr.yaml"
MKDOCS_YML = REPO / "mkdocs.yml"

MODE_LETTER = {"tutorial": "T", "how-to": "H", "reference": "R", "explanation": "E"}

ID_RE = re.compile(r"^(\d{2})\.(\d{3})\.([A-Z])$")
ADR_REF_RE = re.compile(r"^ADR-(\d+(?:\.\d+)?)$")
ADR_FILE_RE = re.compile(r"^ADR-(\d+(?:\.\d+)?)")
WIKILINK_RE = re.compile(r"^\[\[(.+?)\]\]$")

# Catalog pages live in docs/ but not these subtrees.
SKIP_DIR_PARTS = {"architecture", "scripts"}

# Retired-range scan (opt-in via adr.yaml legacy.retired).
RETIRED_SCAN_EXTS = {".md", ".py", ".ts", ".tsx", ".js", ".mjs", ".rs",
                     ".sh", ".yml", ".yaml", ".json"}
RETIRED_SKIP_PARTS = {"node_modules", "dist", "site", ".git"}
RETIRED_EXEMPT_NAMES = {"adr.yaml"}
RETIRED_ALLOW_MARKER = "doclint-allow-retired"
ADR_ANYREF_RE = re.compile(r"\bADR-0*(\d+)(\.\d+)?\b")


# ============================================================================
# Config
# ============================================================================

def load_config() -> dict:
    if not ADR_YAML.exists():
        print(f"Error: {ADR_YAML} not found (run from a repo with ADR tooling).",
              file=sys.stderr)
        sys.exit(1)
    with open(ADR_YAML) as f:
        return yaml.safe_load(f) or {}


def domain_digits(cfg: dict) -> dict:
    """Map domain key -> leading digit, derived from adr.yaml ranges."""
    digits = {}
    for key, dcfg in cfg.get("domains", {}).items():
        digits[key] = dcfg["range"][0] // 100
    return digits


# ============================================================================
# Parsing
# ============================================================================

@dataclass
class Node:
    kind: str                       # 'doc' | 'adr'
    key: str                        # catalog id ('04.001.H') or 'ADR-411'
    path: Path
    rel: str
    domain: str = None
    mode: str = None
    refs: list = field(default_factory=list)    # (field_name, target_string)
    issues: list = field(default_factory=list)  # (severity, message)


def parse_frontmatter(path: Path) -> dict:
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return {}   # skip unreadable/non-UTF-8 files rather than abort the run
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
    """Coerce a related/supersedes value into target strings, stripping wikilinks.

    Catalog edges are Obsidian `[[wikilinks]]`; the inside is the catalog id or
    ADR reference. The aliased form `[[target|alias]]` keeps only `target`. Bare
    strings are accepted too (pre-wikilink ADRs).
    """
    if not value:
        return []
    items = [value] if isinstance(value, str) else value if isinstance(value, list) else []
    out = []
    for v in items:
        s = str(v).strip()
        m = WIKILINK_RE.match(s)
        if m:
            s = m.group(1).split("|", 1)[0].strip()   # [[target|alias]] -> target
        out.append(s)
    return out


def iter_catalog_pages():
    """Yield candidate catalog page paths (docs/ outside skipped subtrees)."""
    if not DOCS.exists():
        return
    for p in sorted(DOCS.rglob("*.md")):
        if set(p.relative_to(DOCS).parts) & SKIP_DIR_PARTS:
            continue
        yield p


def iter_adrs():
    arch = DOCS / "architecture"
    if arch.exists():
        yield from sorted(arch.rglob("ADR-*.md"))


def build_doc_node(path: Path, digits: dict):
    """Parse a docs/ page into a catalog Node, or None if it is not a catalog page.

    Opt-in membership: a page is only a catalog node if it declares at least one
    of id/domain/mode. That lets a repo adopt the catalog gradually.
    """
    fm = parse_frontmatter(path)
    cid, domain, mode = fm.get("id"), fm.get("domain"), fm.get("mode")
    if not (cid or domain or mode):
        return None   # ordinary prose, not (yet) a catalog page

    rel = str(path.relative_to(REPO))
    node = Node(kind="doc", key=cid or f"?{rel}", path=path, rel=rel,
                domain=domain, mode=mode)

    for fname, val in (("id", cid), ("domain", domain), ("mode", mode)):
        if not val:
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
            band, _serial, letter = m.groups()
            if domain in digits and int(band) != digits[domain]:
                node.issues.append(
                    ("error", f"id domain band {band} != domain '{domain}' "
                              f"(expected {digits[domain]:02d})"))
            if mode in MODE_LETTER and letter != MODE_LETTER[mode]:
                node.issues.append(
                    ("error", f"id pole {letter} != mode '{mode}' "
                              f"(expected {MODE_LETTER[mode]})"))

    node.refs += [("related", r) for r in _as_ref_list(fm.get("related"))]
    node.refs += [("supersedes", r) for r in _as_ref_list(fm.get("supersedes"))]
    return node


def build_adr_node(path: Path) -> Node:
    rel = str(path.relative_to(REPO))
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

def collect_nav_pages():
    """Doc paths (relative to docs/) referenced by mkdocs nav, or None if no nav."""
    if not MKDOCS_YML.exists():
        return None

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
    """Flag related/supersedes targets that resolve to no known node."""
    keys = {n.key for n in nodes}
    base_parts = {m.group(1) for k in keys
                  if (m := re.match(r"^(ADR-\d+)\.\d+$", k))}
    for node in nodes:
        for fname, target in node.refs:
            t = target.strip()
            if not (ADR_REF_RE.match(t) or ID_RE.match(t)):
                continue   # prose `amends:` and other non-refs are not edges
            if t in keys:
                continue
            if "." not in t and t in base_parts:
                continue   # base ref satisfied by a part (ADR-603 -> ADR-603.1)
            node.issues.append(
                ("error", f"dangling {fname} reference: {t} (no such record)"))


def check_supersede_cycles(nodes: list):
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
                if k in by_key:
                    by_key[k].issues.append(
                        ("error", f"supersede cycle: {' -> '.join(stack + [nxt])}"))
            elif color[nxt] == WHITE:
                visit(nxt, stack + [nxt])
        color[k] = BLACK

    for k in list(edges):
        if color[k] == WHITE:
            visit(k, [k])


def check_orphans(doc_nodes: list, nav_pages):
    if nav_pages is None:
        return
    for n in doc_nodes:
        if str(n.path.relative_to(DOCS)) not in nav_pages:
            n.issues.append(("warning", "orphan: not referenced by mkdocs nav"))


def check_duplicate_ids(doc_nodes: list):
    by_id = {}
    for n in doc_nodes:
        if n.key and not n.key.startswith("?"):
            by_id.setdefault(n.key, []).append(n)
    for cid, group in by_id.items():
        if len(group) > 1:
            for n in group:
                mates = ", ".join(sorted(g.rel for g in group if g is not n))
                n.issues.append(("error", f"duplicate catalog id {cid} (also on: {mates})"))


def _retired_scan_files():
    """Yield candidate files for the retired-range scan, respecting .gitignore.

    Enumerate via `git ls-files` (tracked + untracked-but-not-ignored) so a
    gitignored corpus, build tree, or scratch dir is never walked — without it,
    the scan reads every ignored file in the repo (e.g. a 500MB private corpus).
    Falls back to rglob for non-git checkouts, preserving portability.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO), "ls-files", "--cached", "--others",
             "--exclude-standard", "-z"],
            capture_output=True, timeout=30)
        if out.returncode == 0:
            for raw in out.stdout.split(b"\x00"):
                if raw:
                    yield REPO / raw.decode("utf-8", "surrogateescape")
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    yield from REPO.rglob("*")   # non-git fallback


def check_retired_refs(lo: int, hi: int, exempt_prefixes: tuple = ()):
    """Scan repo for references into a vacated pre-domain range (opt-in).

    exempt_prefixes: filename prefixes to skip — typically the ADR that vacated
    the range (it names retired numbers legitimately), from adr.yaml
    legacy.defining_adr.
    """
    hits = []
    for f in _retired_scan_files():
        if not f.is_file() or f.suffix not in RETIRED_SCAN_EXTS:
            continue
        if RETIRED_SKIP_PARTS & set(f.parts):
            continue
        if f.name in RETIRED_EXEMPT_NAMES or (exempt_prefixes and f.name.startswith(exempt_prefixes)):
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


# ============================================================================
# Coverage
# ============================================================================

def print_coverage(doc_nodes: list, digits: dict):
    modes = list(MODE_LETTER)
    grid = {}
    for n in doc_nodes:
        if n.domain and n.mode:
            grid[(n.domain, n.mode)] = grid.get((n.domain, n.mode), 0) + 1
    domains = sorted(digits, key=lambda d: digits[d])
    header = f"{'domain':12} " + " ".join(f"{MODE_LETTER[m]:>3}" for m in modes) + "   tot"
    print("\nCoverage matrix (catalog pages per domain x mode):")
    print(header)
    print("-" * len(header))
    for d in domains:
        cells = [grid.get((d, m), 0) for m in modes]
        print(f"{d:12} " + " ".join(f"{c or '.':>3}" for c in cells) + f"   {sum(cells):>3}")
    print("-" * len(header))
    total = sum(grid.values())
    print(f"{'total':12} " + " ".join(
        f"{sum(grid.get((d, m), 0) for d in domains):>3}" for m in modes) + f"   {total:>3}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Graph-aware documentation catalog linter.")
    parser.add_argument("--check", action="store_true", help="exit 1 on errors (CI mode)")
    parser.add_argument("--enforce-adrs", action="store_true",
                        help="treat ADR issues as errors, not warnings")
    parser.add_argument("--quiet", action="store_true", help="suppress coverage matrix")
    args = parser.parse_args()

    cfg = load_config()
    digits = domain_digits(cfg)
    nav_pages = collect_nav_pages()

    doc_nodes = [n for p in iter_catalog_pages()
                 if (n := build_doc_node(p, digits)) is not None]
    adr_nodes = [build_adr_node(p) for p in iter_adrs()]
    all_nodes = doc_nodes + adr_nodes

    check_references(all_nodes)
    check_supersede_cycles(all_nodes)
    check_orphans(doc_nodes, nav_pages)
    check_duplicate_ids(doc_nodes)

    def effective(node, severity):
        if node.kind == "adr" and not args.enforce_adrs and severity == "error":
            return "warning"
        return severity

    errors = warnings = 0
    for node in sorted((n for n in all_nodes if n.issues), key=lambda n: n.rel):
        print(f"\n{node.rel}  [{node.key}]")
        for severity, msg in node.issues:
            sev = effective(node, severity)
            print(f"  {'ERROR' if sev == 'error' else 'warn '}  {msg}")
            if sev == "error":
                errors += 1
            else:
                warnings += 1

    # Retired-range guard (opt-in): legacy: {retired: true} in adr.yaml.
    legacy = cfg.get("legacy", {}) or {}
    if legacy.get("retired"):
        lo, hi = (int(x) for x in legacy.get("range", [1, 99]))
        defining = legacy.get("defining_adr")
        exempt = (f"{defining}-",) if defining else ()
        retired_hits = check_retired_refs(lo, hi, exempt)
        if retired_hits:
            print(f"\nRetired-range references (ADR-{lo}..{hi} are vacated):")
            for rel, ln, ref in sorted(retired_hits):
                print(f"  ERROR  {rel}:{ln}  {ref}")
            errors += len(retired_hits)

    if not args.quiet and doc_nodes:
        print_coverage(doc_nodes, digits)

    print(f"\n{'='*60}")
    print(f"Scanned {len(doc_nodes)} catalog pages + {len(adr_nodes)} ADRs")
    print(f"Summary: {errors} errors, {warnings} warnings")
    print(f"{'='*60}")

    return 1 if (args.check and errors > 0) else 0


if __name__ == "__main__":
    sys.exit(main())
