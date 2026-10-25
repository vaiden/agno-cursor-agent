import pytest

from agno_cursor import REGISTRY, ACPSession
from settings import TeamSettings


@pytest.mark.integration
def test_acp_session_persistence():
    settings = TeamSettings()
    session = ACPSession.from_settings("test", "composer-2.5-fast", "ask", settings)
    try:
        session.ensure_started()
        r1 = session.prompt("Reply with exactly: PERSIST_ONE")
        assert "PERSIST_ONE" in r1
        r2 = session.prompt("What exact phrase did I ask you to reply with earlier? One word.")
        assert "PERSIST" in r2.upper()
    finally:
        session.close()
        REGISTRY.close_all()
