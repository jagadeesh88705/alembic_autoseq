from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple, Union
from .models import Conflict, ConflictType, MigrationFile

class MigrationDAG:
    """Represents the Directed Acyclic Graph (DAG) of Alembic migrations."""

    def __init__(self, migrations: List[MigrationFile]):
        self.migrations = migrations
        self.by_revision: Dict[str, MigrationFile] = {}
        self.children: Dict[str, List[MigrationFile]] = defaultdict(list)
        self.roots: List[MigrationFile] = []
        self.heads: List[MigrationFile] = []
        self.conflicts: List[Conflict] = []

        self._build()

    def _build(self) -> None:
        self.by_revision.clear()
        self.children.clear()
        self.roots.clear()
        self.heads.clear()
        self.conflicts.clear()

        # 1. Check for duplicate revision IDs
        seen_revisions: Dict[str, List[MigrationFile]] = defaultdict(list)
        for m in self.migrations:
            seen_revisions[m.revision].append(m)

        for rev_id, files in seen_revisions.items():
            if len(files) > 1:
                self.conflicts.append(
                    Conflict(
                        type=ConflictType.DUPLICATE_REVISION_ID,
                        message=f"Duplicate revision ID '{rev_id}' found across {len(files)} files: {[f.filename for f in files]}",
                        involved_files=files,
                    )
                )

        # 2. Check for duplicate sequence numbers (e.g. two 0004_ files)
        seen_seq_nums: Dict[int, List[MigrationFile]] = defaultdict(list)
        for m in self.migrations:
            if m.has_seq_num and m.seq_num is not None:
                seen_seq_nums[m.seq_num].append(m)

        for seq_num, files in seen_seq_nums.items():
            if len(files) > 1:
                self.conflicts.append(
                    Conflict(
                        type=ConflictType.DUPLICATE_SEQUENCE_NUMBER,
                        message=f"Duplicate sequence number '{seq_num}' found across files: {[f.filename for f in files]}",
                        involved_files=files,
                    )
                )

        # Store primary mapping (using first seen if duplicate)
        for m in self.migrations:
            if m.revision not in self.by_revision:
                self.by_revision[m.revision] = m

        # 3. Build graph edges
        referenced_down_revs: Set[str] = set()
        for m in self.migrations:
            down_rev = m.down_revision
            if down_rev is None:
                self.roots.append(m)
            elif isinstance(down_rev, str):
                self.children[down_rev].append(m)
                referenced_down_revs.add(down_rev)
            elif isinstance(down_rev, tuple):
                for dr in down_rev:
                    self.children[dr].append(m)
                    referenced_down_revs.add(dr)

        # 4. Check for missing down_revisions
        for dr in referenced_down_revs:
            if dr not in self.by_revision:
                affected_files = [
                    m for m in self.migrations
                    if (isinstance(m.down_revision, str) and m.down_revision == dr)
                    or (isinstance(m.down_revision, tuple) and dr in m.down_revision)
                ]
                self.conflicts.append(
                    Conflict(
                        type=ConflictType.MISSING_DOWN_REVISION,
                        message=f"Migration points to non-existent down_revision '{dr}' in: {[f.filename for f in affected_files]}",
                        involved_files=affected_files,
                    )
                )

        # 5. Detect Heads (nodes with no children)
        for m in self.migrations:
            if not self.children[m.revision]:
                self.heads.append(m)

        if len(self.heads) > 1:
            self.conflicts.append(
                Conflict(
                    type=ConflictType.MULTIPLE_HEADS,
                    message=f"Multiple heads detected ({len(self.heads)} heads): {[h.revision + ' (' + h.filename + ')' for h in self.heads]}",
                    involved_files=self.heads,
                )
            )

    @property
    def is_clean(self) -> bool:
        return len(self.conflicts) == 0

    def get_max_sequence_number(self) -> int:
        max_seq = 0
        for m in self.migrations:
            if m.seq_num is not None and m.seq_num > max_seq:
                max_seq = m.seq_num
        return max_seq

    def get_ancestors(self, revision: str) -> List[str]:
        """Returns ordered list of ancestors from root to given revision."""
        ancestors: List[str] = []
        curr = revision
        visited = set()
        while curr and curr not in visited:
            visited.add(curr)
            ancestors.append(curr)
            node = self.by_revision.get(curr)
            if not node or node.down_revision is None:
                break
            if isinstance(node.down_revision, str):
                curr = node.down_revision
            else:
                # Merge revision: pick first ancestor
                curr = node.down_revision[0] if node.down_revision else None
        ancestors.reverse()
        return ancestors

