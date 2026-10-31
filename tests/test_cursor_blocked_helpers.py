import json

from agno_cursor.acp.cursor_blocked import (
    CursorBlockedTurn,
    append_plan_snapshot,
    build_extension_rpc_result,
    cancelled_rpc_result,
    format_blocked_envelope,
    parse_resume_payload,
    validate_resume_payload,
)


def test_cursor_blocked_turn_method_property():
    ask = CursorBlockedTurn(kind="ask_question", agent_key="a", params={})
    plan = CursorBlockedTurn(kind="create_plan", agent_key="a", params={})
    assert ask.method == "cursor/ask_question"
    assert plan.method == "cursor/create_plan"


def test_parse_resume_payload_variants():
    assert parse_resume_payload('{"kind":"ask_question"}') == {"kind": "ask_question"}
    assert parse_resume_payload("prefix {\"kind\": \"x\"} suffix") == {"kind": "x"}
    assert parse_resume_payload("not json") is None
    assert parse_resume_payload("{bad") is None


def test_validate_resume_payload_errors():
    assert "Expected kind" in validate_resume_payload("ask_question", {"kind": "create_plan"})  # type: ignore[arg-type]
    assert validate_resume_payload("ask_question", {"kind": "ask_question", "outcome": "answered", "answers": []})
    assert validate_resume_payload("ask_question", {"kind": "ask_question", "outcome": "skipped"}) is None
    assert validate_resume_payload("ask_question", {"kind": "ask_question", "outcome": "cancelled"}) is None
    assert "Invalid ask_question" in validate_resume_payload("ask_question", {"kind": "ask_question", "outcome": "nope"})  # type: ignore[arg-type]
    assert validate_resume_payload("create_plan", {"kind": "create_plan", "outcome": "accepted"}) is None
    assert validate_resume_payload("create_plan", {"kind": "create_plan", "outcome": "rejected", "reason": "no"}) is None
    assert validate_resume_payload("create_plan", {"kind": "create_plan", "outcome": "cancelled"}) is None
    assert "requires a reason" in validate_resume_payload("create_plan", {"kind": "create_plan", "outcome": "rejected"})  # type: ignore[arg-type]
    assert "Unknown blocked kind" in validate_resume_payload("other", {"kind": "other", "outcome": "x"})  # type: ignore[arg-type]


def test_build_extension_rpc_result_variants():
    assert build_extension_rpc_result(
        "ask_question",
        {"outcome": "answered", "answers": [{"questionId": "q1", "selectedOptionIds": ["a"]}]},
    )["outcome"] == "answered"
    assert build_extension_rpc_result("ask_question", {"outcome": "skipped", "reason": "later"}) == {
        "outcome": "skipped",
        "reason": "later",
    }
    assert build_extension_rpc_result("ask_question", {"outcome": "cancelled"}) == {"outcome": "cancelled"}
    assert build_extension_rpc_result("create_plan", {"outcome": "accepted", "planUri": "u"}) == {
        "outcome": "accepted",
        "planUri": "u",
    }
    assert build_extension_rpc_result("create_plan", {"outcome": "rejected", "reason": "n"}) == {
        "outcome": "rejected",
        "reason": "n",
    }
    assert build_extension_rpc_result("create_plan", {"outcome": "cancelled"}) == {"outcome": "cancelled"}


def test_cancelled_rpc_result():
    assert cancelled_rpc_result("ask_question") == {"outcome": "cancelled"}
    assert cancelled_rpc_result("create_plan") == {"outcome": "cancelled"}


def test_format_blocked_envelope_ask_and_plan():
    ask = CursorBlockedTurn(
        kind="ask_question",
        agent_key="coder",
        params={"questions": []},
        plans={"p": {"planId": "p"}},
        parse_error="bad",
    )
    text = format_blocked_envelope(ask)
    assert "[cursor_blocked]" in text
    assert "parse_error: bad" in text
    assert "plan_snapshot:" in text
    assert "ask_question" in text

    plan = CursorBlockedTurn(kind="create_plan", agent_key="planner", params={"plan": "x"})
    plan_text = format_blocked_envelope(plan)
    assert "create_plan" in plan_text
    assert "reply_with_json_only" in plan_text


def test_append_plan_snapshot():
    assert append_plan_snapshot("hi", {}) == "hi"
    out = append_plan_snapshot("", {"a": 1})
    assert out.startswith("[cursor_plan_snapshot]")
    assert "hi" in append_plan_snapshot("hi", {"planId": "1"})


def test_resume_validation_in_session(harness_settings):
    from tests.fake_acp import BlockingAskFake

    from agno_cursor.acp.session import ACPSession

    session = ACPSession.from_settings(
        "coder",
        "composer-2.5",
        "ask",
        harness_settings,
        popen_factory=BlockingAskFake,
    )
    try:
        session.prompt("start")
        err = session.resume({"kind": "ask_question", "outcome": "answered", "answers": []})
        assert hasattr(err, "parse_error")
        assert session.is_parked()
    finally:
        session.close()


def test_invalid_resume_cancels_after_max(harness_settings):
    from tests.fake_acp import BlockingAskFake

    from agno_cursor.acp.session import ACPSession

    session = ACPSession.from_settings(
        "coder",
        "composer-2.5",
        "ask",
        harness_settings,
        popen_factory=BlockingAskFake,
    )
    try:
        session.prompt("start")
        for _ in range(2):
            blocked = session.invalid_resume("bad")
            assert blocked.kind == "ask_question"
        finished = session.invalid_resume("bad")
        assert isinstance(finished, str)
        assert "after-resume" in finished
    finally:
        session.close()
