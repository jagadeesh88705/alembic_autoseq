import ast
import re
from pathlib import Path
from typing import List, Optional, Tuple, Union
from .models import MigrationFile

SEQ_PREFIX_REGEX = re.compile(r"^(\d+)[_\-\.](.*)\.py$")
PLAIN_SEQ_REGEX = re.compile(r"^(\d+)\.py$")

REVISION_VAR_REGEX = re.compile(
    r"^(?P<indent>\s*)revision\s*(?::\s*[^=]+)?\s*=\s*(?P<val>None|'[^']*'|\"[^\"]*\")",
    re.MULTILINE
)

DOWN_REVISION_VAR_REGEX = re.compile(
    r"^(?P<indent>\s*)down_revision\s*(?::\s*[^=]+)?\s*=\s*(?P<val>None|'[^']*'|\"[^\"]*\"|\([^\)]*\)|\[[^\]]*\])",
    re.MULTILINE
)

def parse_sequence_info(filename: str) -> Tuple[Optional[int], int, str]:
    """Extracts sequence number, digit width, and slug from filename."""
    match = SEQ_PREFIX_REGEX.match(filename)
    if match:
        raw_digits, slug = match.groups()
        return int(raw_digits), len(raw_digits), slug
    plain_match = PLAIN_SEQ_REGEX.match(filename)
    if plain_match:
        raw_digits = plain_match.group(1)
        return int(raw_digits), len(raw_digits), ""
    return None, 4, Path(filename).stem

def scan_migration_file(file_path: Path) -> Optional[MigrationFile]:
    """Safely inspects an alembic migration script using AST to extract metadata."""
    if not file_path.is_file() or not file_path.name.endswith(".py"):
        return None
    if file_path.name.startswith("__"):
        return None

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except Exception:
        # Ignore syntax error or unreadable files
        return None

    revision: Optional[str] = None
    down_revision: Optional[Union[str, Tuple[str, ...]]] = None
    branch_labels = None
    depends_on = None

    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target_id = None
            if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                target_id = node.targets[0].id
                value_node = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                target_id = node.target.id
                value_node = node.value
            else:
                continue

            if target_id == "revision" and value_node is not None:
                if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
                    revision = value_node.value
            elif target_id == "down_revision" and value_node is not None:
                if isinstance(value_node, ast.Constant):
                    down_revision = value_node.value
                elif isinstance(value_node, (ast.Tuple, ast.List)):
                    elements = []
                    for elt in value_node.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            elements.append(elt.value)
                    down_revision = tuple(elements)

    if revision is None:
        # Not a valid Alembic migration file
        return None

    seq_num, num_digits, slug = parse_sequence_info(file_path.name)
    is_merge = isinstance(down_revision, tuple) and len(down_revision) > 1

    return MigrationFile(
        path=file_path,
        filename=file_path.name,
        revision=str(revision),
        down_revision=down_revision,
        branch_labels=branch_labels,
        depends_on=depends_on,
        seq_num=seq_num,
        num_digits=num_digits,
        slug=slug,
        is_merge_revision=is_merge,
    )

def scan_directory(versions_dir: Path) -> List[MigrationFile]:
    """Scans all migration files in a versions directory."""
    if not versions_dir.exists() or not versions_dir.is_dir():
        return []
    
    migrations = []
    for file_path in versions_dir.iterdir():
        migration = scan_migration_file(file_path)
        if migration:
            migrations.append(migration)
            
    return migrations

def rewrite_migration_file(
    file_path: Path,
    new_revision: Optional[str] = None,
    new_down_revision: Optional[Union[str, Tuple[str, ...]]] = None,
) -> bool:
    """Safely updates revision and/or down_revision in a migration file preserving formatting."""
    content = file_path.read_text(encoding="utf-8")
    modified = False

    if new_revision is not None:
        def repl_rev(match: re.Match) -> str:
            indent = match.group("indent")
            return f"{indent}revision = {repr(new_revision)}"
        new_content, count = REVISION_VAR_REGEX.subn(repl_rev, content, count=1)
        if count > 0:
            content = new_content
            modified = True

    if new_down_revision is not None:
        def repl_down_rev(match: re.Match) -> str:
            indent = match.group("indent")
            if new_down_revision is None:
                val_repr = "None"
            elif isinstance(new_down_revision, tuple):
                val_repr = repr(new_down_revision)
            else:
                val_repr = repr(new_down_revision)
            return f"{indent}down_revision = {val_repr}"
        new_content, count = DOWN_REVISION_VAR_REGEX.subn(repl_down_rev, content, count=1)
        if count > 0:
            content = new_content
            modified = True

    if modified:
        file_path.write_text(content, encoding="utf-8")
    return modified

