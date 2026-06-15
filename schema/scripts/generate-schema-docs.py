#!/usr/bin/env python3
"""Generate the Database Schema reference page from SQL DDL.

Source of truth: schema/00_baseline.sql plus schema/migrations/*.sql. The
generator parses the DDL textually (no database connection, no psql) so it runs
in CI with nothing but Python. It extracts CREATE TABLE column definitions,
COMMENT ON TABLE/COLUMN statements (including those that appear in later
migrations), and the header comment block of each migration, then emits one
markdown page at docs/reference/schema.md suitable for mkdocs.

This matches the house style of the FUSE generator (fuse/scripts/
generate-fuse-docs.py): parse the source, resolve paths relative to this
script, stamp the output with a generated-on date, write a single page.

Run directly or via `make docs-schema`.

Output: docs/reference/schema.md
"""

import re
import sys
from datetime import date
from pathlib import Path

# Resolve paths relative to this script (house style: no cwd dependence).
SCRIPT_DIR = Path(__file__).resolve().parent
SCHEMA_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = SCHEMA_ROOT.parent
BASELINE = SCHEMA_ROOT / "00_baseline.sql"
MIGRATIONS_DIR = SCHEMA_ROOT / "migrations"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "reference"
OUTPUT_FILE = OUTPUT_DIR / "schema.md"

# Platform versions are pinned in the Postgres image, not in the DDL. Stated
# here so the reference does not repeat the stale "Postgres 16 / AGE 1.5.0"
# claim that the consolidation audit flagged. Verified against
# docker/Dockerfile.postgres (apache/age:release_PG18_1.7.0).
POSTGRES_VERSION = "18"
AGE_VERSION = "1.7.0"

# Logical schemas and what each holds, for the page intro. Sourced from the
# COMMENT ON SCHEMA statements in 00_baseline.sql.
SCHEMA_BLURBS = {
    "public": "Cross-schema bookkeeping (migration tracking).",
    "kg_api": "API operational state: jobs, sessions, vocabulary, ontology.",
    "kg_auth": "Authentication and authorization (dynamic RBAC).",
    "kg_logs": "Observability: audit trails, metrics, health.",
}


def strip_sql_comments_inline(line: str) -> str:
    """Drop a trailing ``-- ...`` comment from one DDL line.

    Only used on column-definition lines, which never contain a string
    literal holding ``--``, so a plain split is safe here.
    """
    idx = line.find("--")
    return line[:idx] if idx >= 0 else line


def find_create_tables(sql: str):
    """Yield (qualified_name, body) for each CREATE TABLE in *sql*.

    Handles ``CREATE TABLE`` and ``CREATE TABLE IF NOT EXISTS`` with an
    optional schema qualifier. *body* is the raw text between the outer
    parentheses, with nested parens balanced so CHECK (...) constraints and
    composite PRIMARY KEY (...) clauses do not terminate the table early.
    """
    pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][\w.]*)\s*\(",
        re.IGNORECASE,
    )
    for match in pattern.finditer(sql):
        name = match.group(1)
        start = match.end()  # first char after the opening paren
        depth = 1
        i = start
        while i < len(sql) and depth > 0:
            ch = sql[i]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            i += 1
        body = sql[start : i - 1]
        yield name, body


def split_top_level_commas(body: str):
    """Split a table body on commas that are not inside parentheses.

    Keeps ``CHECK (a IN ('x', 'y'))`` and ``PRIMARY KEY (a, b)`` intact.
    """
    parts = []
    depth = 0
    current = []
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


# Clauses that begin a table-level constraint rather than a column.
CONSTRAINT_KEYWORDS = re.compile(
    r"^\s*(PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK|CONSTRAINT|EXCLUDE)\b",
    re.IGNORECASE,
)


def parse_columns(body: str):
    """Parse a table body into a list of column dicts and a constraint list.

    Returns ``(columns, table_constraints)``. Each column dict has name, type,
    and a flags string (NOT NULL, PRIMARY KEY, UNIQUE, DEFAULT ..., REFERENCES
    ..., CHECK ...). Table-level constraints are returned as raw strings.
    """
    columns = []
    constraints = []
    for raw in split_top_level_commas(body):
        segment = strip_sql_comments_inline(raw).strip()
        if not segment:
            continue
        if CONSTRAINT_KEYWORDS.match(segment):
            constraints.append(" ".join(segment.split()))
            continue

        tokens = segment.split(None, 1)
        if not tokens:
            continue
        col_name = tokens[0].strip('"')
        rest = tokens[1] if len(tokens) > 1 else ""
        rest_norm = " ".join(rest.split())

        # Column type is everything up to the first attribute keyword.
        type_match = re.match(
            r"^([A-Za-z_][\w]*(?:\s*\([\d,\s]*\))?(?:\[\])?)",
            rest_norm,
        )
        col_type = type_match.group(1).strip() if type_match else rest_norm
        attrs = rest_norm[len(col_type):].strip() if type_match else ""

        flags = []
        if re.search(r"\bPRIMARY\s+KEY\b", attrs, re.IGNORECASE):
            flags.append("PK")
        if re.search(r"\bUNIQUE\b", attrs, re.IGNORECASE):
            flags.append("UNIQUE")
        if re.search(r"\bNOT\s+NULL\b", attrs, re.IGNORECASE):
            flags.append("NOT NULL")

        default_match = re.search(
            r"\bDEFAULT\s+(.+?)(?=\s+(?:NOT\s+NULL|CHECK|REFERENCES|UNIQUE|PRIMARY)\b|$)",
            attrs,
            re.IGNORECASE,
        )
        if default_match:
            flags.append(f"DEFAULT {default_match.group(1).strip()}")

        ref_match = re.search(
            r"\bREFERENCES\s+([A-Za-z_][\w.]*\s*(?:\([^)]*\))?)",
            attrs,
            re.IGNORECASE,
        )
        if ref_match:
            flags.append(f"FK → {ref_match.group(1).strip()}")

        check_match = re.search(r"\bCHECK\s*(\(.+\))", attrs, re.IGNORECASE)
        if check_match:
            flags.append(f"CHECK {check_match.group(1).strip()}")

        columns.append(
            {
                "name": col_name,
                "type": col_type,
                "flags": flags,
                "comment": "",
            }
        )
    return columns, constraints


def find_comments(sql: str):
    """Extract COMMENT ON TABLE/COLUMN statements from *sql*.

    Returns ``(table_comments, column_comments)`` where table_comments maps a
    qualified table name to its comment, and column_comments maps
    ``"table.column"`` to its comment. Handles single- and multi-line
    quoted comment strings.
    """
    table_comments = {}
    column_comments = {}

    table_pat = re.compile(
        r"COMMENT\s+ON\s+TABLE\s+([A-Za-z_][\w.]*)\s+IS\s+'((?:[^']|'')*)'",
        re.IGNORECASE | re.DOTALL,
    )
    for m in table_pat.finditer(sql):
        table_comments[m.group(1)] = _clean_comment(m.group(2))

    col_pat = re.compile(
        r"COMMENT\s+ON\s+COLUMN\s+([A-Za-z_][\w.]*)\s+IS\s+'((?:[^']|'')*)'",
        re.IGNORECASE | re.DOTALL,
    )
    for m in col_pat.finditer(sql):
        column_comments[m.group(1)] = _clean_comment(m.group(2))

    return table_comments, column_comments


def _clean_comment(text: str) -> str:
    """Normalize a SQL comment string for one-line markdown table display."""
    text = text.replace("''", "'")
    return " ".join(text.split())


def parse_migration_header(path: Path):
    """Extract version, title, description, ADR refs, date from a migration.

    Reads only the leading comment block. Handles both header styles seen in
    the corpus: ``-- Migration: NNN_name`` and ``-- Migration NNN: Title``,
    plus Description/Purpose, ADR/Related/inline (ADR-NNN), Date, and Issue.
    """
    info = {
        "version": None,
        "title": "",
        "description": "",
        "adrs": [],
        "date": "",
        "issue": "",
    }
    lines = path.read_text().splitlines()
    header = []
    for line in lines:
        stripped = line.strip()
        if stripped == "" or stripped.startswith("--"):
            header.append(stripped.lstrip("-").strip())
            # Stop once we hit real DDL after collecting some header.
            continue
        if stripped.startswith(("CREATE", "ALTER", "INSERT", "UPDATE",
                                "BEGIN", "DROP", "DO", "SELECT", "GRANT",
                                "COMMENT", "WITH")):
            break

    blob = "\n".join(header)

    # Version + title. Try "Migration NNN: Title" then "Migration: NNN_name".
    m = re.search(r"Migration\s+(\d+)\s*:\s*(.+)", blob)
    if m:
        info["version"] = int(m.group(1))
        info["title"] = m.group(2).strip()
    else:
        m = re.search(r"Migration\s*:\s*(\d+)[_\s]+(.+)", blob)
        if m:
            info["version"] = int(m.group(1))
            info["title"] = m.group(2).strip().replace("_", " ")

    # Fall back to the filename for the version if the header is unusual.
    if info["version"] is None:
        fn = re.match(r"(\d+)", path.name)
        if fn:
            info["version"] = int(fn.group(1))

    desc = re.search(r"(?:Description|Purpose)\s*:\s*(.+)", blob)
    if desc:
        info["description"] = desc.group(1).strip()

    date_m = re.search(r"Date\s*:\s*(.+)", blob)
    if date_m:
        info["date"] = date_m.group(1).strip()

    issue_m = re.search(r"Issue\s*:\s*(#?\d+)", blob)
    if issue_m:
        info["issue"] = issue_m.group(1).strip()

    adrs = re.findall(r"ADR[-\s]?(\d{2,3})", blob)
    info["adrs"] = sorted({f"ADR-{a}" for a in adrs})

    # Title fallback: strip the numeric prefix off the filename.
    if not info["title"]:
        stem = path.stem
        stem = re.sub(r"^\d+[_-]?", "", stem)
        info["title"] = stem.replace("_", " ").strip().title()

    return info


def collect_sources():
    """Return the baseline path plus migration paths in version order."""
    migrations = sorted(
        MIGRATIONS_DIR.glob("*.sql"),
        key=lambda p: int(re.match(r"(\d+)", p.name).group(1))
        if re.match(r"(\d+)", p.name)
        else 0,
    )
    # 001_baseline.sql is a reference snapshot of 00_baseline.sql — skip it as
    # a table source so tables are not double-counted, but keep it in the
    # migration history list.
    return migrations


def build_table_index():
    """Parse every SQL source into a table -> definition map.

    Tables come from 00_baseline.sql and the migrations. COMMENT ON statements
    are merged across all sources, so a comment added in a late migration
    attaches to a table defined in the baseline. Returns
    ``(tables, all_table_comments, all_column_comments)`` where *tables* maps
    qualified name to ``{schema, name, columns, constraints, source}``.
    """
    tables = {}
    all_table_comments = {}
    all_column_comments = {}

    sources = [(BASELINE, "00_baseline.sql")]
    for path in collect_sources():
        if path.name == "001_baseline.sql":
            continue
        sources.append((path, path.name))

    for path, label in sources:
        if not path.exists():
            continue
        sql = path.read_text()

        for qualified, body in find_create_tables(sql):
            columns, constraints = parse_columns(body)
            if "." in qualified:
                schema, name = qualified.split(".", 1)
            else:
                schema, name = "public", qualified
            # First definition wins; later ALTERs are folded via comments and
            # the migration history rather than re-parsed in full.
            if qualified not in tables:
                tables[qualified] = {
                    "schema": schema,
                    "name": name,
                    "columns": columns,
                    "constraints": constraints,
                    "source": label,
                }

        tcs, ccs = find_comments(sql)
        all_table_comments.update(tcs)
        all_column_comments.update(ccs)

    return tables, all_table_comments, all_column_comments


def render(tables, table_comments, column_comments, migrations):
    """Render the full markdown page as a string."""
    today = date.today().isoformat()
    out = []

    # Documentation-catalog frontmatter (ADR-908). Emitted here, not hand-injected,
    # because this page is overwritten on every docs build. domain=db (schema),
    # mode=reference. Stripped from GitHub Pages (mkdocs ignores unknown keys).
    out.append("---")
    out.append("id: 2.R.01")
    out.append("domain: db")
    out.append("mode: reference")
    out.append("---")
    out.append("")
    out.append("# Database Schema")
    out.append("")
    out.append(
        "Relational schema for the Kappa Graph control plane. The knowledge "
        "graph itself (concepts, sources, instances, and their typed edges) "
        "lives in the Apache AGE `knowledge_graph` graph; the tables below "
        "hold operational state, authorization, and observability around it."
    )
    out.append("")
    out.append(
        f"Backed by PostgreSQL {POSTGRES_VERSION} with Apache AGE "
        f"{AGE_VERSION}. This page is generated from `schema/00_baseline.sql` "
        "and `schema/migrations/*.sql`; do not edit it by hand."
    )
    out.append("")
    out.append("<!-- GENERATED FILE — edit the SQL DDL, then run "
               "`make docs-schema`. -->")
    out.append(f"<!-- Generated: {today} -->")
    out.append("")

    # Group tables by logical schema.
    by_schema = {}
    for qualified, tbl in tables.items():
        by_schema.setdefault(tbl["schema"], []).append((qualified, tbl))

    schema_order = ["public", "kg_api", "kg_auth", "kg_logs"]
    ordered_schemas = [s for s in schema_order if s in by_schema]
    ordered_schemas += [s for s in sorted(by_schema) if s not in schema_order]

    # Summary section.
    out.append("## Schemas")
    out.append("")
    out.append("| Schema | Purpose | Tables |")
    out.append("|---|---|---|")
    for schema in ordered_schemas:
        blurb = SCHEMA_BLURBS.get(schema, "")
        count = len(by_schema[schema])
        out.append(f"| `{schema}` | {blurb} | {count} |")
    out.append("")

    # Per-schema, per-table detail.
    for schema in ordered_schemas:
        out.append(f"## `{schema}`")
        out.append("")
        blurb = SCHEMA_BLURBS.get(schema)
        if blurb:
            out.append(blurb)
            out.append("")

        for qualified, tbl in sorted(by_schema[schema], key=lambda x: x[1]["name"]):
            out.append(f"### `{tbl['name']}`")
            out.append("")
            tc = table_comments.get(qualified)
            if tc:
                out.append(tc)
                out.append("")

            out.append("| Column | Type | Constraints | Description |")
            out.append("|---|---|---|---|")
            for col in tbl["columns"]:
                flags = "; ".join(col["flags"]) if col["flags"] else ""
                comment = column_comments.get(
                    f"{qualified}.{col['name']}", ""
                )
                out.append(
                    f"| `{col['name']}` | `{col['type']}` | "
                    f"{_md_escape(flags)} | {_md_escape(comment)} |"
                )
            out.append("")

            if tbl["constraints"]:
                out.append("**Table constraints:**")
                out.append("")
                for c in tbl["constraints"]:
                    out.append(f"- `{c}`")
                out.append("")

    # Migration history.
    out.append("## Migration history")
    out.append("")
    out.append(
        "Schema evolves through numbered migrations under "
        "`schema/migrations/`. Each is recorded in `public.schema_migrations` "
        "when applied. The baseline (`00_baseline.sql`) is the consolidated "
        "starting point; migrations after it are applied in order."
    )
    out.append("")
    out.append("| # | Migration | ADRs | Description |")
    out.append("|---|---|---|---|")
    for info in migrations:
        ver = info["version"] if info["version"] is not None else ""
        adrs = ", ".join(info["adrs"])
        # Avoid echoing the title back as the description when the header had
        # no distinct Description/Purpose line.
        desc = info["description"]
        if desc.strip() == info["title"].strip():
            desc = ""
        if info["issue"] and info["issue"] not in desc:
            desc = f"{desc} ({info['issue']})".strip()
        out.append(
            f"| {ver} | {_md_escape(info['title'])} | {adrs} | "
            f"{_md_escape(desc)} |"
        )
    out.append("")

    return "\n".join(out) + "\n"


def _md_escape(text: str) -> str:
    """Escape pipe characters so cell content does not break the table."""
    return text.replace("|", "\\|")


def main() -> int:
    """Parse the DDL, render the page, and write docs/reference/schema.md."""
    if not BASELINE.exists():
        print(f"error: baseline not found at {BASELINE}", file=sys.stderr)
        return 1

    tables, table_comments, column_comments = build_table_index()

    migrations = []
    for path in collect_sources():
        migrations.append(parse_migration_header(path))
    migrations.sort(key=lambda i: i["version"] if i["version"] is not None else 0)

    page = render(tables, table_comments, column_comments, migrations)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(page)

    print(
        f"Generated {OUTPUT_FILE.relative_to(PROJECT_ROOT)} "
        f"({len(tables)} tables, {len(migrations)} migrations)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
