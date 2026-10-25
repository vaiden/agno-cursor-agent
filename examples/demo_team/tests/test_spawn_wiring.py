from agno_cursor.acp.session import ACPSession

from settings import TeamSettings


def test_acp_session_argv_property():
    s = TeamSettings()
    session = ACPSession.from_settings("coder", "composer-2.5", "ask", s)
    assert session.argv == s.spawn_argv("composer-2.5", "ask")
