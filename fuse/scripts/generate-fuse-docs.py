#!/usr/bin/env python3
"""Generate markdown API reference for kg-fuse from source docstrings.

Uses Python's ast module to extract module, class, and function docstrings
without importing the code (no dependency on runtime packages).

Output: docs/reference/fuse/README.md
"""

import ast
import sys
import textwrap
from datetime import date
from pathlib import Path

# Resolve paths relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
FUSE_ROOT = SCRIPT_DIR.parent
PROJECT_ROOT = FUSE_ROOT.parent
SOURCE_DIR = FUSE_ROOT / "kg_fuse"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "reference" / "fuse"

# Modules to skip in docs
SKIP_MODULES = {"__init__", "__pycache__"}


def extract_module(filepath: Path) -> dict:
    """Parse a Python file and extract documentation items."""
    source = filepath.read_text()
    tree = ast.parse(source, filename=str(filepath))

    module_doc = ast.get_docstring(tree) or ""
    classes = []
    functions = []

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            cls = {
                "name": node.name,
                "line": node.lineno,
                "doc": ast.get_docstring(node) or "",
                "methods": [],
            }
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if item.name.startswith("_") and item.name != "__init__":
                        continue
                    cls["methods"].append({
                        "name": item.name,
                        "line": item.lineno,
                        "doc": ast.get_docstring(item) or "",
                        "args": _format_args(item),
                        "is_async": isinstance(item, ast.AsyncFunctionDef),
                    })
            classes.append(cls)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("_"):
                continue
            functions.append({
                "name": node.name,
                "line": node.lineno,
                "doc": ast.get_docstring(node) or "",
                "args": _format_args(node),
                "is_async": isinstance(node, ast.AsyncFunctionDef),
            })

    return {
        "name": filepath.stem,
        "doc": module_doc,
        "classes": classes,
        "functions": functions,
    }


def _format_args(node) -> str:
    """Format function arguments as a signature string."""
    args = node.args
    parts = []

    # Regular args (skip 'self'/'cls')
    for arg in args.args:
        name = arg.arg
        if name in ("self", "cls"):
            continue
        annotation = ""
        if arg.annotation:
            annotation = f": {ast.unparse(arg.annotation)}"
        parts.append(f"{name}{annotation}")

    # *args
    if args.vararg:
        parts.append(f"*{args.vararg.arg}")

    # **kwargs
    if args.kwarg:
        parts.append(f"**{args.kwarg.arg}")

    return ", ".join(parts)


def generate_markdown(modules: list[dict]) -> str:
    """Generate a single markdown document from extracted module data."""
    lines = []

    lines.append("# FUSE Driver API Reference (Auto-Generated)")
    lines.append("")
    lines.append("> **Auto-Generated Documentation**")
    lines.append("> ")
    lines.append("> Generated from FUSE driver source code docstrings.")
    lines.append(f"> Last updated: {date.today().isoformat()}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Table of contents
    lines.append("## Modules")
    lines.append("")
    for mod in modules:
        summary = mod["doc"].split("\n")[0] if mod["doc"] else ""
        anchor = mod["name"].replace("_", "-")
        if summary:
            lines.append(f"- [`{mod['name']}`](#{anchor}) - {summary}")
        else:
            lines.append(f"- [`{mod['name']}`](#{anchor})")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Module details
    for mod in modules:
        lines.append(f"## {mod['name']}")
        lines.append("")

        if mod["doc"]:
            lines.append(mod["doc"])
            lines.append("")

        # Functions
        for func in mod["functions"]:
            prefix = "async " if func["is_async"] else ""
            lines.append(f"### `{prefix}{func['name']}({func['args']})`")
            lines.append("")
            if func["doc"]:
                lines.append(func["doc"])
                lines.append("")

        # Classes
        for cls in mod["classes"]:
            lines.append(f"### class `{cls['name']}`")
            lines.append("")
            if cls["doc"]:
                lines.append(cls["doc"])
                lines.append("")

            for method in cls["methods"]:
                prefix = "async " if method["is_async"] else ""
                display_name = method["name"]
                if display_name == "__init__":
                    display_name = f"{cls['name']}.__init__"
                lines.append(
                    f"#### `{prefix}{display_name}({method['args']})`"
                )
                lines.append("")
                if method["doc"]:
                    lines.append(method["doc"])
                    lines.append("")

        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def main():
    # Collect and sort source files
    source_files = sorted(
        f for f in SOURCE_DIR.glob("*.py")
        if f.stem not in SKIP_MODULES
    )

    if not source_files:
        print(f"Error: no Python files found in {SOURCE_DIR}", file=sys.stderr)
        sys.exit(1)

    # Extract docs from each module
    modules = []
    for filepath in source_files:
        mod = extract_module(filepath)
        # Skip empty modules (no docs, no public items)
        if mod["doc"] or mod["classes"] or mod["functions"]:
            modules.append(mod)

    # Generate markdown
    content = generate_markdown(modules)

    # Write output (smart writer: only if changed)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_DIR / "README.md"

    if output_file.exists() and output_file.read_text() == content:
        print(f"  {output_file} (unchanged)")
    else:
        output_file.write_text(content)
        print(f"  {output_file} (updated)")

    print(f"  {len(modules)} modules documented")


if __name__ == "__main__":
    main()
