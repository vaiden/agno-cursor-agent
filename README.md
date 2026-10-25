# agno-cursor

[![CI](https://github.com/vaiden/agno-cursor-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/vaiden/agno-cursor-agent/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/vaiden/agno-cursor-agent/graph/badge.svg)](https://codecov.io/gh/vaiden/agno-cursor-agent)

Agno `Model` adapter that talks to the **Cursor CLI** over a persistent **ACP** (JSON-RPC) session.

Install from PyPI (after the first release tag):

```bash
pip install agno-cursor
# AgentOS with WebSockets:
pip install "agno-cursor[standard]"
```

Editable install from this repo:

```bash
pip install -e ".[dev]"
pytest -m "not integration" --cov=agno_cursor --cov-fail-under=85
```

## Quick usage

```python
from agno.agent import Agent
from agno_cursor import CursorACPChat, HarnessSettings

settings = HarnessSettings(acp_trace=False)
model = CursorACPChat(agent_key="coder", model="composer-2.5", mode="ask", settings=settings)

agent = Agent(id="coder", model=model, instructions=["You write code."])
# Requires cursor-agent login on the machine running this code.
```

Harness environment variables use the `AGNO_CURSOR_` prefix (for example `AGNO_CURSOR_ACP_TRACE=true`).

## Demo team

A full **Agno AgentOS + A2A** team lives under [`examples/demo_team`](examples/demo_team/README.md). It uses `CURSOR_TEAM_*` settings and role-based models (leader defaults to `auto`).

```bash
cd examples/demo_team
pip install -e "../..[standard]"
cursor-agent login
python team_os.py
```

Connect the Agno UI to **http://localhost:7777** (not `0.0.0.0`).

## Development

- Unit tests mock ACP I/O; CI never calls `cursor-agent`.
- Integration tests: `pytest -m integration` locally with login and optional `team_os` running.

See [CONTRIBUTING.md](CONTRIBUTING.md).
