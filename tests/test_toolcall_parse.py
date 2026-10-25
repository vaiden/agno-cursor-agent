from agno_cursor import CursorACPChat


def test_parse_tool_calls():
    model = CursorACPChat(id="composer-2.5", agent_key="leader", model="composer-2.5")
    raw = '{"tool_calls":[{"name":"delegate_task_to_member","arguments":{"member_id":"coder","task":"fix bug"}}]}'
    resp = model._parse_provider_response(raw)
    assert resp.tool_calls
    assert resp.tool_calls[0]["function"]["name"] == "delegate_task_to_member"


def test_parse_content_json():
    model = CursorACPChat(id="composer-2.5", agent_key="leader", model="composer-2.5")
    raw = '{"content":"Hello world"}'
    resp = model._parse_provider_response(raw)
    assert resp.content == "Hello world"


def test_parse_plain_text_fallback():
    model = CursorACPChat(id="composer-2.5", agent_key="leader", model="composer-2.5")
    raw = "Just plain text"
    resp = model._parse_provider_response(raw)
    assert resp.content == "Just plain text"


def test_extract_json_embedded():
    model = CursorACPChat(id="composer-2.5", agent_key="leader", model="composer-2.5")
    raw = 'Here is JSON: {"content":"ok"} trailing'
    parsed = model._extract_json(raw)
    assert parsed and parsed.get("content") == "ok"
