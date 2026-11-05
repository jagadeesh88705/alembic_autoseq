import logging
import os
import sys
from pathlib import Path
from typing import Optional, Union
from .dag import MigrationDAG
from .db import check_db_revisions_sync
from .models import GuardReport, ResolutionAction
from .resolver import MigrationResolver
from .scanner import scan_directory

logger = logging.getLogger("alembic_autoseq")

class AlembicConflictError(Exception):
    """Raised when migration conflicts or multi-heads are detected and auto_heal is disabled."""
    pass

def find_versions_dir(start_dir: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """Auto-detects the Alembic versions directory in common project structures."""
    # 0. Check if running inside Alembic context (e.g. from env.py)
    try:
        from alembic import context
        if hasattr(context, "script") and context.script is not None:
            script_path = Path(context.script.dir)
            if (script_path / "versions").exists():
                return script_path / "versions"
            if script_path.exists():
                return script_path
    except Exception:
        pass

    curr = Path(start_dir or os.getcwd()).resolve()

    # Search current and up to 4 parent directories
    for _ in range(5):
        # 1. Check alembic.ini if present
        ini_file = curr / "alembic.ini"
        if ini_file.exists():
            try:
                for line in ini_file.read_text(encoding="utf-8").splitlines():
                    clean_line = line.strip()
                    if clean_line.startswith("script_location"):
                        parts = clean_line.split("=", 1)
                        if len(parts) == 2:
                            loc = parts[1].strip()
                            loc_path = Path(loc)
                            target = loc_path if loc_path.is_absolute() else (curr / loc)
                            v_dir = target / "versions"
                            if v_dir.exists():
                                return v_dir
            except Exception:
                pass

        # 2. Check standard directory layouts
        for candidate in [
            curr / "alembic" / "versions",
            curr / "migrations" / "versions",
            curr / "db" / "migrations" / "versions",
            curr / "database" / "migrations" / "versions",
            curr / "versions",
        ]:
            if candidate.exists() and candidate.is_dir():
                return candidate

        parent = curr.parent
        if parent == curr:
            break
        curr = parent

    return None

def guard(
    directory: Optional[Union[str, Path]] = None,
    connection=None,
    auto_heal: bool = True,
    strict: bool = False,
    quiet: bool = False,
    digits: Optional[int] = None,
) -> GuardReport:
    """
    Primary production entry point to protect Alembic migrations against multi-heads and collisions.

    Example in alembic/env.py:
        import alembic_autoseq
        alembic_autoseq.guard()

    :param directory: Explicit path to migrations versions directory (auto-detected if None).
    :param connection: Optional database connection to check for shared DB orphan revisions.
    :param auto_heal: If True, automatically rebases and re-sequences conflicting branch migrations.
    :param strict: If True, raises AlembicConflictError if any conflicts remain.
    :param quiet: If True, suppresses console logs.
    :param digits: Optional sequence digit padding (e.g. 4 for 0001, 3 for 001).
    :return: GuardReport with DAG status, conflicts found, and actions taken.
    """
    v_dir = Path(directory) if directory else find_versions_dir()
    if not v_dir or not v_dir.exists():
        if not quiet:
            logger.debug("[alembic-autoseq] No versions directory found; skipping check.")
        return GuardReport(is_clean=True)

    # Initial scan
    migrations = scan_directory(v_dir)
    dag = MigrationDAG(migrations)

    actions = []
    if not dag.is_clean:
        if auto_heal:
            resolver = MigrationResolver(v_dir, digits=digits)
            actions = resolver.resolve()
            
            # Re-scan after resolution
            migrations = scan_directory(v_dir)
            dag = MigrationDAG(migrations)

            # Refresh Alembic's internal RevisionMap in memory if active in context
            try:
                from alembic import context
                from alembic.script.revision import RevisionMap
                if hasattr(context, "script") and context.script is not None:
                    context.script.revision_map = RevisionMap(context.script._load_revisions)
            except Exception:
                pass

            if actions and not quiet:
                for act in actions:
                    logger.info("🔧 [alembic-autoseq] %s", act.description)
                    if not logging.getLogger().handlers:
                        # Fallback to stdout if application has not configured logging handlers
                        print(f"🔧 [alembic-autoseq] {act.description}")

    # Check for orphan database revisions if database connection is available
    conn = connection
    if conn is None:
        try:
            from alembic import context
            if not context.is_offline_mode():
                conn = context.get_bind()
        except Exception:
            pass

    if conn is not None:
        db_conflicts, db_actions = check_db_revisions_sync(conn, dag, auto_heal=auto_heal)
        if db_conflicts and not auto_heal:
            dag.conflicts.extend(db_conflicts)

    if not dag.is_clean and (strict or not auto_heal):
        conflict_msgs = "\n".join(f"  - {c.message}" for c in dag.conflicts)
        raise AlembicConflictError(
            f"Alembic migration conflicts detected:\n{conflict_msgs}"
        )

    return GuardReport(
        is_clean=dag.is_clean,
        conflicts=dag.conflicts,
        actions_taken=actions,
        heads=[h.revision for h in dag.heads],
    )

def check(directory: Optional[Union[str, Path]] = None) -> bool:
    """Non-destructive validation check. Returns True if clean, False if conflicts exist."""
    report = guard(directory=directory, auto_heal=False, strict=False, quiet=True)
    return report.is_clean
