from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from core.logging import get_logger
from core.types import Session


class StorageAdapter(ABC):
    @abstractmethod
    def save_session(self, session: Session) -> None:
        raise NotImplementedError

    @abstractmethod
    def append_event(self, session_id: str, event: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_session(self, session_id: str) -> Optional[Session]:
        raise NotImplementedError


class LocalFileStorageAdapter(StorageAdapter):
    def __init__(self, base_dir: Path | str = "logs"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.log = get_logger("storage.local")

    def _jsonl_path(self, session_id: str) -> Path:
        return self.base_dir / f"{session_id}_events.jsonl"

    def append_event(self, session_id: str, event: Dict[str, Any]) -> None:
        path = self._jsonl_path(session_id)
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=True))
                f.write("\n")
        except OSError as exc:
            self.log.warning("Failed to append event to %s: %s", path, exc)

    def save_session(self, session: Session) -> None:
        path = self.base_dir / f"{session.id}_session.json"
        try:
            payload = {
                "session_id": session.id,
                "profile_name": session.profile.name,
                "started_at": session.started_at.isoformat(),
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "utterances": [
                    {
                        "timestamp": utt.timestamp.isoformat(),
                        "role": utt.speaker.role,
                        "speaker": utt.speaker.display_name,
                        "text": utt.text,
                        "language": utt.language,
                        "source": utt.source,
                    }
                    for utt in session.utterances
                ],
                "suggestions": [
                    {
                        "text": s.text,
                        "tone": s.tone,
                        "length": s.length,
                        "risk": s.risk,
                        "auto_send": s.auto_send,
                    }
                    for s in session.suggestions
                ],
                "metadata": session.metadata,
            }
            with path.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=True, indent=2)
        except OSError as exc:
            self.log.warning("Failed to save session snapshot to %s: %s", path, exc)

    def load_session(self, session_id: str) -> Optional[Session]:
        _ = session_id
        return None
