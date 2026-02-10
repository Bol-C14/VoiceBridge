from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from voicebridge.core.events import Event
from voicebridge.core.types import MeetingSummary, TranscriptSegment, TranslationSegment
from voicebridge.storage.sqlite_index import SessionIndex


def default_storage_root() -> Path:
    return Path.home() / ".voicebridge"


@dataclass
class SessionPaths:
    session_dir: Path
    audio_wav: Path
    events_jsonl: Path
    transcript_jsonl: Path
    translations_jsonl: Path
    summary_json: Path
    summary_updates_jsonl: Path
    pending_json: Path
    export_md: Path


class SessionStore:
    """
    Persists a meeting session as:
    - audio.wav (optional)
    - events.jsonl (append-only)
    - transcript.jsonl (append-only upserts by segment_id)
    - translations.jsonl (append-only)
    - summary.json (overwrite latest)
    - summary_updates.jsonl (append-only)
    - pending.json (overwrite)
    - export.md (overwrite)
    - sessions.sqlite index at root
    """

    def __init__(self, storage_root: Optional[Path] = None):
        self.storage_root = storage_root or default_storage_root()
        self.sessions_dir = self.storage_root / "sessions"
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self.index = SessionIndex(self.storage_root / "sessions.sqlite")

    def session_paths(self, session_id: str) -> SessionPaths:
        d = self.sessions_dir / session_id
        return SessionPaths(
            session_dir=d,
            audio_wav=d / "audio.wav",
            events_jsonl=d / "events.jsonl",
            transcript_jsonl=d / "transcript.jsonl",
            translations_jsonl=d / "translations.jsonl",
            summary_json=d / "summary.json",
            summary_updates_jsonl=d / "summary_updates.jsonl",
            pending_json=d / "pending.json",
            export_md=d / "export.md",
        )

    def create_session(self, *, session_id: str, started_at_iso: str, profile: str, mode: str) -> SessionPaths:
        paths = self.session_paths(session_id)
        paths.session_dir.mkdir(parents=True, exist_ok=True)
        self.index.insert_session(
            session_id=session_id,
            started_at=started_at_iso,
            profile=profile,
            mode=mode,
            dir_path=paths.session_dir,
        )
        return paths

    def end_session(self, *, session_id: str, ended_at_iso: str) -> None:
        self.index.end_session(session_id=session_id, ended_at=ended_at_iso)

    def append_event(self, paths: SessionPaths, event: Event) -> None:
        paths.events_jsonl.parent.mkdir(parents=True, exist_ok=True)
        with paths.events_jsonl.open("a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")

    def append_transcript_segment(self, paths: SessionPaths, segment: TranscriptSegment) -> None:
        with paths.transcript_jsonl.open("a", encoding="utf-8") as f:
            f.write(json.dumps(segment.__dict__, ensure_ascii=False) + "\n")

    def append_translation(self, paths: SessionPaths, translation: TranslationSegment) -> None:
        with paths.translations_jsonl.open("a", encoding="utf-8") as f:
            f.write(json.dumps(translation.__dict__, ensure_ascii=False) + "\n")

    def write_summary(self, paths: SessionPaths, summary: MeetingSummary) -> None:
        with paths.summary_json.open("w", encoding="utf-8") as f:
            json.dump(summary.__dict__, f, ensure_ascii=False, indent=2)
        with paths.summary_updates_jsonl.open("a", encoding="utf-8") as f:
            f.write(json.dumps(summary.__dict__, ensure_ascii=False) + "\n")

    def write_pending(self, paths: SessionPaths, pending: Dict[str, Any]) -> None:
        with paths.pending_json.open("w", encoding="utf-8") as f:
            json.dump(pending, f, ensure_ascii=False, indent=2)

    def read_events(self, paths: SessionPaths) -> Iterable[Dict[str, Any]]:
        if not paths.events_jsonl.exists():
            return []
        with paths.events_jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    def read_latest_summary(self, paths: SessionPaths) -> Optional[MeetingSummary]:
        if not paths.summary_json.exists():
            return None
        with paths.summary_json.open("r", encoding="utf-8") as f:
            obj = json.load(f) or {}
        return MeetingSummary(
            bullets=list(obj.get("bullets") or []),
            decisions=list(obj.get("decisions") or []),
            action_items=list(obj.get("action_items") or []),
            keywords=list(obj.get("keywords") or []),
            topics=list(obj.get("topics") or []),
            open_questions=list(obj.get("open_questions") or []),
            glossary_suggestions=dict(obj.get("glossary_suggestions") or {}),
        )

    def read_recent_transcript(self, paths: SessionPaths, limit: int = 50) -> List[TranscriptSegment]:
        if not paths.transcript_jsonl.exists():
            return []
        segments_by_id: Dict[str, TranscriptSegment] = {}
        with paths.transcript_jsonl.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                seg_id = str(obj.get("id"))
                segments_by_id[seg_id] = (
                    TranscriptSegment(
                        id=seg_id,
                        start_ms=int(obj.get("start_ms") or 0),
                        end_ms=int(obj.get("end_ms") or 0),
                        text=str(obj.get("text") or ""),
                        language=obj.get("language"),
                        speaker_id=obj.get("speaker_id"),
                        confidence=obj.get("confidence"),
                    )
                )
        segments = sorted(
            segments_by_id.values(),
            key=lambda s: (s.start_ms, s.end_ms, s.id),
        )
        return segments[-limit:]
