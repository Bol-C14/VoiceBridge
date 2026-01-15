from __future__ import annotations

from typing import Any, Dict

from core.types import Profile
from services.llm_base import LLMService


EXPLAIN_LAST_PROMPT = """You explain what the last utterance means in context.
Return JSON only, following the schema."""

EXPLAIN_LAST_SCHEMA = {
    "name": "explain_utterance_payload",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "intent": {"type": "string"},
            "key_points": {"type": "array", "items": {"type": "string"}},
            "implied_meaning": {"type": "string"},
            "examples": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["intent", "key_points", "implied_meaning", "examples"],
    },
}


class ExplainUtteranceEngine:
    def __init__(self, profile: Profile, llm: LLMService):
        self.profile = profile
        self.llm = llm

    def _build_messages(self, text: str) -> list[dict[str, str]]:
        prompt = self.profile.prompts.get("explain_last", "").strip()
        messages = [{"role": "system", "content": EXPLAIN_LAST_PROMPT}]
        if prompt:
            messages.append({"role": "system", "content": prompt})
        messages.append({"role": "user", "content": text})
        return messages

    def explain(self, text: str) -> Dict[str, Any]:
        if not self.llm:
            return {
                "intent": "other",
                "key_points": [text],
                "implied_meaning": "",
                "examples": [],
            }
        messages = self._build_messages(text)
        payload = self.llm.structured(messages, model=None, schema=EXPLAIN_LAST_SCHEMA)
        if isinstance(payload, dict) and payload.get("intent"):
            return payload
        raw = self.llm.complete(messages, model=None)
        return {
            "intent": "other",
            "key_points": [raw or text],
            "implied_meaning": "",
            "examples": [],
        }
