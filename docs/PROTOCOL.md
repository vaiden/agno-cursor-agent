# Protocols

This stack uses **both** A2A and ACP. They sit on different hops and are not substitutes for each other.

| Hop | Protocol | Who speaks it |
| --- | --- | --- |
| Caller → deployed team | **A2A** (Agno [AgentOS](https://docs.agno.com/reference/agent-os/agent-os), REST) | `examples/demo_team/a2a_client.py` |
| Team → remote member | **A2A** REST | [`RemoteAgent`](https://docs.agno.com/reference/agents/remote-agent) in `examples/demo_team/members.py` → `worker_os.py` |
| Agno UI → [AgentOS](https://docs.agno.com/reference/agent-os/agent-os) | [AgentOS](https://docs.agno.com/reference/agent-os/agent-os) HTTP | [os.agno.com](https://os.agno.com) connects to the [AgentOS](https://docs.agno.com/reference/agent-os/agent-os) root, not the A2A path |
| Each local agent → Cursor | **ACP** (Agent Client Protocol) | `CursorACPChat` → `ACPSession` → `cursor-agent acp` |

```text
caller
  |
  |  A2A REST
  v
[Agno] AgentOS  a2a_interface=True, agent card, REST routes
  |
  v
[Agno] Team  mode=coordinate, delegation tool calls, synthesis
  |
  +-- leader and local member
  |     |
  |     v
  |   [Agno] Agent run loop
  |     |
  |     v
  |   [agno-cursor-agent] CursorACPChat          Model adapter: messages and tools <-> ACP text
  |     |
  |     v
  |   [agno-cursor-agent] ACPSession             persistent JSON-RPC on stdio
  |     |
  |     |  ACP
  |     v
  |   [Cursor] cursor-agent acp
  |
  +-- remote member
        |
        v
      [Agno] RemoteAgent            protocol="a2a", a2a_protocol="rest"
        |
        |  A2A REST
        v
      [Agno] worker AgentOS
        |
        v
      [agno-cursor-agent] CursorACPChat -> ACPSession -> [Cursor] cursor-agent acp
```

Agno classes in the diagram: [AgentOS](https://docs.agno.com/reference/agent-os/agent-os), [Team](https://docs.agno.com/reference/teams/team), [Agent](https://docs.agno.com/reference/agents/agent), [RemoteAgent](https://docs.agno.com/reference/agents/remote-agent). `CursorACPChat` subclasses [Model](https://docs.agno.com/reference/models/model).

The demo scripts only construct those Agno objects and point local agents at `CursorACPChat`. The Agno UI uses [AgentOS](https://docs.agno.com/reference/agent-os/agent-os) HTTP, which is also Agno. The library itself is the `[agno-cursor-agent]` slice: `CursorACPChat` and `ACPSession`.

The package implements the ACP hop. A2A is Agno's. The demo team turns it on with [`AgentOS`](https://docs.agno.com/reference/agent-os/agent-os)`(..., a2a_interface=True)` and calls it through [`RemoteAgent`](https://docs.agno.com/reference/agents/remote-agent).

**A2A** is [Agent2Agent](https://a2a-protocol.org/). **ACP** is the [Agent Client Protocol](https://cursor.com/docs/cli/acp): newline-delimited JSON-RPC 2.0 on the stdin/stdout of a long-lived `cursor-agent acp` process. Cursor runs the model. `CursorACPChat` is the Agno [`Model`](https://docs.agno.com/reference/models/model) adapter in front of that session.

## ACP

Implemented in `src/agno_cursor/acp/session.py`.

One `cursor-agent acp` process and one ACP session per `agent_key`. `ACPSessionRegistry` keeps them for the life of the process. A later turn is another `session/prompt` on that session. The process is respawned only if it has exited, and the handshake runs again only if the session is not initialized.

### Spawn

`build_spawn_argv` in `src/agno_cursor/settings.py`:

| Mode | Command |
| --- | --- |
| `ask` | `cursor-agent --model <model> --mode ask acp` |
| `plan` | `cursor-agent --model <model> --mode plan acp` |
| `agent` | `cursor-agent --model <model> --force acp` |

The working directory is `project_root`. That path is also sent as `cwd` in `session/new`.

### Handshake

`ACPSession._initialize_session` sends three requests and waits for each result:

1. `initialize`

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": 1,
    "clientCapabilities": {
      "fs": {"readTextFile": false, "writeTextFile": false},
      "terminal": false
    },
    "clientInfo": {"name": "agno-cursor-acp", "version": "0.1.0"}
  }
}
```

`clientCapabilities` says this client will not serve ACP filesystem or terminal requests. Cursor still uses its own tools inside the CLI. `agent` mode passes `--force` so those tools can run unattended.

2. `authenticate` with `{"methodId": "cursor_login"}`. Call `check_cursor_login()` before warming sessions. It expects `cursor-agent status` to report `Logged in`. The handshake does not send an API key.

3. `session/new` with `{"cwd": "<project root>", "mcpServers": []}`. The `sessionId` in the result is kept and reused.

### Prompt

`session/prompt`:

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "session/prompt",
  "params": {
    "sessionId": "<id from session/new>",
    "prompt": [{"type": "text", "text": "<prompt>"}]
  }
}
```

While that call is in flight, the reader thread collects `session/update` notifications whose `sessionUpdate` is `agent_message_chunk`, concatenates `params.update.content.text`, and returns that string when `session/prompt` completes. The adapter does not stream chunks up into Agno; `CursorACPChat` yields one full response.

#### `plan_update`

ACP `session/update` notifications with `sessionUpdate: "plan_update"` carry a full plan snapshot (`planId`, `entries` with `content`, `priority`, `status`). Each update replaces the cached plan for that `planId`. These are not blocking: Cursor does not wait for a reply. When `session/prompt` completes, the latest snapshots are appended to the member text as `[cursor_plan_snapshot]`.

#### Blocking Cursor extensions

While `session/prompt` is still open, Cursor may send JSON-RPC **requests** (with an `id`):

| Method | Purpose |
| --- | --- |
| `cursor/ask_question` | Multiple-choice questions; blocks until the client responds |
| `cursor/create_plan` | Plan approval; blocks until the client responds |

`ACPSession` parks the open prompt, returns a `[cursor_blocked]` envelope to Agno, and waits. The coordinator (team leader) must delegate back to the **same** member with a single JSON resume object. The adapter sends a nested JSON-RPC result and keeps waiting on the original `session/prompt`:

```json
{"jsonrpc":"2.0","id":12,"result":{"outcome":{"outcome":"answered","answers":[{"questionId":"q1","selectedOptionIds":["agent"]}]}}}
```

```json
{"jsonrpc":"2.0","id":13,"result":{"outcome":{"outcome":"accepted"}}}
```

A flat `{ "outcome": "accepted" }` at the top level of `result` is treated by Cursor as a cancel. While parked, no second `session/prompt` is sent. Invalid resume JSON is rejected up to three times, then the parked request is cancelled.

### Permissions

`session/request_permission` is answered immediately:

```json
{
  "jsonrpc": "2.0",
  "id": "<request id>",
  "result": {"outcome": {"outcome": "selected", "optionId": "allow-once"}}
}
```

### What the adapter sends

`CursorACPChat` (`src/agno_cursor/model/cursor_acp.py`) turns Agno messages into the text inside `session/prompt`:

- The first turn includes system messages.
- Later turns send only the newest user message or tool result. Earlier turns stay in the ACP session.
- When Agno provides tools, the prompt requires a single JSON object, either `{"content": "..."}` or `{"tool_calls": [{"name": "...", "arguments": {}}]}`. Non-JSON text is returned as assistant content.

Default prompt timeout is 180 seconds. Each JSON-RPC call times out at 120 seconds unless the caller overrides it.

### Framing

Messages are one JSON object per line. Requests carry `jsonrpc`, `id`, `method`, and `params`. Matching responses carry `result` or `error`. A dead process surfaces as `ACP process died during <method>`. A hung call surfaces as `ACP call timed out`.

## A2A

Used by the demo team, not by the library core. `examples/demo_team/team_os.py` builds [`AgentOS`](https://docs.agno.com/reference/agent-os/agent-os)`(..., a2a_interface=True)` around the coordinate [`Team`](https://docs.agno.com/reference/teams/team). `worker_os.py` does the same for a single [`Agent`](https://docs.agno.com/reference/agents/agent). Agno serves the A2A routes. Callers use REST (`a2a_protocol="rest"`).

| Role | Base URL |
| --- | --- |
| [AgentOS](https://docs.agno.com/reference/agent-os/agent-os) root | `http://localhost:7777` |
| Team | `http://localhost:7777/a2a/teams/cursor_team` |
| Team agent card | `http://localhost:7777/a2a/teams/cursor_team/.well-known/agent-card.json` |
| Worker root | `http://localhost:7801` (override with `CURSOR_TEAM_PORT`) |
| Worker health | `http://localhost:7801/health` |

`examples/demo_team/a2a_client.py` constructs a [`RemoteAgent`](https://docs.agno.com/reference/agents/remote-agent):

```python
RemoteAgent(
    base_url=f"{base}/a2a/teams/{team_id}",
    agent_id=team_id,
    protocol="a2a",
    a2a_protocol="rest",
    timeout=300.0,
)
```

A remote member uses the worker's [AgentOS](https://docs.agno.com/reference/agent-os/agent-os) root as `base_url`, not the nested `/a2a/agents/...` path:

```python
RemoteAgent(
    base_url=worker_url,
    agent_id=member_id,
    protocol="a2a",
    a2a_protocol="rest",
    timeout=180.0,
)
```

The worker then runs its own ACP session and returns the agent reply over A2A. If `worker_fallback_local` is on and `GET {worker}/health` fails, that member is built as a local [`Agent`](https://docs.agno.com/reference/agents/agent) instead.

The Agno control plane talks to the [AgentOS](https://docs.agno.com/reference/agent-os/agent-os) root (`http://localhost:7777`). A2A clients talk to the `/a2a/...` path.

## What lives where

| Concern | Location |
| --- | --- |
| ACP process, handshake, prompt, permissions | `src/agno_cursor/acp/session.py` |
| Session registry | `src/agno_cursor/acp/registry.py` |
| Agno [`Model`](https://docs.agno.com/reference/models/model) ↔ ACP text, tool-call JSON | `src/agno_cursor/model/cursor_acp.py` |
| Team exposed over A2A | `examples/demo_team/team_os.py` |
| One member exposed over A2A | `examples/demo_team/worker_os.py` |
| Local ACP agent vs remote A2A member | `examples/demo_team/members.py` |
| A2A caller | `examples/demo_team/a2a_client.py` |
