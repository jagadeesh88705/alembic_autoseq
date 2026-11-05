from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Tuple, Union

class ConflictType(str, Enum):
    DUPLICATE_REVISION_ID = "DUPLICATE_REVISION_ID"
    DUPLICATE_SEQUENCE_NUMBER = "DUPLICATE_SEQUENCE_NUMBER"
    MULTIPLE_HEADS = "MULTIPLE_HEADS"
    ORPHAN_DATABASE_REVISION = "ORPHAN_DATABASE_REVISION"
    CYCLE_DETECTED = "CYCLE_DETECTED"
    MISSING_DOWN_REVISION = "MISSING_DOWN_REVISION"

@dataclass
class MigrationFile:
    path: Path
    filename: str
    revision: str
    down_revision: Optional[Union[str, Tuple[str, ...]]] = None
    branch_labels: Optional[Union[str, Tuple[str, ...]]] = None
    depends_on: Optional[Union[str, Tuple[str, ...]]] = None
    seq_num: Optional[int] = None
    num_digits: int = 4
    slug: str = ""
    is_merge_revision: bool = False

    @property
    def has_seq_num(self) -> bool:
        return self.seq_num is not None

@dataclass
class Conflict:
    type: ConflictType
    message: str
    involved_files: List[MigrationFile] = field(default_factory=list)

@dataclass
class ResolutionAction:
    file: MigrationFile
    old_path: Path
    new_path: Path
    old_revision: str
    new_revision: str
    old_down_revision: Optional[Union[str, Tuple[str, ...]]]
    new_down_revision: Optional[Union[str, Tuple[str, ...]]]
    description: str

@dataclass
class GuardReport:
    is_clean: bool
    conflicts: List[Conflict] = field(default_factory=list)
    actions_taken: List[ResolutionAction] = field(default_factory=list)
    heads: List[str] = field(default_factory=list)

