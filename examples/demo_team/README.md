# Demo team (Agno AgentOS + Cursor ACP)

Multi-agent team with a coordinating leader and specialist members (researcher, coder, writer). Each local member uses a persistent `cursor-agent acp` session via the **`agno-cursor-agent`** package (`import agno_cursor`).

## Prerequisites

- Python 3.10+
- [Cursor CLI](https://cursor.com/docs/cli) installed and logged in: `cursor-agent login`
- This repo installed editable from the monorepo root

```bash
cd /path/to/agno-cursor-agent
pip install -e ".[standard]"
cd examples/demo_team
```

## Run

```bash
python team_os.py
```

Default port **7777**. In [os.agno.com](https://os.agno.com) or Agent UI, connect to:

- `http://localhost:7777` or `http://127.0.0.1:7777`

Do **not** use `http://0.0.0.0:7777` in the browser.

## Configuration

| Mechanism | Purpose |
|-----------|---------|
| `.env` | `CURSOR_TEAM_*` overrides (see `.env.example`) |
| `config.yaml` | Optional YAML (copy from `config.yaml.example`) |

Role → model defaults include **leader: auto**. Per-agent overrides via `agents` or shorthand `workers` / `models` / `modes` JSON env vars.

For the generic harness library, prefer **`AGNO_CURSOR_*`** env vars (see root README). `CURSOR_TEAM_*` remains the demo convention.

## Trace

```bash
export CURSOR_TEAM_ACP_TRACE=true
export CURSOR_TEAM_ACP_TRACE_COLOR=1  # optional
python team_os.py
```

## Remote workers

Run a worker on another host/port:

```bash
CURSOR_TEAM_AGENT_ID=researcher CURSOR_TEAM_PORT=7801 python worker_os.py
```

Point the team at the worker with `config.yaml` or `CURSOR_TEAM_WORKERS`.

## A2A client

With `team_os` running:

```bash
python a2a_client.py "What can this team do?"
```

## Tests

From repo root:

```bash
pytest examples/demo_team/tests -m "not integration"
```

Integration A2A tests live in the root `tests/` tree and require a running team.
