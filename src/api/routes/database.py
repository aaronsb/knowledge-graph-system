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

from ..models.database import (
    DatabaseStatsResponse,
    DatabaseInfoResponse,
    DatabaseHealthResponse
)
from src.api.lib.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/database", tags=["database"])


def get_neo4j_client() -> Neo4jClient:
    """Get Neo4j client instance"""
    return Neo4jClient()


@router.get("/stats", response_model=DatabaseStatsResponse)
async def get_database_stats():
    """
    Get database statistics including node and relationship counts.

    Returns:
        DatabaseStatsResponse with node counts by type and relationship breakdown

    Example:
        GET /database/stats
    """
    client = get_neo4j_client()
    try:
        with client.driver.session() as session:
            # Node counts by label
            stats = {}
            for label in ['Concept', 'Source', 'Instance']:
                result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                stats[label] = result.single()['count']

            # Total relationship count
            rel_result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            total_relationships = rel_result.single()['count']

            # Concept relationship breakdown by type
            rel_types = session.run("""
                MATCH (c1:Concept)-[r]->(c2:Concept)
                RETURN type(r) as rel_type, count(*) as count
                ORDER BY count DESC
            """)

            rel_type_list = [
                {"rel_type": record['rel_type'], "count": record['count']}
                for record in rel_types
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
async def get_database_info():
    """
    Get database connection information.

    Returns:
        DatabaseInfoResponse with connection details and version info

    Example:
        GET /database/info
    """
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")

    info = {
        "uri": neo4j_uri,
        "user": neo4j_user,
        "connected": False,
        "version": None,
        "edition": None,
        "error": None
    }

    try:
        client = get_neo4j_client()
        try:
            with client.driver.session() as session:
                result = session.run("CALL dbms.components() YIELD name, versions, edition")
                component = result.single()
                if component:
                    info["connected"] = True
                    info["version"] = component["versions"][0] if component["versions"] else None
                    info["edition"] = component["edition"]
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
    - Index availability
    - Constraint availability

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
        client = get_neo4j_client()
        try:
            with client.driver.session() as session:
                # Check basic connectivity
                result = session.run("RETURN 1 as ping")
                if result.single()["ping"] == 1:
                    health["responsive"] = True
                    health["checks"]["connectivity"] = "ok"

                # Check indexes
                indexes = session.run("SHOW INDEXES")
                index_count = len(list(indexes))
                health["checks"]["indexes"] = {
                    "count": index_count,
                    "status": "ok" if index_count > 0 else "warning"
                }

                # Check constraints
                constraints = session.run("SHOW CONSTRAINTS")
                constraint_count = len(list(constraints))
                health["checks"]["constraints"] = {
                    "count": constraint_count,
                    "status": "ok" if constraint_count > 0 else "warning"
                }

                # Overall status
                if health["responsive"] and index_count > 0:
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
