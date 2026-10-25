from unittest.mock import MagicMock, patch

from agno.models.message import Message

from agno_cursor import CursorACPChat
from agno_cursor.settings import HarnessSettings


def test_build_prompt_first_turn_includes_system():
    model = CursorACPChat(agent_key="a", model="composer-2.5", settings=HarnessSettings())
    messages = [
        Message(role="system", content="You are helpful"),
        Message(role="user", content="Hi"),
    ]
    prompt = model._build_prompt(messages)
    assert "System instructions" in prompt
    assert "Hi" in prompt


def test_build_prompt_later_turn_user_only():
    model = CursorACPChat(agent_key="a", model="composer-2.5", settings=HarnessSettings())
    model._first_turn = False
    messages = [
        Message(role="system", content="You are helpful"),
        Message(role="user", content="Second question"),
    ]
    prompt = model._build_prompt(messages)
    assert "System instructions" not in prompt
    assert prompt == "Second question"


def test_invoke_uses_registry_prompt():
    settings = HarnessSettings()
    model = CursorACPChat(agent_key="a", model="composer-2.5", settings=settings)
    session = MagicMock()
    session.prompt.return_value = '{"content":"done"}'
    with patch("agno_cursor.model.cursor_acp.REGISTRY.get_or_create", return_value=session):
        resp = model.invoke(
            [Message(role="user", content="go")],
            Message(role="assistant", content=""),
        )
    assert resp.content == "done"
    session.prompt.assert_called_once()
