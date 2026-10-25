"""Per-host A2A worker wrapping one Cursor ACP agent (remote member target)."""

from __future__ import annotations

import atexit
import logging
import os

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.os import AgentOS

from agno_cursor import REGISTRY, CursorACPChat, check_cursor_login

from members import ROSTER
from settings import TeamSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = TeamSettings()
worker_agent_id = settings.agent_id or os.environ.get("CURSOR_TEAM_AGENT_ID", "researcher")
worker_port = int(os.environ.get("CURSOR_TEAM_PORT", os.environ.get("AGENT_OS_PORT", "7801")))

spec = next((s for s in ROSTER if s.id == worker_agent_id), ROSTER[0])
cfg = settings.resolve(spec.id, spec.role)

db = SqliteDb(db_file=str(settings.project_root / f"worker_{spec.id}.db"))

agent = Agent(
    id=spec.id,
    name=spec.name,
    role=spec.description,
    model=CursorACPChat(
        agent_key=spec.id,
        model=cfg.model,
        mode=cfg.mode,
        settings=settings,
    ),
    db=db,
    markdown=True,
)

agent_os = AgentOS(agents=[agent], db=db, a2a_interface=True)
app = agent_os.get_app()


def _startup() -> None:
    check_cursor_login()
    REGISTRY.warm([(spec.id, cfg.model, cfg.mode)], settings)
    session = REGISTRY.get_or_create(spec.id, cfg.model, cfg.mode, settings)
    logger.info("Worker %s ACP argv: %s", spec.id, session.argv)


def _shutdown() -> None:
    REGISTRY.close_all()


atexit.register(_shutdown)

if __name__ == "__main__":
    _startup()
    try:
        agent_os.serve(app=app, host="0.0.0.0", port=worker_port, reload=False)
    finally:
        _shutdown()
