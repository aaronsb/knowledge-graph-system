"""
Tests for Backup Integrity Check Module (ADR-015 Phase 2)

Tests cover:
- Valid backup validation
- Missing field detection
- Invalid format detection
- Reference integrity checking
- Statistics validation
- External dependency detection
- Edge cases and error handling
"""

import pytest
import json
import tempfile
from pathlib import Path
from typing import Dict, Any

from api.app.lib.backup_integrity import (
    BackupIntegrityChecker,
    BackupIntegrity,
    check_backup_integrity,
    check_backup_data
)


# ========== Fixtures ==========

@pytest.fixture
def valid_full_backup() -> Dict[str, Any]:
    """Valid full database backup"""
    return {
        "version": "1.0",
        "type": "full_backup",
        "timestamp": "2025-10-09T04:00:00Z",
        "ontology": None,
        "statistics": {
            "concepts": 2,
            "sources": 1,
            "instances": 2,
            "relationships": 1
        },
        "data": {
            "concepts": [
                {"concept_id": "concept_1", "label": "Test Concept 1", "search_terms": []},
                {"concept_id": "concept_2", "label": "Test Concept 2", "search_terms": []}
            ],
            "sources": [
                {
                    "source_id": "source_1",
                    "document": "Test Document",
                    "paragraph": 1,
                    "full_text": "Test content"
                }
            ],
            "instances": [
                {
                    "instance_id": "inst_1",
                    "quote": "Test quote 1",
                    "concept_id": "concept_1",
                    "source_id": "source_1"
                },
                {
                    "instance_id": "inst_2",
                    "quote": "Test quote 2",
                    "concept_id": "concept_2",
                    "source_id": "source_1"
                }
            ],
            "relationships": [
                {
                    "from": "concept_1",
                    "to": "concept_2",
                    "type": "SUPPORTS",
                    "properties": {}
                }
            ]
        }
    }


@pytest.fixture
def valid_ontology_backup() -> Dict[str, Any]:
    """Valid ontology backup with external dependencies"""
    return {
        "version": "1.0",
        "type": "ontology_backup",
        "timestamp": "2025-10-09T04:00:00Z",
        "ontology": "Test Ontology",
        "statistics": {
            "concepts": 1,
            "sources": 1,
            "instances": 2,
            "relationships": 1
        },
        "data": {
            "concepts": [
                {"concept_id": "local_concept_1", "label": "Local Concept", "search_terms": []}
            ],
            "sources": [
                {
                    "source_id": "source_1",
                    "document": "Test Document",
                    "paragraph": 1,
                    "full_text": "Test content"
                }
            ],
            "instances": [
                {
                    "instance_id": "inst_1",
                    "quote": "Local quote",
                    "concept_id": "local_concept_1",
                    "source_id": "source_1"
                },
                {
                    "instance_id": "inst_2",
                    "quote": "External quote",
                    "concept_id": "external_concept_99",  # External reference
                    "source_id": "source_1"
                }
            ],
            "relationships": [
                {
                    "from": "local_concept_1",
                    "to": "external_concept_77",  # External reference
                    "type": "RELATES_TO",
                    "properties": {}
                }
            ]
        }
    }


# ========== Unit Tests: Valid Backups ==========

@pytest.mark.unit
def test_valid_full_backup_passes(valid_full_backup):
    """Test that valid full backup passes all checks"""
    checker = BackupIntegrityChecker()
    result = checker.check_data(valid_full_backup)

    assert result.valid is True
    assert len(result.errors) == 0
    assert result.statistics == valid_full_backup["statistics"]


@pytest.mark.unit
def test_valid_ontology_backup_passes(valid_ontology_backup):
    """Test that valid ontology backup passes (with warnings for external deps)"""
    checker = BackupIntegrityChecker()
    result = checker.check_data(valid_ontology_backup)

    assert result.valid is True
    assert len(result.errors) == 0
    assert result.has_external_deps is True
    assert result.external_deps == 2  # 1 in instances, 1 in relationships


# ========== Unit Tests: Format Validation ==========

@pytest.mark.unit
def test_missing_required_field_fails():
    """Test that missing required fields are detected"""
    invalid_data = {
        "version": "1.0",
        "type": "full_backup"
        # Missing: timestamp, data, statistics
    }

    checker = BackupIntegrityChecker()
    result = checker.check_data(invalid_data)

    assert result.valid is False
    assert len(result.errors) > 0
    assert any("Missing required fields" in e.message for e in result.errors)


@pytest.mark.unit
def test_invalid_backup_type_fails():
    """Test that invalid backup type is detected"""
    invalid_data = {
        "version": "1.0",
        "type": "invalid_type",
        "timestamp": "2025-10-09T04:00:00Z",
        "statistics": {},
        "data": {}
    }

    checker = BackupIntegrityChecker()
    result = checker.check_data(invalid_data)

    assert result.valid is False
    assert any("Invalid backup type" in e.message for e in result.errors)


@pytest.mark.unit
def test_invalid_version_fails():
    """Test that invalid version format is detected"""
    invalid_data = {
        "version": None,  # Invalid
        "type": "full_backup",
        "timestamp": "2025-10-09T04:00:00Z",
        "statistics": {},
        "data": {}
    }

    checker = BackupIntegrityChecker()
    result = checker.check_data(invalid_data)

    assert result.valid is False
    assert any("version" in e.message.lower() for e in result.errors)


@pytest.mark.unit
def test_missing_data_sections_fails():
    """Test that missing data sections are detected"""
    invalid_data = {
        "version": "1.0",
        "type": "full_backup",
        "timestamp": "2025-10-09T04:00:00Z",
        "statistics": {},
        "data": {
            "concepts": [],
            "sources": []
            # Missing: instances, relationships
        }
    }

    checker = BackupIntegrityChecker()
    result = checker.check_data(invalid_data)

    assert result.valid is False
    assert any("Missing data sections" in e.message for e in result.errors)


@pytest.mark.unit
def test_non_list_data_section_fails():
    """Test that data sections must be lists"""
    invalid_data = {
        "version": "1.0",
        "type": "full_backup",
        "timestamp": "2025-10-09T04:00:00Z",
        "statistics": {},
        "data": {
            "concepts": "not a list",  # Invalid
            "sources": [],
            "instances": [],
            "relationships": []
        }
    }

    checker = BackupIntegrityChecker()
    result = checker.check_data(invalid_data)

    assert result.valid is False
    assert any("must be a list" in e.message for e in result.errors)


# ========== Unit Tests: Reference Integrity ==========

@pytest.mark.unit
def test_instance_with_invalid_concept_id_fails(valid_full_backup):
    """Test that instances referencing non-existent concepts are detected"""
    invalid_backup = valid_full_backup.copy()
    invalid_backup["data"]["instances"][0]["concept_id"] = "nonexistent_concept"

    checker = BackupIntegrityChecker()
    result = checker.check_data(invalid_backup)

    assert result.valid is False
    assert any("unknown concept" in e.message for e in result.errors)


@pytest.mark.unit
def test_instance_with_invalid_source_id_fails(valid_full_backup):
    """Test that instances referencing non-existent sources are detected"""
    invalid_backup = valid_full_backup.copy()
    invalid_backup["data"]["instances"][0]["source_id"] = "nonexistent_source"

    checker = BackupIntegrityChecker()
    result = checker.check_data(invalid_backup)

    assert result.valid is False
    assert any("unknown source" in e.message for e in result.errors)


@pytest.mark.unit
def test_relationship_with_invalid_from_concept_fails(valid_full_backup):
    """Test that relationships with invalid 'from' concept are detected"""
    invalid_backup = valid_full_backup.copy()
    invalid_backup["data"]["relationships"][0]["from"] = "nonexistent_concept"

    checker = BackupIntegrityChecker()
    result = checker.check_data(invalid_backup)

    assert result.valid is False
    assert any("unknown 'from' concept" in e.message for e in result.errors)


@pytest.mark.unit
def test_relationship_with_invalid_to_concept_fails(valid_full_backup):
    """Test that relationships with invalid 'to' concept are detected"""
    invalid_backup = valid_full_backup.copy()
    invalid_backup["data"]["relationships"][0]["to"] = "nonexistent_concept"

    checker = BackupIntegrityChecker()
    result = checker.check_data(invalid_backup)

    assert result.valid is False
    assert any("unknown 'to' concept" in e.message for e in result.errors)


@pytest.mark.unit
def test_unusual_relationship_type_warning(valid_full_backup):
    """Test that unusual relationship types generate warnings"""
    backup = valid_full_backup.copy()
    backup["data"]["relationships"][0]["type"] = "UNUSUAL_TYPE"

    checker = BackupIntegrityChecker()
    result = checker.check_data(backup)

    assert result.valid is True  # Warning, not error
    assert any("unusual type" in w.message for w in result.warnings)


# ========== Unit Tests: Statistics Validation ==========

@pytest.mark.unit
def test_statistics_mismatch_warning(valid_full_backup):
    """Test that statistics mismatches generate warnings"""
    invalid_backup = valid_full_backup.copy()
    invalid_backup["statistics"]["concepts"] = 999  # Wrong count

    checker = BackupIntegrityChecker()
    result = checker.check_data(invalid_backup)

    assert result.valid is True  # Warning, not error
    assert any("Statistics mismatch" in w.message for w in result.warnings)
    assert any("concepts" in w.message for w in result.warnings)


# ========== Unit Tests: External Dependencies ==========

@pytest.mark.unit
def test_external_deps_detected_in_ontology_backup(valid_ontology_backup):
    """Test that external dependencies are detected in ontology backups"""
    checker = BackupIntegrityChecker()
    result = checker.check_data(valid_ontology_backup)

    assert result.valid is True
    assert result.has_external_deps is True
    assert result.external_deps == 2  # 1 from instance, 1 from relationship
    assert any("external concept references" in w.message for w in result.warnings)


@pytest.mark.unit
def test_no_external_deps_in_full_backup(valid_full_backup):
    """Test that full backups don't report external dependencies"""
    checker = BackupIntegrityChecker()
    result = checker.check_data(valid_full_backup)

    assert result.valid is True
    assert result.has_external_deps is False
    assert result.external_deps == 0


# ========== Integration Tests: File Operations ==========

@pytest.mark.integration
def test_check_file_with_valid_backup(valid_full_backup):
    """Test checking backup from file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(valid_full_backup, f)
        temp_path = f.name

    try:
        checker = BackupIntegrityChecker()
        result = checker.check_file(temp_path)

        assert result.valid is True
        assert len(result.errors) == 0
    finally:
        Path(temp_path).unlink()


@pytest.mark.integration
def test_check_file_with_nonexistent_file():
    """Test checking non-existent file"""
    checker = BackupIntegrityChecker()
    result = checker.check_file("/nonexistent/path/backup.json")

    assert result.valid is False
    assert any("not found" in e.message for e in result.errors)


@pytest.mark.integration
def test_check_file_with_invalid_json():
    """Test checking file with invalid JSON"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write("{ invalid json }")
        temp_path = f.name

    try:
        checker = BackupIntegrityChecker()
        result = checker.check_file(temp_path)

        assert result.valid is False
        assert any("JSON" in e.message for e in result.errors)
    finally:
        Path(temp_path).unlink()


# ========== Integration Tests: Convenience Functions ==========

@pytest.mark.integration
def test_convenience_function_check_backup_integrity(valid_full_backup):
    """Test check_backup_integrity() convenience function"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(valid_full_backup, f)
        temp_path = f.name

    try:
        result = check_backup_integrity(temp_path)
        assert result.valid is True
        assert len(result.errors) == 0
    finally:
        Path(temp_path).unlink()


@pytest.mark.unit
def test_convenience_function_check_backup_data(valid_full_backup):
    """Test check_backup_data() convenience function"""
    result = check_backup_data(valid_full_backup)

    assert result.valid is True
    assert len(result.errors) == 0
    assert result.statistics == valid_full_backup["statistics"]


# ========== Edge Cases ==========

@pytest.mark.unit
def test_empty_backup_warning():
    """Test that empty backup generates warning"""
    empty_backup = {
        "version": "1.0",
        "type": "full_backup",
        "timestamp": "2025-10-09T04:00:00Z",
        "statistics": {},
        "data": {
            "concepts": [],
            "sources": [],
            "instances": [],
            "relationships": []
        }
    }

    checker = BackupIntegrityChecker()
    result = checker.check_data(empty_backup)

    assert result.valid is True  # Empty is valid, just warned
    assert any("no data" in w.message.lower() for w in result.warnings)


@pytest.mark.unit
def test_missing_instance_concept_id_error():
    """Test that instances without concept_id are detected"""
    invalid_backup = {
        "version": "1.0",
        "type": "full_backup",
        "timestamp": "2025-10-09T04:00:00Z",
        "statistics": {},
        "data": {
            "concepts": [{"concept_id": "concept_1", "label": "Test"}],
            "sources": [{"source_id": "source_1", "document": "Test", "paragraph": 1, "full_text": "Test"}],
            "instances": [
                {
                    "instance_id": "inst_1",
                    "quote": "Test",
                    # Missing: concept_id
                    "source_id": "source_1"
                }
            ],
            "relationships": []
        }
    }

    checker = BackupIntegrityChecker()
    result = checker.check_data(invalid_backup)

    assert result.valid is False
    assert any("missing concept_id" in e.message for e in result.errors)


@pytest.mark.unit
def test_all_valid_relationship_types_pass(valid_full_backup):
    """Test that all valid relationship types are accepted"""
    valid_types = ["IMPLIES", "SUPPORTS", "CONTRADICTS", "RELATES_TO", "PART_OF"]

    for rel_type in valid_types:
        backup = valid_full_backup.copy()
        backup["data"]["relationships"][0]["type"] = rel_type

        checker = BackupIntegrityChecker()
        result = checker.check_data(backup)

        assert result.valid is True, f"Valid type {rel_type} should pass"
        assert len([w for w in result.warnings if "unusual type" in w.message]) == 0


# ========== Test Coverage Report ==========

def test_integrity_checker_coverage_summary():
    """
    Summary of test coverage for BackupIntegrityChecker

    Covered:
    - ✅ Valid full backup validation
    - ✅ Valid ontology backup validation
    - ✅ Missing required fields detection
    - ✅ Invalid backup type detection
    - ✅ Invalid version format detection
    - ✅ Missing data sections detection
    - ✅ Non-list data section detection
    - ✅ Instance with invalid concept_id
    - ✅ Instance with invalid source_id
    - ✅ Relationship with invalid from concept
    - ✅ Relationship with invalid to concept
    - ✅ Unusual relationship type warnings
    - ✅ Statistics mismatch warnings
    - ✅ External dependency detection (ontology backups)
    - ✅ File operations (load from disk)
    - ✅ Non-existent file handling
    - ✅ Invalid JSON handling
    - ✅ Convenience functions
    - ✅ Empty backup warnings
    - ✅ Missing instance concept_id
    - ✅ All valid relationship types accepted

    Test Counts:
    - Unit tests: 19
    - Integration tests: 4
    - Total: 23 tests
    """
    pass
