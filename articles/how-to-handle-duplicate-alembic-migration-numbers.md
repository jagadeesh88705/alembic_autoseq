# How to Handle Duplicate Alembic Migration Numbers When Developers Work in Parallel

If your engineering team uses **SQLAlchemy** and **Alembic** to manage database migrations, you have almost certainly encountered this painful scenario:

Two developers branch off `main` at the same time to build different features. Both developers generate an Alembic migration. When their branches are merged or tested on a shared database, Alembic explodes:

```text
alembic.util.exc.CommandError: Multiple head revisions are present for given argument 'head'; please specify a revision or 'heads'
```

Or worse, if you use sequential prefixes like `0001_`, `0002_`, both developers end up with a file starting with `0004_`, causing duplicate revision conflicts, broken CI pipelines, and corrupted shared dev databases.

In this article, we’ll explore **why** this happens, why the standard `alembic merge` command is often frustrating, and how to automate the resolution cleanly.

---

## The Root Cause: Why Parallel Branching Breaks Migration Chains

Alembic represents migration history as a **Directed Acyclic Graph (DAG)** where each migration script points to its parent via `down_revision`:

```text
0001_initial.py  <-  0002_users.py  <-  0003_profiles.py
```

### The Conflict Scenario:
1. **Developer A** branches off `main` at revision `0003`. They generate migration `0004_add_orders.py` (`down_revision = '0003'`).
2. **Developer B** branches off `main` at the exact same time. They generate migration `0004_add_inventory.py` (`down_revision = '0003'`).

Now your migration tree has forked into two heads:

```text
                        ┌──> 0004_add_orders.py (HEAD 1)
0003_profiles.py ───────┤
                        └──> 0004_add_inventory.py (HEAD 2)
```

When either developer (or your CI/CD pipeline) runs `alembic upgrade head`, Alembic halts immediately because it does not know which branch to apply first.

---

## Why Standard `alembic merge` is Problematic for Sequential Migrations

Alembic provides a native command:
```bash
alembic merge heads -m "merge orders and inventory"
```

While this works, it introduces several major headaches for development teams:

1. **Cluttered "Diamond" Merge Graph:** It creates a dedicated merge migration file (`0005_merge_heads.py`) that contains no actual schema changes—just `down_revision = ('0004_orders', '0004_inventory')`. Over a few months with an active team, your migration tree becomes a tangled web of diamond merge nodes.
2. **No File Renumbering:** If your team prefers human-readable sequence prefixes (`0001`, `0002`, `0003`), `alembic merge` does **not** renumber the conflicting files. You are left with two `0004_` files permanently in your repository.
3. **Shared Database Desynchronization:** If Developer A tests on a shared dev database, the database gets stamped with `0004_orders`. When Developer B pulls the shared database to test their branch, Alembic crashes with `Can't locate revision identified by '0004_orders'` because Developer B’s local branch doesn't have Developer A’s file yet.

---

## The Alternative: Automated In-Place Rebase with `alembic-autoseq`

Instead of creating diamond merge nodes or manually renaming files and editing `down_revision` by hand, the ideal workflow is an **automated rebase**:

```text
0003_profiles.py -> 0004_add_orders.py -> 0005_add_inventory.py (HEAD)
```

This is what [`alembic-autoseq`](https://pypi.org/project/alembic-autoseq/) does.

### How It Works:
1. **AST Parsing:** It safely inspects your `versions/` folder using Python's native `ast` module (without executing migration code or creating database side-effects).
2. **Conflict Detection:** It identifies multiple heads, duplicate revision IDs, and sequential prefix collisions.
3. **Atomic Rebase:** It determines which migration belongs to the active branch, updates `down_revision` to the latest upstream head, auto-increments the sequence number (`0004_add_inventory.py` $\rightarrow$ `0005_add_inventory.py`), and renames the file on disk.
4. **In-Memory Cache Reload:** It refreshes Alembic's in-memory `RevisionMap` on the fly so the migration command completes without error.

---

## Step-by-Step Implementation

### Step 1: Install the Package
```bash
pip install alembic-autoseq
```

### Step 2: Add the 1-Line Guard to `alembic/env.py`
Inside your project's `alembic/env.py`:

```python
import alembic_autoseq

def run_migrations_online():
    connectable = engine_from_config(...)

    with connectable.connect() as connection:
        # Intercepts and heals parallel branch conflicts before Alembic runs
        alembic_autoseq.guard(connection=connection, auto_heal=True)

        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()
```

### Step 3: Run Your Normal Migration
Now, developers simply run:
```bash
alembic upgrade head
```
If a colleague merged a migration while they were working, `alembic-autoseq` automatically linearizes the branch migration and applies it cleanly.

---

## Adding a CI/CD Quality Gate

To ensure that no conflicting or multi-head migrations are ever merged into `main`, you can add a check to your GitHub Actions pipeline:

```yaml
# .github/workflows/migrations.yml
name: Migration Check

on: [pull_request]

jobs:
  verify-migrations:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install alembic-autoseq
      - run: alembic-autoseq check
```

If a Pull Request introduces a duplicate revision ID or a multi-head fork, `alembic-autoseq check` will exit with code `1` and display a clear error message in the PR logs.

---

## When NOT to Rebase

* **Production Migrations:** Never modify migrations that have already been applied to your production database. `alembic-autoseq` is strictly designed for **unmerged, local feature branches** before code is merged into your production release branch.
* **Intentional Multi-Database Branching:** If your infrastructure deliberately uses separate Alembic branches for multi-tenant or multi-database architectures, stick to Alembic’s native branching.

---

## Conclusion

Parallel development shouldn't mean wasting 30 minutes resolving migration merge conflicts or cluttering your Git history with empty merge commits. By adopting an automated sequential rebase strategy, teams can maintain clean, linear database migration histories effortlessly.

* 📦 **PyPI:** [`pip install alembic-autoseq`](https://pypi.org/project/alembic-autoseq/)
* 💻 **GitHub:** [https://github.com/jagadeesh88705/alembic_autoseq](https://github.com/jagadeesh88705/alembic_autoseq)
