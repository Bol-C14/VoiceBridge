from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from voicebridge.core.types import MeetingSummary
from voicebridge.storage.session_store import SessionPaths, SessionStore


def export_markdown(store: SessionStore, paths: SessionPaths, *, title: Optional[str] = None) -> Path:
    summary = store.read_latest_summary(paths)
    transcript = store.read_recent_transcript(paths, limit=10_000)
    translations = _read_translations(paths.translations_jsonl)

    heading = title or "VoiceBridge Meeting"

    lines = [f"# {heading}", ""]
    lines.append(f"- Session: `{paths.session_dir.name}`")
    lines.append(f"- Exported: {datetime.utcnow().isoformat()}Z")
    lines.append("")

    if summary:
        lines.extend(_render_summary(summary))
        lines.append("")

    lines.append("## Transcript")
    lines.append("")
    for seg in transcript:
        t = _fmt_ms(seg.start_ms)
        speaker = seg.speaker_id or "Speaker"
        lines.append(f"- **{t} {speaker}:** {seg.text}")
        tr = translations.get(seg.id)
        if tr:
            lines.append(f"  - _{tr}_")

    paths.export_md.parent.mkdir(parents=True, exist_ok=True)
    paths.export_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return paths.export_md


def _render_summary(summary: MeetingSummary) -> list[str]:
    lines = ["## Summary", ""]
    if summary.bullets:
        lines.append("### Key points")
        lines.extend([f"- {b}" for b in summary.bullets])
        lines.append("")
    if summary.decisions:
        lines.append("### Decisions")
        lines.extend([f"- {d}" for d in summary.decisions])
        lines.append("")
    if summary.action_items:
        lines.append("### Action items")
        lines.extend([f"- {a}" for a in summary.action_items])
        lines.append("")
    if summary.keywords:
        lines.append("### Keywords")
        lines.append(", ".join(summary.keywords))
        lines.append("")
    if summary.topics:
        lines.append("### Topics")
        lines.append(", ".join(summary.topics))
        lines.append("")
    if summary.open_questions:
        lines.append("### Open questions")
        lines.extend([f"- {q}" for q in summary.open_questions])
        lines.append("")
    if summary.glossary_suggestions:
        lines.append("### Glossary")
        for k, v in summary.glossary_suggestions.items():
            lines.append(f"- **{k}:** {v}")
        lines.append("")
    return lines


def _read_translations(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    out: Dict[str, str] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            seg_id = str(obj.get("segment_id") or "")
            text = str(obj.get("text") or "")
            if seg_id:
                out[seg_id] = text
    return out


def _fmt_ms(ms: int) -> str:
    sec = max(0, int(ms // 1000))
    mm = sec // 60
    ss = sec % 60
    return f"{mm:02d}:{ss:02d}"

