#!/usr/bin/env python3
"""
Permission System Test Script (ADR-074)

Tests the RBAC permission system including:
- Direct role permissions
- Role inheritance (parent_role)
- Permission denials

Usage:
    docker exec kg-api-dev python /workspace/scripts/development/test/test_permissions.py
    docker exec kg-api-dev python /workspace/scripts/development/test/test_permissions.py --user admin
    docker exec kg-api-dev python /workspace/scripts/development/test/test_permissions.py --verbose
"""

import argparse
import sys
from typing import List, Tuple

from api.api.dependencies.auth import get_db_connection, check_permission
from api.api.models.auth import UserInDB


def get_user(username: str) -> UserInDB:
    """Retrieve user from database."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT id, username, password_hash, primary_role, created_at, last_login, disabled
            FROM kg_auth.users WHERE username = %s
        ''', (username,))
        row = cur.fetchone()
        if not row:
            print(f"Error: User '{username}' not found")
            sys.exit(1)
        return UserInDB(
            id=row[0],
            username=row[1],
            password_hash=row[2],
            role=row[3],
            created_at=row[4],
            last_login=row[5],
            disabled=row[6]
        )
    finally:
        conn.close()


def get_role_hierarchy() -> dict:
    """Get role inheritance hierarchy."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT role_name, parent_role
            FROM kg_auth.roles
            WHERE is_active = TRUE
        ''')
        return {row[0]: row[1] for row in cur.fetchall()}
    finally:
        conn.close()


def get_role_permissions(role_name: str) -> List[Tuple[str, str]]:
    """Get all permissions for a role."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            SELECT resource_type, action
            FROM kg_auth.role_permissions
            WHERE role_name = %s AND granted = TRUE
            ORDER BY resource_type, action
        ''', (role_name,))
        return [(row[0], row[1]) for row in cur.fetchall()]
    finally:
        conn.close()


# Test cases: (resource, action, description, expected_for_roles)
# expected_for_roles is a dict mapping role -> expected result (True/False/None for skip)
PERMISSION_TESTS = [
    # Platform admin only
    ('api_keys', 'write', 'API keys write', {'platform_admin': True, 'admin': False, 'curator': False, 'contributor': False}),
    ('api_keys', 'delete', 'API keys delete', {'platform_admin': True, 'admin': False, 'curator': False, 'contributor': False}),
    ('backups', 'create', 'Backups create', {'platform_admin': True, 'admin': False, 'curator': False, 'contributor': False}),
    ('backups', 'restore', 'Backups restore', {'platform_admin': True, 'admin': False, 'curator': False, 'contributor': False}),
    ('rbac', 'write', 'RBAC write', {'platform_admin': True, 'admin': False, 'curator': False, 'contributor': False}),
    ('rbac', 'create', 'RBAC create', {'platform_admin': True, 'admin': False, 'curator': False, 'contributor': False}),
    ('rbac', 'delete', 'RBAC delete', {'platform_admin': True, 'admin': False, 'curator': False, 'contributor': False}),

    # Admin and above
    ('admin', 'status', 'Admin status', {'platform_admin': True, 'admin': True, 'curator': False, 'contributor': False}),
    ('users', 'read', 'Users read', {'platform_admin': True, 'admin': True, 'curator': False, 'contributor': False}),
    ('users', 'write', 'Users write', {'platform_admin': True, 'admin': True, 'curator': False, 'contributor': False}),
    ('users', 'delete', 'Users delete', {'platform_admin': True, 'admin': True, 'curator': False, 'contributor': False}),
    ('oauth_clients', 'read', 'OAuth clients read', {'platform_admin': True, 'admin': True, 'curator': False, 'contributor': False}),
    ('oauth_clients', 'create', 'OAuth clients create', {'platform_admin': True, 'admin': True, 'curator': False, 'contributor': False}),
    ('rbac', 'read', 'RBAC read', {'platform_admin': True, 'admin': True, 'curator': False, 'contributor': False}),
    ('api_keys', 'read', 'API keys read', {'platform_admin': True, 'admin': True, 'curator': False, 'contributor': False}),
    ('backups', 'read', 'Backups read', {'platform_admin': True, 'admin': True, 'curator': False, 'contributor': False}),

    # Curator and above (admin inherits via parent_role if set)
    ('vocabulary', 'write', 'Vocabulary write', {'platform_admin': True, 'admin': True, 'curator': True, 'contributor': False}),
    ('ontologies', 'create', 'Ontologies create', {'platform_admin': True, 'admin': True, 'curator': True, 'contributor': False}),

    # Contributor and above
    ('graph', 'read', 'Graph read', {'platform_admin': True, 'admin': True, 'curator': True, 'contributor': True}),
    ('ingest', 'create', 'Ingest create', {'platform_admin': True, 'admin': True, 'curator': True, 'contributor': True}),
    ('sources', 'read', 'Sources read', {'platform_admin': True, 'admin': True, 'curator': True, 'contributor': True}),
    ('vocabulary', 'read', 'Vocabulary read', {'platform_admin': True, 'admin': True, 'curator': True, 'contributor': True}),
    ('ontologies', 'read', 'Ontologies read', {'platform_admin': True, 'admin': True, 'curator': True, 'contributor': True}),
]


def test_user_permissions(user: UserInDB, verbose: bool = False) -> Tuple[int, int]:
    """Test permissions for a specific user."""
    passed = 0
    failed = 0

    print(f"\nTesting permissions for user: {user.username} (role: {user.role})")
    print("=" * 60)

    for resource, action, desc, expected_by_role in PERMISSION_TESTS:
        expected = expected_by_role.get(user.role)
        if expected is None:
            continue

        result = check_permission(user, resource, action)

        if result == expected:
            status = '✓'
            passed += 1
        else:
            status = '✗'
            failed += 1

        expectation = "should HAVE" if expected else "should NOT have"

        if verbose or result != expected:
            print(f"  {status} {resource}:{action} - {expectation}")
            if result != expected:
                print(f"      FAILED: got {result}, expected {expected}")

    return passed, failed


def test_all_roles(verbose: bool = False):
    """Test permissions for all standard roles."""
    # Create mock users for each role
    roles = ['platform_admin', 'admin', 'curator', 'contributor']

    total_passed = 0
    total_failed = 0

    for role in roles:
        # Check if a user with this role exists, or create a mock
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                SELECT id, username, password_hash, primary_role, created_at, last_login, disabled
                FROM kg_auth.users WHERE primary_role = %s LIMIT 1
            ''', (role,))
            row = cur.fetchone()

            if row:
                user = UserInDB(
                    id=row[0],
                    username=row[1],
                    password_hash=row[2],
                    role=row[3],
                    created_at=row[4],
                    last_login=row[5],
                    disabled=row[6]
                )
            else:
                # Create a mock user for testing (won't be saved)
                from datetime import datetime
                user = UserInDB(
                    id=99999,
                    username=f"test_{role}",
                    password_hash="mock",
                    role=role,
                    created_at=datetime.now(),
                    last_login=None,
                    disabled=False
                )
                print(f"\n(Using mock user for role: {role})")
        finally:
            conn.close()

        passed, failed = test_user_permissions(user, verbose)
        total_passed += passed
        total_failed += failed

    return total_passed, total_failed


def show_role_info():
    """Display role hierarchy and permissions."""
    print("\n" + "=" * 60)
    print("ROLE HIERARCHY")
    print("=" * 60)

    hierarchy = get_role_hierarchy()
    for role, parent in sorted(hierarchy.items()):
        parent_str = f" -> inherits from {parent}" if parent else ""
        print(f"  {role}{parent_str}")

    print("\n" + "=" * 60)
    print("ROLE PERMISSIONS (direct grants only)")
    print("=" * 60)

    for role in sorted(hierarchy.keys()):
        permissions = get_role_permissions(role)
        print(f"\n  {role}:")
        if permissions:
            for resource, action in permissions:
                print(f"    - {resource}:{action}")
        else:
            print("    (no direct permissions)")


def main():
    parser = argparse.ArgumentParser(description='Test RBAC permission system')
    parser.add_argument('--user', '-u', help='Test specific user by username')
    parser.add_argument('--verbose', '-v', action='store_true', help='Show all test results')
    parser.add_argument('--info', '-i', action='store_true', help='Show role hierarchy and permissions')
    parser.add_argument('--all', '-a', action='store_true', help='Test all roles')
    args = parser.parse_args()

    if args.info:
        show_role_info()
        return

    if args.all:
        passed, failed = test_all_roles(args.verbose)
    elif args.user:
        user = get_user(args.user)
        passed, failed = test_user_permissions(user, args.verbose)
    else:
        # Default: test admin user
        user = get_user('admin')
        passed, failed = test_user_permissions(user, args.verbose)

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    if failed > 0:
        print("\nNote: Some failures may be expected if role inheritance is not configured.")
        print("Check that roles have correct parent_role values in kg_auth.roles table.")
        sys.exit(1)


if __name__ == '__main__':
    main()
