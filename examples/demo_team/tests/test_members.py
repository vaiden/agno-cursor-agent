from agno.agent import Agent, RemoteAgent

from members import ROSTER, build_member


def test_build_member_local(settings_factory):
    s = settings_factory()
    member = build_member(ROSTER[1], s)
    assert isinstance(member, Agent)
    assert member.model.id == "composer-2.5"


def test_build_member_remote(settings_factory):
    s = settings_factory(workers={"coder": "http://localhost:7801"})
    member = build_member(ROSTER[1], s)
    assert isinstance(member, RemoteAgent)
    assert member.agent_id == "coder"


def test_build_team_smoke():
    from members import ROSTER, build_leader_model, build_member
    from settings import TeamSettings

    settings = TeamSettings()
    members = [build_member(spec, settings) for spec in ROSTER]
    leader = build_leader_model(settings)
    assert leader.model == settings.resolve("leader", "leader").model
    assert len(members) == 3

