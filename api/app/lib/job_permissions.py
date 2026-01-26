"""
Job-Specific Permission Checking

Extends RBAC permission checking with job ownership and system job awareness.
Used by job routes to enforce per-job access control based on role permissions.

Permission scopes:
- own: User's own jobs (user_id matches)
- global: All user-created jobs
- system: System/scheduled jobs (is_system_job=true or created_by starts with 'system:')
"""

from typing import Dict, Optional, Any
from .permissions import PermissionChecker


class JobPermissionChecker:
    """
    Check job permissions with ownership and system job awareness.

    Uses the underlying RBAC PermissionChecker but adds job-specific
    context building for filter-scoped permission checks.
    """

    def __init__(self, permission_checker: PermissionChecker):
        """
        Initialize with a PermissionChecker instance.

        Args:
            permission_checker: RBAC permission checker with DB connection
        """
        self.checker = permission_checker

    def can_access_job(
        self,
        user_id: int,
        action: str,
        job: Dict[str, Any]
    ) -> bool:
        """
        Check if user can perform action on a specific job.

        Args:
            user_id: Current user's ID
            action: Action to perform ('read', 'cancel', 'delete')
            job: Job dict with at least 'user_id', optionally 'is_system_job', 'created_by'

        Returns:
            True if user has permission, False otherwise

        Examples:
            # User can always access their own jobs (if they have 'own' scope)
            >>> checker.can_access_job(user_id=1, action='read', job={'user_id': 1})
            True

            # User cannot access system jobs (unless platform_admin)
            >>> checker.can_access_job(user_id=1, action='delete', job={'is_system_job': True})
            False
        """
        job_owner_id = job.get('user_id')
        is_system_job = self._is_system_job(job)

        # For system jobs, check system job permissions
        if is_system_job:
            return self.checker.can_user(
                user_id=user_id,
                action=action,
                resource_type='jobs',
                resource_context={'is_system': True}
            )

        # For user jobs, check global permission first (covers all user jobs)
        if self.checker.can_user(user_id, action, 'jobs'):
            return True

        # Check filter-scoped permission for own jobs
        # Maps to scope_filter {"owner": "self"} in role_permissions table
        return self.checker.can_user(
            user_id=user_id,
            action=action,
            resource_type='jobs',
            resource_context={'owner': 'self' if job_owner_id == user_id else 'other'}
        )

    def get_job_list_filter(self, user_id: int) -> Dict[str, Any]:
        """
        Return filter conditions for listing jobs based on user's permissions.

        Used by list_jobs endpoint to filter jobs before returning.

        Args:
            user_id: Current user's ID

        Returns:
            Dict with filter conditions:
            - {} = no filter (can see everything including system jobs)
            - {'exclude_system': True} = can see user jobs, not system
            - {'user_id': int} = can only see own jobs

        Examples:
            # platform_admin sees everything
            >>> checker.get_job_list_filter(platform_admin_id)
            {}

            # admin sees user jobs but not system jobs
            >>> checker.get_job_list_filter(admin_id)
            {'exclude_system': True}

            # contributor sees only their own jobs
            >>> checker.get_job_list_filter(contributor_id)
            {'user_id': 123}
        """
        # Check if user has global read permission
        has_global_read = self.checker.can_user(user_id, 'read', 'jobs')

        if has_global_read:
            # Check system job access
            has_system_read = self.checker.can_user(
                user_id, 'read', 'jobs',
                resource_context={'is_system': True}
            )
            if has_system_read:
                return {}  # No filter - can see everything
            return {'exclude_system': True}  # Can see user jobs, not system

        # No global read - filter to own jobs only
        return {'user_id': user_id}

    def can_delete_in_bulk(
        self,
        user_id: int,
        include_system: bool = False
    ) -> bool:
        """
        Check if user can perform bulk delete operations.

        Args:
            user_id: Current user's ID
            include_system: Whether the bulk delete includes system jobs

        Returns:
            True if user has permission for bulk delete
        """
        # Need global delete permission for bulk delete
        has_global_delete = self.checker.can_user(user_id, 'delete', 'jobs')

        if not has_global_delete:
            return False

        if include_system:
            # Need system job delete permission
            return self.checker.can_user(
                user_id, 'delete', 'jobs',
                resource_context={'is_system': True}
            )

        return True

    def _is_system_job(self, job: Dict[str, Any]) -> bool:
        """
        Determine if a job is a system job.

        System jobs are:
        - Jobs with is_system_job=True
        - Jobs created by 'system:*' (e.g., 'system:scheduler')
        """
        if job.get('is_system_job'):
            return True

        created_by = job.get('created_by', '')
        if isinstance(created_by, str) and created_by.startswith('system:'):
            return True

        return False


# Context manager for proper connection cleanup
class JobPermissionContext:
    """
    Context manager for job permission checking with automatic cleanup.

    Usage:
        with JobPermissionContext() as checker:
            if checker.can_access_job(user_id, 'read', job):
                ...
    """

    def __init__(self):
        self.conn = None
        self.checker = None

    def __enter__(self) -> JobPermissionChecker:
        from api.app.dependencies.auth import get_db_connection

        self.conn = get_db_connection()
        permission_checker = PermissionChecker(self.conn)
        self.checker = JobPermissionChecker(permission_checker)
        return self.checker

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
        return False
