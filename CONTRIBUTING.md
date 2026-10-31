# Contributing

## Setup

Use a **project-local virtual environment**. Do not rely on Conda base, system `python`, or `PYTHONPATH=src` alone — those miss installed dependencies (`agno`, `pydantic`, etc.).

```bash
cd /path/to/agno-cursor-agent
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
python -m pip install -U pip
pip install -e ".[dev]"
```

**Alternative (uv):** if you use [uv](https://docs.astral.sh/uv/) and `uv.lock`:

```bash
uv sync --extra dev
uv run pytest -m "not integration"
```

## Tests

Always run unit tests **with the venv activated** or via the helper script (creates `.venv` if missing):

```bash
./scripts/run-unit-tests.sh
```

Default markers match CI (no Cursor login):

```bash
source .venv/bin/activate
pytest -m "not integration" --cov=agno_cursor --cov-report=term-missing --cov-fail-under=85
```

Integration (local only, requires `cursor-agent login` and optionally `python team_os.py` in `examples/demo_team`):

```bash
source .venv/bin/activate
pytest -m integration
```

CI runs on **GitHub-hosted Ubuntu** with `actions/setup-python` (3.10–3.12), `pip install -e ".[dev]"`, then the same pytest command — not your Mac’s default interpreter.

CI does **not** use Cursor credentials; unit tests mock ACP subprocess I/O.

### Cursor agents

When an agent runs tests in this repo, it must use `.venv/bin/python`, `uv run pytest`, or `./scripts/run-unit-tests.sh`. See `.cursor/skills/agno-cursor-unit-tests/SKILL.md` for the verifier + test-runner workflow.

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
