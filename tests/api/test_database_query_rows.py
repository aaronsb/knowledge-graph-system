"""/database/query returns rows as the execution path parsed them (#561).

_execute_cypher already runs every value through _parse_agtype; the route
must not parse again, or a string such as "123" would become the int 123.
@verified 41de99362
"""
from unittest.mock import MagicMock, patch

import pytest

from api.app.models.database import CypherQueryRequest
from api.app.routes import database


@pytest.mark.unit
def test_query_rows_pass_through_without_reparsing():
    client = MagicMock()
    client._execute_cypher.return_value = [{"code": "123", "n": {"id": 1}}]
    with patch.object(database, "get_age_client", return_value=client):
        resp = database.execute_cypher_query(
            CypherQueryRequest(query="RETURN '123' AS code", namespace=None),
            current_user=MagicMock(),
        )
    assert resp.success is True
    assert resp.results == [{"code": "123", "n": {"id": 1}}]
