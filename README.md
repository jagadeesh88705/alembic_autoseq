# alembic-autoseq 🛡️

[![CI](https://github.com/jagadeesh88705/alembic_autoseq/actions/workflows/ci.yml/badge.svg)](https://github.com/jagadeesh88705/alembic_autoseq/actions)
[![PyPI version](https://img.shields.io/pypi/v/alembic-autoseq.svg)](https://pypi.org/project/alembic-autoseq/)
[![Python versions](https://img.shields.io/pypi/pyversions/alembic-autoseq.svg)](https://pypi.org/project/alembic-autoseq/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Alembic AutoSeq** is a lightweight, zero-overhead, production-ready Python package that eliminates migration collisions, duplicate sequence numbers (`0001`, `0002`), and multi-head branch conflicts in Alembic.

Designed specifically for engineering teams developing features in parallel on shared or local databases.

---

## ⚡ The Real-World Problem

When multiple developers branch off the same base migration:
1. **Duplicate Sequence Numbers:** Dev A creates `0004_add_users.py` and Dev B creates `0004_add_orders.py`.
2. **Multi-Head Crash:** Running `alembic upgrade head` crashes with:
   ```text
   alembic.util.exc.CommandError: Multiple head revisions are present for given argument 'head'; please specify a revision or 'heads'
   ```
3. **Database Drift:** When testing on a shared dev database, the database gets stamped with a revision from another branch, breaking migrations for everyone else on the team.
4. **Production Safety Constraint:** You **cannot** rewrite or renumber historical migrations because production already has historical revision hashes stored in `alembic_version`.

**`alembic-autoseq` solves this non-destructively: it auto-reconciles branch revisions in a single line without breaking past migrations or production state.**

---

## 🚀 Installation

```bash
pip install alembic-autoseq
```

---

## 💡 Quick Start (1-Line Integration)

In your `alembic/env.py`:

```python
import alembic_autoseq

# Automatically heals multi-heads and re-sequences branch revisions before Alembic runs
alembic_autoseq.guard()
```

That's it! Now when any developer runs `alembic upgrade head`, conflicting branch revisions are automatically rebased and re-linked in place.

---

## 🛠️ CLI Usage

`alembic-autoseq` includes a command-line interface for local workflows and CI/CD pipelines:

### 1. Pre-Merge Validation (`check`)
Checks if your migration history is clean and linear. Exits with code `1` if conflicts or multi-heads exist.
```bash
alembic-autoseq check
```

### 2. Auto-Rebase (`rebase`)
Automatically re-links branch migrations onto the latest upstream head and increments sequence numbers:
```bash
alembic-autoseq rebase
```

### 3. ASCII History Visualizer (`tree`)
Prints an ASCII tree of the migration DAG directly in your terminal:
```bash
alembic-autoseq tree
```
Example output:
```text
📂 Versions Directory: /path/to/alembic/versions
Total Migrations: 5 | Heads: 1

└── [0001] 0001 -> 0001_init.py
    └── [0002] 0002 -> 0002_accounts.py
        └── [0003] 0003 -> 0003_profiles.py
            └── [0004] 0004 -> 0004_users.py
                └── [0005] 0005 -> 0005_orders.py (HEAD)

✨ DAG is clean and linear.
```

---

## ⚙️ Advanced Configuration

### Python API Options

```python
from alembic_autoseq import guard

guard(
    directory=None,     # Optional path to versions/ (auto-detected by default)
    auto_heal=True,     # Auto-rebase branch revisions (set False for strict check)
    strict=False,       # Raise AlembicConflictError if conflicts remain
    quiet=False,        # Suppress informative console messages
    digits=4,           # Number of digits for prefix padding (e.g. 4 -> '0001', 3 -> '001')
)
```

### Pre-Commit Hook Integration

Add to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/jagadeesh88705/alembic_autoseq
    rev: v0.1.0
    hooks:
      - id: alembic-autoseq-check
```

---

## 🏗️ How It Works Behind the Scenes

> 📖 **Deep Dive:** For a full technical walkthrough of how `alembic-autoseq` handles shared database drift and parallel branch collisions, see [UNDER_THE_HOOD.md](UNDER_THE_HOOD.md).

```
                      alembic_autoseq.guard()
                                │
        ┌───────────────────────┴───────────────────────┐
        ▼                                               ▼
1. Scan Migration Files                         2. Auto-Discover Layout
   • Python AST metadata parsing                   • Inspects alembic.ini & versions/
   • Sequence number & digit width detection       • Zero runtime code execution
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
source .venv/bin/activate  # or .\.venv\Scripts\activate on Windows
pip install -e .[dev]
pytest -v
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
