"""
API Authentication Audit Regression Test (ADR-060)

Ensures the authentication audit tool correctly detects security patterns
and that no endpoints have unclear authentication requirements.

This test runs the actual audit script to verify:
- All endpoints are categorized (PUBLIC, USER, or ADMIN)
- Zero unclear/missing authentication endpoints
- Authentication patterns are correctly detected
"""

import pytest
import subprocess
import re


@pytest.mark.security
@pytest.mark.smoke
def test_api_auth_audit_no_unclear_endpoints():
    """Test authentication audit finds zero unclear endpoints"""
    # Run the actual audit script
    result = subprocess.run(
        ["./scripts/development/audit-api-auth.sh"],
        capture_output=True,
        text=True,
        timeout=30
    )

    # Audit should succeed
    assert result.returncode == 0, f"Audit script failed:\n{result.stderr}"

    output = result.stdout

    # Parse the output to find unclear endpoint count
    # Look for "⚠️  Unclear/Missing Auth |       N |"
    unclear_match = re.search(r'⚠️\s+Unclear/Missing Auth\s+\|\s+(\d+)\s+\|', output)

    assert unclear_match is not None, "Could not find unclear endpoint count in audit output"

    unclear_count = int(unclear_match.group(1))

    # Critical assertion: No endpoints should have unclear authentication
    assert unclear_count == 0, f"Found {unclear_count} endpoints with unclear authentication requirements"


@pytest.mark.security
def test_api_auth_audit_categorizes_all_endpoints():
    """Test authentication audit categorizes all endpoints"""
    result = subprocess.run(
        ["./scripts/development/audit-api-auth.sh"],
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result.returncode == 0, f"Audit script failed:\n{result.stderr}"

    output = result.stdout

    # Extract counts for each category
    public_match = re.search(r'Public \(no auth\)\s+\|\s+(\d+)\s+\|', output)
    user_match = re.search(r'Authenticated \(user\)\s+\|\s+(\d+)\s+\|', output)
    role_match = re.search(r'Role-based\s+\|\s+(\d+)\s+\|', output)
    total_match = re.search(r'Total endpoints:\s+(\d+)', output)

    # Verify all matches found
    assert public_match is not None, "Could not find PUBLIC endpoint count"
    assert user_match is not None, "Could not find USER endpoint count"
    assert role_match is not None, "Could not find ROLE endpoint count"
    assert total_match is not None, "Could not find total endpoint count"

    public_count = int(public_match.group(1))
    user_count = int(user_match.group(1))
    role_count = int(role_match.group(1))
    total_count = int(total_match.group(1))

    # All endpoints should be categorized
    categorized = public_count + user_count + role_count

    assert categorized == total_count, \
        f"Not all endpoints categorized: {categorized}/{total_count} " \
        f"(PUBLIC: {public_count}, USER: {user_count}, ROLE: {role_count})"


@pytest.mark.security
def test_api_auth_audit_has_public_endpoints():
    """Test audit detects PUBLIC endpoints (health, docs, OAuth)"""
    result = subprocess.run(
        ["./scripts/development/audit-api-auth.sh"],
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result.returncode == 0

    output = result.stdout

    public_match = re.search(r'Public \(no auth\)\s+\|\s+(\d+)\s+\|', output)
    assert public_match is not None

    public_count = int(public_match.group(1))

    # Should have multiple PUBLIC endpoints (health, docs, OAuth flows)
    assert public_count > 0, "No PUBLIC endpoints found - expected health, docs, OAuth endpoints"
    assert public_count >= 10, f"Expected at least 10 PUBLIC endpoints, found {public_count}"


@pytest.mark.security
def test_api_auth_audit_has_user_endpoints():
    """Test audit detects USER-level endpoints (queries, reads)"""
    result = subprocess.run(
        ["./scripts/development/audit-api-auth.sh"],
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result.returncode == 0

    output = result.stdout

    user_match = re.search(r'Authenticated \(user\)\s+\|\s+(\d+)\s+\|', output)
    assert user_match is not None

    user_count = int(user_match.group(1))

    # Should have USER endpoints (queries, database stats, ontology list, etc.)
    assert user_count > 0, "No USER endpoints found - expected query, read endpoints"
    assert user_count >= 10, f"Expected at least 10 USER endpoints, found {user_count}"


@pytest.mark.security
def test_api_auth_audit_has_admin_endpoints():
    """Test audit detects ADMIN endpoints (system admin, RBAC)"""
    result = subprocess.run(
        ["./scripts/development/audit-api-auth.sh"],
        capture_output=True,
        text=True,
        timeout=30
    )

    assert result.returncode == 0

    output = result.stdout

    role_match = re.search(r'Role-based\s+\|\s+(\d+)\s+\|', output)
    assert role_match is not None

    role_count = int(role_match.group(1))

    # Should have ADMIN endpoints (admin routes, RBAC, config)
    assert role_count > 0, "No ADMIN endpoints found - expected admin, RBAC endpoints"
    assert role_count >= 20, f"Expected at least 20 ADMIN endpoints, found {role_count}"


@pytest.mark.security
def test_api_auth_audit_script_exists():
    """Test authentication audit script exists and is executable"""
    import os

    script_path = "./scripts/development/audit-api-auth.sh"

    assert os.path.exists(script_path), f"Audit script not found at {script_path}"
    assert os.access(script_path, os.X_OK), f"Audit script is not executable: {script_path}"
