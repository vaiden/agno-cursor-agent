import json

import pytest

from agno_cursor.acp.registry import ACPSessionRegistry
from agno_cursor.acp.session import ACPSession
from agno_cursor.settings import HarnessSettings


def test_acp_session_argv_property(harness_settings):
    session = ACPSession.from_settings("coder", "composer-2.5", "ask", harness_settings)
    assert session.argv == harness_settings.spawn_argv("composer-2.5", "ask")


def test_acp_session_prompt_fake_process(harness_settings, fake_popen_factory):
    session = ACPSession.from_settings(
        "coder",
        "composer-2.5",
        "ask",
        harness_settings,
        popen_factory=fake_popen_factory,
    )
    try:
        reply = session.prompt("hello")
        assert reply == "fake-reply"
    finally:
        session.close()


def test_acp_session_process_death(harness_settings):
    class DeadProcess:
        class _In:
            def write(self, data: str) -> None:
                del data

            def flush(self) -> None:
                pass

        def __init__(self, *args, **kwargs):
            del args, kwargs
            self.stdin = DeadProcess._In()
            self.stdout = iter([])
            self.stderr = iter(["boom\n"])

        def poll(self):
            return 1

    session = ACPSession.from_settings(
        "x",
        "composer-2.5",
        "ask",
        harness_settings,
        popen_factory=DeadProcess,
    )
    with pytest.raises(RuntimeError, match="died"):
        session.ensure_started()


def test_registry_reuse_and_close(harness_settings, fake_popen_factory):
    reg = ACPSessionRegistry()
    reg.set_popen_factory(fake_popen_factory)
    try:
        s1 = reg.get_or_create("a", "composer-2.5", "ask", harness_settings)
        s2 = reg.get_or_create("a", "composer-2.5", "ask", harness_settings)
        assert s1 is s2
        reg.close_all()
        s3 = reg.get_or_create("a", "composer-2.5", "ask", harness_settings)
        assert s3 is not s1
    finally:
        reg.close_all()


def test_permission_auto_reply(harness_settings):
    """session/request_permission should auto-allow without hanging."""
    from tests.fake_acp import FakeAcpProcess as BaseFake

    class PermFake(BaseFake):
        def _handle_request(self, msg):
            if msg.get("method") == "session/prompt":
                self.stdout_stream.push(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "method": "session/request_permission",
                            "id": 99,
                            "params": {},
                        }
                    )
                )
            super()._handle_request(msg)

    session = ACPSession.from_settings(
        "p",
        "composer-2.5",
        "ask",
        harness_settings,
        popen_factory=PermFake,
    )
    try:
        assert session.prompt("hi") == "fake-reply"
    finally:
        session.close()
