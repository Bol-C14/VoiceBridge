from __future__ import annotations

from typing import Any, Dict

from conversation.session_manager import ConversationSession
from core.types import Profile
from services.llm_base import LLMService


SUMMARY_PROMPT = """Summarize the recent conversation.
Return JSON only, following the schema."""

SUMMARY_SCHEMA = {
    "name": "summary_payload",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary_markdown": {"type": "string"},
            "key_points": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["summary_markdown", "key_points"],
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

    def summarize(self, session: ConversationSession, max_turns: int = 12) -> Dict[str, Any]:
        if not self.llm:
            return {
                "summary_markdown": "- LLM not configured; summary unavailable.",
                "key_points": [],
            }
        transcript = self._build_transcript(session, max_turns=max_turns)
        if not transcript.strip():
            return {"summary_markdown": "- No conversation to summarize.", "key_points": []}
        messages = self._build_messages(transcript)
        payload = self.llm.structured(messages, model=None, schema=SUMMARY_SCHEMA)
        if isinstance(payload, dict) and payload.get("summary_markdown"):
            return payload
        raw = self.llm.complete(messages, model=None)
        summary = raw or "No summary generated."
        return {"summary_markdown": summary, "key_points": []}
