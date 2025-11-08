"""
Backup Integrity Check Module (ADR-015 Phase 2)

Validates backup files before restore operations. Checks:
- JSON format validity
- Required fields presence
- Data completeness
- Reference integrity (concept_id, source_id consistency)
- External dependencies (cross-ontology references)
- Data consistency (statistics accuracy)
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from pathlib import Path
import json

from ..constants import RELATIONSHIP_TYPES, BACKUP_TYPES


@dataclass
class IntegrityIssue:
    """Represents a single integrity check issue"""
    severity: str  # "error", "warning", "info"
    category: str  # "format", "references", "consistency", "external_deps"
    message: str
    details: Optional[Dict[str, Any]] = None


@dataclass
class BackupIntegrity:
    """
    Backup integrity check result

    Attributes:
        valid: True if backup passes all critical checks
        errors: Critical issues that prevent restore
        warnings: Non-critical issues that should be reviewed
        info: Informational messages about backup content
        external_deps: Count of external concept references (for ontology backups)
        statistics: Validated statistics from backup
    """
    valid: bool
    errors: List[IntegrityIssue]
    warnings: List[IntegrityIssue]
    info: List[IntegrityIssue]
    external_deps: int = 0
    statistics: Optional[Dict[str, int]] = None

    @property
    def has_external_deps(self) -> bool:
        """Check if backup has external dependencies"""
        return self.external_deps > 0

    def add_error(self, category: str, message: str, details: Optional[Dict] = None):
        """Add an error issue"""
        self.errors.append(IntegrityIssue("error", category, message, details))
        self.valid = False

    def add_warning(self, category: str, message: str, details: Optional[Dict] = None):
        """Add a warning issue"""
        self.warnings.append(IntegrityIssue("warning", category, message, details))

    def add_info(self, category: str, message: str, details: Optional[Dict] = None):
        """Add an info message"""
        self.info.append(IntegrityIssue("info", category, message, details))


class BackupIntegrityChecker:
    """
    Validates backup file integrity before restore

    Usage:
        checker = BackupIntegrityChecker()

        # From file path
        result = checker.check_file("/path/to/backup.json")

        # From loaded data
        result = checker.check_data(backup_dict)

        if not result.valid:
            print(f"Backup validation failed: {result.errors}")
    """

    # Required top-level fields
    REQUIRED_FIELDS = {"version", "type", "timestamp", "data", "statistics"}

    # Required data sections
    REQUIRED_DATA_SECTIONS = {"concepts", "sources", "instances", "relationships"}

    # Valid backup types (from data contract)
    VALID_TYPES = BACKUP_TYPES

    # Valid relationship types (from data contract)
    VALID_RELATIONSHIP_TYPES = RELATIONSHIP_TYPES

    def check_file(self, file_path: str) -> BackupIntegrity:
        """
        Check backup file integrity

        Args:
            file_path: Path to backup JSON file

        Returns:
            BackupIntegrity result with validation status
        """
        result = BackupIntegrity(valid=True, errors=[], warnings=[], info=[])

        # Check file exists
        path = Path(file_path)
        if not path.exists():
            result.add_error("format", f"Backup file not found: {file_path}")
            return result

        # Try to load JSON
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            result.add_error("format", f"Invalid JSON format: {e}")
            return result
        except Exception as e:
            result.add_error("format", f"Failed to read backup file: {e}")
            return result

        # Check loaded data
        return self.check_data(data, file_path=file_path)

    def check_data(self, data: Dict[str, Any], file_path: Optional[str] = None) -> BackupIntegrity:
        """
        Check backup data integrity

        Args:
            data: Loaded backup dictionary
            file_path: Optional path for error messages

        Returns:
            BackupIntegrity result with validation status
        """
        result = BackupIntegrity(valid=True, errors=[], warnings=[], info=[])

        # Validate format
        self._check_format(data, result)
        if not result.valid:
            return result

        # Validate data completeness
        self._check_data_sections(data, result)
        if not result.valid:
            return result

        # Validate reference integrity
        self._check_references(data, result)

        # Validate statistics consistency
        self._check_statistics(data, result)

        # Check for external dependencies (ontology backups)
        if data.get("type") == "ontology_backup":
            self._check_external_deps(data, result)

        # Add info messages
        backup_type = data.get("type", "unknown")
        ontology = data.get("ontology")
        stats = data.get("statistics", {})
        data_section = data.get("data", {})

        if ontology:
            result.add_info("info", f"Ontology backup: {ontology}", stats)
        else:
            result.add_info("info", f"Full database backup", stats)

        # Check vocabulary section (ADR-032)
        if "vocabulary" in data_section:
            vocab_entries = data_section.get("vocabulary", [])
            builtin_count = sum(1 for v in vocab_entries if v.get("is_builtin"))
            custom_count = len(vocab_entries) - builtin_count
            result.add_info("vocabulary",
                f"Vocabulary: {len(vocab_entries)} types ({builtin_count} builtin, {custom_count} extended)",
                {"builtin": builtin_count, "extended": custom_count})

        result.statistics = stats

        return result

    def _check_format(self, data: Dict[str, Any], result: BackupIntegrity):
        """Validate backup format and required fields"""

        # Check required top-level fields
        missing = self.REQUIRED_FIELDS - set(data.keys())
        if missing:
            result.add_error("format", f"Missing required fields: {missing}")
            return

        # Check backup type
        backup_type = data.get("type")
        if backup_type not in self.VALID_TYPES:
            result.add_error(
                "format",
                f"Invalid backup type: {backup_type}",
                {"expected": list(self.VALID_TYPES)}
            )

        # Check version format
        version = data.get("version")
        if not isinstance(version, str) or not version:
            result.add_error("format", "Invalid or missing version field")

        # Check timestamp format
        timestamp = data.get("timestamp")
        if not isinstance(timestamp, str) or not timestamp:
            result.add_warning("format", "Invalid or missing timestamp field")

    def _check_data_sections(self, data: Dict[str, Any], result: BackupIntegrity):
        """Validate data sections completeness"""

        data_section = data.get("data")
        if not isinstance(data_section, dict):
            result.add_error("format", "Invalid or missing 'data' section")
            return

        # Check required sections
        missing = self.REQUIRED_DATA_SECTIONS - set(data_section.keys())
        if missing:
            result.add_error("format", f"Missing data sections: {missing}")
            return

        # Validate section types
        for section in self.REQUIRED_DATA_SECTIONS:
            if not isinstance(data_section.get(section), list):
                result.add_error("format", f"Section '{section}' must be a list")

        # Check for empty backup (warning, not error)
        if all(len(data_section.get(s, [])) == 0 for s in self.REQUIRED_DATA_SECTIONS):
            result.add_warning("consistency", "Backup contains no data (all sections empty)")

    def _check_references(self, data: Dict[str, Any], result: BackupIntegrity):
        """Validate reference integrity between entities"""

        data_section = data.get("data", {})
        is_ontology_backup = data.get("type") == "ontology_backup"

        # Build ID sets for validation
        concept_ids: Set[str] = {c.get("concept_id") for c in data_section.get("concepts", []) if c.get("concept_id")}
        source_ids: Set[str] = {s.get("source_id") for s in data_section.get("sources", []) if s.get("source_id")}

        # Check instances reference valid concepts and sources
        instances = data_section.get("instances", [])
        for idx, instance in enumerate(instances):
            concept_id = instance.get("concept_id")
            source_id = instance.get("source_id")

            if not concept_id:
                result.add_error("references", f"Instance {idx} missing concept_id field")
            elif concept_id not in concept_ids:
                # External concept references are allowed in ontology backups (warnings handled separately)
                if not is_ontology_backup:
                    result.add_error("references",
                        f"Referential integrity: Instance {idx} references concept_id '{concept_id}' which doesn't exist in backup")

            if not source_id:
                result.add_error("references", f"Instance {idx} missing source_id field")
            elif source_id not in source_ids:
                result.add_error("references",
                    f"Referential integrity: Instance {idx} references source_id '{source_id}' which doesn't exist in backup")

        # Check relationships reference valid concepts
        relationships = data_section.get("relationships", [])
        for idx, rel in enumerate(relationships):
            from_id = rel.get("from")
            to_id = rel.get("to")
            rel_type = rel.get("type")

            if not from_id:
                result.add_error("references", f"Relationship {idx} missing 'from' field")
            elif from_id not in concept_ids:
                # External concept references are allowed in ontology backups (warnings handled separately)
                if not is_ontology_backup:
                    result.add_error("references",
                        f"Referential integrity: Relationship {idx} 'from' references concept_id '{from_id}' which doesn't exist in backup")

            if not to_id:
                result.add_error("references", f"Relationship {idx} missing 'to' field")
            elif to_id not in concept_ids:
                # External concept references are allowed in ontology backups (warnings handled separately)
                if not is_ontology_backup:
                    result.add_error("references",
                        f"Referential integrity: Relationship {idx} 'to' references concept_id '{to_id}' which doesn't exist in backup")

            # Check relationship type (ADR-032: Extended vocabulary support)
            # If backup has vocabulary section, check against that; otherwise use builtin types
            vocabulary_types = set()
            if "vocabulary" in data_section:
                vocabulary_types = {v.get("relationship_type") for v in data_section.get("vocabulary", []) if v.get("relationship_type")}
            else:
                # Old backups without vocabulary section - use builtin types only
                vocabulary_types = self.VALID_RELATIONSHIP_TYPES

            if rel_type and rel_type not in vocabulary_types:
                # Only warn if type is not in vocabulary AND not a structural type
                structural_types = {"APPEARS_IN", "EVIDENCED_BY", "FROM_SOURCE"}
                if rel_type not in structural_types:
                    result.add_warning("references",
                        f"Vocabulary integrity: Relationship {idx} uses edge type '{rel_type}' which is not in vocabulary table (pre-ADR-032 data)")

    def _check_statistics(self, data: Dict[str, Any], result: BackupIntegrity):
        """Validate statistics match actual data"""

        stats = data.get("statistics", {})
        data_section = data.get("data", {})

        # Count actual data
        actual = {
            "concepts": len(data_section.get("concepts", [])),
            "sources": len(data_section.get("sources", [])),
            "instances": len(data_section.get("instances", [])),
            "relationships": len(data_section.get("relationships", []))
        }

        # Compare with claimed statistics
        for key, expected in stats.items():
            if key in actual:
                if actual[key] != expected:
                    result.add_warning(
                        "consistency",
                        f"Statistics mismatch for {key}: claimed {expected}, actual {actual[key]}"
                    )

    def _check_external_deps(self, data: Dict[str, Any], result: BackupIntegrity):
        """Check for external concept dependencies (ontology backups)"""

        ontology_name = data.get("ontology")
        if not ontology_name:
            result.add_warning("external_deps", "Ontology backup missing ontology name")
            return

        data_section = data.get("data", {})
        concepts = data_section.get("concepts", [])
        instances = data_section.get("instances", [])
        relationships = data_section.get("relationships", [])

        # Build set of concept IDs in this backup
        local_concept_ids: Set[str] = {c.get("concept_id") for c in concepts if c.get("concept_id")}

        # Check for external concept references in instances
        external_concept_refs = set()
        for instance in instances:
            concept_id = instance.get("concept_id")
            if concept_id and concept_id not in local_concept_ids:
                external_concept_refs.add(concept_id)

        # Check for external concept references in relationships
        external_rel_refs = set()
        for rel in relationships:
            from_id = rel.get("from")
            to_id = rel.get("to")

            if from_id and from_id not in local_concept_ids:
                external_rel_refs.add(from_id)
            if to_id and to_id not in local_concept_ids:
                external_rel_refs.add(to_id)

        # Report external dependencies
        total_external = len(external_concept_refs) + len(external_rel_refs)
        result.external_deps = total_external

        if total_external > 0:
            result.add_warning(
                "external_deps",
                f"Cross-ontology referential integrity: Ontology backup references {total_external} concept_ids from other ontologies not included in this backup",
                {
                    "external_concepts_in_instances": len(external_concept_refs),
                    "external_concepts_in_relationships": len(external_rel_refs)
                }
            )
            result.add_info(
                "external_deps",
                "These external references will create dangling edges if other ontologies are not present in target database"
            )


def check_backup_integrity(file_path: str) -> BackupIntegrity:
    """
    Convenience function to check backup file integrity

    Args:
        file_path: Path to backup JSON file

    Returns:
        BackupIntegrity result

    Example:
        result = check_backup_integrity("/path/to/backup.json")
        if result.valid:
            print("Backup is valid")
        else:
            for error in result.errors:
                print(f"ERROR: {error.message}")
    """
    checker = BackupIntegrityChecker()
    return checker.check_file(file_path)


def check_backup_data(data: Dict[str, Any]) -> BackupIntegrity:
    """
    Convenience function to check loaded backup data integrity

    Args:
        data: Loaded backup dictionary

    Returns:
        BackupIntegrity result
    """
    checker = BackupIntegrityChecker()
    return checker.check_data(data)
