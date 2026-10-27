# agno-cursor-agent

![CI](https://github.com/vaiden/agno-cursor-agent/actions/workflows/ci.yml/badge.svg)
![codecov](https://codecov.io/gh/vaiden/agno-cursor-agent/graph/badge.svg)
![PyPI Version](https://img.shields.io/pypi/v/agno-cursor-agent)

Agno `Model` adapter that talks to the **Cursor CLI** over a persistent **ACP** (JSON-RPC) session.

The library speaks ACP. The demo team is reached over A2A. 

See [`docs/PROTOCOL.md`](docs/PROTOCOL.md) or feed it directly to your Agentic coder.  

## Reasoning

Cursor unlocks multiple exciting features: multiple model providers, cost router, agentic memory, code indexing, cloud agent provisioning and a powerful harness.
Now available to power your Agno agents for the best aSDLC pipeline experience.

## Prerequisites

- Python 3.10+
- [Cursor CLI](https://cursor.com/cli) installed (`cursor-agent` on your PATH)

## Cursor authorization

Running agents that call Cursor (local ACP or the demo team) requires an authenticated Cursor CLI session on **that machine**. This repo does not store or ship credentials.

**Option A — one-time CLI login (typical for local dev):**

```bash
cursor-agent login
```

**Option B — API key in your environment** (CI, servers, or automation on your own infra):

Set `CURSOR_API_KEY` in the environment (or your local `.env`, never committed). See [Cursor CLI](https://cursor.com/cli) docs for how to obtain a key.

The library’s `check_cursor_login()` verifies `cursor-agent status` shows a logged-in session when you start the demo stack; use whichever auth method Cursor supports for your setup.

## Quickstart

Install from PyPI:

```bash
pip install agno-cursor-agent
# AgentOS with WebSockets:
pip install "agno-cursor-agent[standard]"
```

Import name on PyPI is `agno-cursor-agent`; in Python you still `import agno_cursor`.

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

## Local and remote invocation

**Local.** `CursorACPChat` starts `cursor-agent acp` on the same machine as your Python process. That machine has to be logged into Cursor before the first prompt. Two ways to do that:

- `cursor-agent login` once. This is the usual setup on a laptop.
- `CURSOR_API_KEY` in the environment, or in a private `.env` you never commit. This is the usual setup for CI and a server.

`cursor-agent status` should say `Logged in`. The library does not read or store the key. The CLI picks it up from that environment.

**Remote.** A team member can run on another host. Start `worker_os.py` there and give that member a `worker_url` (the [demo team](examples/demo_team/README.md) shows the commands). The team sends the task over A2A. Cursor login stays on the worker host, same two choices: `cursor-agent login`, or `CURSOR_API_KEY` in the worker's environment.

## Demo team

A full **Agno AgentOS + A2A** team lives under [`examples/demo_team`](examples/demo_team/README.md). It uses `CURSOR_TEAM_*` settings and role-based models (leader defaults to `auto`).

See [`examples/demo_team/doc/ARCHITECTURE.md`](examples/demo_team/doc/ARCHITECTURE.md).

```bash
cd examples/demo_team
pip install -e "../..[standard]"
cursor-agent login
python team_os.py
```

Connect the Agno UI to **http://localhost:7777** (not `0.0.0.0`).

## Caveats

`cursor/ask_question`, `cursor/create_plan`, and `plan_update` are still ignored, so a Cursor question or plan approval never reaches the coordinator.

## Roadmap

- [x] Cursor ACP integration
- [x] Remote Cursor agent
- [ ] Native container support
- [ ] Cursor as a [DevContainer](https://github.com/devcontainers/images)

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md).
