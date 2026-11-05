import sys
from pathlib import Path
from typing import Optional
import click
from .dag import MigrationDAG
from .guard import find_versions_dir, guard
from .resolver import MigrationResolver
from .scanner import scan_directory

@click.group()
@click.version_option()
def main():
    """alembic-autoseq: Sequential migration conflict resolver and multi-head guard for Alembic."""
    pass

@main.command()
@click.option("--dir", "-d", "directory", type=click.Path(exists=True), help="Path to versions directory.")
def check(directory: Optional[str]):
    """Verify that migrations have no multi-heads or numbering collisions (CI check)."""
    v_dir = Path(directory) if directory else find_versions_dir()
    if not v_dir:
        click.echo("Error: Could not locate Alembic versions directory.", err=True)
        sys.exit(1)

    migrations = scan_directory(v_dir)
    dag = MigrationDAG(migrations)

    if dag.is_clean:
        click.secho("✅ All migrations are linear with no conflicts or duplicate sequence numbers.", fg="green")
        sys.exit(0)
    else:
        click.secho(f"❌ Found {len(dag.conflicts)} conflict(s):", fg="red", bold=True)
        for c in dag.conflicts:
            click.echo(f"  • [{c.type.value}] {c.message}")
        sys.exit(1)

@main.command()
@click.option("--dir", "-d", "directory", type=click.Path(exists=True), help="Path to versions directory.")
def rebase(directory: Optional[str]):
    """Automatically resolve multi-head branch conflicts and re-sequence migrations."""
    v_dir = Path(directory) if directory else find_versions_dir()
    if not v_dir:
        click.echo("Error: Could not locate Alembic versions directory.", err=True)
        sys.exit(1)

    click.echo(f"Scanning versions directory: {v_dir}")
    report = guard(directory=v_dir, auto_heal=True, quiet=False)

    if report.is_clean:
        if report.actions_taken:
            click.secho(f"✅ Successfully healed {len(report.actions_taken)} migration conflict(s).", fg="green", bold=True)
        else:
            click.secho("✅ Migration history is already clean and linear.", fg="green")
        sys.exit(0)
    else:
        click.secho("⚠️ Could not automatically resolve all conflicts:", fg="yellow", bold=True)
        for c in report.conflicts:
            click.echo(f"  • {c.message}")
        sys.exit(1)

@main.command()
@click.option("--dir", "-d", "directory", type=click.Path(exists=True), help="Path to versions directory.")
def tree(directory: Optional[str]):
    """Print an ASCII visualization of the migration history DAG."""
    v_dir = Path(directory) if directory else find_versions_dir()
    if not v_dir:
        click.echo("Error: Could not locate Alembic versions directory.", err=True)
        sys.exit(1)

    migrations = scan_directory(v_dir)
    dag = MigrationDAG(migrations)

    click.echo(f"\n📂 Versions Directory: {v_dir}")
    click.echo(f"Total Migrations: {len(migrations)} | Heads: {len(dag.heads)}\n")

    # Render roots to heads
    for root in dag.roots:
        _print_node(root, dag, prefix="", is_last=True)

    if not dag.is_clean:
        click.echo("")
        click.secho(f"⚠️ Conflicts ({len(dag.conflicts)}):", fg="yellow", bold=True)
        for c in dag.conflicts:
            click.echo(f"  - {c.message}")
    else:
        click.echo("")
        click.secho("✨ DAG is clean and linear.", fg="green")

def _print_node(node, dag: MigrationDAG, prefix: str = "", is_last: bool = True):
    connector = "└── " if is_last else "├── "
    is_head = node in dag.heads
    head_tag = " (HEAD)" if is_head else ""
    seq_str = f"[{node.seq_num:0{node.num_digits}d}] " if node.seq_num is not None else ""
    
    click.echo(f"{prefix}{connector}{seq_str}{node.revision} -> {node.filename}{head_tag}")

    children = dag.children.get(node.revision, [])
    new_prefix = prefix + ("    " if is_last else "│   ")
    for i, child in enumerate(children):
        _print_node(child, dag, prefix=new_prefix, is_last=(i == len(children) - 1))

if __name__ == "__main__":
    main()

