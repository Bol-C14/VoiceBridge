import json

from voicebridge.core.events import make_event


def test_event_roundtrip():
    ev = make_event("s1", 1, "session.started", {"x": 1})
    obj = json.loads(ev.to_json())
    assert obj["schema_version"]
    assert obj["session_id"] == "s1"
    assert obj["seq"] == 1
    assert obj["type"] == "session.started"
    assert obj["payload"]["x"] == 1

