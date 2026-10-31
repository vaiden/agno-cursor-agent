import json
from unittest.mock import MagicMock, patch

import pytest

from agno_cursor.acp.registry import ACPSessionRegistry
from agno_cursor.acp.session import ACPSession, _trace_preview
from agno_cursor.model.cursor_acp import CursorACPChat
from agno_cursor.settings import HarnessSettings


def test_trace_preview_truncates():
    long = "x" * 2000
    out = _trace_preview(long, limit=100)
    assert "chars total" in out


def test_session_acp_error_response(harness_settings, fake_popen_factory):
    from tests.fake_acp import FakeAcpProcess as Base

    class ErrFake(Base):
        def _handle_request(self, msg):
            req_id = msg.get("id")
            if msg.get("method") == "initialize":
                self.stdout_stream.push(
                    json.dumps({"jsonrpc": "2.0", "id": req_id, "error": {"message": "nope"}})
                )

    session = ACPSession.from_settings("e", "m", "ask", harness_settings, popen_factory=ErrFake)
    with pytest.raises(RuntimeError, match="error"):
        session.ensure_started()


def test_session_closed_raises(harness_settings, fake_popen_factory):
    session = ACPSession.from_settings("c", "m", "ask", harness_settings, popen_factory=fake_popen_factory)
    session.close()
    with pytest.raises(RuntimeError, match="closed"):
        session.ensure_started()


def test_session_trace_prompt(harness_settings, fake_popen_factory):
    settings = HarnessSettings(project_root=harness_settings.project_root, acp_trace=True)
    session = ACPSession.from_settings("t", "m", "ask", settings, popen_factory=fake_popen_factory)
    try:
        session.prompt("hello")
    finally:
        session.close()


def test_registry_warm(harness_settings, fake_popen_factory):
    reg = ACPSessionRegistry()
    reg.set_popen_factory(fake_popen_factory)
    try:
        reg.warm([("a", "m", "ask"), ("b", "m", "plan")], harness_settings)
        assert len(reg._sessions) == 2
    finally:
        reg.close_all()


@pytest.mark.asyncio
async def test_cursor_ainvoke_and_stream():
    model = CursorACPChat(agent_key="a", model="composer-2.5")
    session = MagicMock()
    session.is_parked.return_value = False
    session.parked_kind = None
    session.prompt.return_value = '{"content":"async"}'
    with patch("agno_cursor.model.cursor_acp.REGISTRY.get_or_create", return_value=session):
        from agno.models.message import Message

        msgs = [Message(role="user", content="hi")]
        asst = Message(role="assistant", content="")
        resp = await model.ainvoke(msgs, asst)
        assert resp.content == "async"
        streamed = [r async for r in model.ainvoke_stream(msgs, asst)]
        assert streamed[0].content == "async"
        sync_stream = list(model.invoke_stream(msgs, asst))
        assert sync_stream[0].content == "async"


def test_build_prompt_with_tools():
    from agno.models.message import Message

    model = CursorACPChat(agent_key="a", model="composer-2.5")
    tools = [{"type": "function", "function": {"name": "fn", "description": "d", "parameters": {}}}]
    prompt = model._build_prompt([Message(role="user", content="u")], tools=tools)
    assert "tool_calls" in prompt
    assert "fn" in prompt
