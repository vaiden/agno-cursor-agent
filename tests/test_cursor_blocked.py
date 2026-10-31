import json

from agno_cursor.acp.session import ACPSession
from agno_cursor.model.cursor_acp import CursorACPChat
from tests.fake_acp import BlockingAskFake, BlockingPlanFake


def test_ask_question_parks_and_resumes(harness_settings):
    session = ACPSession.from_settings(
        "coder",
        "composer-2.5",
        "ask",
        harness_settings,
        popen_factory=BlockingAskFake,
    )
    try:
        first = session.prompt("start")
        assert hasattr(first, "kind")
        assert first.kind == "ask_question"
        assert "plan-1" in first.plans

        second = session.prompt("ignored while parked")
        assert second.kind == "ask_question"

        writes_before = len(session._proc.stdin.writes)  # type: ignore[union-attr]
        finished = session.resume(
            {
                "kind": "ask_question",
                "outcome": "answered",
                "answers": [{"questionId": "q1", "selectedOptionIds": ["agent"]}],
            }
        )
        assert isinstance(finished, str)
        assert "after-resume" in finished
        assert "[cursor_plan_snapshot]" in finished
        assert "plan-1" in finished
        writes_after = session._proc.stdin.writes  # type: ignore[union-attr]
        assert len(writes_after) == writes_before + 1
        ext_reply = json.loads(writes_after[-1].strip())
        assert ext_reply["id"] == BlockingAskFake.EXTENSION_ID
        assert ext_reply["result"]["outcome"]["outcome"] == "answered"
    finally:
        session.close()


def test_invalid_resume_returns_envelope_again(harness_settings):
    session = ACPSession.from_settings(
        "coder",
        "composer-2.5",
        "ask",
        harness_settings,
        popen_factory=BlockingAskFake,
    )
    try:
        session.prompt("start")
        bad = session.invalid_resume("not json")
        assert bad.kind == "ask_question"
        assert bad.parse_error == "not json"
    finally:
        session.close()


def test_create_plan_resume(harness_settings):
    session = ACPSession.from_settings(
        "planner",
        "composer-2.5",
        "plan",
        harness_settings,
        popen_factory=BlockingPlanFake,
    )
    try:
        blocked = session.prompt("plan something")
        assert blocked.kind == "create_plan"
        reply = session.resume({"kind": "create_plan", "outcome": "accepted"})
        assert isinstance(reply, str)
        assert "after-resume" in reply
    finally:
        session.close()


def test_cursor_acp_chat_blocked_envelope(harness_settings, monkeypatch):
    from agno.models.message import Message

    from agno_cursor.acp.registry import ACPSessionRegistry
    import agno_cursor.model.cursor_acp as cursor_acp_mod

    reg = ACPSessionRegistry()
    reg.set_popen_factory(BlockingAskFake)
    monkeypatch.setattr(cursor_acp_mod, "REGISTRY", reg)
    model = CursorACPChat(agent_key="coder", model="composer-2.5", mode="ask", settings=harness_settings)
    try:
        out = model.invoke([Message(role="user", content="go")], Message(role="assistant", content=""))
        assert out.content
        assert out.content.startswith("[cursor_blocked]")
        assert "ask_question" in out.content
    finally:
        reg.close_all()
