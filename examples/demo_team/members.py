"""Shared roster and transport-agnostic member builder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Union

import httpx
from agno.agent import Agent, RemoteAgent

from agno_cursor import CursorACPChat

from settings import TeamSettings

Member = Union[Agent, RemoteAgent]


@dataclass(frozen=True)
class MemberSpec:
    id: str
    name: str
    role: str
    description: str


ROSTER: List[MemberSpec] = [
    MemberSpec(
        id="researcher",
        name="Researcher",
        role="researcher",
        description="Researches topics and gathers factual information concisely.",
    ),
    MemberSpec(
        id="coder",
        name="Coder",
        role="coder",
        description="Writes and explains code, inspects repositories, and implements technical tasks.",
    ),
    MemberSpec(
        id="writer",
        name="Writer",
        role="writer",
        description="Produces clear prose, documentation, and summaries for non-technical audiences.",
    ),
]

LEADER_ID = "leader"


def _worker_reachable(url: str, timeout: float = 3.0) -> bool:
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.get(f"{url.rstrip('/')}/health", follow_redirects=True)
            if r.status_code < 500:
                return True
    except Exception:
        return False
    return False


def build_member(spec: MemberSpec, settings: TeamSettings) -> Member:
    cfg = settings.resolve(spec.id, spec.role)

    if cfg.worker_url:
        if settings.worker_fallback_local and not _worker_reachable(cfg.worker_url):
            pass
        else:
            return RemoteAgent(
                base_url=cfg.worker_url.rstrip("/"),
                agent_id=spec.id,
                protocol="a2a",
                a2a_protocol="rest",
                timeout=180.0,
            )

    return Agent(
        id=spec.id,
        name=spec.name,
        role=spec.description,
        model=CursorACPChat(
            agent_key=spec.id,
            model=cfg.model,
            mode=cfg.mode,
            settings=settings,
        ),
    )


def build_leader_model(settings: TeamSettings) -> CursorACPChat:
    lc = settings.resolve(LEADER_ID, "leader")
    return CursorACPChat(
        agent_key=LEADER_ID,
        model=lc.model,
        mode=lc.mode,
        settings=settings,
    )
