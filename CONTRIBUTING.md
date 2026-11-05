# Contributing to alembic-autoseq 🤝

Thank you for your interest in improving `alembic-autoseq`!

## Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/jagadeesh88705/alembic_autoseq.git
   cd alembic_autoseq
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .\.venv\Scripts\activate
   ```

3. Install in editable mode with development dependencies:
   ```bash
   pip install -e .[dev]
   ```

4. Run tests:
   ```bash
   pytest -v
   ```

## Pull Request Guidelines

- Ensure all new features or bug fixes have corresponding tests in `tests/`.
- Verify that `pytest` passes with 100% success before submitting.
- Write clear, semantic commit messages (e.g., `feat: ...`, `fix: ...`, `docs: ...`).

