from pathlib import Path
import pytest
from alembic.config import Config
from alembic import command
import alembic_autoseq
from alembic.util.exc import CommandError

def setup_alembic_test_env(tmp_path: Path):
    """Sets up a complete Alembic environment with SQLite database."""
    alembic_dir = tmp_path / "alembic"
    versions_dir = alembic_dir / "versions"
    versions_dir.mkdir(parents=True)

    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path.as_posix()}"

    # Create alembic.ini with absolute script_location
    ini_path = tmp_path / "alembic.ini"
    ini_content = f"""[alembic]
script_location = {alembic_dir.as_posix()}
sqlalchemy.url = {db_url}
"""
    ini_path.write_text(ini_content, encoding="utf-8")

    # Create env.py
    env_content = f"""import os
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import alembic_autoseq

# Auto-guard call: auto-resolves any conflicting revisions before running migrations
alembic_autoseq.guard(auto_heal=True)

config = context.config

def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None
        )

        with context.begin_transaction():
            context.run_migrations()

run_migrations_online()
"""
    (alembic_dir / "env.py").write_text(env_content, encoding="utf-8")

    # Create script.py.mako
    mako_content = """# ${message}
revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}

def upgrade():
    pass

def downgrade():
    pass
"""
    (alembic_dir / "script.py.mako").write_text(mako_content, encoding="utf-8")

    cfg = Config(str(ini_path))
    return cfg, versions_dir

def test_guard_auto_heals_in_live_alembic_upgrade(tmp_path: Path):
    cfg, versions_dir = setup_alembic_test_env(tmp_path)

    # 0001_init
    (versions_dir / "0001_init.py").write_text('''
revision = '0001'
down_revision = None
def upgrade(): pass
def downgrade(): pass
''', encoding="utf-8")

    # Developer A created 0002_user
    (versions_dir / "0002_user.py").write_text('''
revision = '0002'
down_revision = '0001'
def upgrade(): pass
def downgrade(): pass
''', encoding="utf-8")

    # Developer B created 0002_order (conflict! same down_revision and duplicate number)
    (versions_dir / "0002_order.py").write_text('''
revision = '0002'
down_revision = '0001'
def upgrade(): pass
def downgrade(): pass
''', encoding="utf-8")

    # Run upgrade head!
    # Without alembic_autoseq, Alembic would crash with multiple heads/duplicate revision ID.
    # With alembic_autoseq in env.py, it auto-resolves and finishes without error!
    command.upgrade(cfg, "head")

    # Verify that the directory was healed to 0001 -> 0002 -> 0003
    assert (versions_dir / "0001_init.py").exists()
    assert (versions_dir / "0002_user.py").exists()
    assert (versions_dir / "0003_order.py").exists()
