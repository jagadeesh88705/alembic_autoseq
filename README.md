# alembic-autoseq 🛡️

[![CI](https://github.com/jagadeesh88705/alembic_autoseq/actions/workflows/ci.yml/badge.svg)](https://github.com/jagadeesh88705/alembic_autoseq/actions)
[![PyPI version](https://img.shields.io/pypi/v/alembic-autoseq.svg)](https://pypi.org/project/alembic-autoseq/)
[![Python versions](https://img.shields.io/pypi/pyversions/alembic-autoseq.svg)](https://pypi.org/project/alembic-autoseq/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Alembic AutoSeq** automatically reconciles sequential migration numbers, resolves duplicate revision IDs, and heals multi-head branch conflicts for teams developing with **SQLAlchemy** and **Alembic** in parallel.

---

## ⚡ The Problem: Alembic Migration Conflicts in Parallel Development

When multiple developers work on different Git feature branches off the same base migration:

1. **Duplicate Sequence Numbers:** Developer A creates `0004_add_orders.py` and Developer B creates `0004_add_inventory.py`. Both files share sequence number `0004` and point to `down_revision = '0003'`.
2. **Multiple Heads Crash:** Running `alembic upgrade head` crashes with:
   ```text
   alembic.util.exc.CommandError: Multiple head revisions are present for given argument 'head'; please specify a revision or 'heads'
   ```
3. **Missing Revision Crash on Shared DBs:** When testing on a shared dev/staging database, Developer A applies their migration. When Developer B pulls or switches branches, Alembic crashes with:
   ```text
   alembic.util.exc.CommandError: Can't locate revision identified by '0004_add_orders'
   ```
4. **The "Silent Skip" Hazard:** If both developers use the same revision string (e.g. `'0004'`), Alembic thinks the migration has already run and **silently skips** creating the new tables, causing unexpected runtime SQL errors.

---

## ⚖️ Comparison: `alembic merge` vs. `alembic-autoseq`

Alembic provides a native command `alembic merge heads`, but its behavior is often undesirable for teams using human-readable sequential migrations:

| Feature / Behavior | Standard `alembic merge` | `alembic-autoseq` |
| :--- | :--- | :--- |
| **Migration History Graph** | Creates diamond merge nodes (`merge_heads_rev.py`) that clutter migration history | Maintains a **clean, 100% linear chain** (`0001 -> 0002 -> 0003 -> 0004 -> 0005`) |
| **Sequential File Renaming** | ❌ No. Keeps duplicate prefixes like two `0004_` files | ✅ Yes. Automatically renames `0004_` to `0005_` on disk |
| **Revision ID Updating** | ❌ Leaves duplicate revision IDs intact | ✅ Safely updates `revision` and `down_revision` variables via AST |
| **Shared Database Desync** | ❌ Crashes with `Can't locate revision` | ✅ Auto-reconciles DB stamp to highest common ancestor |
| **Developer Overhead** | Requires manual developer intervention and extra merge commits | **Zero overhead**: automatically runs via a **single line** in `env.py` |

### ⚠️ When NOT to use `alembic-autoseq`
* **Historical / Production Migrations:** Never use AutoSeq to renumber migrations that have already been applied to production. AutoSeq is strictly designed to reconcile **active, unmerged branch migrations** before they hit `main` or production.
* **Complex Multi-Database Branches:** If your architecture intentionally relies on complex non-linear DAG branching across separate database clusters, use Alembic's native multi-head tracking.

---

## 🚀 Quick Start (1-Line Integration)

### 1. Install via pip
```bash
pip install alembic-autoseq
```

### 2. Add to your `alembic/env.py`
In your `alembic/env.py`, add `alembic_autoseq.guard()` inside `run_migrations_online()`:

```python
import alembic_autoseq

def run_migrations_online():
    connectable = engine_from_config(...)

    with connectable.connect() as connection:
        # Automatically detects conflicts and heals branch revision links before Alembic runs
        alembic_autoseq.guard(connection=connection, auto_heal=True)

        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()
```

Now, whenever you run `alembic upgrade head`, any parallel branch collisions are **automatically linearized and applied without crashing**.

---

## 🛠️ CLI Usage & CI/CD Guard

`alembic-autoseq` comes with a CLI for local validation and automated CI checks:

### 1. Pre-Merge CI Validation (`check`)
Fails with exit code `1` if any duplicate sequence numbers or multiple heads are present. Perfect for GitHub Actions or pre-commit hooks:
```bash
alembic-autoseq check
```
Output when conflict exists:
```text
❌ Found 3 conflict(s):
  • [DUPLICATE_REVISION_ID] Duplicate revision ID '0004' found across 2 files: ['0004_add_inventory.py', '0004_add_orders.py']
  • [DUPLICATE_SEQUENCE_NUMBER] Duplicate sequence number '4' found across files: ['0004_add_inventory.py', '0004_add_orders.py']
  • [MULTIPLE_HEADS] Multiple heads detected (2 heads): ['0004 (0004_add_inventory.py)', '0004 (0004_add_orders.py)']
```

### 2. Auto-Rebase (`rebase`)
Automatically re-links the active branch migration to the latest upstream head and increments sequence numbers:
```bash
alembic-autoseq rebase
```

### 3. Migration DAG Tree Visualizer (`tree`)
Prints an ASCII tree of the migration DAG directly in your terminal:
```bash
alembic-autoseq tree
```
```text
📂 Versions Directory: /path/to/alembic/versions
Total Migrations: 5 | Heads: 1

└── [0001] 0001 -> 0001_initial_tables.py
    └── [0002] 0002 -> 0002_add_roles.py
        └── [0003] 0003 -> 0003_add_departments.py
            └── [0004] 0004 -> 0004_add_orders.py
                └── [0005] 0005 -> 0005_add_inventory.py (HEAD)

✨ DAG is clean and linear.
```

---

## 🤖 GitHub Actions CI Workflow

Add this step to your GitHub Actions `.github/workflows/ci.yml` to prevent broken migration chains from being merged into `main`:

```yaml
name: Migrations Guard
on: [pull_request]

jobs:
  check-migrations:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install alembic-autoseq
        run: pip install alembic-autoseq
      - name: Verify migration linearity
        run: alembic-autoseq check
```

---

## 🪝 Pre-Commit Hook Integration

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/jagadeesh88705/alembic_autoseq
    rev: v0.1.1
    hooks:
      - id: alembic-autoseq-check
```

---

## 🏗️ Architecture & Mechanics

> 📖 **Under the Hood:** For a detailed breakdown of how AST parsing, SQLite/PostgreSQL savepoints, and in-memory revision map reloading work, read [UNDER_THE_HOOD.md](UNDER_THE_HOOD.md).

```
                      alembic_autoseq.guard()
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
1. Scan Migration Files                         2. Inspect Database
   • Python AST metadata parsing                   • Reads alembic_version table
   • Sequence number & digit width detection       • Detects orphan DB stamps
        │                                               │
        └───────────────────────┬───────────────────────┘
                                ▼
                     3. DAG Conflict Detection
                        ┌──────────────────────────────┐
                        │ Are there multiple heads?    │
                        │ Are sequence IDs duplicated? │
                        │ Are down_revisions broken?   │
                        └──────────────┬───────────────┘
                                       │
                   ┌───────────────────┴───────────────────┐
             No Conflicts                             Conflicts Found
                   │                                       │
                   ▼                                       ▼
           Proceed normally                       4. Automatic Rebase Engine
                                                     • Detects active branch migration
                                                     • Auto-increments sequence ID (0004 -> 0005)
                                                     • Updates down_revision to upstream head
                                                     • Atomically updates file & in-memory map
                                                           │
                                                           ▼
                                                  Proceed with Alembic Upgrade!
```

---

## 🧪 Running the Test Suite

```bash
git clone https://github.com/jagadeesh88705/alembic_autoseq.git
cd alembic_autoseq
python -m venv .venv
source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate
pip install -e .[dev]
pytest -v
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
