from __future__ import annotations

import pytest

from settings import TeamSettings


@pytest.fixture
def settings_factory():
    def _factory(**overrides):
        data = {
            "port": 7777,
            "team_id": "cursor_team",
            "default_model": "composer-2.5",
            "default_mode": "ask",
            "agents": {},
            "workers": {},
            "models": {},
            "modes": {},
        }
        data.update(overrides)
        return TeamSettings(**data)

    return _factory
