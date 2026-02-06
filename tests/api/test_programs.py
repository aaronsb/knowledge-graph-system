"""
Program notarization API tests (ADR-500 Phase 2b).

Tests for POST /programs, POST /programs/validate, GET /programs/{id}.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from datetime import datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def valid_program():
    """Return a minimal valid GraphProgram dict."""
    return {
        "version": 1,
        "statements": [
            {
                "op": "+",
                "operation": {
                    "type": "cypher",
                    "query": "MATCH (c:Concept) RETURN c LIMIT 10",
                },
            }
        ],
    }


def invalid_program_write():
    """Return a program with a write keyword (should be rejected)."""
    return {
        "version": 1,
        "statements": [
            {
                "op": "+",
                "operation": {
                    "type": "cypher",
                    "query": "MATCH (n) DETACH DELETE n",
                },
            }
        ],
    }


def mock_db_cursor(returning_row=None):
    """Create a mock connection + cursor that returns a given row."""
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = returning_row
    mock_cur.__enter__ = lambda self: self
    mock_cur.__exit__ = MagicMock(return_value=False)

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cur
    return mock_conn, mock_cur


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_auth_mocks(mock_oauth_validation, bypass_permission_check):
    """Auto-use mock OAuth validation and bypass RBAC for all tests."""
    pass


# ---------------------------------------------------------------------------
# POST /programs (notarize + store)
# ---------------------------------------------------------------------------

class TestCreateProgram:
    """Tests for POST /programs."""

    def test_requires_auth(self, api_client: TestClient):
        response = api_client.post(
            "/programs",
            json={"program": valid_program()},
        )
        assert response.status_code == 401

    def test_valid_program_stored(self, api_client: TestClient, auth_headers_user):
        now = datetime(2024, 1, 1)
        mock_conn, mock_cur = mock_db_cursor(
            returning_row=(42, now, now)
        )

        with patch(
            "api.app.routes.programs.get_db_connection",
            return_value=mock_conn,
        ):
            response = api_client.post(
                "/programs",
                json={"name": "My Program", "program": valid_program()},
                headers=auth_headers_user,
            )

        assert response.status_code == 201
        data = response.json()
        assert data["id"] == 42
        assert data["name"] == "My Program"
        assert data["valid"] is True
        assert data["program"]["version"] == 1
        assert len(data["program"]["statements"]) == 1

        # Verify INSERT was called with definition_type='program'
        call_args = mock_cur.execute.call_args
        assert "program" in call_args[0][0]  # SQL contains 'program'

    def test_invalid_program_rejected(self, api_client: TestClient, auth_headers_user):
        response = api_client.post(
            "/programs",
            json={"program": invalid_program_write()},
            headers=auth_headers_user,
        )
        assert response.status_code == 400
        data = response.json()
        assert "validation" in data["detail"]
        errors = data["detail"]["validation"]["errors"]
        rule_ids = [e["rule_id"] for e in errors]
        assert "V016" in rule_ids  # DETACH
        assert "V012" in rule_ids  # DELETE

    def test_malformed_program_rejected(self, api_client: TestClient, auth_headers_user):
        response = api_client.post(
            "/programs",
            json={"program": {"version": 1}},  # missing statements
            headers=auth_headers_user,
        )
        assert response.status_code == 400

    def test_name_from_metadata(self, api_client: TestClient, auth_headers_user):
        """When no submission name, falls back to metadata.name."""
        now = datetime(2024, 1, 1)
        mock_conn, mock_cur = mock_db_cursor(returning_row=(1, now, now))

        program = valid_program()
        program["metadata"] = {"name": "From Metadata"}

        with patch(
            "api.app.routes.programs.get_db_connection",
            return_value=mock_conn,
        ):
            response = api_client.post(
                "/programs",
                json={"program": program},
                headers=auth_headers_user,
            )

        assert response.status_code == 201
        assert response.json()["name"] == "From Metadata"

    def test_name_defaults_to_untitled(self, api_client: TestClient, auth_headers_user):
        now = datetime(2024, 1, 1)
        mock_conn, mock_cur = mock_db_cursor(returning_row=(1, now, now))

        with patch(
            "api.app.routes.programs.get_db_connection",
            return_value=mock_conn,
        ):
            response = api_client.post(
                "/programs",
                json={"program": valid_program()},
                headers=auth_headers_user,
            )

        assert response.status_code == 201
        assert response.json()["name"] == "Untitled program"


# ---------------------------------------------------------------------------
# POST /programs/validate (dry run)
# ---------------------------------------------------------------------------

class TestValidateProgram:
    """Tests for POST /programs/validate."""

    def test_requires_auth(self, api_client: TestClient):
        response = api_client.post(
            "/programs/validate",
            json={"program": valid_program()},
        )
        assert response.status_code == 401

    def test_valid_program_returns_valid(self, api_client: TestClient, auth_headers_user):
        response = api_client.post(
            "/programs/validate",
            json={"program": valid_program()},
            headers=auth_headers_user,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["valid"] is True
        assert data["errors"] == []

    def test_invalid_program_returns_errors(self, api_client: TestClient, auth_headers_user):
        response = api_client.post(
            "/programs/validate",
            json={"program": invalid_program_write()},
            headers=auth_headers_user,
        )
        assert response.status_code == 200  # validate always returns 200
        data = response.json()
        assert data["valid"] is False
        assert len(data["errors"]) > 0

    def test_no_storage_on_validate(self, api_client: TestClient, auth_headers_user):
        """Validate endpoint should never touch the database."""
        with patch(
            "api.app.routes.programs.get_db_connection",
        ) as mock_get_conn:
            response = api_client.post(
                "/programs/validate",
                json={"program": valid_program()},
                headers=auth_headers_user,
            )
            mock_get_conn.assert_not_called()

        assert response.status_code == 200


# ---------------------------------------------------------------------------
# GET /programs/{id}
# ---------------------------------------------------------------------------

class TestGetProgram:
    """Tests for GET /programs/{id}."""

    def test_requires_auth(self, api_client: TestClient):
        response = api_client.get("/programs/1")
        assert response.status_code == 401

    def test_retrieve_program(self, api_client: TestClient, auth_headers_user):
        now = datetime(2024, 1, 1)
        stored_program = valid_program()
        stored_program["metadata"] = {}
        mock_conn, mock_cur = mock_db_cursor(
            returning_row=(
                42,                     # id
                "My Program",           # name
                stored_program,         # definition (JSON)
                100,                    # owner_id (matches test user)
                now,                    # created_at
                now,                    # updated_at
            )
        )

        with patch(
            "api.app.routes.programs.get_db_connection",
            return_value=mock_conn,
        ):
            response = api_client.get(
                "/programs/42",
                headers=auth_headers_user,
            )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 42
        assert data["name"] == "My Program"
        assert data["program"]["version"] == 1

    def test_not_found(self, api_client: TestClient, auth_headers_user):
        mock_conn, mock_cur = mock_db_cursor(returning_row=None)

        with patch(
            "api.app.routes.programs.get_db_connection",
            return_value=mock_conn,
        ):
            response = api_client.get(
                "/programs/999",
                headers=auth_headers_user,
            )

        assert response.status_code == 404

    def test_wrong_owner_forbidden(self, api_client: TestClient, auth_headers_user):
        now = datetime(2024, 1, 1)
        mock_conn, mock_cur = mock_db_cursor(
            returning_row=(
                42,
                "Someone Else's Program",
                valid_program(),
                999,                    # different owner
                now,
                now,
            )
        )

        with patch(
            "api.app.routes.programs.get_db_connection",
            return_value=mock_conn,
        ):
            response = api_client.get(
                "/programs/42",
                headers=auth_headers_user,
            )

        assert response.status_code == 403

    def test_admin_can_access_any(self, api_client: TestClient, auth_headers_admin):
        now = datetime(2024, 1, 1)
        mock_conn, mock_cur = mock_db_cursor(
            returning_row=(
                42,
                "Someone's Program",
                valid_program(),
                999,                    # different owner
                now,
                now,
            )
        )

        with patch(
            "api.app.routes.programs.get_db_connection",
            return_value=mock_conn,
        ):
            response = api_client.get(
                "/programs/42",
                headers=auth_headers_admin,
            )

        assert response.status_code == 200
