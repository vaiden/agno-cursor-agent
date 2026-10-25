"""Agno + Cursor CLI ACP harness."""

from agno_cursor.acp.registry import ACPSessionRegistry, REGISTRY
from agno_cursor.acp.session import ACPSession
from agno_cursor.model.cursor_acp import CursorACPChat
from agno_cursor.settings import (
    AcpMode,
    HarnessSettings,
    build_spawn_argv,
    check_cursor_login,
)
from agno_cursor.trace import log_agent_block, log_agent_meta

__all__ = [
    "ACPSession",
    "ACPSessionRegistry",
    "AcpMode",
    "CursorACPChat",
    "HarnessSettings",
    "REGISTRY",
    "build_spawn_argv",
    "check_cursor_login",
    "log_agent_block",
    "log_agent_meta",
]

__version__ = "0.1.0"
