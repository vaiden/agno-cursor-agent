import subprocess
from unittest.mock import MagicMock, patch

import pytest

from agno_cursor.settings import HarnessSettings, check_cursor_login, resolve_acp_role


def test_harness_settings_env_prefix(monkeypatch):
    monkeypatch.setenv("AGNO_CURSOR_BASE_SPAWN_CMD", "agent")
    monkeypatch.setenv("AGNO_CURSOR_ACP_TRACE", "true")
    s = HarnessSettings()
    assert s.base_spawn_cmd == "agent"
    assert s.acp_trace is True


def test_resolve_acp_role_without_resolve(harness_settings):
    assert resolve_acp_role(harness_settings, "coder") == "coder"


def test_check_cursor_login_success():
    with patch("agno_cursor.settings.shutil.which", return_value="/usr/bin/cursor-agent"):
        with patch("agno_cursor.settings.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 0, stdout="Logged in as user", stderr="")
            check_cursor_login()


def test_check_cursor_login_missing_cli():
    with patch("agno_cursor.settings.shutil.which", return_value=None):
        with pytest.raises(RuntimeError, match="not found"):
            check_cursor_login()


def test_check_cursor_login_not_logged_in():
    with patch("agno_cursor.settings.shutil.which", return_value="/usr/bin/cursor-agent"):
        with patch("agno_cursor.settings.subprocess.run") as run:
            run.return_value = subprocess.CompletedProcess([], 1, stdout="", stderr="not logged in")
            with pytest.raises(RuntimeError, match="not logged in"):
                check_cursor_login()
