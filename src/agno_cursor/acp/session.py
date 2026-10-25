"""Persistent ACP session bridge to cursor-agent acp (JSON-RPC over stdio)."""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from agno_cursor.settings import ACPSettings, AcpMode, resolve_acp_role
from agno_cursor.trace import log_agent_block

logger = logging.getLogger(__name__)

_TRACE_PREVIEW = 1500

PopenFactory = Callable[..., subprocess.Popen[str]]


def _trace_preview(text: str, limit: int = _TRACE_PREVIEW) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}… ({len(text)} chars total)"


@dataclass
class ACPSession:
    agent_key: str
    model: str
    mode: AcpMode
    cwd: str
    spawn_argv: List[str]
    trace: bool = False
    role: str = ""
    popen_factory: PopenFactory = field(default=subprocess.Popen, repr=False)

    _proc: Optional[subprocess.Popen[str]] = field(default=None, init=False, repr=False)
    _session_id: Optional[str] = field(default=None, init=False, repr=False)
    _req_id: int = field(default=0, init=False, repr=False)
    _pending: Dict[int, Any] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _io_lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)
    _reader_thread: Optional[threading.Thread] = field(default=None, init=False, repr=False)
    _stderr_thread: Optional[threading.Thread] = field(default=None, init=False, repr=False)
    _stderr_tail: List[str] = field(default_factory=list, init=False, repr=False)
    _active_chunks: List[str] = field(default_factory=list, init=False, repr=False)
    _initialized: bool = field(default=False, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    @classmethod
    def from_settings(
        cls,
        agent_key: str,
        model: str,
        mode: AcpMode,
        settings: ACPSettings,
        *,
        popen_factory: PopenFactory | None = None,
    ) -> "ACPSession":
        return cls(
            agent_key=agent_key,
            model=model,
            mode=mode,
            cwd=str(settings.project_root),
            spawn_argv=settings.spawn_argv(model, mode),
            trace=settings.acp_trace,
            role=resolve_acp_role(settings, agent_key),
            popen_factory=popen_factory or subprocess.Popen,
        )

    @property
    def argv(self) -> List[str]:
        return list(self.spawn_argv)

    def ensure_started(self) -> None:
        with self._lock:
            if self._closed:
                raise RuntimeError(f"ACP session {self.agent_key} is closed")
            if self._proc is None or self._proc.poll() is not None:
                self._start_process()
            if not self._initialized:
                self._initialize_session()
                self._initialized = True

    def _start_process(self) -> None:
        logger.info("Starting ACP process for %s: %s", self.agent_key, self.spawn_argv)
        self._stderr_tail = []
        self._proc = self.popen_factory(
            self.spawn_argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=self.cwd,
        )
        self._pending.clear()
        self._reader_thread = threading.Thread(
            target=self._read_loop, daemon=True, name=f"acp-{self.agent_key}"
        )
        self._reader_thread.start()
        self._stderr_thread = threading.Thread(
            target=self._stderr_loop, daemon=True, name=f"acp-err-{self.agent_key}"
        )
        self._stderr_thread.start()

    def _stderr_loop(self) -> None:
        assert self._proc and self._proc.stderr
        for line in self._proc.stderr:
            line = line.rstrip("\n")
            if not line:
                continue
            self._stderr_tail.append(line)
            if len(self._stderr_tail) > 20:
                self._stderr_tail.pop(0)

    def _read_loop(self) -> None:
        assert self._proc and self._proc.stdout
        for line in self._proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                logger.debug("ACP non-JSON stdout: %s", line[:200])
                continue
            self._handle_message(msg)

    def _handle_message(self, msg: Dict[str, Any]) -> None:
        if "id" in msg and ("result" in msg or "error" in msg):
            with self._io_lock:
                self._pending[msg["id"]] = msg
            return

        method = msg.get("method")
        if method == "session/update":
            update = msg.get("params", {}).get("update", {})
            if update.get("sessionUpdate") == "agent_message_chunk":
                text = update.get("content", {}).get("text", "")
                if text:
                    self._active_chunks.append(text)
            return

        if method == "session/request_permission":
            req_id = msg.get("id")
            if req_id is not None:
                self._send_raw(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": {"outcome": {"outcome": "selected", "optionId": "allow-once"}},
                    }
                )
            return

        logger.debug("ACP notification %s: %s", method, str(msg)[:200])

    def _send_raw(self, payload: Dict[str, Any]) -> None:
        assert self._proc and self._proc.stdin
        with self._io_lock:
            self._proc.stdin.write(json.dumps(payload) + "\n")
            self._proc.stdin.flush()

    def _call(self, method: str, params: Dict[str, Any], timeout: float = 120.0) -> Dict[str, Any]:
        with self._io_lock:
            self._req_id += 1
            req_id = self._req_id
            self._send_raw({"jsonrpc": "2.0", "id": req_id, "method": method, "params": params})

        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._io_lock:
                if req_id in self._pending:
                    msg = self._pending.pop(req_id)
                    if "error" in msg:
                        raise RuntimeError(f"ACP {method} error: {msg['error']}")
                    return msg.get("result", {})
            if self._proc and self._proc.poll() is not None:
                exit_code = self._proc.poll()
                tail = list(self._stderr_tail)
                detail = tail[-1] if tail else f"exit code {exit_code}"
                raise RuntimeError(f"ACP process died during {method}: {detail}")
            time.sleep(0.02)
        raise TimeoutError(f"ACP call timed out: {method}")

    def _initialize_session(self) -> None:
        self._call(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": False, "writeTextFile": False},
                    "terminal": False,
                },
                "clientInfo": {"name": "agno-cursor-acp", "version": "0.1.0"},
            },
        )
        self._call("authenticate", {"methodId": "cursor_login"})
        result = self._call("session/new", {"cwd": self.cwd, "mcpServers": []})
        self._session_id = result["sessionId"]
        logger.info("ACP session ready for %s: %s", self.agent_key, self._session_id)

    def prompt(self, text: str, timeout: float = 180.0) -> str:
        with self._lock:
            self.ensure_started()
            assert self._session_id
            if self.trace:
                log_agent_block(
                    role=self.role,
                    model=self.model,
                    agent_key=self.agent_key,
                    mode=self.mode,
                    label=f"ACP → Cursor (session={self._session_id})",
                    body=_trace_preview(text),
                )
            self._active_chunks = []
            self._call(
                "session/prompt",
                {
                    "sessionId": self._session_id,
                    "prompt": [{"type": "text", "text": text}],
                },
                timeout=timeout,
            )
            reply = "".join(self._active_chunks).strip()
            if self.trace:
                log_agent_block(
                    role=self.role,
                    model=self.model,
                    agent_key=self.agent_key,
                    mode=self.mode,
                    label="ACP ← Cursor",
                    body=_trace_preview(reply) if reply else "(empty)",
                )
            return reply

    def close(self) -> None:
        with self._lock:
            self._closed = True
            if self._proc and self._proc.poll() is None:
                try:
                    self._proc.terminate()
                    self._proc.wait(timeout=5)
                except Exception:
                    self._proc.kill()
            self._proc = None
            self._initialized = False
