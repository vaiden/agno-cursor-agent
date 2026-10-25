"""Colored, bounded log blocks for ACP trace (role/model header + <EOF AGENT>)."""

from __future__ import annotations

import logging
import os
import sys

logger = logging.getLogger(__name__)

_TRACE_STYLE = "bold bright_cyan"
_ANSI_BEGIN = "\033[96m\033[1m"
_ANSI_END = "\033[0m"


def _color_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    force = (
        os.environ.get("AGNO_CURSOR_ACP_TRACE_COLOR")
        or os.environ.get("CURSOR_TEAM_ACP_TRACE_COLOR")
        or ""
    ).lower()
    if force in ("0", "false", "no"):
        return False
    if force in ("1", "true", "yes"):
        return True
    return sys.stderr.isatty() or sys.stdout.isatty()


def _agent_header(*, role: str, model: str, agent_key: str, mode: str, label: str) -> str:
    return f"── {label} ──  role={role}  model={model}  agent_key={agent_key}  mode={mode}"


def log_agent_block(
    *,
    role: str,
    model: str,
    agent_key: str,
    mode: str,
    label: str,
    body: str,
) -> None:
    """Emit one readable trace block: agent line, body, then <EOF AGENT>."""
    header = _agent_header(role=role, model=model, agent_key=agent_key, mode=mode, label=label)
    eof = "<EOF AGENT>"
    plain = f"{header}\n{body}\n{eof}"

    if _color_enabled():
        try:
            from rich.console import Console

            console = Console(stderr=True, highlight=False)
            console.print(f"[{_TRACE_STYLE}]{header}[/]")
            console.print(body)
            console.print(f"[{_TRACE_STYLE}]{eof}[/]")
            console.print()
            return
        except Exception:
            pass
        logger.info("%s%s%s", _ANSI_BEGIN, plain, _ANSI_END)
        return

    logger.info("\n%s", plain)


def log_agent_meta(
    *,
    role: str,
    model: str,
    agent_key: str,
    mode: str,
    label: str,
    detail: str,
) -> None:
    log_agent_block(
        role=role,
        model=model,
        agent_key=agent_key,
        mode=mode,
        label=label,
        body=detail,
    )
