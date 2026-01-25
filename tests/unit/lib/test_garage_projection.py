"""
Garage projection storage tests (ADR-079).

Tests for projection storage operations in GarageClient:
- store_projection
- get_projection
- get_projection_history
- delete_projection
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import json


# Sample projection dataset for testing
@pytest.fixture
def sample_projection():
    """Provide sample projection dataset."""
    return {
        "ontology": "TestOntology",
        "changelist_id": "c1234",
        "algorithm": "tsne",
        "computed_at": "2025-12-13T22:00:00Z",
        "parameters": {
            "n_components": 3,
            "perplexity": 30,
            "metric": "cosine"
        },
        "statistics": {
            "concept_count": 100,
            "computation_time_ms": 1500,
            "embedding_dims": 768
        },
        "concepts": [
            {
                "concept_id": "c-abc123",
                "label": "test concept",
                "x": 1.0,
                "y": 2.0,
                "z": 3.0,
                "grounding_strength": 0.5
            }
        ]
    }


@pytest.fixture
def mock_s3_client():
    """Provide mock S3 client."""
    return MagicMock()


@pytest.fixture
def mock_garage_client(mock_s3_client):
    """Provide GarageClient with mocked S3 client."""
    with patch('api.app.lib.garage_client._get_garage_credentials') as mock_creds:
        mock_creds.return_value = ('test_access_key', 'test_secret_key')

        with patch('boto3.client') as mock_boto:
            mock_boto.return_value = mock_s3_client

            from api.app.lib.garage_client import GarageClient
            client = GarageClient(
                endpoint="http://test:3900",
                bucket_name="test-bucket"
            )
            client.client = mock_s3_client
            return client


class TestBuildProjectionKey:
    """Tests for _build_projection_key method."""

    def test_latest_key_format(self, mock_garage_client):
        """Test that latest key is formatted correctly."""
        key = mock_garage_client._build_projection_key("TestOntology", "concepts")
        assert key == "projections/TestOntology/concepts/latest.json"

    def test_timestamped_key_format(self, mock_garage_client):
        """Test that timestamped key is formatted correctly."""
        key = mock_garage_client._build_projection_key(
            "TestOntology",
            "concepts",
            "2025-12-13T22:00:00Z"
        )
        assert key == "projections/TestOntology/concepts/2025-12-13T22:00:00Z.json"

    def test_sanitizes_ontology_name(self, mock_garage_client):
        """Test that ontology names with spaces/slashes are sanitized."""
        key = mock_garage_client._build_projection_key("Test Ontology/Sub", "concepts")
        assert key == "projections/Test_Ontology_Sub/concepts/latest.json"

    def test_different_embedding_sources(self, mock_garage_client):
        """Test different embedding source types."""
        for source in ["concepts", "sources", "vocabulary", "combined"]:
            key = mock_garage_client._build_projection_key("Test", source)
            assert source in key


class TestStoreProjection:
    """Tests for store_projection method."""

    def test_stores_latest_and_historical(self, mock_garage_client, sample_projection, mock_s3_client):
        """Test that both latest and historical snapshots are stored."""
        mock_garage_client.store_projection(
            ontology="TestOntology",
            embedding_source="concepts",
            projection_data=sample_projection,
            keep_history=True
        )

        # Should call put_object twice (latest + historical)
        assert mock_s3_client.put_object.call_count == 2

        # Verify latest was stored
        calls = mock_s3_client.put_object.call_args_list
        keys = [call.kwargs.get('Key') or call[1].get('Key') for call in calls]

        assert any('latest.json' in k for k in keys)

    def test_stores_only_latest_when_history_disabled(self, mock_garage_client, sample_projection, mock_s3_client):
        """Test that only latest is stored when keep_history=False."""
        mock_garage_client.store_projection(
            ontology="TestOntology",
            embedding_source="concepts",
            projection_data=sample_projection,
            keep_history=False
        )

        # Should call put_object once (latest only)
        assert mock_s3_client.put_object.call_count == 1

    def test_returns_storage_key(self, mock_garage_client, sample_projection, mock_s3_client):
        """Test that storage key is returned."""
        key = mock_garage_client.store_projection(
            ontology="TestOntology",
            embedding_source="concepts",
            projection_data=sample_projection
        )

        assert key is not None
        assert "TestOntology" in key
        assert "latest.json" in key

    def test_content_type_is_json(self, mock_garage_client, sample_projection, mock_s3_client):
        """Test that content type is set to application/json."""
        mock_garage_client.store_projection(
            ontology="TestOntology",
            embedding_source="concepts",
            projection_data=sample_projection
        )

        call_kwargs = mock_s3_client.put_object.call_args_list[0].kwargs
        assert call_kwargs.get('ContentType') == 'application/json'


class TestGetProjection:
    """Tests for get_projection method."""

    def test_returns_projection_data(self, mock_garage_client, sample_projection, mock_s3_client):
        """Test that projection data is returned correctly."""
        # Mock get_object response
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(sample_projection).encode('utf-8')
        mock_s3_client.get_object.return_value = {'Body': mock_body}

        result = mock_garage_client.get_projection("TestOntology", "concepts")

        assert result is not None
        assert result["ontology"] == "TestOntology"
        assert result["algorithm"] == "tsne"
        assert len(result["concepts"]) == 1

    def test_returns_none_when_not_found(self, mock_garage_client, mock_s3_client):
        """Test that None is returned when projection doesn't exist."""
        from botocore.exceptions import ClientError

        mock_s3_client.get_object.side_effect = ClientError(
            {'Error': {'Code': '404', 'Message': 'Not Found'}},
            'GetObject'
        )

        result = mock_garage_client.get_projection("NonExistent", "concepts")

        assert result is None

    def test_uses_correct_key(self, mock_garage_client, sample_projection, mock_s3_client):
        """Test that correct S3 key is used."""
        mock_body = MagicMock()
        mock_body.read.return_value = json.dumps(sample_projection).encode('utf-8')
        mock_s3_client.get_object.return_value = {'Body': mock_body}

        mock_garage_client.get_projection("TestOntology", "concepts")

        call_kwargs = mock_s3_client.get_object.call_args.kwargs
        assert "projections/TestOntology/concepts/latest.json" == call_kwargs['Key']


class TestGetProjectionHistory:
    """Tests for get_projection_history method."""

    def test_returns_historical_snapshots(self, mock_garage_client, mock_s3_client):
        """Test that historical snapshots are listed."""
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': 'projections/Test/concepts/2025-12-13T22:00:00Z.json', 'Size': 1000, 'LastModified': datetime.now()},
                {'Key': 'projections/Test/concepts/2025-12-13T23:00:00Z.json', 'Size': 1100, 'LastModified': datetime.now()},
                {'Key': 'projections/Test/concepts/latest.json', 'Size': 1100, 'LastModified': datetime.now()},
            ]
        }

        history = mock_garage_client.get_projection_history("Test", "concepts", limit=10)

        # Should exclude latest.json
        assert len(history) == 2
        assert all('latest' not in h['key'] for h in history)

    def test_respects_limit(self, mock_garage_client, mock_s3_client):
        """Test that limit parameter is respected."""
        mock_s3_client.list_objects_v2.return_value = {
            'Contents': [
                {'Key': f'projections/Test/concepts/2025-12-{i:02d}T00:00:00Z.json', 'Size': 1000, 'LastModified': datetime.now()}
                for i in range(1, 11)
            ]
        }

        history = mock_garage_client.get_projection_history("Test", "concepts", limit=5)

        assert len(history) <= 5

    def test_returns_empty_list_when_no_history(self, mock_garage_client, mock_s3_client):
        """Test that empty list is returned when no history exists."""
        mock_s3_client.list_objects_v2.return_value = {}

        history = mock_garage_client.get_projection_history("Test", "concepts")

        assert history == []


class TestDeleteProjection:
    """Tests for delete_projection method."""

    def test_deletes_latest_projection(self, mock_garage_client, mock_s3_client):
        """Test that latest projection is deleted."""
        mock_s3_client.delete_object.return_value = {}

        result = mock_garage_client.delete_projection("Test", "concepts")

        assert result is True
        mock_s3_client.delete_object.assert_called_once()

        call_kwargs = mock_s3_client.delete_object.call_args.kwargs
        assert "latest.json" in call_kwargs['Key']

    def test_returns_false_on_error(self, mock_garage_client, mock_s3_client):
        """Test that False is returned on deletion error."""
        from botocore.exceptions import ClientError

        mock_s3_client.delete_object.side_effect = ClientError(
            {'Error': {'Code': '500', 'Message': 'Internal Error'}},
            'DeleteObject'
        )

        result = mock_garage_client.delete_projection("Test", "concepts")

        assert result is False
