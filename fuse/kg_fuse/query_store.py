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
    """A user-created query directory definition with .meta control plane settings."""
    query_text: str
    threshold: float = 0.7  # Default similarity threshold
    limit: int = 50  # Default max results
    exclude: list[str] = None  # Terms to exclude (NOT)
    union: list[str] = None  # Terms to add (OR)
    symlinks: list[str] = None  # Linked ontology names (OR for sources)
    created_at: str = ""

    def __post_init__(self):
        # Initialize mutable defaults
        if self.exclude is None:
            self.exclude = []
        if self.union is None:
            self.union = []
        if self.symlinks is None:
            self.symlinks = []

    def to_dict(self) -> dict:
        return asdict(self)


class QueryStore:
    """Manages user-created query directories with TOML persistence."""

    # Special key prefix for global queries (ontology=None)
    GLOBAL_PREFIX = "_global_"

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

    def _make_key(self, ontology: Optional[str], path: str) -> str:
        """Generate storage key for a query."""
        if ontology is None:
            return f"{self.GLOBAL_PREFIX}{path}"
        return f"{ontology}/{path}"

    def _make_prefix(self, ontology: Optional[str], path: str = "") -> str:
        """Generate prefix for listing children."""
        if ontology is None:
            if path:
                return f"{self.GLOBAL_PREFIX}{path}/"
            return self.GLOBAL_PREFIX
        if path:
            return f"{ontology}/{path}/"
        return f"{ontology}/"

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
            lines.append(f"limit = {query.limit}")
            # Format lists as TOML arrays
            exclude_str = ", ".join(f'"{e}"' for e in query.exclude)
            lines.append(f"exclude = [{exclude_str}]")
            union_str = ", ".join(f'"{u}"' for u in query.union)
            lines.append(f"union = [{union_str}]")
            symlinks_str = ", ".join(f'"{s}"' for s in query.symlinks)
            lines.append(f"symlinks = [{symlinks_str}]")
            lines.append(f'created_at = "{query.created_at}"')
            lines.append("")

        with open(self.path, "w") as f:
            f.write("\n".join(lines))

    def add_query(self, ontology: Optional[str], path: str, query_text: Optional[str] = None) -> Query:
        """
        Add a query (called on mkdir).

        Args:
            ontology: The ontology name (None for global queries)
            path: Relative path (e.g., "leadership" or "leadership/communication")
            query_text: Custom query text (defaults to last path component)

        Returns:
            The created Query
        """
        key = self._make_key(ontology, path)

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

    def remove_query(self, ontology: Optional[str], path: str):
        """
        Remove a query and all children (called on rmdir).

        Args:
            ontology: The ontology name (None for global queries)
            path: Relative path
        """
        key = self._make_key(ontology, path)
        # Remove exact match and all children
        self.queries = {
            k: v for k, v in self.queries.items()
            if k != key and not k.startswith(key + "/")
        }
        self._save()

    def get_query(self, ontology: Optional[str], path: str) -> Optional[Query]:
        """Get query definition by ontology and path."""
        return self.queries.get(self._make_key(ontology, path))

    def is_query_dir(self, ontology: Optional[str], path: str) -> bool:
        """Check if path is a user-created query directory."""
        return self._make_key(ontology, path) in self.queries

    def list_queries_under(self, ontology: Optional[str], path: str = "") -> list[str]:
        """
        List immediate child query directories under a path.

        Args:
            ontology: The ontology name (None for global queries)
            path: Parent path (empty string for root)

        Returns:
            List of child directory names (not full paths)
        """
        prefix = self._make_prefix(ontology, path)

        children = []
        for key in self.queries:
            if key.startswith(prefix):
                remainder = key[len(prefix):]
                # Only immediate children (no "/" in remainder)
                if "/" not in remainder:
                    children.append(remainder)

        return children

    def get_query_chain(self, ontology: Optional[str], path: str) -> list[Query]:
        """
        Get all queries in the path hierarchy (for nested query resolution).

        Args:
            ontology: The ontology name (None for global queries)
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

    def update_limit(self, ontology: Optional[str], path: str, limit: int) -> bool:
        """Update the limit parameter for a query."""
        query = self.get_query(ontology, path)
        if query:
            query.limit = max(1, min(limit, 1000))  # Clamp to reasonable range
            self._save()
            return True
        return False

    def update_threshold(self, ontology: Optional[str], path: str, threshold: float) -> bool:
        """Update the threshold parameter for a query."""
        query = self.get_query(ontology, path)
        if query:
            query.threshold = max(0.0, min(threshold, 1.0))  # Clamp to 0.0-1.0
            self._save()
            return True
        return False

    def add_exclude(self, ontology: Optional[str], path: str, term: str) -> bool:
        """Add a term to the exclude list."""
        query = self.get_query(ontology, path)
        if query:
            term = term.strip()
            if term and term not in query.exclude:
                query.exclude.append(term)
                self._save()
            return True
        return False

    def add_union(self, ontology: Optional[str], path: str, term: str) -> bool:
        """Add a term to the union list."""
        query = self.get_query(ontology, path)
        if query:
            term = term.strip()
            if term and term not in query.union:
                query.union.append(term)
                self._save()
            return True
        return False

    def clear_exclude(self, ontology: Optional[str], path: str) -> bool:
        """Clear all exclude terms."""
        query = self.get_query(ontology, path)
        if query:
            query.exclude = []
            self._save()
            return True
        return False

    def clear_union(self, ontology: Optional[str], path: str) -> bool:
        """Clear all union terms."""
        query = self.get_query(ontology, path)
        if query:
            query.union = []
            self._save()
            return True
        return False

    def add_symlink(self, ontology: Optional[str], path: str, linked_ontology: str) -> bool:
        """Add a symlinked ontology to the query."""
        query = self.get_query(ontology, path)
        if query:
            if linked_ontology not in query.symlinks:
                query.symlinks.append(linked_ontology)
                self._save()
            return True
        return False

    def remove_symlink(self, ontology: Optional[str], path: str, linked_ontology: str) -> bool:
        """Remove a symlinked ontology from the query."""
        query = self.get_query(ontology, path)
        if query:
            if linked_ontology in query.symlinks:
                query.symlinks.remove(linked_ontology)
                self._save()
            return True
        return False

    def get_symlinks(self, ontology: Optional[str], path: str) -> list[str]:
        """Get list of symlinked ontologies for a query."""
        query = self.get_query(ontology, path)
        if query:
            return query.symlinks.copy()
        return []
