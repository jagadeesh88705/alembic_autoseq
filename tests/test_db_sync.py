from pathlib import Path
from sqlalchemy import create_engine, text
from alembic_autoseq.models import MigrationFile
from alembic_autoseq.dag import MigrationDAG
from alembic_autoseq.db import check_db_revisions_sync

def test_db_orphan_revision_auto_reconciled(tmp_path: Path):
    db_file = tmp_path / "sync_test.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")

    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        # Peer migrated their branch '0004_peer' into shared DB
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('0004_peer')"))

    # Current developer's branch only has up to 0003, and their own 0004_my_feature
    m1 = MigrationFile(path=Path("0001.py"), filename="0001.py", revision="0001", down_revision=None, seq_num=1)
    m2 = MigrationFile(path=Path("0002.py"), filename="0002.py", revision="0002", down_revision="0001", seq_num=2)
    m3 = MigrationFile(path=Path("0003.py"), filename="0003.py", revision="0003", down_revision="0002", seq_num=3)
    m4 = MigrationFile(path=Path("0004.py"), filename="0004.py", revision="0004", down_revision="0003", seq_num=4)

    dag = MigrationDAG([m1, m2, m3, m4])

    with engine.begin() as conn:
        conflicts, actions = check_db_revisions_sync(conn, dag, auto_heal=True)
        assert len(conflicts) == 1
        assert "0004_peer" in conflicts[0].message
        assert len(actions) == 1

        # Check DB was restamped back to 0003 so 0004 can be safely applied
        res = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert res == "0003"

