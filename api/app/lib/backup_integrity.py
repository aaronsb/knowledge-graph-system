"""
Backup Integrity Check Module (ADR-015 Phase 2; retargeted to kg-backup/2 in ADR-102 P3)

Runtime defense-in-depth validation of a backup object before it is streamed,
archived, or restored. Validates the single backup model (``kg-backup/2``):
- Structural format (declarative ``header`` + ``bulk`` regions; negotiable version)
- Data completeness (required bulk record streams present and list-typed)
- Reference integrity (instance→source, evidence→concept/instance, relationship endpoints)
- External dependencies (concept references not contained in this backup — partial backups)
- Statistics (record counts surfaced for logging)

This is the *runtime* checker. The exhaustive *offline* oracle is
``scripts/development/lint/lint_backup.py`` (used in tests/linting). Consolidating
the two v2 validators is tracked for ADR-102 P6.
"""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from pathlib import Path
import json

from ..constants import RELATIONSHIP_TYPES
from ...lib.serialization import KgBackupV2Reader


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
        external_deps: Count of external concept references (partial backups)
        statistics: Validated record counts from the backup
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
    Validates a kg-backup/2 object before stream/archive/restore (ADR-102 P3).

    Usage:
        checker = BackupIntegrityChecker()
        result = checker.check_file("/path/to/backup.json")   # from path
        result = checker.check_data(backup_dict)               # from loaded data
        if not result.valid:
            print(f"Backup validation failed: {result.errors}")
    """

    # Required bulk record streams (graph_epochs / evidence / vocabulary are optional).
    REQUIRED_BULK_SECTIONS = {"concepts", "sources", "instances", "relationships"}

    # Structural edge types reconstructed on restore (never in the vocabulary table).
    STRUCTURAL_TYPES = {"APPEARS", "EVIDENCED_BY", "FROM_SOURCE"}

    # Builtin relationship types — fallback when a backup carries no vocabulary stream.
    VALID_RELATIONSHIP_TYPES = RELATIONSHIP_TYPES

    def check_file(self, file_path: str) -> BackupIntegrity:
        """Check a backup file on disk: load JSON, then validate the object."""
        result = BackupIntegrity(valid=True, errors=[], warnings=[], info=[])

        path = Path(file_path)
        if not path.exists():
            result.add_error("format", f"Backup file not found: {file_path}")
            return result

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            result.add_error("format", f"Invalid JSON format: {e}")
            return result
        except Exception as e:
            result.add_error("format", f"Failed to read backup file: {e}")
            return result

        return self.check_data(data, file_path=file_path)

    def check_data(self, data: Dict[str, Any], file_path: Optional[str] = None) -> BackupIntegrity:
        """Validate a loaded kg-backup/2 object. Returns a BackupIntegrity result."""
        result = BackupIntegrity(valid=True, errors=[], warnings=[], info=[])

        # Format + structure: constructing the reader negotiates format_version and
        # asserts the header/bulk regions exist (raises ValueError otherwise).
        try:
            reader = KgBackupV2Reader(data)
        except ValueError as e:
            result.add_error("format", str(e))
            return result

        self._check_bulk_sections(reader, result)
        if not result.valid:
            return result

        self._check_references(reader, result)
        self._check_external_deps(reader, result)

        counts = reader.counts()
        result.statistics = {
            k: counts[k] for k in ("concepts", "sources", "instances", "relationships", "vocabulary")
        }

        ontologies = [o.get("name") for o in reader.header.get("ontologies", []) if o.get("name")]
        if len(ontologies) == 1:
            result.add_info("info", f"Ontology backup: {ontologies[0]}", result.statistics)
        else:
            result.add_info("info", "Full database backup", result.statistics)

        vocab = reader.vocabulary()
        if vocab:
            builtin_count = sum(1 for v in vocab if v.get("is_builtin"))
            result.add_info(
                "vocabulary",
                f"Vocabulary: {len(vocab)} types ({builtin_count} builtin, "
                f"{len(vocab) - builtin_count} extended)",
                {"builtin": builtin_count, "extended": len(vocab) - builtin_count},
            )

        if all(counts[s] == 0 for s in self.REQUIRED_BULK_SECTIONS):
            result.add_warning("consistency", "Backup contains no data (all bulk sections empty)")

        return result

    def _check_bulk_sections(self, reader: KgBackupV2Reader, result: BackupIntegrity):
        """Ensure the required bulk record streams are present and list-typed."""
        bulk = reader.bulk
        missing = self.REQUIRED_BULK_SECTIONS - set(bulk.keys())
        if missing:
            result.add_error("format", f"Missing bulk sections: {missing}")
            return
        for section in self.REQUIRED_BULK_SECTIONS:
            if not isinstance(bulk.get(section), list):
                result.add_error("format", f"Bulk section '{section}' must be a list")

    def _check_references(self, reader: KgBackupV2Reader, result: BackupIntegrity):
        """Validate reference integrity across the normalized record streams."""
        concept_ids: Set[str] = {c.get("concept_id") for c in reader.concepts() if c.get("concept_id")}
        source_ids: Set[str] = {s.get("source_id") for s in reader.sources() if s.get("source_id")}
        instance_ids: Set[str] = {i.get("instance_id") for i in reader.instances() if i.get("instance_id")}

        # Instances must name an instance_id and a source that exists in the backup.
        # (Instances are normalized: no concept_id — Concept↔Instance is in evidence.)
        for idx, inst in enumerate(reader.instances()):
            if not inst.get("instance_id"):
                result.add_error("references", f"Instance {idx} missing instance_id field")
            source_id = inst.get("source_id")
            if not source_id:
                result.add_error("references", f"Instance {idx} missing source_id field")
            elif source_id not in source_ids:
                result.add_error(
                    "references",
                    f"Referential integrity: Instance {idx} references source_id "
                    f"'{source_id}' which doesn't exist in backup",
                )

        # Evidence links (Concept→Instance). Missing instance is structural (error);
        # missing concept is treated as an external dependency (warning) since partial
        # backups legitimately evidence concepts held in other ontologies.
        for idx, ev in enumerate(reader.bulk.get("evidence", [])):
            if ev.get("instance_id") not in instance_ids:
                result.add_error(
                    "references",
                    f"Evidence {idx} references instance_id "
                    f"'{ev.get('instance_id')}' which doesn't exist in backup",
                )

        # Relationships: endpoints reference concepts; missing endpoints are external
        # deps (warnings) — the restore skips edges with absent endpoints. Validate the
        # de-interned edge type against the carried vocabulary.
        vocab_types = {v.get("relationship_type") for v in reader.vocabulary() if v.get("relationship_type")}
        if not vocab_types:
            vocab_types = set(self.VALID_RELATIONSHIP_TYPES)

        for idx, rel in enumerate(reader.relationships()):
            if not rel.get("from"):
                result.add_error("references", f"Relationship {idx} missing 'from' field")
            if not rel.get("to"):
                result.add_error("references", f"Relationship {idx} missing 'to' field")
            rel_type = rel.get("type")
            if rel_type and rel_type not in vocab_types and rel_type not in self.STRUCTURAL_TYPES:
                result.add_warning(
                    "references",
                    f"Vocabulary integrity: Relationship {idx} uses edge type "
                    f"'{rel_type}' which is not in the vocabulary stream",
                )

    def _check_external_deps(self, reader: KgBackupV2Reader, result: BackupIntegrity):
        """Count concept references not contained in this backup (partial/adjacent restores)."""
        local_concept_ids: Set[str] = {c.get("concept_id") for c in reader.concepts() if c.get("concept_id")}

        external_in_evidence = {
            ev.get("concept_id") for ev in reader.bulk.get("evidence", [])
            if ev.get("concept_id") and ev.get("concept_id") not in local_concept_ids
        }
        external_in_rels: Set[str] = set()
        for rel in reader.relationships():
            for endpoint in (rel.get("from"), rel.get("to")):
                if endpoint and endpoint not in local_concept_ids:
                    external_in_rels.add(endpoint)

        total_external = len(external_in_evidence) + len(external_in_rels)
        result.external_deps = total_external

        if total_external > 0:
            result.add_warning(
                "external_deps",
                f"Cross-ontology referential integrity: backup references {total_external} "
                f"concept_ids not contained in this backup",
                {
                    "external_concepts_in_evidence": len(external_in_evidence),
                    "external_concepts_in_relationships": len(external_in_rels),
                },
            )
            result.add_info(
                "external_deps",
                "These external references create dangling edges unless the referenced "
                "concepts already exist in the target database",
            )


def check_backup_integrity(file_path: str) -> BackupIntegrity:
    """Convenience function to check a backup file's integrity by path."""
    checker = BackupIntegrityChecker()
    return checker.check_file(file_path)


def check_backup_data(data: Dict[str, Any]) -> BackupIntegrity:
    """Convenience function to check a loaded kg-backup/2 object's integrity."""
    checker = BackupIntegrityChecker()
    return checker.check_data(data)
