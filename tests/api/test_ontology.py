"""
Ontology endpoints tests.

Tests for: kg ontology list, kg ontology info
Endpoints: GET /ontology/, GET /ontology/{name}
"""

import pytest
from fastapi.testclient import TestClient


@pytest.mark.api
@pytest.mark.integration
@pytest.mark.skip("Requires database connection - will implement when DB fixtures ready")
def test_ontology_list_empty_database(api_client):
    """Test that /ontology/ returns empty list for empty database"""
    response = api_client.get("/ontology/")

    assert response.status_code == 200
    data = response.json()
    assert "ontologies" in data
    assert isinstance(data["ontologies"], list)


@pytest.mark.api
@pytest.mark.integration
@pytest.mark.skip("Requires database connection - will implement when DB fixtures ready")
def test_ontology_list_response_structure(api_client):
    """Test that /ontology/ returns correct structure"""
    response = api_client.get("/ontology/")

    assert response.status_code == 200
    data = response.json()

    # Should have count and ontologies list
    assert "count" in data
    assert "ontologies" in data
    assert isinstance(data["count"], int)
    assert isinstance(data["ontologies"], list)


@pytest.mark.api
@pytest.mark.integration
@pytest.mark.skip("Requires database connection - will implement when DB fixtures ready")
def test_ontology_info_not_found(api_client):
    """Test that /ontology/{name} returns 404 for non-existent ontology"""
    response = api_client.get("/ontology/NonExistentOntology")

    assert response.status_code == 404


@pytest.mark.api
@pytest.mark.integration
@pytest.mark.skip("Requires database connection - will implement when DB fixtures ready")
def test_ontology_info_response_structure(api_client):
    """Test that /ontology/{name} returns correct structure (when ontology exists)"""
    # This test would require creating an ontology first
    # Will implement when we have database fixtures
    pass


# Placeholder for future tests when we have database fixtures
@pytest.mark.api
@pytest.mark.integration
@pytest.mark.skip("Requires test data setup - will implement with DB fixtures")
def test_ontology_with_test_data(api_client):
    """
    Test full ontology workflow with test data.

    When DB fixtures are ready:
    1. Create test ontology via ingestion
    2. List ontologies (should find our test ontology)
    3. Get ontology info (should return stats)
    4. Delete ontology
    5. Verify deletion
    """
    pass
