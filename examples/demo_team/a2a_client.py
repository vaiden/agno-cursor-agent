"""Standalone A2A client for the deployed Agno team."""

from __future__ import annotations

import asyncio
import sys

from agno.agent import RemoteAgent

from settings import TeamSettings, team_base_url


async def main() -> None:
    settings = TeamSettings()
    base = team_base_url().rstrip("/")
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Briefly describe what this team can help with."

    remote = RemoteAgent(
        base_url=f"{base}/a2a/teams/{settings.team_id}",
        agent_id=settings.team_id,
        protocol="a2a",
        a2a_protocol="rest",
        timeout=300.0,
    )
    response = await remote.arun(prompt)
    print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
