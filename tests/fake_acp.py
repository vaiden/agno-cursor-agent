"""Fake subprocess for ACP session unit tests."""

from __future__ import annotations

import json
import queue
import threading
from typing import Any, Callable, Dict, Iterator, List, Optional


class _LineStream:
    def __init__(self) -> None:
        self._q: queue.Queue[Optional[str]] = queue.Queue()

    def push(self, line: str) -> None:
        self._q.put(line if line.endswith("\n") else line + "\n")

    def close(self) -> None:
        self._q.put(None)

    def __iter__(self) -> Iterator[str]:
        while True:
            line = self._q.get()
            if line is None:
                return
            yield line


class _FakeStdin:
    def __init__(self, on_line: Callable[[Dict[str, Any]], None]) -> None:
        self._on_line = on_line
        self.writes: List[str] = []

    def write(self, data: str) -> None:
        self.writes.append(data)
        for raw in data.strip().split("\n"):
            if not raw.strip():
                continue
            self._on_line(json.loads(raw))

    def flush(self) -> None:
        pass


class FakeAcpProcess:
    def __init__(self, cmd: List[str], *args: Any, **kwargs: Any) -> None:
        del cmd, args, kwargs
        self.stdout_stream = _LineStream()
        self.stdout = self.stdout_stream
        self.stderr = iter([])
        self.stdin = _FakeStdin(self._handle_request)
        self._returncode: Optional[int] = None
        self._lock = threading.Lock()

    def _handle_request(self, msg: Dict[str, Any]) -> None:
        req_id = msg.get("id")
        method = msg.get("method")
        if req_id is None or not method:
            return
        with self._lock:
            if method == "initialize":
                self.stdout_stream.push(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}}))
            elif method == "authenticate":
                self.stdout_stream.push(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}}))
            elif method == "session/new":
                self.stdout_stream.push(
                    json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {"sessionId": "test-session"}})
                )
            elif method == "session/prompt":
                self.stdout_stream.push(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "session/update",
                            "params": {
                                "update": {
                                    "sessionUpdate": "agent_message_chunk",
                                    "content": {"text": "fake-reply"},
                                }
                            },
                        }
                    )
                )
                self.stdout_stream.push(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}}))

    def poll(self) -> Optional[int]:
        return self._returncode

    def terminate(self) -> None:
        self._returncode = 0
        self.stdout_stream.close()

    def wait(self, timeout: Optional[float] = None) -> int:
        del timeout
        self._returncode = 0
        return 0

    def kill(self) -> None:
        self._returncode = -9
        self.stdout_stream.close()
