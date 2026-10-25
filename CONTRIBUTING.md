# Contributing

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Tests

Default (CI-safe, no Cursor login):

```bash
pytest -m "not integration" --cov=agno_cursor --cov-report=term-missing --cov-fail-under=85
```

Integration (local only, requires `cursor-agent login` and optionally `python team_os.py` in `examples/demo_team`):

```bash
pytest -m integration
```

CI does **not** use Cursor credentials; unit tests mock ACP subprocess I/O.

## Pull requests

- Keep CI green on Python 3.10–3.12.
- Do not commit `.env`, `config.yaml`, or `*.db` files.

## Releases (maintainers)

1. Merge to `main` with passing CI.
2. Bump `version` in `pyproject.toml` and `agno_cursor/__init__.py` (`__version__`).
3. Tag and push: `git tag v0.1.0 && git push origin v0.1.0`.
4. GitHub Actions workflow **`publish.yml`** runs unit tests, builds the wheel/sdist, and publishes **`agno-cursor-agent`** to PyPI via **OIDC trusted publishing** (no PyPI token in GitHub secrets).

### PyPI trusted publisher

Configured on PyPI for GitHub repository `vaiden/agno-cursor-agent` and workflow filename **`publish.yml`**.

### Codecov

Coverage uploads use the `CODECOV_TOKEN` repository secret in **`ci.yml`** only.
