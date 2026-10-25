import logging

from agno_cursor import trace as trace_mod


def test_log_agent_block_plain(caplog, monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("AGNO_CURSOR_ACP_TRACE_COLOR", "0")
    monkeypatch.setattr(trace_mod.sys.stderr, "isatty", lambda: False)
    monkeypatch.setattr(trace_mod.sys.stdout, "isatty", lambda: False)
    with caplog.at_level(logging.INFO):
        trace_mod.log_agent_block(
            role="leader",
            model="auto",
            agent_key="leader",
            mode="ask",
            label="test",
            body="hello",
        )
    assert "<EOF AGENT>" in caplog.text


def test_color_disabled_no_color(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert trace_mod._color_enabled() is False
