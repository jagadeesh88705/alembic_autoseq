from pathlib import Path
from alembic_autoseq.scanner import (
    parse_sequence_info,
    scan_migration_file,
    rewrite_migration_file,
)

SAMPLE_MIGRATION = '''"""create users table

Revision ID: 0001
Revises: 
Create Date: 2026-01-01 12:00:00

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table('users', sa.Column('id', sa.Integer, primary_key=True))

def downgrade() -> None:
    op.drop_table('users')
'''

def test_parse_sequence_info():
    seq, digits, slug = parse_sequence_info("0001_create_users.py")
    assert seq == 1
    assert digits == 4
    assert slug == "create_users"

    seq, digits, slug = parse_sequence_info("042_add_orders.py")
    assert seq == 42
    assert digits == 3
    assert slug == "add_orders"

    seq, digits, slug = parse_sequence_info("custom_hash.py")
    assert seq is None
    assert slug == "custom_hash"

def test_scan_migration_file(tmp_path: Path):
    file_path = tmp_path / "0001_create_users.py"
    file_path.write_text(SAMPLE_MIGRATION, encoding="utf-8")

    mig = scan_migration_file(file_path)
    assert mig is not None
    assert mig.revision == "0001"
    assert mig.down_revision is None
    assert mig.seq_num == 1
    assert mig.slug == "create_users"

def test_rewrite_migration_file(tmp_path: Path):
    file_path = tmp_path / "0004_add_orders.py"
    file_path.write_text(SAMPLE_MIGRATION, encoding="utf-8")

    # Update revision and down_revision
    modified = rewrite_migration_file(file_path, new_revision="0005", new_down_revision="0004")
    assert modified is True

    mig = scan_migration_file(file_path)
    assert mig is not None
    assert mig.revision == "0005"
    assert mig.down_revision == "0004"

