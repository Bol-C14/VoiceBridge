from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from uuid import uuid4

from core.types import Profile, Session, Suggestion, Utterance


class ConversationSession:
    """
    In-memory container for utterances and suggestions within a single profile-bound session.
    """

    def __init__(self, profile: Profile):
        self.session = Session(id=str(uuid4()), profile=profile)

    def add_utterance(self, utterance: Utterance) -> None:
        self.session.add_utterance(utterance)

    def add_suggestion(self, suggestion: Suggestion) -> None:
        self.session.add_suggestion(suggestion)

    def get_recent_context(self, max_turns: int = 8) -> list[Utterance]:
        return self.session.utterances[-max_turns:]

    def select_last_utterance(self, role: str = "remote_user") -> Utterance | None:
        for utt in reversed(self.session.utterances):
            if utt.speaker.role == role:
                return utt
        return None

    def get_window(
        self,
        since_last_summary: bool = True,
        max_turns: int = 12,
    ) -> list[Utterance]:
        utterances = self.session.utterances
        if since_last_summary:
            last_idx = self.session.metadata.get("last_summary_index")
            if isinstance(last_idx, int):
                utterances = utterances[last_idx:]
        if max_turns:
            utterances = utterances[-max_turns:]
        return utterances

    def export_transcript(self, format: str = "jsonl") -> str:
        session_meta = {
            "type": "session",
            "session_id": self.session.id,
            "profile_name": self.session.profile.name,
            "started_at": self.session.started_at.isoformat(),
        }

        if format == "md":
            lines = [
                f"# Transcript: {self.session.profile.name}",
                f"- Session: {self.session.id}",
                f"- Started: {self.session.started_at.isoformat()}",
                "",
            ]
            for utt in self.session.utterances:
                ts = utt.timestamp.isoformat()
                role = utt.speaker.display_name or utt.speaker.role
                lines.append(f"- [{ts}] {role}: {utt.text}")
            return "\n".join(lines)

        lines = [json.dumps(session_meta, ensure_ascii=True)]
        for utt in self.session.utterances:
            lines.append(
                json.dumps(
                    {
                        "type": "utterance",
                        "timestamp": utt.timestamp.isoformat(),
                        "role": utt.speaker.role,
                        "speaker": utt.speaker.display_name,
                        "text": utt.text,
                        "language": utt.language,
                        "source": utt.source,
                    },
                    ensure_ascii=True,
                )
            )
        for suggestion in self.session.suggestions:
            lines.append(
                json.dumps(
                    {
                        "type": "suggestion",
                        "text": suggestion.text,
                        "tone": suggestion.tone,
                        "length": suggestion.length,
                        "risk": suggestion.risk,
                        "auto_send": suggestion.auto_send,
                    },
                    ensure_ascii=True,
                )
            )
        return "\n".join(lines)

    def export_transcript_jsonl(self, path: Path) -> None:
        transcript = self.export_transcript(format="jsonl")
        path.write_text(transcript, encoding="utf-8")

    def export_summary_md(self, path: Path, summary: Dict[str, Any] | str) -> None:
        if isinstance(summary, dict):
            summary_text = summary.get("summary_markdown")
            if not summary_text:
                summary_text = self._render_summary_md(summary)
        else:
            summary_text = str(summary)
        path.write_text(summary_text or "- No summary available.", encoding="utf-8")

    def _render_summary_md(self, summary: Dict[str, Any]) -> str:
        sections = [
            ("Summary", summary.get("summary")),
            ("Misconceptions", summary.get("misconceptions")),
            ("Homework", summary.get("homework")),
            ("Next Session Plan", summary.get("next_session_plan")),
        ]
        lines: list[str] = []
        for title, items in sections:
            if not items:
                continue
            lines.append(f"{title}:")
            if isinstance(items, list):
                for item in items:
                    text = str(item).strip()
                    if text:
                        lines.append(f"- {text}")
            lines.append("")
        return "\n".join(lines).strip() or "- No summary available."

    def to_chat_history(
        self,
        max_turns: int = 8,
        system_prompt: str | None = None,
    ) -> list[dict[str, str]]:
        """
        Convert recent utterances to OpenAI-style chat messages.
        Speaker role is mapped: local_user -> user, others -> assistant.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        for utt in self.get_recent_context(max_turns):
            role = "user" if utt.speaker.role == "local_user" else "assistant"
            messages.append({"role": role, "content": utt.text})
        return messages

    @property
    def profile(self) -> Profile:
        return self.session.profile
