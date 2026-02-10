from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict


SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class Event:
    schema_version: str
    session_id: str
    seq: int
    ts: str
    type: str
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "seq": self.seq,
            "ts": self.ts,
            "type": self.type,
            "payload": self.payload,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_event(session_id: str, seq: int, event_type: str, payload: Dict[str, Any]) -> Event:
    return Event(
        schema_version=SCHEMA_VERSION,
        session_id=session_id,
        seq=seq,
        ts=utc_now_iso(),
        type=event_type,
        payload=payload,
    )

