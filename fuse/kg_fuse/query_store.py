"""
Query Store - Client-side persistence for user-created query directories.

Query directories are created with mkdir and stored in TOML format.
Each directory name becomes a semantic search term.
"""

import os
import tomllib
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# tomli_w for writing TOML (tomllib is read-only)
try:
    import tomli_w
except ImportError:
    tomli_w = None


@dataclass
class Query:
    """A user-created query directory definition."""
    query_text: str
    threshold: float = 0.5  # Lower default for broader matches
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class QueryStore:
    """Manages user-created query directories with TOML persistence."""

    def __init__(self, data_path: Optional[Path] = None):
        self.path = data_path or (self._get_data_path() / "queries.toml")
        self.queries: dict[str, Query] = {}
        self._load()

    def _get_data_path(self) -> Path:
        """Get XDG data directory for kg-fuse."""
        xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        data_dir = Path(xdg_data) / "kg-fuse"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir

    def _load(self):
        """Load queries from TOML file."""
        if not self.path.exists():
            return

        try:
            with open(self.path, "rb") as f:
                data = tomllib.load(f)

            for key, value in data.get("queries", {}).items():
                self.queries[key] = Query(**value)
        except Exception as e:
            # If file is corrupted, start fresh
            print(f"Warning: Could not load queries from {self.path}: {e}")

    def _save(self):
        """Save queries to TOML file."""
        if tomli_w is None:
            # Fallback: write TOML manually
            self._save_manual()
            return

        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"queries": {k: v.to_dict() for k, v in self.queries.items()}}
        with open(self.path, "wb") as f:
            tomli_w.dump(data, f)

    def _save_manual(self):
        """Manual TOML writing when tomli_w is not available."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Knowledge Graph FUSE Query Definitions", ""]

        for key, query in self.queries.items():
            # TOML table with dotted key
            lines.append(f'[queries."{key}"]')
            lines.append(f'query_text = "{query.query_text}"')
            lines.append(f"threshold = {query.threshold}")
            lines.append(f'created_at = "{query.created_at}"')
            lines.append("")

        with open(self.path, "w") as f:
            f.write("\n".join(lines))

    def add_query(self, ontology: str, path: str, query_text: Optional[str] = None) -> Query:
        """
        Add a query (called on mkdir).

        Args:
            ontology: The ontology name
            path: Relative path under ontology (e.g., "leadership" or "leadership/communication")
            query_text: Custom query text (defaults to last path component)

        Returns:
            The created Query
        """
        key = f"{ontology}/{path}"

        # Default query text is the last path component
        if query_text is None:
            query_text = path.split("/")[-1]

        query = Query(
            query_text=query_text,
            threshold=0.5,  # Lower default for broader matches
            created_at=datetime.now().isoformat(),
        )
        self.queries[key] = query
        self._save()
        return query

    def remove_query(self, ontology: str, path: str):
        """
        Remove a query and all children (called on rmdir).

        Args:
            ontology: The ontology name
            path: Relative path under ontology
        """
        prefix = f"{ontology}/{path}"
        # Remove exact match and all children
        self.queries = {
            k: v for k, v in self.queries.items()
            if k != prefix and not k.startswith(prefix + "/")
        }
        self._save()

    def get_query(self, ontology: str, path: str) -> Optional[Query]:
        """Get query definition by ontology and path."""
        return self.queries.get(f"{ontology}/{path}")

    def is_query_dir(self, ontology: str, path: str) -> bool:
        """Check if path is a user-created query directory."""
        return f"{ontology}/{path}" in self.queries

    def list_queries_under(self, ontology: str, path: str = "") -> list[str]:
        """
        List immediate child query directories under a path.

        Args:
            ontology: The ontology name
            path: Parent path (empty string for ontology root)

        Returns:
            List of child directory names (not full paths)
        """
        if path:
            prefix = f"{ontology}/{path}/"
        else:
            prefix = f"{ontology}/"

        children = []
        for key in self.queries:
            if key.startswith(prefix):
                remainder = key[len(prefix):]
                # Only immediate children (no "/" in remainder)
                if "/" not in remainder:
                    children.append(remainder)

        return children

    def get_query_chain(self, ontology: str, path: str) -> list[Query]:
        """
        Get all queries in the path hierarchy (for nested query resolution).

        Args:
            ontology: The ontology name
            path: Full path (e.g., "leadership/communication")

        Returns:
            List of Query objects from root to leaf
        """
        queries = []
        parts = path.split("/") if path else []

        current = ""
        for part in parts:
            current = f"{current}/{part}".lstrip("/")
            query = self.get_query(ontology, current)
            if query:
                queries.append(query)

        return queries
