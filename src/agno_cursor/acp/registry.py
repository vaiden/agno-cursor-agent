"""Shared in-process ACP session registry."""

from __future__ import annotations

import threading
from typing import Dict, List, Tuple

from agno_cursor.acp.session import ACPSession, PopenFactory
from agno_cursor.settings import ACPSettings, AcpMode


class ACPSessionRegistry:
    def __init__(self) -> None:
        self._sessions: Dict[str, ACPSession] = {}
        self._lock = threading.Lock()
        self._popen_factory: PopenFactory | None = None

    def set_popen_factory(self, factory: PopenFactory | None) -> None:
        self._popen_factory = factory

    def get_or_create(
        self,
        agent_key: str,
        model: str,
        mode: AcpMode,
        settings: ACPSettings,
    ) -> ACPSession:
        with self._lock:
            session = self._sessions.get(agent_key)
            if session is None or session._closed:
                session = ACPSession.from_settings(
                    agent_key,
                    model,
                    mode,
                    settings,
                    popen_factory=self._popen_factory,
                )
                session.ensure_started()
                self._sessions[agent_key] = session
            return session

    def warm(self, keys: List[Tuple[str, str, AcpMode]], settings: ACPSettings) -> None:
        for agent_key, model, mode in keys:
            self.get_or_create(agent_key, model, mode, settings)

    def close_all(self) -> None:
        with self._lock:
            for session in self._sessions.values():
                session.close()
            self._sessions.clear()


REGISTRY = ACPSessionRegistry()
