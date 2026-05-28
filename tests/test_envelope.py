from claude_chat import envelope


def test_text_roundtrip():
    body = "héllo 🌍 bob"  # intentionally multibyte UTF-8
    env = envelope.make_text(body)
    parsed = envelope.parse(envelope.encode(env))
    assert parsed["type"] == "text"
    assert parsed["data"]["body"] == body
    assert parsed["uuid"] == env["uuid"]


def test_parse_non_json_is_treated_as_text():
    parsed = envelope.parse(b"just a plain message")
    assert parsed["type"] == "text"
    assert parsed["data"]["body"] == "just a plain message"
    assert parsed["uuid"]  # a uuid is synthesized


def test_parse_fills_missing_uuid_and_ts():
    parsed = envelope.parse(b'{"type": "text", "data": {"body": "hi"}}')
    assert parsed["uuid"]
    assert parsed["ts"]
    assert parsed["data"]["body"] == "hi"
