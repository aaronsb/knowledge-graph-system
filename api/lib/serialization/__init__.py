"""
kg-backup/2 serialization package (ADR-102).

Re-exports the public surface so ``from api.lib.serialization import ...`` keeps
working unchanged after the P6d split of the former single-module file into
:mod:`format`, :mod:`exporter`, and :mod:`importer`.
"""

from .format import BackupFormat, KgBackupV2Reader, KG_BACKUP_FORMAT_VERSION
from .exporter import DataExporter
from .importer import DataImporter

__all__ = [
    "BackupFormat",
    "KgBackupV2Reader",
    "KG_BACKUP_FORMAT_VERSION",
    "DataExporter",
    "DataImporter",
]
