"""
Audit logging service for graph mutations (ADR-089 Phase 1b).

Provides simple audit logging to kg_logs.audit_trail table for
tracking who did what, when, and with what outcome.
"""

import json
import logging
from typing import Optional, Dict, Any
from enum import Enum

logger = logging.getLogger(__name__)


class AuditAction(str, Enum):
    """Auditable actions for graph operations."""

    # Concept operations
    CREATE_CONCEPT = "create_concept"
    UPDATE_CONCEPT = "update_concept"
    DELETE_CONCEPT = "delete_concept"

    # Edge operations
    CREATE_EDGE = "create_edge"
    UPDATE_EDGE = "update_edge"
    DELETE_EDGE = "delete_edge"

    # Batch operations
    BATCH_CREATE = "batch_create"


class AuditOutcome(str, Enum):
    """Outcome of an audited action."""

    SUCCESS = "success"
    DENIED = "denied"
    ERROR = "error"


class AuditService:
    """
    Service for logging audit trail entries.

    Designed to work within existing database connections/transactions
    to ensure audit logs are committed with the operations they track.
    """

    @staticmethod
    def log(
        cursor,
        user_id: Optional[int],
        action: AuditAction,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> None:
        """
        Log an audit trail entry.

        Args:
            cursor: Database cursor (to use existing transaction)
            user_id: ID of user performing action (None for system actions)
            action: The action being performed
            resource_type: Type of resource (concepts, edges, batch)
            resource_id: Specific resource identifier
            details: Additional context as JSON
            outcome: Result of the action
            ip_address: Client IP address
            user_agent: Client user agent string
        """
        try:
            query = """
                INSERT INTO kg_logs.audit_trail
                (user_id, action, resource_type, resource_id, details, outcome, ip_address, user_agent)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """

            # Convert details dict to JSON string for JSONB column
            details_json = json.dumps(details) if details else None

            cursor.execute(query, (
                user_id,
                action.value if isinstance(action, AuditAction) else action,
                resource_type,
                resource_id,
                details_json,
                outcome.value if isinstance(outcome, AuditOutcome) else outcome,
                ip_address,
                user_agent
            ))

            logger.debug(
                f"Audit logged: {action} on {resource_type}/{resource_id} "
                f"by user {user_id} -> {outcome}"
            )

        except Exception as e:
            # Don't let audit logging failures break the main operation
            # Log the error but don't re-raise
            logger.error(f"Failed to log audit entry: {e}")


def log_audit(
    cursor,
    user_id: Optional[int],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    outcome: str = "success",
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> None:
    """
    Convenience function for audit logging (requires cursor).

    Wraps AuditService.log() for simpler usage.
    """
    AuditService.log(
        cursor=cursor,
        user_id=user_id,
        action=AuditAction(action) if action in [a.value for a in AuditAction] else action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
        outcome=AuditOutcome(outcome) if outcome in [o.value for o in AuditOutcome] else outcome,
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_audit_standalone(
    age_client,
    user_id: Optional[int],
    action: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    outcome: str = "success"
) -> None:
    """
    Standalone audit logging (gets its own connection).

    Use this for route-level audit logging where you don't have
    an existing database cursor. Note: This is NOT transactional
    with the main operation.

    Args:
        age_client: AGEClient instance for database access
        user_id: ID of user performing action
        action: The action being performed
        resource_type: Type of resource (concepts, edges)
        resource_id: Specific resource identifier
        details: Additional context as JSON
        outcome: Result of the action
    """
    conn = None
    try:
        conn = age_client.pool.getconn()
        with conn.cursor() as cur:
            log_audit(
                cursor=cur,
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                details=details,
                outcome=outcome
            )
        conn.commit()
    except Exception as e:
        logger.error(f"Standalone audit logging failed: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            age_client.pool.putconn(conn)
