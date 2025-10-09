"""
Backup streaming tests (ADR-015 Phase 2).

Tests for: kg admin backup (streaming)
Endpoint: POST /admin/backup
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient


# ============================================================================
# Unit Tests - Backup Streaming Module
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_backup_json_chunks_data():
    """Test that stream_backup_json yields data in chunks"""
    from src.api.lib.backup_streaming import stream_backup_json

    backup_data = {
        "version": "1.0",
        "type": "full_backup",
        "data": {"concepts": [], "sources": []}
    }

    chunks = []
    async for chunk in stream_backup_json(backup_data, chunk_size=10):
        chunks.append(chunk)
        assert isinstance(chunk, bytes)

    # Verify we got multiple chunks
    assert len(chunks) > 1

    # Verify chunks reassemble to original JSON
    full_data = b"".join(chunks)
    parsed = json.loads(full_data.decode('utf-8'))
    assert parsed == backup_data


@pytest.mark.unit
@pytest.mark.asyncio
async def test_stream_backup_json_respects_chunk_size():
    """Test that chunks are properly sized"""
    from src.api.lib.backup_streaming import stream_backup_json

    backup_data = {"data": "x" * 100}  # Create data larger than chunk size
    chunk_size = 20

    chunks = []
    async for chunk in stream_backup_json(backup_data, chunk_size=chunk_size):
        chunks.append(chunk)
        # Each chunk (except possibly last) should be <= chunk_size
        assert len(chunk) <= chunk_size

    # Verify last chunk might be smaller
    assert len(chunks[-1]) <= chunk_size


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_backup_stream_full_backup():
    """Test creating full backup stream"""
    from src.api.lib.backup_streaming import create_backup_stream

    mock_client = Mock()
    mock_backup_data = {
        "version": "1.0",
        "type": "full_backup",
        "timestamp": "2025-10-09T10:00:00",
        "data": {"concepts": [], "sources": [], "instances": [], "relationships": []},
        "statistics": {"concepts": 0, "sources": 0, "instances": 0, "relationships": 0}
    }

    with patch('src.api.lib.backup_streaming.DataExporter') as mock_exporter, \
         patch('src.api.lib.backup_streaming.check_backup_data') as mock_check:

        mock_exporter.export_full_backup.return_value = mock_backup_data

        # Mock successful validation
        mock_integrity = Mock()
        mock_integrity.valid = True
        mock_integrity.statistics = mock_backup_data["statistics"]
        mock_integrity.warnings = []
        mock_check.return_value = mock_integrity

        stream, filename = await create_backup_stream(
            client=mock_client,
            backup_type="full"
        )

        # Verify filename format
        assert filename.startswith("full_backup_")
        assert filename.endswith(".json")

        # Verify stream is async generator
        chunks = []
        async for chunk in stream:
            chunks.append(chunk)
        assert len(chunks) > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_backup_stream_ontology_backup():
    """Test creating ontology-specific backup stream"""
    from src.api.lib.backup_streaming import create_backup_stream

    mock_client = Mock()
    mock_backup_data = {
        "version": "1.0",
        "type": "ontology_backup",
        "ontology": "Test Ontology",
        "timestamp": "2025-10-09T10:00:00",
        "data": {"concepts": [], "sources": [], "instances": [], "relationships": []},
        "statistics": {"concepts": 0, "sources": 0, "instances": 0, "relationships": 0}
    }

    with patch('src.api.lib.backup_streaming.DataExporter') as mock_exporter, \
         patch('src.api.lib.backup_streaming.check_backup_data') as mock_check:

        mock_exporter.export_ontology_backup.return_value = mock_backup_data

        # Mock successful validation
        mock_integrity = Mock()
        mock_integrity.valid = True
        mock_integrity.statistics = mock_backup_data["statistics"]
        mock_integrity.warnings = []
        mock_check.return_value = mock_integrity

        stream, filename = await create_backup_stream(
            client=mock_client,
            backup_type="ontology",
            ontology_name="Test Ontology"
        )

        # Verify filename format (sanitized ontology name)
        assert "test_ontology" in filename
        assert filename.endswith(".json")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_backup_stream_missing_ontology_name():
    """Test that ontology backup requires ontology_name"""
    from src.api.lib.backup_streaming import create_backup_stream

    mock_client = Mock()

    with pytest.raises(ValueError, match="ontology_name required"):
        await create_backup_stream(
            client=mock_client,
            backup_type="ontology",
            ontology_name=None
        )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_backup_stream_invalid_type():
    """Test that invalid backup_type raises ValueError"""
    from src.api.lib.backup_streaming import create_backup_stream

    mock_client = Mock()

    with pytest.raises(ValueError, match="Invalid backup_type"):
        await create_backup_stream(
            client=mock_client,
            backup_type="invalid_type"
        )


@pytest.mark.unit
def test_get_backup_size():
    """Test backup size calculation"""
    from src.api.lib.backup_streaming import get_backup_size

    backup_data = {
        "version": "1.0",
        "data": {"concepts": []}
    }

    size = get_backup_size(backup_data)

    # Verify size is positive
    assert size > 0

    # Verify it matches JSON encoding size
    json_str = json.dumps(backup_data, indent=2)
    expected_size = len(json_str.encode('utf-8'))
    assert size == expected_size


# ============================================================================
# Unit Tests - Backup Validation (Defense in Depth)
# ============================================================================

@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_backup_stream_validates_backup_data():
    """Test that create_backup_stream validates backup before streaming"""
    from src.api.lib.backup_streaming import create_backup_stream

    mock_client = Mock()
    valid_backup_data = {
        "version": "1.0",
        "type": "full_backup",
        "timestamp": "2025-10-09T10:00:00",
        "data": {
            "concepts": [],
            "sources": [],
            "instances": [],
            "relationships": []
        },
        "statistics": {
            "concepts": 0,
            "sources": 0,
            "instances": 0,
            "relationships": 0
        }
    }

    with patch('src.api.lib.backup_streaming.DataExporter') as mock_exporter, \
         patch('src.api.lib.backup_streaming.check_backup_data') as mock_check:

        mock_exporter.export_full_backup.return_value = valid_backup_data

        # Mock successful validation
        mock_integrity = Mock()
        mock_integrity.valid = True
        mock_integrity.statistics = valid_backup_data["statistics"]
        mock_integrity.warnings = []
        mock_check.return_value = mock_integrity

        stream, filename = await create_backup_stream(
            client=mock_client,
            backup_type="full"
        )

        # Verify validation was called
        mock_check.assert_called_once_with(valid_backup_data)

        # Verify stream is generated (validation passed)
        chunks = []
        async for chunk in stream:
            chunks.append(chunk)
        assert len(chunks) > 0


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_backup_stream_fails_on_invalid_backup():
    """Test that create_backup_stream raises error when validation fails"""
    from src.api.lib.backup_streaming import create_backup_stream

    mock_client = Mock()
    invalid_backup_data = {
        "version": "1.0",
        "type": "full_backup",
        # Missing required fields
    }

    with patch('src.api.lib.backup_streaming.DataExporter') as mock_exporter, \
         patch('src.api.lib.backup_streaming.check_backup_data') as mock_check:

        mock_exporter.export_full_backup.return_value = invalid_backup_data

        # Mock failed validation
        mock_integrity = Mock()
        mock_integrity.valid = False
        mock_error = Mock()
        mock_error.category = "format"
        mock_error.message = "Missing required fields"
        mock_integrity.errors = [mock_error]
        mock_check.return_value = mock_integrity

        # Should raise ValueError with error details
        with pytest.raises(ValueError, match="Backup generation failed validation"):
            await create_backup_stream(
                client=mock_client,
                backup_type="full"
            )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_backup_stream_logs_validation_success(caplog):
    """Test that successful validation logs statistics"""
    from src.api.lib.backup_streaming import create_backup_stream
    import logging

    caplog.set_level(logging.INFO)

    mock_client = Mock()
    valid_backup_data = {
        "version": "1.0",
        "type": "full_backup",
        "timestamp": "2025-10-09T10:00:00",
        "data": {
            "concepts": [],
            "sources": [],
            "instances": [],
            "relationships": []
        },
        "statistics": {
            "concepts": 42,
            "sources": 10,
            "instances": 50,
            "relationships": 15
        }
    }

    with patch('src.api.lib.backup_streaming.DataExporter') as mock_exporter, \
         patch('src.api.lib.backup_streaming.check_backup_data') as mock_check:

        mock_exporter.export_full_backup.return_value = valid_backup_data

        # Mock successful validation
        mock_integrity = Mock()
        mock_integrity.valid = True
        mock_integrity.statistics = valid_backup_data["statistics"]
        mock_integrity.warnings = []
        mock_check.return_value = mock_integrity

        stream, filename = await create_backup_stream(
            client=mock_client,
            backup_type="full"
        )

        # Verify success log contains statistics
        assert any("Backup validated successfully" in record.message
                   for record in caplog.records)
        assert any("Concepts: 42" in record.message
                   for record in caplog.records)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_backup_stream_logs_validation_warnings(caplog):
    """Test that validation warnings are logged"""
    from src.api.lib.backup_streaming import create_backup_stream
    import logging

    caplog.set_level(logging.WARNING)

    mock_client = Mock()
    valid_backup_data = {
        "version": "1.0",
        "type": "full_backup",
        "timestamp": "2025-10-09T10:00:00",
        "data": {
            "concepts": [],
            "sources": [],
            "instances": [],
            "relationships": []
        },
        "statistics": {
            "concepts": 0,
            "sources": 0,
            "instances": 0,
            "relationships": 0
        }
    }

    with patch('src.api.lib.backup_streaming.DataExporter') as mock_exporter, \
         patch('src.api.lib.backup_streaming.check_backup_data') as mock_check:

        mock_exporter.export_full_backup.return_value = valid_backup_data

        # Mock validation with warnings
        mock_integrity = Mock()
        mock_integrity.valid = True
        mock_integrity.statistics = valid_backup_data["statistics"]

        mock_warning = Mock()
        mock_warning.category = "consistency"
        mock_warning.message = "Statistics mismatch detected"
        mock_integrity.warnings = [mock_warning]

        mock_check.return_value = mock_integrity

        stream, filename = await create_backup_stream(
            client=mock_client,
            backup_type="full"
        )

        # Verify warning log
        assert any("Backup validation warning" in record.message and
                   "Statistics mismatch detected" in record.message
                   for record in caplog.records)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_backup_stream_ontology_validates():
    """Test that ontology backups are also validated"""
    from src.api.lib.backup_streaming import create_backup_stream

    mock_client = Mock()
    valid_backup_data = {
        "version": "1.0",
        "type": "ontology_backup",
        "ontology": "Test Ontology",
        "timestamp": "2025-10-09T10:00:00",
        "data": {
            "concepts": [],
            "sources": [],
            "instances": [],
            "relationships": []
        },
        "statistics": {
            "concepts": 0,
            "sources": 0,
            "instances": 0,
            "relationships": 0
        }
    }

    with patch('src.api.lib.backup_streaming.DataExporter') as mock_exporter, \
         patch('src.api.lib.backup_streaming.check_backup_data') as mock_check:

        mock_exporter.export_ontology_backup.return_value = valid_backup_data

        # Mock successful validation
        mock_integrity = Mock()
        mock_integrity.valid = True
        mock_integrity.statistics = valid_backup_data["statistics"]
        mock_integrity.warnings = []
        mock_check.return_value = mock_integrity

        stream, filename = await create_backup_stream(
            client=mock_client,
            backup_type="ontology",
            ontology_name="Test Ontology"
        )

        # Verify validation was called for ontology backup too
        mock_check.assert_called_once_with(valid_backup_data)


# ============================================================================
# API Tests - Backup Endpoint
# ============================================================================

@pytest.mark.api
def test_backup_endpoint_full_backup_streams_response(api_client):
    """Test POST /admin/backup streams full backup"""
    with patch('src.api.routes.admin.AGEClient') as mock_client_class, \
         patch('src.api.routes.admin.create_backup_stream') as mock_stream:

        # Mock the stream generator
        async def mock_generator():
            yield b'{"version": "1.0", '
            yield b'"type": "full_backup"}'

        mock_stream.return_value = (mock_generator(), "test_backup.json")

        response = api_client.post(
            "/admin/backup",
            json={"backup_type": "full"}
        )

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        assert "content-disposition" in response.headers
        assert "attachment" in response.headers["content-disposition"]
        assert "test_backup.json" in response.headers["content-disposition"]


@pytest.mark.api
def test_backup_endpoint_ontology_backup_includes_headers(api_client):
    """Test POST /admin/backup includes custom headers for ontology backup"""
    with patch('src.api.routes.admin.AGEClient') as mock_client_class, \
         patch('src.api.routes.admin.create_backup_stream') as mock_stream:

        async def mock_generator():
            yield b'{"type": "ontology_backup"}'

        mock_stream.return_value = (mock_generator(), "ontology_backup.json")

        response = api_client.post(
            "/admin/backup",
            json={
                "backup_type": "ontology",
                "ontology_name": "My Ontology"
            }
        )

        assert response.status_code == 200
        assert response.headers.get("x-backup-type") == "ontology"
        assert response.headers.get("x-ontology-name") == "My Ontology"


@pytest.mark.api
def test_backup_endpoint_missing_ontology_name_returns_400(api_client):
    """Test POST /admin/backup returns 400 when ontology_name missing"""
    with patch('src.api.routes.admin.AGEClient') as mock_client_class, \
         patch('src.api.routes.admin.create_backup_stream') as mock_stream:

        mock_stream.side_effect = ValueError("ontology_name required for ontology backup")

        response = api_client.post(
            "/admin/backup",
            json={"backup_type": "ontology"}
        )

        assert response.status_code == 400
        assert "ontology_name required" in response.json()["detail"]


@pytest.mark.api
def test_backup_endpoint_invalid_backup_type_returns_400(api_client):
    """Test POST /admin/backup returns 400 for invalid backup type"""
    with patch('src.api.routes.admin.AGEClient') as mock_client_class, \
         patch('src.api.routes.admin.create_backup_stream') as mock_stream:

        mock_stream.side_effect = ValueError("Invalid backup_type: invalid")

        response = api_client.post(
            "/admin/backup",
            json={"backup_type": "invalid"}
        )

        assert response.status_code == 400
        assert "Invalid backup_type" in response.json()["detail"]


@pytest.mark.api
def test_backup_endpoint_database_error_returns_500(api_client):
    """Test POST /admin/backup returns 500 on database error"""
    with patch('src.api.routes.admin.AGEClient') as mock_client_class:
        mock_client_class.side_effect = Exception("Database connection failed")

        response = api_client.post(
            "/admin/backup",
            json={"backup_type": "full"}
        )

        assert response.status_code == 500
        assert "Backup failed" in response.json()["detail"]


@pytest.mark.api
def test_backup_endpoint_content_disposition_header_format(api_client):
    """Test that Content-Disposition header is properly formatted"""
    with patch('src.api.routes.admin.AGEClient') as mock_client_class, \
         patch('src.api.routes.admin.create_backup_stream') as mock_stream:

        async def mock_generator():
            yield b'{}'

        filename = "full_backup_20251008_123456.json"
        mock_stream.return_value = (mock_generator(), filename)

        response = api_client.post(
            "/admin/backup",
            json={"backup_type": "full"}
        )

        assert response.status_code == 200
        disposition = response.headers["content-disposition"]
        assert disposition == f"attachment; filename={filename}"


# ============================================================================
# Integration Tests - Full Flow
# ============================================================================

@pytest.mark.integration
@pytest.mark.slow
def test_full_backup_stream_e2e():
    """
    End-to-end test of full backup streaming.

    Tests complete flow:
    1. Request backup
    2. Stream JSON response
    3. Parse streamed data
    4. Validate backup structure
    """
    pytest.skip("Integration test - requires live database")

    # TODO: Implement when database fixtures are ready
    # Should test:
    # - Real AGEClient connection
    # - Real backup data export
    # - Stream reassembly
    # - JSON validation
