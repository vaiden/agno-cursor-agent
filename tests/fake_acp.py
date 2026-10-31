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
        self.stdin = _FakeStdin(self._handle_inbound)
        self._returncode: Optional[int] = None
        self._lock = threading.Lock()
        self._pending_prompt_id: Optional[int] = None
        self._extension_id: Optional[int] = None

    def _handle_inbound(self, msg: Dict[str, Any]) -> None:
        if msg.get("method"):
            self._handle_request(msg)
        elif msg.get("id") is not None and "result" in msg:
            self._handle_client_response(msg)

    def _finish_prompt(self, text: str = "fake-reply") -> None:
        if self._pending_prompt_id is None:
            return
        prompt_id = self._pending_prompt_id
        self._pending_prompt_id = None
        self.stdout_stream.push(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "session/update",
                    "params": {
                        "update": {
                            "sessionUpdate": "agent_message_chunk",
                            "content": {"text": text},
                        }
                    },
                }
            )
        )
        self.stdout_stream.push(json.dumps({"jsonrpc": "2.0", "id": prompt_id, "result": {}}))

    def _handle_client_response(self, msg: Dict[str, Any]) -> None:
        with self._lock:
            if self._extension_id is not None and msg.get("id") == self._extension_id:
                self._extension_id = None
                self._finish_prompt("after-resume")

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
                self._pending_prompt_id = int(req_id)
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


class BlockingAskFake(FakeAcpProcess):
    """Emits plan_update + cursor/ask_question; completes prompt after extension response."""

    EXTENSION_ID = 501

    def _handle_request(self, msg: Dict[str, Any]) -> None:
        req_id = msg.get("id")
        method = msg.get("method")
        if req_id is None or not method:
            return
        with self._lock:
            if method in ("initialize", "authenticate"):
                self.stdout_stream.push(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}}))
            elif method == "session/new":
                self.stdout_stream.push(
                    json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {"sessionId": "test-session"}})
                )
            elif method == "session/prompt":
                self._pending_prompt_id = int(req_id)
                self._extension_id = self.EXTENSION_ID
                self.stdout_stream.push(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "session/update",
                            "params": {
                                "sessionId": "test-session",
                                "update": {
                                    "sessionUpdate": "plan_update",
                                    "plan": {
                                        "type": "items",
                                        "planId": "plan-1",
                                        "entries": [
                                            {
                                                "content": "Step one",
                                                "priority": "high",
                                                "status": "pending",
                                            }
                                        ],
                                    },
                                },
                            },
                        }
                    )
                )
                self.stdout_stream.push(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": self.EXTENSION_ID,
                            "method": "cursor/ask_question",
                            "params": {
                                "toolCallId": "tc-1",
                                "title": "Pick one",
                                "questions": [
                                    {
                                        "id": "q1",
                                        "prompt": "Which mode?",
                                        "options": [
                                            {"id": "agent", "label": "Agent"},
                                            {"id": "plan", "label": "Plan"},
                                        ],
                                        "allowMultiple": False,
                                    }
                                ],
                            },
                        }
                    )
                )


class BlockingPlanFake(FakeAcpProcess):
    EXTENSION_ID = 502

    def _handle_request(self, msg: Dict[str, Any]) -> None:
        req_id = msg.get("id")
        method = msg.get("method")
        if req_id is None or not method:
            return
        with self._lock:
            if method in ("initialize", "authenticate"):
                self.stdout_stream.push(json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {}}))
            elif method == "session/new":
                self.stdout_stream.push(
                    json.dumps({"jsonrpc": "2.0", "id": req_id, "result": {"sessionId": "test-session"}})
                )
            elif method == "session/prompt":
                self._pending_prompt_id = int(req_id)
                self._extension_id = self.EXTENSION_ID
                self.stdout_stream.push(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": self.EXTENSION_ID,
                            "method": "cursor/create_plan",
                            "params": {
                                "toolCallId": "tc-2",
                                "name": "Test plan",
                                "plan": "Do the thing.",
                                "todos": [{"id": "t1", "content": "Do it", "status": "pending"}],
                                "isProject": False,
                            },
                        }
                    )
                )
