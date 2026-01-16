from __future__ import annotations

from typing import Any, Dict, List
import textwrap

from conversation.session_manager import ConversationSession
from core.types import Profile
from services.llm_base import LLMService


SUMMARY_PROMPT = """Summarize the recent teaching session.
Return JSON only, following the schema."""

SUMMARY_SCHEMA = {
    "name": "summary_payload",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {"type": "array", "items": {"type": "string"}},
            "misconceptions": {"type": "array", "items": {"type": "string"}},
            "homework": {"type": "array", "items": {"type": "string"}},
            "next_session_plan": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary", "misconceptions", "homework", "next_session_plan"],
    },
}


class Summarizer:
    def __init__(self, profile: Profile, llm: LLMService):
        self.profile = profile
        self.llm = llm

    def _build_messages(self, transcript: str) -> list[dict[str, str]]:
        prompt = self.profile.prompts.get("summarize", "").strip()
        messages = [{"role": "system", "content": SUMMARY_PROMPT}]
        if prompt:
            messages.append({"role": "system", "content": prompt})
        messages.append({"role": "user", "content": transcript})
        return messages

    def _build_transcript(self, session: ConversationSession, max_turns: int) -> str:
        parts = []
        for utt in session.get_window(since_last_summary=True, max_turns=max_turns):
            speaker = (
                "User" if utt.speaker.role == "local_user" else utt.speaker.display_name
            )
            parts.append(f"{speaker}: {utt.text}")
        return "\n".join(parts)

    def _limit_text(self, text: str, max_chars: int | None) -> str:
        if not max_chars or len(text) <= max_chars:
            return text
        return textwrap.shorten(text, width=max_chars, placeholder="...")

    def _sanitize_list(self, items: Any, max_items: int, max_chars: int) -> List[str]:
        if not isinstance(items, list):
            return []
        cleaned: List[str] = []
        for item in items:
            text = str(item).strip()
            if not text:
                continue
            cleaned.append(self._limit_text(text, max_chars))
            if len(cleaned) >= max_items:
                break
        return cleaned

    def _render_summary_markdown(self, payload: Dict[str, Any]) -> str:
        sections = [
            ("Summary", payload.get("summary")),
            ("Misconceptions", payload.get("misconceptions")),
            ("Homework", payload.get("homework")),
            ("Next Session Plan", payload.get("next_session_plan")),
        ]
        lines: List[str] = []
        for title, items in sections:
            if not items:
                continue
            lines.append(f"{title}:")
            for item in items:
                lines.append(f"- {item}")
            lines.append("")
        return "\n".join(lines).strip() or "- No summary available."

    def summarize(self, session: ConversationSession, max_turns: int = 12) -> Dict[str, Any]:
        if not self.llm:
            return {
                "summary": ["LLM not configured; summary unavailable."],
                "misconceptions": [],
                "homework": [],
                "next_session_plan": [],
                "summary_markdown": "- LLM not configured; summary unavailable.",
            }
        transcript = self._build_transcript(session, max_turns=max_turns)
        if not transcript.strip():
            return {
                "summary": ["No conversation to summarize."],
                "misconceptions": [],
                "homework": [],
                "next_session_plan": [],
                "summary_markdown": "- No conversation to summarize.",
            }
        messages = self._build_messages(transcript)
        payload = self.llm.structured(messages, model=None, schema=SUMMARY_SCHEMA)
        max_items = int(self.profile.metadata.get("max_summary_items", 5))
        max_chars = int(self.profile.metadata.get("max_summary_item_chars", 160))
        if isinstance(payload, dict) and payload.get("summary"):
            cleaned = {
                "summary": self._sanitize_list(payload.get("summary"), max_items, max_chars),
                "misconceptions": self._sanitize_list(
                    payload.get("misconceptions"), max_items, max_chars
                ),
                "homework": self._sanitize_list(
                    payload.get("homework"), max_items, max_chars
                ),
                "next_session_plan": self._sanitize_list(
                    payload.get("next_session_plan"), max_items, max_chars
                ),
            }
            cleaned["summary_markdown"] = self._render_summary_markdown(cleaned)
            return cleaned
        raw = self.llm.complete(messages, model=None)
        fallback = {
            "summary": [raw or "No summary generated."],
            "misconceptions": [],
            "homework": [],
            "next_session_plan": [],
        }
        fallback["summary_markdown"] = self._render_summary_markdown(fallback)
        return fallback
