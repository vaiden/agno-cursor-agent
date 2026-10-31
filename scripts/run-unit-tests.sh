#!/usr/bin/env bash
# Run CI-equivalent unit tests in a project-local venv (see CONTRIBUTING.md).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  echo "Creating .venv …"
  python3 -m venv .venv
fi

# shellcheck source=/dev/null
source .venv/bin/activate

python -m pip install -q -U pip
python -m pip install -q -e ".[dev]"

exec python -m pytest -m "not integration" \
  --cov=agno_cursor \
  --cov-report=term-missing \
  --cov-fail-under=85 \
  "$@"
