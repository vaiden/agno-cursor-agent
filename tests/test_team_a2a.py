import httpx
import pytest


@pytest.fixture
def team_base_url_fixture():
    import os

    return os.environ.get("TEAM_BASE_URL", "http://localhost:7777")


@pytest.mark.integration
def test_team_agent_card(team_base_url_fixture):
    url = f"{team_base_url_fixture.rstrip('/')}/a2a/teams/cursor_team/.well-known/agent-card.json"
    r = httpx.get(url, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data


@pytest.mark.integration
@pytest.mark.asyncio
async def test_team_a2a_message_send(team_base_url_fixture):
    from agno.agent import RemoteAgent

    remote = RemoteAgent(
        base_url=f"{team_base_url_fixture.rstrip('/')}/a2a/teams/cursor_team",
        agent_id="cursor_team",
        protocol="a2a",
        a2a_protocol="rest",
        timeout=300.0,
    )
    response = await remote.arun("What is 2+2? Answer in one word only.")
    assert response.content
    assert "tool_calls" not in str(response.content)
    assert len(response.content.strip()) > 0
