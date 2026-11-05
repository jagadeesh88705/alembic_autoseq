import os
import subprocess
from pathlib import Path
from typing import List, Optional, Set, Tuple
from .dag import MigrationDAG
from .models import ConflictType, MigrationFile, ResolutionAction
from .scanner import rewrite_migration_file, scan_directory

def get_git_modified_files(repo_root: Optional[Path] = None) -> Set[str]:
    """Returns set of relative file paths modified/added in the current Git working tree or branch."""
    modified: Set[str] = set()
    try:
        # Check uncommitted untracked / modified files
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root or "."),
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                if len(line) > 3:
                    path_str = line[3:].strip().strip('"')
                    modified.add(Path(path_str).name)

        # Also check files changed against main/master if possible
        for target_branch in ["main", "master", "origin/main", "origin/master"]:
            diff_res = subprocess.run(
                ["git", "diff", "--name-only", f"{target_branch}...HEAD"],
                cwd=str(repo_root or "."),
                capture_output=True,
                text=True,
                check=False,
            )
            if diff_res.returncode == 0 and diff_res.stdout.strip():
                for line in diff_res.stdout.splitlines():
                    modified.add(Path(line.strip()).name)
                break
    except Exception:
        pass
    return modified

def choose_rebase_candidate(
    candidates: List[MigrationFile],
    versions_dir: Path
) -> Tuple[MigrationFile, MigrationFile]:
    """
    Given a list of conflicting head migrations, determines which one is the
    'upstream' head (keep intact) and which one is the 'branch' candidate to rebase.
    Returns (upstream_head, branch_candidate).
    """
    # 1. Prefer git status: if one file is uncommitted or in git diff, that is the branch candidate
    git_modified = get_git_modified_files(versions_dir.parent)
    for c in candidates:
        if c.filename in git_modified:
            others = [other for other in candidates if other.filename != c.filename]
            if others:
                return others[0], c

    # 2. Prefer file modification timestamp if there is a distinct difference
    try:
        sorted_by_mtime = sorted(
            candidates,
            key=lambda f: f.path.stat().st_mtime if f.path.exists() else 0
        )
        t_first = sorted_by_mtime[0].path.stat().st_mtime
        t_last = sorted_by_mtime[-1].path.stat().st_mtime
        if (t_last - t_first) >= 0.05:  # At least 50ms difference
            return sorted_by_mtime[0], sorted_by_mtime[-1]
    except Exception:
        pass

    # 3. Deterministic fallback: alphabetical filename order
    sorted_alpha = sorted(candidates, key=lambda f: f.filename)
    return sorted_alpha[0], sorted_alpha[-1]

class MigrationResolver:
    """Detects and automatically resolves revision conflicts and multi-head branching."""

    def __init__(self, versions_dir: Path, digits: Optional[int] = None):
        self.versions_dir = versions_dir
        self.digits = digits

    def resolve(self, max_iterations: int = 10) -> List[ResolutionAction]:
        """
        Iteratively resolves conflicts (duplicate sequence numbers, duplicate IDs, multiple heads)
        until the migration DAG is clean and linear, or max_iterations is reached.
        """
        all_actions: List[ResolutionAction] = []

        for _ in range(max_iterations):
            migrations = scan_directory(self.versions_dir)
            dag = MigrationDAG(migrations)

            if dag.is_clean:
                break

            action_taken = False

            # Check 1: Duplicate revision IDs or Duplicate Sequence Numbers
            seq_conflicts = [c for c in dag.conflicts if c.type in (
                ConflictType.DUPLICATE_SEQUENCE_NUMBER,
                ConflictType.DUPLICATE_REVISION_ID,
                ConflictType.MULTIPLE_HEADS
            )]

            if not seq_conflicts:
                break

            # Handle multiple heads or sequence collisions
            heads = dag.heads
            if len(heads) >= 2:
                upstream, branch = choose_rebase_candidate(heads, self.versions_dir)
                action = self._rebase_branch_on_head(dag, upstream, branch)
                if action:
                    all_actions.append(action)
                    action_taken = True
            elif any(c.type == ConflictType.DUPLICATE_SEQUENCE_NUMBER for c in dag.conflicts):
                # Duplicate sequence numbers without multiple heads
                for conflict in dag.conflicts:
                    if conflict.type == ConflictType.DUPLICATE_SEQUENCE_NUMBER and len(conflict.involved_files) >= 2:
                        upstream, branch = choose_rebase_candidate(conflict.involved_files, self.versions_dir)
                        action = self._rebase_branch_on_head(dag, upstream, branch)
                        if action:
                            all_actions.append(action)
                            action_taken = True
                            break

            if not action_taken:
                # Could not resolve remaining conflicts automatically
                break

        return all_actions

    def _rebase_branch_on_head(
        self,
        dag: MigrationDAG,
        upstream_head: MigrationFile,
        branch_candidate: MigrationFile,
    ) -> Optional[ResolutionAction]:
        """Rebases branch_candidate so its down_revision becomes upstream_head.revision."""
        max_seq = dag.get_max_sequence_number()
        next_seq = max_seq + 1
        num_digits = self.digits or branch_candidate.num_digits or 4
        new_seq_prefix = f"{next_seq:0{num_digits}d}"

        old_path = branch_candidate.path
        old_revision = branch_candidate.revision
        old_down_revision = branch_candidate.down_revision

        # Determine new revision and new filename
        # If the revision was prefixed with old sequence number, update it
        if branch_candidate.seq_num is not None:
            old_seq_prefix = f"{branch_candidate.seq_num:0{num_digits}d}"
            if old_revision.startswith(old_seq_prefix):
                new_revision = old_revision.replace(old_seq_prefix, new_seq_prefix, 1)
            else:
                new_revision = new_seq_prefix
            
            # Construct new filename
            slug_part = f"_{branch_candidate.slug}" if branch_candidate.slug else ""
            new_filename = f"{new_seq_prefix}{slug_part}.py"
        else:
            # Hash-based revision: keep revision or prepend sequence
            new_revision = old_revision
            new_filename = f"{new_seq_prefix}_{branch_candidate.filename}"

        new_down_revision = upstream_head.revision
        new_path = self.versions_dir / new_filename

        # 1. Update file contents
        rewrite_migration_file(
            old_path,
            new_revision=new_revision,
            new_down_revision=new_down_revision,
        )

        # 2. Rename file on disk if filename changed
        if old_path != new_path:
            old_path.rename(new_path)

        return ResolutionAction(
            file=branch_candidate,
            old_path=old_path,
            new_path=new_path,
            old_revision=old_revision,
            new_revision=new_revision,
            old_down_revision=old_down_revision,
            new_down_revision=new_down_revision,
            description=f"Rebased '{branch_candidate.filename}' -> '{new_filename}' on top of '{upstream_head.revision}'",
        )

