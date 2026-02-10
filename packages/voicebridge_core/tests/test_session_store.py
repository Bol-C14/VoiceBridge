import json
from pathlib import Path

from voicebridge.core.events import make_event
from voicebridge.core.types import MeetingSummary, TranscriptSegment, TranslationSegment
from voicebridge.storage.session_store import SessionStore


def test_session_store_writes_files(tmp_path: Path):
    store = SessionStore(tmp_path)
    sid = "test-session"
    paths = store.create_session(session_id=sid, started_at_iso="t0", profile="Meeting", mode="meeting")

    store.append_event(paths, make_event(sid, 1, "session.started", {"a": 1}))
    store.append_transcript_segment(
        paths,
        TranscriptSegment(id="seg1", start_ms=0, end_ms=1000, text="hello"),
    )
    store.append_translation(paths, TranslationSegment(segment_id="seg1", target_lang="zh", text="你好"))
    store.write_summary(paths, MeetingSummary(bullets=["b1"], keywords=["k1"]))
    store.write_pending(paths, {"translations": ["seg1"], "summary": False})

    assert paths.events_jsonl.exists()
    assert paths.transcript_jsonl.exists()
    assert paths.translations_jsonl.exists()
    assert paths.summary_json.exists()
    assert paths.pending_json.exists()

    obj = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    assert obj["bullets"] == ["b1"]

