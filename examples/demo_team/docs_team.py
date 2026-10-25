"""Self-documenting Agno team that writes project documentation."""

from __future__ import annotations

import asyncio
import logging

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.team import Team
from agno.team.mode import TeamMode

from agno_cursor import REGISTRY, CursorACPChat, check_cursor_login

from members import MemberSpec
from settings import AgentConfig, TeamSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DOCS_ROSTER = [
    MemberSpec(
        id="product_owner",
        name="Product Owner",
        role="product_owner",
        description="Defines documentation scope, audience, and acceptance criteria.",
    ),
    MemberSpec(
        id="coder",
        name="Coder",
        role="coder",
        description="Inspects the repository and extracts accurate architecture and API details.",
    ),
    MemberSpec(
        id="writer",
        name="Writer",
        role="writer",
        description="Authors README.md and docs/ARCHITECTURE.md with clear structure.",
    ),
]


def _docs_agent_key(agent_id: str) -> str:
    return f"docs:{agent_id}"


def build_docs_team(settings: TeamSettings) -> Team:
    doc_settings = settings.model_copy(deep=True)
    for spec in DOCS_ROSTER:
        base = doc_settings.agents.get(spec.id, AgentConfig())
        doc_settings.agents[spec.id] = AgentConfig(**{**base.model_dump(), "mode": "agent"})

    lc = doc_settings.resolve("leader", "leader")

    def _key(agent_id: str) -> str:
        return _docs_agent_key(agent_id)

    leader = CursorACPChat(agent_key=_key("leader"), model=lc.model, mode="agent", settings=doc_settings)

    members = []
    for spec in DOCS_ROSTER:
        cfg = doc_settings.resolve(spec.id, spec.role)
        members.append(
            Agent(
                id=spec.id,
                name=spec.name,
                role=spec.description,
                model=CursorACPChat(
                    agent_key=_key(spec.id),
                    model=cfg.model,
                    mode="agent",
                    settings=doc_settings,
                ),
            )
        )

    db = SqliteDb(db_file=str(settings.project_root / "docs_team.db"))
    return Team(
        id="docs_team",
        name="Documentation Team",
        model=leader,
        members=members,
        mode=TeamMode.coordinate,
        db=db,
        instructions=[
            "Produce documentation for this Agno + Cursor ACP + A2A project.",
            "The coder inspects source files; the writer creates README.md and docs/ARCHITECTURE.md.",
            "Cover: architecture, setup, local vs remote config, role-based models, tests, and Agno UI.",
            "Write files inside the project directory only.",
        ],
        markdown=True,
        show_members_responses=True,
    )


async def run_docs() -> None:
    settings = TeamSettings()
    check_cursor_login()
    team = build_docs_team(settings)
    lc = settings.resolve("leader", "leader")

    warm = [(_docs_agent_key("leader"), lc.model, "agent")]
    for spec in DOCS_ROSTER:
        cfg = settings.resolve(spec.id, spec.role)
        warm.append((_docs_agent_key(spec.id), cfg.model, "agent"))
    REGISTRY.warm(warm, settings)

    prompt = (
        f"Document this project under {settings.project_root}. "
        "Update README.md and create docs/ARCHITECTURE.md with accurate details from the codebase."
    )
    try:
        await team.arun(prompt)
        logger.info("Documentation team run completed")
    finally:
        REGISTRY.close_all()


if __name__ == "__main__":
    asyncio.run(run_docs())
