from pathlib import Path
from alembic_autoseq.models import ConflictType, MigrationFile
from alembic_autoseq.dag import MigrationDAG

def test_dag_linear_clean():
    m1 = MigrationFile(path=Path("0001_a.py"), filename="0001_a.py", revision="0001", down_revision=None, seq_num=1)
    m2 = MigrationFile(path=Path("0002_b.py"), filename="0002_b.py", revision="0002", down_revision="0001", seq_num=2)
    m3 = MigrationFile(path=Path("0003_c.py"), filename="0003_c.py", revision="0003", down_revision="0002", seq_num=3)

    dag = MigrationDAG([m1, m2, m3])
    assert dag.is_clean is True
    assert len(dag.heads) == 1
    assert dag.heads[0].revision == "0003"
    assert dag.get_max_sequence_number() == 3

def test_dag_duplicate_sequence_number():
    m1 = MigrationFile(path=Path("0001_a.py"), filename="0001_a.py", revision="0001", down_revision=None, seq_num=1)
    m2 = MigrationFile(path=Path("0002_a.py"), filename="0002_a.py", revision="0002a", down_revision="0001", seq_num=2)
    m3 = MigrationFile(path=Path("0002_b.py"), filename="0002_b.py", revision="0002b", down_revision="0001", seq_num=2)

    dag = MigrationDAG([m1, m2, m3])
    assert dag.is_clean is False
    conflict_types = [c.type for c in dag.conflicts]
    assert ConflictType.DUPLICATE_SEQUENCE_NUMBER in conflict_types
    assert ConflictType.MULTIPLE_HEADS in conflict_types

def test_dag_missing_down_revision():
    m1 = MigrationFile(path=Path("0002_b.py"), filename="0002_b.py", revision="0002", down_revision="non_existent", seq_num=2)
    dag = MigrationDAG([m1])
    assert dag.is_clean is False
    conflict_types = [c.type for c in dag.conflicts]
    assert ConflictType.MISSING_DOWN_REVISION in conflict_types

