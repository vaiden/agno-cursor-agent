"""Pytest fixtures."""

from __future__ import annotations

import pytest

from agno_cursor.settings import HarnessSettings
from tests.fake_acp import FakeAcpProcess


@pytest.fixture
def fake_popen_factory():
    def _factory(*args, **kwargs):
        return FakeAcpProcess(*args, **kwargs)

    return _factory


@pytest.fixture
def harness_settings(tmp_path):
    return HarnessSettings(project_root=tmp_path, acp_trace=False)
