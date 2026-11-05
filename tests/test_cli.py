from pathlib import Path
from click.testing import CliRunner
from alembic_autoseq.cli import main

def test_cli_tree_and_check(tmp_path: Path):
    runner = CliRunner()
    versions_dir = tmp_path / "versions"
    versions_dir.mkdir()

    # Create a linear sequence
    (versions_dir / "0001_init.py").write_text('''
revision = "0001"
down_revision = None
''', encoding="utf-8")
    (versions_dir / "0002_users.py").write_text('''
revision = "0002"
down_revision = "0001"
''', encoding="utf-8")

    # Run check
    result = runner.invoke(main, ["check", "--dir", str(versions_dir)])
    assert result.exit_code == 0
    assert "All migrations are linear" in result.output

    # Run tree
    result_tree = runner.invoke(main, ["tree", "--dir", str(versions_dir)])
    assert result_tree.exit_code == 0
    assert "0001 -> 0001_init.py" in result_tree.output
    assert "0002 -> 0002_users.py (HEAD)" in result_tree.output

def test_cli_rebase_conflict(tmp_path: Path):
    runner = CliRunner()
    versions_dir = tmp_path / "versions"
    versions_dir.mkdir()

    # Conflicting parallel migrations
    (versions_dir / "0001_init.py").write_text('revision = "0001"\ndown_revision = None\n', encoding="utf-8")
    (versions_dir / "0002_users.py").write_text('revision = "0002"\ndown_revision = "0001"\n', encoding="utf-8")
    (versions_dir / "0002_orders.py").write_text('revision = "0002"\ndown_revision = "0001"\n', encoding="utf-8")

    # check should fail with exit code 1
    result_check = runner.invoke(main, ["check", "--dir", str(versions_dir)])
    assert result_check.exit_code == 1

    # rebase should succeed and heal it
    result_rebase = runner.invoke(main, ["rebase", "--dir", str(versions_dir)])
    assert result_rebase.exit_code == 0
    assert "Successfully healed" in result_rebase.output

    # check should now pass
    result_check_again = runner.invoke(main, ["check", "--dir", str(versions_dir)])
    assert result_check_again.exit_code == 0

