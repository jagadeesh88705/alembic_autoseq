"""
alembic-autoseq: Sequential migration conflict resolver and multi-head guard for Alembic.
"""

from .guard import guard, check, AlembicConflictError
from .models import ConflictType, GuardReport, MigrationFile
from .dag import MigrationDAG
from .scanner import scan_directory, scan_migration_file
from .resolver import MigrationResolver

__version__ = "0.1.0"
__all__ = [
    "guard",
    "check",
    "AlembicConflictError",
    "ConflictType",
    "GuardReport",
    "MigrationFile",
    "MigrationDAG",
    "scan_directory",
    "scan_migration_file",
    "MigrationResolver",
]

