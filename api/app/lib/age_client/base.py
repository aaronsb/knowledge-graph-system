"""
Base mixin for Apache AGE graph database operations.

Provides connection pool management, Cypher query execution,
and AGE-specific type parsing. All other mixins depend on the
infrastructure defined here.

Key infrastructure:
- ThreadedConnectionPool (psycopg2) for thread-safe connection reuse
- _execute_cypher(): AGE query wrapper with parameter substitution
- _parse_agtype(): Converts AGE's agtype values to Python dicts
- _extract_column_spec(): Parses RETURN clauses for AGE column specs
"""

import os
import json
import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any
import psycopg2
from psycopg2 import pool, extras

logger = logging.getLogger(__name__)


class BaseMixin:
    """Connection management and Cypher query execution."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None
    ):
        """
        Initialize AGE client with connection details.

        Args:
            host: PostgreSQL host (defaults to POSTGRES_HOST env var)
            port: PostgreSQL port (defaults to POSTGRES_PORT env var)
            database: Database name (defaults to POSTGRES_DB env var)
            user: Database user (defaults to POSTGRES_USER env var)
            password: Database password (defaults to POSTGRES_PASSWORD env var)

        Raises:
            ValueError: If connection details are missing
            psycopg2.OperationalError: If cannot connect to PostgreSQL
        """
        self.host = host or os.getenv("POSTGRES_HOST", "localhost")
        self.port = port or int(os.getenv("POSTGRES_PORT", "5432"))
        self.database = database or os.getenv("POSTGRES_DB", "knowledge_graph")
        self.user = user or os.getenv("POSTGRES_USER", "admin")
        self.password = password or os.getenv("POSTGRES_PASSWORD", "password")
        self.graph_name = "knowledge_graph"

        if not all([self.host, self.port, self.database, self.user, self.password]):
            raise ValueError(
                "Missing PostgreSQL connection details. Provide via parameters or "
                "set POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, "
                "POSTGRES_PASSWORD environment variables."
            )

        try:
            # Create connection pool for better performance
            # ThreadedConnectionPool for thread-safe access (parallel requests, ADR-071)
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                1,  # minconn
                20,  # maxconn (supports up to 16 parallel workers + buffer)
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password
            )
            # Test connection and setup AGE
            conn = self.pool.getconn()
            try:
                self._setup_age(conn)
            finally:
                self.pool.putconn(conn)
        except psycopg2.OperationalError as e:
            raise psycopg2.OperationalError(
                f"Cannot connect to PostgreSQL at {self.host}:{self.port}: {e}"
            )

        # Lazy-loaded facade for namespace-safe queries (ADR-048)
        self._facade = None

        # Lazy-loaded graph facade for accelerated traversal (ADR-201)
        self._graph_facade = None

    def _setup_age(self, conn):
        """Load AGE extension and set search path."""
        with conn.cursor() as cur:
            cur.execute("LOAD 'age';")
            cur.execute("SET search_path = ag_catalog, \"$user\", public;")
        conn.commit()

    def _execute_cypher(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
        fetch_one: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query via AGE.

        Args:
            query: Cypher query string
            params: Query parameters (will be interpolated into query)
            fetch_one: If True, return only first result

        Returns:
            List of dictionaries with query results
        """
        conn = self.pool.getconn()
        try:
            self._setup_age(conn)

            # Extract column names from RETURN clause BEFORE parameter substitution
            # (otherwise document content can interfere with regex parsing)
            column_spec = self._extract_column_spec(query)

            # Replace parameters in query (AGE doesn't support parameterized Cypher)
            if params:
                for key, value in params.items():
                    # Convert Python types to Cypher literals
                    if isinstance(value, str):
                        # Escape backslashes FIRST (critical for docs with code examples)
                        value_str = value.replace("\\", "\\\\")
                        # Then escape single quotes
                        value_str = value_str.replace("'", "\\'")
                        query = query.replace(f"${key}", f"'{value_str}'")
                    elif isinstance(value, list):
                        # Lists: JSON array syntax is Cypher-compatible
                        value_str = json.dumps(value).replace("\\", "\\\\").replace("'", "\\'")
                        query = query.replace(f"${key}", value_str)
                    elif isinstance(value, dict):
                        # Dicts: Store as JSON string (Cypher maps require unquoted keys,
                        # but JSON uses quoted keys - see GitHub issue for future improvement)
                        value_str = json.dumps(value).replace("\\", "\\\\").replace("'", "\\'")
                        query = query.replace(f"${key}", f"'{value_str}'")
                    elif isinstance(value, (int, float)):
                        query = query.replace(f"${key}", str(value))
                    elif value is None:
                        query = query.replace(f"${key}", "null")
                    else:
                        query = query.replace(f"${key}", str(value))

            # Wrap Cypher in AGE SELECT statement with dynamic column specification
            age_query = f"""
                SELECT * FROM cypher('{self.graph_name}', $$
                    {query}
                $$) as ({column_spec});
            """

            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                try:
                    cur.execute(age_query)
                except Exception as e:
                    error_str = str(e)

                    # Check if this is an expected race condition (parallel restore operations)
                    is_expected_race = (
                        "already exists" in error_str or
                        "Entity failed to be updated" in error_str
                    )

                    # Log at appropriate level (DEBUG for expected races, ERROR for real problems)
                    log_level = logger.debug if is_expected_race else logger.error

                    log_level("=" * 80)
                    log_level("Query execution failed" if not is_expected_race else "Expected concurrency conflict (will retry)")
                    log_level(f"Error: {e}")
                    log_level(f"Column spec: {column_spec}")
                    log_level(f"Original query length: {len(query)} chars")
                    log_level(f"First 500 chars: {query[:500]}")
                    log_level(f"Last 500 chars: {query[-500:]}")
                    if params:
                        log_level(f"Parameters:")
                        for k, v in params.items():
                            val_preview = str(v)[:200] if isinstance(v, str) else str(v)
                            log_level(f"  {k}: {val_preview}")
                    log_level("=" * 80)
                    raise

                if fetch_one:
                    result = cur.fetchone()
                    if result:
                        # Parse all agtype values in the result dict
                        return {k: self._parse_agtype(v) for k, v in result.items()}
                    return None
                else:
                    results = cur.fetchall()
                    # Parse all agtype values in each result dict
                    return [
                        {k: self._parse_agtype(v) for k, v in row.items()}
                        for row in results
                    ]

        finally:
            conn.commit()
            self.pool.putconn(conn)

    def _extract_column_spec(self, query: str) -> str:
        """
        Extract column names from Cypher RETURN clause to build AGE column specification.

        Parses patterns like:
        - RETURN count(n) as node_count -> "node_count agtype"
        - RETURN n.id, n.label -> "id agtype, label agtype"
        - RETURN n -> "n agtype"

        Args:
            query: Cypher query string

        Returns:
            Column specification string for AGE query (e.g., "col1 agtype, col2 agtype")
        """
        import re

        # Find the RETURN clause (case-insensitive)
        # Match everything after RETURN until ORDER BY, LIMIT, or end of string
        return_match = re.search(r'\bRETURN\s+(.+?)(?:\s+ORDER\s+BY|\s+LIMIT|$)', query, re.IGNORECASE | re.DOTALL)

        if not return_match:
            # No RETURN clause found, default to single result column
            return "result agtype"

        return_clause = return_match.group(1).strip()

        # Extract column names/aliases
        # Pattern: matches "expr as alias" or just "expr"
        columns = []
        for part in return_clause.split(','):
            part = part.strip()

            # Check for "as alias" pattern
            as_match = re.search(r'\s+as\s+(\w+)', part, re.IGNORECASE)
            if as_match:
                # Use the alias
                columns.append(as_match.group(1))
            else:
                # Extract last identifier (e.g., "n.label" -> "label", "count(n)" -> "count")
                # This is a simplified heuristic
                # For complex expressions, use a generic name
                tokens = re.findall(r'\w+', part)
                if tokens:
                    # Use the last token as column name
                    col_name = tokens[-1]
                    columns.append(col_name)
                else:
                    columns.append(f"col{len(columns)}")

        # Build column specification
        if not columns:
            return "result agtype"

        # De-duplicate column names by adding suffix if needed
        seen = {}
        unique_columns = []
        for col in columns:
            if col in seen:
                seen[col] += 1
                unique_columns.append(f"{col}_{seen[col]}")
            else:
                seen[col] = 0
                unique_columns.append(col)

        return ", ".join(f"{col} agtype" for col in unique_columns)

    def _parse_agtype(self, agtype_value: Any) -> Any:
        """
        Parse AGE's agtype values to Python types.

        AGE returns values as special agtype format that needs parsing.
        """
        if agtype_value is None:
            return None

        # Convert agtype to string and parse as JSON
        value_str = str(agtype_value)

        # AGE returns vertices as: {"id": ..., "label": ..., "properties": {...}}::vertex
        # AGE returns edges as: {"id": ..., "label": ..., "start_id": ..., "end_id": ..., "properties": {...}}::edge
        # AGE returns lists with type annotations: [{...}::vertex, {...}::vertex]
        # Strip ALL ::vertex and ::edge suffixes (not just the first one)
        if '::vertex' in value_str or '::edge' in value_str:
            import re
            # Remove all ::vertex and ::edge type annotations
            value_str = re.sub(r'::(vertex|edge|path)', '', value_str)

        try:
            return json.loads(value_str)
        except json.JSONDecodeError:
            # If not JSON, return as-is (might be a simple value)
            return agtype_value

    def close(self):
        """Close all database connections."""
        if hasattr(self, 'pool'):
            self.pool.closeall()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
