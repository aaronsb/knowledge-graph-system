"""
Database operations endpoints for system information and health checks.

Provides REST API access to:
- Database statistics (node/relationship counts)
- Connection information
- Health checks
"""

from fastapi import APIRouter, HTTPException
import logging
import os

from ..dependencies.auth import CurrentUser
from ..models.database import (
    DatabaseStatsResponse,
    DatabaseInfoResponse,
    DatabaseHealthResponse,
    CypherQueryRequest,
    CypherQueryResponse
)
from api.api.lib.age_client import AGEClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/database", tags=["database"])


def get_age_client() -> AGEClient:
    """Get AGE client instance"""
    return AGEClient()


@router.get("/stats", response_model=DatabaseStatsResponse)
async def get_database_stats(
    current_user: CurrentUser
):
    """
    Get database statistics including node and relationship counts (ADR-060).

    **Authentication:** Requires valid OAuth token

    Returns:
        DatabaseStatsResponse with node counts by type and relationship breakdown

    Example:
        GET /database/stats
    """
    client = get_age_client()
    try:
        # Node counts by label
        stats = {}
        for label in ['Concept', 'Source', 'Instance']:
            result = client._execute_cypher(
                f"MATCH (n:{label}) RETURN count(n) as node_count",
                fetch_one=True
            )
            stats[label] = result['node_count'] if result else 0

        # Total relationship count
        rel_result = client._execute_cypher(
            "MATCH ()-[r]->() RETURN count(r) as rel_count",
            fetch_one=True
        )
        total_relationships = rel_result['rel_count'] if rel_result else 0

        # Concept relationship breakdown by type
        rel_types = client._execute_cypher("""
            MATCH (c1:Concept)-[r]->(c2:Concept)
            RETURN type(r) as rel_type, count(*) as type_count
            ORDER BY count(*) DESC
        """)

        rel_type_list = [
            {"rel_type": record['rel_type'], "count": record['type_count']}
            for record in (rel_types or [])
        ]

        return DatabaseStatsResponse(
            nodes={
                "concepts": stats['Concept'],
                "sources": stats['Source'],
                "instances": stats['Instance']
            },
            relationships={
                "total": total_relationships,
                "by_type": rel_type_list
            }
        )

    except Exception as e:
        logger.error(f"Failed to get database stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get database stats: {str(e)}")
    finally:
        client.close()


@router.get("/info", response_model=DatabaseInfoResponse)
async def get_database_info(
    current_user: CurrentUser
):
    """
    Get database connection information (ADR-060).

    **Authentication:** Requires valid OAuth token

    Returns:
        DatabaseInfoResponse with connection details and version info

    Example:
        GET /database/info
    """
    postgres_host = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port = os.getenv("POSTGRES_PORT", "5432")
    postgres_db = os.getenv("POSTGRES_DB", "knowledge_graph")
    postgres_user = os.getenv("POSTGRES_USER", "admin")

    uri = f"postgresql://{postgres_host}:{postgres_port}/{postgres_db}"

    info = {
        "uri": uri,
        "user": postgres_user,
        "connected": False,
        "version": None,
        "edition": "PostgreSQL + Apache AGE",
        "error": None
    }

    try:
        client = get_age_client()
        try:
            # Get PostgreSQL version using direct SQL query
            import psycopg2
            conn = client.pool.getconn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    version_result = cur.fetchone()
                    if version_result:
                        info["connected"] = True
                        info["version"] = version_result[0]
            finally:
                client.pool.putconn(conn)
        finally:
            client.close()
    except Exception as e:
        info["error"] = str(e)
        logger.warning(f"Database connection check failed: {e}")

    return DatabaseInfoResponse(**info)


@router.get("/health", response_model=DatabaseHealthResponse)
async def check_database_health():
    """
    Check database health and connectivity.

    Performs multiple checks:
    - Basic connectivity (ping test)
    - AGE extension availability
    - Graph schema existence

    Returns:
        DatabaseHealthResponse with overall status and check results

    Example:
        GET /database/health
    """
    health = {
        "status": "unknown",
        "responsive": False,
        "checks": {},
        "error": None
    }

    try:
        client = get_age_client()
        try:
            # Check basic connectivity
            result = client._execute_cypher("RETURN 1 as ping", fetch_one=True)
            if result and result["ping"] == 1:
                health["responsive"] = True
                health["checks"]["connectivity"] = "ok"

            # Check AGE extension (using direct SQL, not Cypher)
            try:
                import psycopg2
                conn = client.pool.getconn()
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT extname FROM pg_extension WHERE extname = 'age'")
                        age_check = cur.fetchone()
                    health["checks"]["age_extension"] = {
                        "installed": bool(age_check),
                        "status": "ok" if age_check else "error"
                    }
                finally:
                    client.pool.putconn(conn)
            except:
                health["checks"]["age_extension"] = {
                    "installed": False,
                    "status": "error"
                }

            # Check graph existence (ADR-048: namespace-aware)
            try:
                # Use facade to verify graph is accessible with proper namespace awareness
                concept_count = client.facade.count_concepts()
                health["checks"]["graph"] = {
                    "accessible": True,
                    "status": "ok",
                    "concept_count": concept_count
                }
            except:
                health["checks"]["graph"] = {
                    "accessible": False,
                    "status": "warning"
                }

            # Overall status
            if (health["responsive"] and
                health["checks"].get("age_extension", {}).get("status") == "ok"):
                health["status"] = "healthy"
            elif health["responsive"]:
                health["status"] = "degraded"
            else:
                health["status"] = "unhealthy"

        finally:
            client.close()

    except Exception as e:
        health["status"] = "unhealthy"
        health["error"] = str(e)
        logger.error(f"Database health check failed: {e}", exc_info=True)

    return DatabaseHealthResponse(**health)


@router.post("/query", response_model=CypherQueryResponse)
async def execute_cypher_query(
    request: CypherQueryRequest,
    current_user: CurrentUser
):
    """
    Execute a custom openCypher/GQL query (ADR-048).

    **Namespace Safety (ADR-048):**
    - `namespace='concept'`: Query operates on Concept/Source/Instance nodes (default namespace)
    - `namespace='vocab'`: Query operates on VocabType/VocabCategory nodes
    - `namespace=None` (raw): Full control, no automatic label injection (use with caution)

    **Warning:** Raw queries without namespace can operate on mixed node types.
    For internal code, always use namespace-safe facade methods when possible.

    **Authentication:** Requires valid OAuth token

    Args:
        request: CypherQueryRequest with query, optional params, optional namespace

    Returns:
        CypherQueryResponse with results, row count, namespace used, and any warnings

    Examples:
        ```json
        // Concept namespace (safe)
        {
          "query": "MATCH (c) WHERE c.label =~ '.*recursive.*' RETURN c.label, c.concept_id LIMIT 5",
          "namespace": "concept"
        }

        // Vocabulary namespace (safe)
        {
          "query": "MATCH (v) WHERE v.is_active = true RETURN v.name, v.edge_count ORDER BY v.edge_count DESC",
          "namespace": "vocab"
        }

        // Raw query (powerful but risky)
        {
          "query": "MATCH (n) RETURN labels(n), count(*) GROUP BY labels(n)",
          "namespace": null
        }
        ```
    """
    client = get_age_client()
    try:
        warning = None
        namespace_used = request.namespace

        # Warn if using raw queries without namespace
        if request.namespace is None:
            warning = "Raw query without namespace - may operate on mixed node types. Consider using namespace='concept' or 'vocab' for safety (ADR-048)."
            logger.warning(f"User {current_user.username} executing raw cypher query: {request.query[:100]}...")

        # Execute query using facade for namespace safety
        try:
            if request.namespace:
                # Use facade's execute_raw with namespace awareness
                results = client.facade.execute_raw(
                    query=request.query,
                    params=request.params or {},
                    namespace=request.namespace
                )
            else:
                # Raw execution - no namespace injection
                results = client._execute_cypher(
                    query=request.query,
                    params=request.params or {}
                )

            # Convert results to list of dicts (handle agtype unwrapping)
            result_list = []
            if results:
                for row in results:
                    # Unwrap agtype values if present
                    unwrapped_row = {}
                    for key, value in row.items():
                        try:
                            # Try to unwrap if it's an agtype value
                            unwrapped_row[key] = client._unwrap_agtype(value)
                        except:
                            # If unwrapping fails, use raw value
                            unwrapped_row[key] = value
                    result_list.append(unwrapped_row)

            return CypherQueryResponse(
                success=True,
                results=result_list,
                rows_returned=len(result_list),
                namespace_used=namespace_used,
                warning=warning
            )

        except Exception as query_error:
            logger.error(f"Cypher query execution failed: {query_error}", exc_info=True)
            return CypherQueryResponse(
                success=False,
                results=[],
                rows_returned=0,
                namespace_used=namespace_used,
                error=str(query_error)
            )

    finally:
        client.close()
