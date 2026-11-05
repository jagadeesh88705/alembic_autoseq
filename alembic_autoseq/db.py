import logging
from typing import List, Optional, Set, Tuple
from sqlalchemy import text
from sqlalchemy.engine import Engine, Connection
from .dag import MigrationDAG
from .models import Conflict, ConflictType, MigrationFile

logger = logging.getLogger("alembic_autoseq")

def get_db_current_revisions(connection: Connection) -> List[str]:
    """Inspects the live database alembic_version table to retrieve active revision stamps."""
    try:
        result = connection.execute(text("SELECT version_num FROM alembic_version"))
        return [row[0] for row in result.fetchall() if row[0]]
    except Exception as e:
        # Table might not exist yet (fresh DB)
        logger.debug("Could not read alembic_version table: %s", e)
        return []

def check_db_revisions_sync(
    connection: Connection,
    dag: MigrationDAG,
    auto_heal: bool = True
) -> Tuple[List[Conflict], List[str]]:
    """
    Checks if the database is stamped with a revision from another developer/branch
    that does NOT exist in the current working copy's migration files.
    """
    conflicts: List[Conflict] = []
    actions_taken: List[str] = []

    db_revs = get_db_current_revisions(connection)
    if not db_revs:
        return conflicts, actions_taken

    orphan_revs: List[str] = [rev for rev in db_revs if rev not in dag.by_revision]

    if orphan_revs:
        msg = (
            f"Database has active revision(s) {orphan_revs} from another developer or branch, "
            f"but these files do not exist in your current branch!"
        )
        conflicts.append(Conflict(
            type=ConflictType.ORPHAN_DATABASE_REVISION,
            message=msg,
            involved_files=[]
        ))

        if auto_heal:
            # Reconcile DB back to the highest common known revision in this branch
            # If nothing known, fallback to roots
            target_rev = None
            if dag.heads:
                # Find the latest parent revision available
                latest_head = dag.heads[0]
                target_rev = latest_head.down_revision if isinstance(latest_head.down_revision, str) else None

            if not target_rev and dag.roots:
                target_rev = dag.roots[0].revision

            if target_rev:
                try:
                    connection.execute(text("DELETE FROM alembic_version"))
                    connection.execute(
                        text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
                        {"rev": target_rev}
                    )
                    action_msg = f"Re-stamped database alembic_version from orphan {orphan_revs} back to known revision '{target_rev}'"
                    actions_taken.append(action_msg)
                    logger.info("🔧 [alembic-autoseq] %s", action_msg)
                except Exception as e:
                    logger.warning("Could not auto-restamp database: %s", e)

    return conflicts, actions_taken

