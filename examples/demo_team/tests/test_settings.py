from settings import AgentConfig, TeamSettings


def test_resolve_role_defaults(settings_factory):
    s: TeamSettings = settings_factory()
    assert s.resolve("leader", "leader").model == "auto"
    assert s.resolve("coder", "coder").model == "composer-2.5"
    assert s.resolve("writer", "writer").model == "claude-sonnet-5-5-medium"
    assert s.resolve("product_owner", "product_owner").model == "claude-sonnet-5-5-medium"
    assert s.resolve("researcher", "researcher").model == "composer-2.5"


def test_resolve_override_wins(settings_factory):
    s: TeamSettings = settings_factory(agents={"researcher": AgentConfig(model="auto")})
    assert s.resolve("researcher", "researcher").model == "auto"


def test_resolve_mode_override(settings_factory):
    s: TeamSettings = settings_factory(agents={"writer": AgentConfig(mode="agent")})
    assert s.resolve("writer", "writer").mode == "agent"


def test_worker_url_from_shorthand(settings_factory):
    s: TeamSettings = settings_factory(workers={"researcher": "http://localhost:7801"})
    assert s.resolve("researcher", "researcher").worker_url == "http://localhost:7801"
