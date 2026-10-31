"""AgentOS deployment: Agno team exposed over A2A, Cursor agents via ACP."""

from __future__ import annotations

import atexit
import logging
from typing import List

from agno.db.sqlite import SqliteDb
from agno.os import AgentOS
from agno.team import Team
from agno.team.mode import TeamMode

from agno_cursor import REGISTRY, check_cursor_login

from members import ROSTER, build_leader_model, build_member
from settings import TeamSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = TeamSettings()
db = SqliteDb(db_file=str(settings.project_root / "agno_team.db"))


def _local_warm_targets(members: List) -> List[tuple[str, str, str]]:
    warm: List[tuple[str, str, str]] = []
    lc = settings.resolve("leader", "leader")
    warm.append(("leader", lc.model, lc.mode))
    for spec in ROSTER:
        cfg = settings.resolve(spec.id, spec.role)
        if not cfg.worker_url or settings.worker_fallback_local:
            warm.append((spec.id, cfg.model, cfg.mode))
    return warm


def build_team() -> Team:
    members = [build_member(spec, settings) for spec in ROSTER]
    leader_model = build_leader_model(settings)
    return Team(
        id=settings.team_id,
        name="Cursor ACP Team",
        model=leader_model,
        members=members,
        mode=TeamMode.coordinate,
        db=db,
        instructions=[
            "You coordinate a team of Cursor-powered specialists.",
            "Delegate research, coding, and writing tasks to the appropriate member.",
            "Synthesize member outputs into a clear final answer.",
            "When a member returns a [cursor_blocked] message, that member is paused inside an open Cursor turn.",
            "If the task already answers the question or plan, delegate back to the same member with only the JSON reply it specifies.",
            "If you need the user, ask them and stop; on their next message, translate their answer into that JSON and delegate it to the same member.",
            "Do not treat [cursor_blocked] as finished work or assign that member a new task while blocked.",
        ],
        markdown=True,
        show_members_responses=True,
    )


team = build_team()
agent_os = AgentOS(teams=[team], db=db, a2a_interface=True)
app = agent_os.get_app()


def _startup() -> None:
    check_cursor_login()
    warm = _local_warm_targets(team.members)
    logger.info("Warming %d local ACP sessions", len(warm))
    REGISTRY.warm(warm, settings)
    for agent_key, model, mode in warm:
        session = REGISTRY.get_or_create(agent_key, model, mode, settings)
        logger.info("ACP argv for %s: %s", agent_key, session.argv)


def _shutdown() -> None:
    REGISTRY.close_all()


atexit.register(_shutdown)


if __name__ == "__main__":
    _startup()
    logger.info(
        "AgentOS is listening on all interfaces (0.0.0.0:%s). "
        "In os.agno.com or Agent UI, connect to http://localhost:%s or http://127.0.0.1:%s — "
        "not http://0.0.0.0:%s (browsers cannot use 0.0.0.0 as a destination).",
        settings.port,
        settings.port,
        settings.port,
        settings.port,
    )
    try:
        agent_os.serve(app=app, host="0.0.0.0", port=settings.port, reload=False)
    finally:
        _shutdown()
