"""
GraphQueryFacade - Namespace-Safe Query Interface

Provides a thin safety layer enforcing explicit labels in Apache AGE queries
to prevent namespace collisions between concept graph and vocabulary metadata.

Part of ADR-048: Vocabulary Metadata as First-Class Graph

Usage:
    from api.api.lib.query_facade import GraphQueryFacade

    facade = GraphQueryFacade(age_client)

    # Safe: Always uses :Concept label
    concepts = facade.match_concepts(where="c.label =~ '(?i).*recursive.*'")

    # Safe: Always uses :VocabType label
    vocab_types = facade.match_vocab_types(where="v.is_active = true")

    # Escape hatch for complex queries (logs for audit)
    results = facade.execute_raw(complex_query, namespace="migration")
"""

from typing import Optional, Dict, List, Any
import logging
from .datetime_utils import to_iso, utcnow

logger = logging.getLogger(__name__)


class QueryAuditLog:
    """
    Lightweight query audit logger.

    Tracks queries for namespace safety analysis without persisting to database.
    """

    def __init__(self):
        self.queries: List[Dict[str, Any]] = []
        self.raw_query_count = 0

    def log_query(
        self,
        query: str,
        namespace: str,
        is_raw: bool = False,
        params: Optional[Dict] = None
    ):
        """Log a query execution for audit trail."""
        entry = {
            "timestamp": to_iso(utcnow()),
            "query": query,
            "namespace": namespace,
            "is_raw": is_raw,
            "params": params or {}
        }

        self.queries.append(entry)

        if is_raw:
            self.raw_query_count += 1
            logger.debug(
                f"[QueryFacade] RAW query in namespace '{namespace}': {query[:100]}..."
            )
        else:
            logger.debug(
                f"[QueryFacade] SAFE query in namespace '{namespace}'"
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get audit statistics."""
        total = len(self.queries)
        safe = total - self.raw_query_count

        return {
            "total_queries": total,
            "safe_queries": safe,
            "raw_queries": self.raw_query_count,
            "safety_ratio": safe / total if total > 0 else 1.0
        }


class GraphQueryFacade:
    """
    Namespace-safe query interface for Apache AGE.

    Enforces explicit labels to prevent catastrophic namespace collisions
    when concept graph and vocabulary metadata coexist in same database.
    """

    def __init__(self, age_client):
        """
        Initialize facade with AGEClient instance.

        Args:
            age_client: Instance of AGEClient from api.api.lib.age_client
        """
        self.db = age_client
        self.audit = QueryAuditLog()

    # -------------------------------------------------------------------------
    # CONCEPT NAMESPACE (Core knowledge graph)
    # -------------------------------------------------------------------------

    def match_concepts(
        self,
        where: Optional[str] = None,
        params: Optional[Dict] = None,
        limit: Optional[int] = None,
        return_clause: str = "c"
    ) -> List[Dict]:
        """
        Match concept nodes with explicit :Concept label.

        Args:
            where: Optional WHERE clause (without WHERE keyword)
            params: Query parameters
            limit: Optional result limit
            return_clause: What to return (default: "c")

        Returns:
            List of result dictionaries

        Example:
            # Find concepts by label pattern
            concepts = facade.match_concepts(
                where="c.label =~ '(?i).*recursive.*'",
                limit=10
            )
        """
        query = "MATCH (c:Concept)"

        if where:
            query += f" WHERE {where}"

        query += f" RETURN {return_clause}"

        if limit:
            query += f" LIMIT {limit}"

        self.audit.log_query(query, namespace="concept", params=params)
        return self.db._execute_cypher(query, params)

    def match_concept_relationships(
        self,
        rel_types: Optional[List[str]] = None,
        where: Optional[str] = None,
        params: Optional[Dict] = None,
        limit: Optional[int] = None,
        include_epistemic_status: Optional[List[str]] = None,
        exclude_epistemic_status: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Match relationships between concepts with optional epistemic status filtering.

        Args:
            rel_types: Optional list of relationship types (e.g., ["IMPLIES", "SUPPORTS"])
            where: Optional WHERE clause
            params: Query parameters
            limit: Optional result limit
            include_epistemic_status: Only include relationships with these epistemic statuses (ADR-065 Phase 2)
            exclude_epistemic_status: Exclude relationships with these epistemic statuses (ADR-065 Phase 2)

        Returns:
            List of (source, relationship, target) dictionaries

        Example:
            # Find all SUPPORTS relationships
            supports = facade.match_concept_relationships(
                rel_types=["SUPPORTS"],
                where="r.edge_count > 5"
            )

            # Find only high-confidence relationships (ADR-065)
            affirmative = facade.match_concept_relationships(
                include_epistemic_status=["AFFIRMATIVE"]
            )

            # Exclude historical relationships (current state only)
            current = facade.match_concept_relationships(
                exclude_epistemic_status=["HISTORICAL"]
            )

            # Explore dialectical tension (contested + contradictory)
            dialectical = facade.match_concept_relationships(
                include_epistemic_status=["CONTESTED", "CONTRADICTORY"]
            )
        """
        # Phase 2 (ADR-065): Get vocabulary types matching epistemic status filters
        if include_epistemic_status or exclude_epistemic_status:
            status_filters = []

            if include_epistemic_status:
                status_list = ", ".join([f"'{s}'" for s in include_epistemic_status])
                status_filters.append(f"v.epistemic_status IN [{status_list}]")

            if exclude_epistemic_status:
                status_list = ", ".join([f"'{s}'" for s in exclude_epistemic_status])
                status_filters.append(f"NOT v.epistemic_status IN [{status_list}]")

            vocab_query = f"""
                MATCH (v:VocabType)
                WHERE {' AND '.join(status_filters)}
                RETURN v.name as type_name
            """

            self.audit.log_query(vocab_query, namespace="vocabulary", params={})
            vocab_results = self.db._execute_cypher(vocab_query, params={})
            status_filtered_types = [row['type_name'] for row in vocab_results]

            # Combine with explicit rel_types if provided
            if rel_types:
                # Intersection: only types that match both filters
                rel_types = [t for t in rel_types if t in status_filtered_types]
            else:
                # Use status-filtered types as the relationship type list
                rel_types = status_filtered_types

        # Build relationship pattern
        rel_pattern = ""
        if rel_types:
            type_str = "|".join(rel_types)
            rel_pattern = f":{type_str}"

        query = f"MATCH (c1:Concept)-[r{rel_pattern}]->(c2:Concept)"

        if where:
            query += f" WHERE {where}"

        query += " RETURN c1, r, c2"

        if limit:
            query += f" LIMIT {limit}"

        self.audit.log_query(query, namespace="concept", params=params)
        return self.db._execute_cypher(query, params)

    def count_concepts(
        self,
        where: Optional[str] = None,
        params: Optional[Dict] = None
    ) -> int:
        """
        Count concept nodes (namespace-safe).

        Args:
            where: Optional WHERE clause
            params: Query parameters

        Returns:
            Count of matching concepts

        Example:
            total_concepts = facade.count_concepts()
        """
        query = "MATCH (c:Concept)"

        if where:
            query += f" WHERE {where}"

        query += " RETURN count(c) as node_count"

        self.audit.log_query(query, namespace="concept", params=params)
        result = self.db._execute_cypher(query, params, fetch_one=True)

        return result.get("node_count", 0) if result else 0

    # -------------------------------------------------------------------------
    # VOCABULARY NAMESPACE (Metadata graph)
    # -------------------------------------------------------------------------

    def match_vocab_types(
        self,
        where: Optional[str] = None,
        params: Optional[Dict] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Match vocabulary type nodes with explicit :VocabType label.

        Args:
            where: Optional WHERE clause
            params: Query parameters
            limit: Optional result limit

        Returns:
            List of vocabulary type dictionaries

        Example:
            # Find active vocabulary types in causation category
            types = facade.match_vocab_types(
                where="v.is_active = true AND v.category = 'causation'"
            )
        """
        query = "MATCH (v:VocabType)"

        if where:
            query += f" WHERE {where}"

        query += " RETURN v"

        if limit:
            query += f" LIMIT {limit}"

        self.audit.log_query(query, namespace="vocabulary", params=params)
        return self.db._execute_cypher(query, params)

    def match_vocab_categories(
        self,
        where: Optional[str] = None,
        params: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Match vocabulary category nodes.

        Args:
            where: Optional WHERE clause
            params: Query parameters

        Returns:
            List of category dictionaries

        Example:
            categories = facade.match_vocab_categories()
        """
        query = "MATCH (c:VocabCategory)"

        if where:
            query += f" WHERE {where}"

        query += " RETURN c"

        self.audit.log_query(query, namespace="vocabulary", params=params)
        return self.db._execute_cypher(query, params)

    def find_vocabulary_synonyms(
        self,
        min_similarity: float = 0.85,
        category: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Find potential vocabulary synonyms using :SIMILAR_TO relationships.

        Args:
            min_similarity: Minimum similarity threshold
            category: Optional category filter
            limit: Optional result limit

        Returns:
            List of (type1, similarity, type2) dictionaries

        Example:
            synonyms = facade.find_vocabulary_synonyms(
                min_similarity=0.85,
                category="causation"
            )
        """
        query = "MATCH (v1:VocabType)-[s:SIMILAR_TO]->(v2:VocabType)"

        conditions = [f"s.similarity >= {min_similarity}"]

        if category:
            conditions.append(f"v1.category = '{category}'")
            conditions.append(f"v2.category = '{category}'")

        query += " WHERE " + " AND ".join(conditions)
        query += " RETURN v1, s, v2"

        if limit:
            query += f" LIMIT {limit}"

        self.audit.log_query(query, namespace="vocabulary", params={})
        return self.db._execute_cypher(query, params={})

    def count_vocab_types(
        self,
        where: Optional[str] = None,
        params: Optional[Dict] = None
    ) -> int:
        """
        Count vocabulary type nodes (namespace-safe).

        Args:
            where: Optional WHERE clause
            params: Query parameters

        Returns:
            Count of vocabulary types

        Example:
            active_types = facade.count_vocab_types(
                where="v.is_active = true"
            )
        """
        query = "MATCH (v:VocabType)"

        if where:
            query += f" WHERE {where}"

        query += " RETURN count(v) as node_count"

        self.audit.log_query(query, namespace="vocabulary", params=params)
        result = self.db._execute_cypher(query, params, fetch_one=True)

        return result.get("node_count", 0) if result else 0

    # -------------------------------------------------------------------------
    # SOURCE & INSTANCE NAMESPACE
    # -------------------------------------------------------------------------

    def match_sources(
        self,
        where: Optional[str] = None,
        params: Optional[Dict] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Match source nodes with explicit :Source label.

        Args:
            where: Optional WHERE clause
            params: Query parameters
            limit: Optional result limit

        Returns:
            List of source dictionaries
        """
        query = "MATCH (s:Source)"

        if where:
            query += f" WHERE {where}"

        query += " RETURN s"

        if limit:
            query += f" LIMIT {limit}"

        self.audit.log_query(query, namespace="concept", params=params)
        return self.db._execute_cypher(query, params)

    def match_instances(
        self,
        where: Optional[str] = None,
        params: Optional[Dict] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """
        Match instance nodes with explicit :Instance label.

        Args:
            where: Optional WHERE clause
            params: Query parameters
            limit: Optional result limit

        Returns:
            List of instance dictionaries
        """
        query = "MATCH (i:Instance)"

        if where:
            query += f" WHERE {where}"

        query += " RETURN i"

        if limit:
            query += f" LIMIT {limit}"

        self.audit.log_query(query, namespace="concept", params=params)
        return self.db._execute_cypher(query, params)

    # -------------------------------------------------------------------------
    # HEALTH & STATISTICS (Namespace-aware)
    # -------------------------------------------------------------------------

    def get_graph_stats(self) -> Dict[str, Any]:
        """
        Get namespace-aware graph statistics.

        Returns comprehensive stats that distinguish between:
        - Concept graph (Concept, Source, Instance nodes)
        - Vocabulary graph (VocabType, VocabCategory nodes)

        Returns:
            Dictionary with node counts by namespace

        Example:
            stats = facade.get_graph_stats()
            # {
            #     "concept_graph": {"concepts": 1234, "sources": 56, "instances": 789},
            #     "vocabulary_graph": {"types": 118, "categories": 8},
            #     "total_nodes": 2205
            # }
        """
        stats = {
            "concept_graph": {
                "concepts": self.count_concepts(),
                "sources": self._count_label("Source"),
                "instances": self._count_label("Instance")
            },
            "vocabulary_graph": {
                "types": self.count_vocab_types(),
                "categories": self._count_label("VocabCategory")
            }
        }

        # Calculate totals
        stats["total_nodes"] = (
            sum(stats["concept_graph"].values()) +
            sum(stats["vocabulary_graph"].values())
        )

        return stats

    def _count_label(self, label: str) -> int:
        """Helper to count nodes by label."""
        query = f"MATCH (n:{label}) RETURN count(n) as node_count"
        self.audit.log_query(query, namespace="internal", params={})
        result = self.db._execute_cypher(query, fetch_one=True)
        return result.get("node_count", 0) if result else 0

    # -------------------------------------------------------------------------
    # ESCAPE HATCH (For complex queries requiring raw Cypher)
    # -------------------------------------------------------------------------

    def execute_raw(
        self,
        query: str,
        params: Optional[Dict] = None,
        namespace: str = "unknown",
        fetch_one: bool = False
    ) -> Any:
        """
        Execute raw Cypher query with audit logging.

        ⚠️  WARNING: No safety guarantees. Only use when facade methods insufficient.

        All raw queries are logged for audit trail and contribute to technical
        debt metric. Prefer facade methods when possible.

        Args:
            query: Raw openCypher query
            params: Query parameters
            namespace: Namespace identifier for audit log (e.g., "migration", "admin")
            fetch_one: Return single result instead of list

        Returns:
            Query results (format depends on fetch_one)

        Example:
            # Complex multi-namespace query
            result = facade.execute_raw(
                '''
                MATCH (c:Concept)-[:RELATED_TO]->(v:VocabType)
                WHERE c.label = $label
                RETURN c, v
                ''',
                params={"label": "recursive depth"},
                namespace="migration"
            )
        """
        self.audit.log_query(query, namespace=namespace, is_raw=True, params=params)

        logger.warning(
            f"[QueryFacade] Using escape hatch for raw query in namespace '{namespace}'. "
            "Consider adding facade method if this pattern is common."
        )

        return self.db._execute_cypher(query, params, fetch_one=fetch_one)

    # -------------------------------------------------------------------------
    # AUDIT & METRICS
    # -------------------------------------------------------------------------

    def get_audit_stats(self) -> Dict[str, Any]:
        """
        Get query audit statistics.

        Returns:
            Dictionary with query safety metrics

        Example:
            stats = facade.get_audit_stats()
            # {
            #     "total_queries": 245,
            #     "safe_queries": 238,
            #     "raw_queries": 7,
            #     "safety_ratio": 0.971
            # }
        """
        return self.audit.get_stats()

    def log_audit_summary(self):
        """Log audit summary to INFO level."""
        stats = self.get_audit_stats()

        logger.info(
            f"[QueryFacade] Audit Summary: "
            f"{stats['safe_queries']}/{stats['total_queries']} safe queries "
            f"({stats['safety_ratio']:.1%} safety ratio), "
            f"{stats['raw_queries']} raw queries"
        )
