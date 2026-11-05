import time
from pathlib import Path
from alembic_autoseq.scanner import scan_directory
from alembic_autoseq.dag import MigrationDAG
from alembic_autoseq.resolver import MigrationResolver

def create_migration_script(dir_path: Path, filename: str, revision: str, down_revision: str) -> Path:
    down_repr = "None" if down_revision is None else repr(down_revision)
    content = f'''"""sample migration

Revision ID: {revision}
Revises: {down_revision}
"""
from alembic import op
import sqlalchemy as sa

revision = {repr(revision)}
down_revision = {down_repr}
branch_labels = None
depends_on = None

def upgrade() -> None:
    pass

def downgrade() -> None:
    pass
'''
    p = dir_path / filename
    p.write_text(content, encoding="utf-8")
    return p

def test_resolve_parallel_branch_collision(tmp_path: Path):
    versions_dir = tmp_path / "versions"
    versions_dir.mkdir()

    # Base migrations (0001, 0002, 0003)
    create_migration_script(versions_dir, "0001_init.py", revision="0001", down_revision=None)
    create_migration_script(versions_dir, "0002_accounts.py", revision="0002", down_revision="0001")
    create_migration_script(versions_dir, "0003_profiles.py", revision="0003", down_revision="0002")

    # Developer A created 0004_users.py
    f_a = create_migration_script(versions_dir, "0004_users.py", revision="0004", down_revision="0003")

    time.sleep(0.05) # ensure timestamp difference for deterministic branch candidate selection

    # Developer B created 0004_orders.py (parallel branch conflict!)
    f_b = create_migration_script(versions_dir, "0004_orders.py", revision="0004", down_revision="0003")

    # Verify conflict exists before resolution
    initial_dag = MigrationDAG(scan_directory(versions_dir))
    assert initial_dag.is_clean is False
    assert len(initial_dag.heads) == 2

    # Run resolver
    resolver = MigrationResolver(versions_dir)
    actions = resolver.resolve()

    assert len(actions) >= 1
    
    # Verify post-resolution state
    resolved_dag = MigrationDAG(scan_directory(versions_dir))
    assert resolved_dag.is_clean is True
    assert len(resolved_dag.heads) == 1
    assert resolved_dag.heads[0].revision == "0005"
    assert resolved_dag.heads[0].seq_num == 5
    assert (versions_dir / "0005_orders.py").exists()

