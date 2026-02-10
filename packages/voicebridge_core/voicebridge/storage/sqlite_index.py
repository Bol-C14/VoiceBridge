from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SessionRow:
    id: str
    started_at: str
    ended_at: Optional[str]
    profile: str
    mode: str
    dir: str


class SessionIndex:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    profile TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    dir TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def insert_session(self, *, session_id: str, started_at: str, profile: str, mode: str, dir_path: Path) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sessions (id, started_at, ended_at, profile, mode, dir) VALUES (?, ?, ?, ?, ?, ?)",
                (session_id, started_at, None, profile, mode, str(dir_path)),
            )
            conn.commit()

    def end_session(self, *, session_id: str, ended_at: str) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE sessions SET ended_at=? WHERE id=?", (ended_at, session_id))
            conn.commit()

    def list_sessions(self, limit: int = 50) -> List[SessionRow]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, started_at, ended_at, profile, mode, dir FROM sessions ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            SessionRow(
                id=r["id"],
                started_at=r["started_at"],
                ended_at=r["ended_at"],
                profile=r["profile"],
                mode=r["mode"],
                dir=r["dir"],
            )
            for r in rows
        ]

    def get_session(self, session_id: str) -> Optional[SessionRow]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, started_at, ended_at, profile, mode, dir FROM sessions WHERE id=?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return SessionRow(
            id=row["id"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            profile=row["profile"],
            mode=row["mode"],
            dir=row["dir"],
        )

    def to_dict(self, row: SessionRow) -> Dict[str, Any]:
        return {
            "id": row.id,
            "started_at": row.started_at,
            "ended_at": row.ended_at,
            "profile": row.profile,
            "mode": row.mode,
            "dir": row.dir,
        }

