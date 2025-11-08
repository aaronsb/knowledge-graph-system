"""
Dynamic RBAC Permission Checker (ADR-028)

Implements fine-grained, scoped permission checking with:
- Global permissions
- Instance-scoped permissions
- Filter-scoped permissions
- Role inheritance
- Explicit denies
"""

from typing import Optional, List, Dict, Any
import psycopg2
from psycopg2.extras import RealDictCursor


class PermissionChecker:
    """
    Dynamic permission checking with multiple scoping levels.

    Permission precedence (checked in order):
    1. Explicit DENY (highest priority - always blocks)
    2. Instance-scoped permissions (most specific)
    3. Filter-scoped permissions
    4. Global permissions
    5. Inherited permissions from parent roles
    """

    def __init__(self, db_connection):
        """
        Initialize permission checker.

        Args:
            db_connection: PostgreSQL connection (with RealDictCursor)
        """
        self.conn = db_connection

    def can_user(
        self,
        user_id: int,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        resource_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Check if user has permission to perform action on resource.

        Args:
            user_id: User ID to check
            action: Action to perform (read, write, delete, approve, etc.)
            resource_type: Type of resource (concepts, vocabulary, jobs, etc.)
            resource_id: Optional specific resource instance ID
            resource_context: Optional context for filter-scoped permissions
                             (e.g., {"ontology": "memory:user_123", "status": "active"})

        Returns:
            True if user has permission, False otherwise

        Examples:
            >>> checker.can_user(1, "read", "concepts")  # Global check
            True

            >>> checker.can_user(1, "write", "concepts",
            ...                  resource_id="concept_123")  # Instance check
            True

            >>> checker.can_user(1, "write", "concepts",
            ...                  resource_context={"ontology": "memory:user_1"})  # Filter check
            True
        """
        # Get user's roles (including expired check)
        roles = self._get_user_roles(user_id, resource_id)

        if not roles:
            return False

        # 1. Check for explicit DENY first (highest priority)
        if self._has_explicit_deny(roles, resource_type, action, resource_id, resource_context):
            return False

        # 2. Check instance-scoped permissions (most specific)
        if resource_id and self._has_instance_permission(roles, resource_type, action, resource_id):
            return True

        # 3. Check filter-scoped permissions
        if resource_context and self._has_filter_permission(roles, resource_type, action, resource_context):
            return True

        # 4. Check global permissions
        if self._has_global_permission(roles, resource_type, action):
            return True

        # 5. Check inherited permissions from parent roles
        if self._check_inherited_permissions(roles, resource_type, action, resource_id, resource_context):
            return True

        return False

    def _get_user_roles(self, user_id: int, resource_id: Optional[str] = None) -> List[Dict]:
        """
        Get all active roles for a user.

        Returns roles that:
        - Are not expired
        - Match resource scope if provided
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT
                    ur.role_name,
                    ur.scope_type,
                    ur.scope_id,
                    r.parent_role
                FROM kg_auth.user_roles ur
                JOIN kg_auth.roles r ON ur.role_name = r.role_name
                WHERE ur.user_id = %s
                  AND r.is_active = TRUE
                  AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
            """, (user_id,))

            return cur.fetchall()

    def _has_explicit_deny(
        self,
        roles: List[Dict],
        resource_type: str,
        action: str,
        resource_id: Optional[str],
        resource_context: Optional[Dict]
    ) -> bool:
        """Check if any role has an explicit DENY for this permission."""
        role_names = [r['role_name'] for r in roles]

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 1
                FROM kg_auth.role_permissions
                WHERE role_name = ANY(%s)
                  AND resource_type = %s
                  AND action = %s
                  AND granted = FALSE
                LIMIT 1
            """, (role_names, resource_type, action))

            return cur.fetchone() is not None

    def _has_instance_permission(
        self,
        roles: List[Dict],
        resource_type: str,
        action: str,
        resource_id: str
    ) -> bool:
        """Check instance-scoped permissions."""
        role_names = [r['role_name'] for r in roles]

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 1
                FROM kg_auth.role_permissions
                WHERE role_name = ANY(%s)
                  AND resource_type = %s
                  AND action = %s
                  AND scope_type = 'instance'
                  AND scope_id = %s
                  AND granted = TRUE
                LIMIT 1
            """, (role_names, resource_type, action, resource_id))

            return cur.fetchone() is not None

    def _has_filter_permission(
        self,
        roles: List[Dict],
        resource_type: str,
        action: str,
        resource_context: Dict
    ) -> bool:
        """
        Check filter-scoped permissions.

        Matches if ALL filter conditions are met by the resource context.
        """
        role_names = [r['role_name'] for r in roles]

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get all filter-scoped permissions for this action
            cur.execute("""
                SELECT scope_filter
                FROM kg_auth.role_permissions
                WHERE role_name = ANY(%s)
                  AND resource_type = %s
                  AND action = %s
                  AND scope_type = 'filter'
                  AND scope_filter IS NOT NULL
                  AND granted = TRUE
            """, (role_names, resource_type, action))

            for row in cur.fetchall():
                scope_filter = row['scope_filter']

                # Check if resource context matches all filter conditions
                if self._matches_filter(resource_context, scope_filter):
                    return True

        return False

    def _matches_filter(self, resource_context: Dict, scope_filter: Dict) -> bool:
        """
        Check if resource context matches filter conditions.

        Supports:
        - Exact match: {"ontology": "memory:user_123"}
        - Wildcard: {"ontology": "memory:*"}
        - Multiple conditions (AND): {"ontology": "memory:*", "status": "active"}
        """
        for key, filter_value in scope_filter.items():
            if key not in resource_context:
                return False

            context_value = resource_context[key]

            # Handle wildcard matching
            if isinstance(filter_value, str) and '*' in filter_value:
                # Convert wildcard to regex-like pattern
                pattern = filter_value.replace('*', '')
                if not str(context_value).startswith(pattern):
                    return False
            elif filter_value == "$user_id":
                # Special case: $user_id placeholder (handled by caller)
                continue
            elif context_value != filter_value:
                return False

        return True

    def _has_global_permission(
        self,
        roles: List[Dict],
        resource_type: str,
        action: str
    ) -> bool:
        """Check global permissions."""
        role_names = [r['role_name'] for r in roles]

        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 1
                FROM kg_auth.role_permissions
                WHERE role_name = ANY(%s)
                  AND resource_type = %s
                  AND action = %s
                  AND scope_type = 'global'
                  AND granted = TRUE
                LIMIT 1
            """, (role_names, resource_type, action))

            return cur.fetchone() is not None

    def _check_inherited_permissions(
        self,
        roles: List[Dict],
        resource_type: str,
        action: str,
        resource_id: Optional[str],
        resource_context: Optional[Dict]
    ) -> bool:
        """
        Check permissions inherited from parent roles.

        Recursively checks parent roles up the hierarchy.
        """
        for role in roles:
            if role['parent_role']:
                # Get parent role info
                with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT role_name, parent_role
                        FROM kg_auth.roles
                        WHERE role_name = %s
                          AND is_active = TRUE
                    """, (role['parent_role'],))

                    parent = cur.fetchone()
                    if parent:
                        parent_roles = [parent]

                        # Check permissions with parent role
                        if (self._has_global_permission(parent_roles, resource_type, action) or
                            (resource_id and self._has_instance_permission(parent_roles, resource_type, action, resource_id)) or
                            (resource_context and self._has_filter_permission(parent_roles, resource_type, action, resource_context))):
                            return True

                        # Recursively check parent's parent
                        if self._check_inherited_permissions(parent_roles, resource_type, action, resource_id, resource_context):
                            return True

        return False

    def get_user_permissions(self, user_id: int) -> List[Dict]:
        """
        Get all effective permissions for a user.

        Returns:
            List of permissions with role_name, resource_type, action, scope details
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT DISTINCT
                    rp.role_name,
                    rp.resource_type,
                    rp.action,
                    rp.scope_type,
                    rp.scope_id,
                    rp.scope_filter,
                    rp.granted
                FROM kg_auth.user_roles ur
                JOIN kg_auth.role_permissions rp ON ur.role_name = rp.role_name
                WHERE ur.user_id = %s
                  AND (ur.expires_at IS NULL OR ur.expires_at > NOW())
                ORDER BY rp.resource_type, rp.action, rp.scope_type
            """, (user_id,))

            return cur.fetchall()

    def get_resource_actions(self, resource_type: str) -> List[str]:
        """Get available actions for a resource type."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT available_actions
                FROM kg_auth.resources
                WHERE resource_type = %s
            """, (resource_type,))

            row = cur.fetchone()
            return row['available_actions'] if row else []
