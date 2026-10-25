from agno_cursor import build_spawn_argv
from agno_cursor.settings import HarnessSettings


def test_spawn_argv_ask():
    s = HarnessSettings()
    assert s.spawn_argv("composer-2.5", "ask") == [
        "cursor-agent",
        "--model",
        "composer-2.5",
        "--mode",
        "ask",
        "acp",
    ]


def test_spawn_argv_plan():
    assert build_spawn_argv("cursor-agent", "gpt-5.5-high", "plan") == [
        "cursor-agent",
        "--model",
        "gpt-5.5-high",
        "--mode",
        "plan",
        "acp",
    ]


def test_spawn_argv_agent():
    s = HarnessSettings()
    assert s.spawn_argv("composer-2.5", "agent") == [
        "cursor-agent",
        "--model",
        "composer-2.5",
        "--force",
        "acp",
    ]
