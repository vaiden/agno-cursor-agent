# Architecture

This project connects three layers:

```text
A2A clients / Agno UI
        |
        v
Agno AgentOS + TeamMode.coordinate
        |
        v
CursorACPChat model adapter
        |
        v
persistent cursor-agent acp subprocesses
```

The result is an Agno team that can be called through A2A while each local agent is powered by Cursor through ACP.

The library lives in `src/agno_cursor`. The demo team lives in `examples/demo_team`.

Wire-level detail for both protocols is in [PROTOCOL.md](../../../docs/PROTOCOL.md).

## Component Map

```text
examples/demo_team/a2a_client.py / os.agno.com / any A2A client
        |
        | HTTP
        v
examples/demo_team/team_os.py
  AgentOS(a2a_interface=True)
  Team(id="cursor_team", mode=TeamMode.coordinate)
        |
        | delegates to
        v
examples/demo_team/members.py
  researcher, coder, writer
        |
        +-- local member:
        |     Agent -> CursorACPChat -> ACPSessionRegistry -> cursor-agent acp
        |
        +-- remote member:
              RemoteAgent -> examples/demo_team/worker_os.py -> CursorACPChat -> cursor-agent acp
```

## Main Server

`examples/demo_team/team_os.py` is the primary entry point. It creates:

- A `Team` with ID `cursor_team`.
- A leader model from `build_leader_model(settings)`.
- Three members from `members.ROSTER`: `researcher`, `coder`, and `writer`.
- `TeamMode.coordinate`, so the leader chooses which member to call and synthesizes responses.
- `SqliteDb` at `agno_team.db`.
- `AgentOS` with `a2a_interface=True`.

Startup checks Cursor login, warms local ACP sessions, logs the Cursor CLI argv for each warmed session, and then serves AgentOS on `0.0.0.0:${settings.port}`. Shutdown closes all registered ACP subprocesses.

## Remote Workers

`examples/demo_team/worker_os.py` exposes one member as an independent AgentOS service.

Worker selection:

| Setting | Source | Default |
| --- | --- | --- |
| Agent ID | `settings.agent_id` or `CURSOR_TEAM_AGENT_ID` | `researcher` |
| Port | `CURSOR_TEAM_PORT` or `AGENT_OS_PORT` | `7801` |

The worker builds one Agno `Agent` with `CursorACPChat`, persists to `worker_{agent_id}.db`, enables A2A, warms that agent's ACP session, and serves on the worker port.

Remote worker URLs in team config should point at the worker AgentOS root, such as `http://localhost:7801`.

## Member Construction

`examples/demo_team/members.py` owns the team roster and the local-vs-remote decision.

For each `MemberSpec`, `build_member()` resolves the effective model, mode, role, and optional worker URL through `TeamSettings.resolve()`.

If `worker_url` is present, the member becomes:

```text
RemoteAgent(base_url=<worker_url>, agent_id=<member id>, protocol="a2a")
```

If no `worker_url` is set, the member becomes a local Agno `Agent`:

```text
Agent(model=CursorACPChat(agent_key=<member id>, model=<resolved model>, mode=<resolved mode>))
```

When `worker_fallback_local` is true, the builder probes the worker's `/health` endpoint. If the worker is not reachable, it falls through to local construction.

## Cursor ACP Bridge

`src/agno_cursor/acp/session.py` is the persistent JSON-RPC bridge to Cursor ACP. `ACPSessionRegistry` lives in `src/agno_cursor/acp/registry.py`.

An `ACPSession` is keyed by `agent_key` and contains:

- The selected Cursor model.
- The ACP mode (`ask`, `plan`, or `agent`).
- The project root as Cursor's working directory.
- A spawned `cursor-agent ... acp` process.
- A reader thread that consumes JSON-RPC responses and notifications.

Session startup flow:

```text
spawn subprocess
initialize
authenticate(methodId="cursor_login")
session/new(cwd=<project root>)
```

Prompt flow:

```text
session/prompt
session/update: agent_message_chunk (stream text into buffer)
session/update: plan_update (replace cached plan by planId; non-blocking)
cursor/ask_question or cursor/create_plan (park prompt; return [cursor_blocked] to leader)
resume JSON from leader -> nested extension result -> same session/prompt completes
join chunks + append [cursor_plan_snapshot] into final model text
```

Permission requests from ACP are answered with `allow-once`, allowing unattended AgentOS runs to continue.

Blocking Cursor questions and plan approval surface to the team leader as `[cursor_blocked]` member content. The leader answers or asks the user, then delegates the resume JSON back to the same member. See [PROTOCOL.md](../../../docs/PROTOCOL.md).

`ACPSessionRegistry` keeps one session per `agent_key` in the current process. The team process and each worker process have their own registry.

## Agno Model Adapter

`src/agno_cursor/model/cursor_acp.py` implements Agno's `Model` interface as `CursorACPChat`.

Responsibilities:

- Convert Agno messages into a Cursor prompt.
- Send the prompt to the correct `ACPSession`.
- Parse Cursor's text response back into an Agno `ModelResponse`.
- Support Agno tool calls by asking Cursor to return strict JSON.

Prompt strategy:

- On the first turn, system messages are included.
- On later turns, only the latest user message or tool result is sent because the ACP session keeps conversational context.
- If tools are available, a JSON-only tool-call instruction is appended.

Response strategy:

```json
{"content":"Plain assistant content"}
```

or:

```json
{"tool_calls":[{"name":"tool_name","arguments":{"key":"value"}}]}
```

If the response is not parseable JSON, the adapter returns the raw text as assistant content.

Streaming methods currently yield a single full response rather than incremental chunks.

## Configuration Model

`examples/demo_team/settings.py` defines `TeamSettings`. Spawn arguments and `check_cursor_login()` live in `src/agno_cursor/settings.py`.

Important defaults:

| Setting | Default |
| --- | --- |
| `port` | `7777` |
| `team_id` | `cursor_team` |
| `base_spawn_cmd` | `cursor-agent` |
| `default_model` | `composer-2.5` |
| `default_mode` | `ask` |
| `worker_fallback_local` | `False` |

Settings use the `CURSOR_TEAM_` env prefix and an optional `.env` file. During validation, the project also reads `config.yaml` from the project root.

Merge behavior:

1. `TeamSettings` starts from pydantic-settings values: defaults plus `.env` and environment variables.
2. `config.yaml` merges into `role_models`, core scalar settings, and `agents`.
3. Shorthand maps `workers`, `models`, and `modes` are applied to `agents`.

The shorthand maps are useful for quick env overrides:

```bash
export CURSOR_TEAM_WORKERS='{"researcher":"http://localhost:7801"}'
export CURSOR_TEAM_MODELS='{"coder":"composer-2.5"}'
export CURSOR_TEAM_MODES='{"writer":"agent"}'
```

## Role-Based Models

Model resolution is:

```text
agents[agent_id].model -> role_models[effective_role] -> default_model
```

Default role models:

| Role | Default model |
| --- | --- |
| `leader` | `auto` |
| `coder` | `composer-2.5` |
| `writer` | `claude-sonnet-5-5-medium` |
| `product_owner` | `claude-sonnet-5-5-medium` |

`researcher` is part of the main roster but has no dedicated entry in `DEFAULT_ROLE_MODELS`, so it uses `default_model`.

Mode resolution is:

```text
agents[agent_id].mode -> default_mode
```

Cursor spawn commands:

| Mode | Spawn argv |
| --- | --- |
| `ask` | `cursor-agent --model <model> --mode ask acp` |
| `plan` | `cursor-agent --model <model> --mode plan acp` |
| `agent` | `cursor-agent --model <model> --force acp` |

## Request Flow

For an all-local team run:

1. A client sends a message to `http://localhost:7777/a2a/teams/cursor_team`.
2. AgentOS routes the message to the Agno team.
3. The team leader runs through `CursorACPChat`.
4. The leader delegates to one or more members.
5. Each local member calls its own persistent ACP session.
6. Cursor responses return through `CursorACPChat` as Agno model responses.
7. The leader synthesizes the final answer.
8. Agno persists run state in `agno_team.db`.

For a remote member, step 5 becomes an A2A REST call to an `examples/demo_team/worker_os.py` process. The worker then performs its own local ACP call and returns the result to the team.

## AgentOS And A2A URLs

Default team deployment:

| Purpose | URL |
| --- | --- |
| AgentOS root | `http://localhost:7777` |
| Team A2A base | `http://localhost:7777/a2a/teams/cursor_team` |
| Team agent card | `http://localhost:7777/a2a/teams/cursor_team/.well-known/agent-card.json` |
| Health check | `http://localhost:7777/health` |

Default worker deployment:

| Purpose | URL |
| --- | --- |
| Worker AgentOS root | `http://localhost:7801` |
| Worker agent card | `http://localhost:7801/a2a/agents/<agent_id>/.well-known/agent-card.json` |
| Worker health check | `http://localhost:7801/health` |

Agno UI connects to the AgentOS root URL. A2A clients target the team or agent A2A path.

## Tests

`pyproject.toml` sets:

```toml
[tool.pytest.ini_options]
addopts = ["-m", "not integration", "--strict-markers"]
```

So `pytest` runs offline unit tests by default.

Unit coverage includes:

- Role model and mode resolution.
- Per-agent overrides.
- Worker URL shorthand.
- Local `Agent` vs remote `RemoteAgent` construction.
- Cursor ACP spawn argv for `ask`, `plan`, and `agent`.
- Tool-call and content JSON parsing.

Integration coverage includes:

- ACP session persistence across prompts.
- Team agent card availability.
- A2A message send through `RemoteAgent.arun()`.

Run commands:

```bash
pytest
pytest -m integration
```

Integration tests require Cursor login. Team A2A integration also requires `team_os.py` running locally or `TEAM_BASE_URL` pointing at a live deployment.

## Documentation Team

`examples/demo_team/docs_team.py` is a separate, self-documenting Agno team with:

- `product_owner`: documentation scope and acceptance criteria.
- `coder`: repository inspection and technical details.
- `writer`: README and architecture writing.

It prefixes ACP agent keys with `docs:` and forces documentation agents into Cursor `agent` mode so they can edit files when run.

## Caveats

- Cursor login is required; the project authenticates ACP with `cursor_login`.
- ACP permission prompts are auto-approved with `allow-once`.
- Cursor ACP stderr is kept as a short tail and included when the process dies.
- Tool-call support depends on Cursor returning parseable JSON when tools are present.
- Streaming is represented as a single full response.
- SQLite database files are created in the project root when servers run.
- Remote worker health checks are coarse and only probe `/health`.
