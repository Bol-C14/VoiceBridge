from __future__ import annotations

from typing import Any, Dict

from core.types import Profile
from services.llm_base import LLMService


EXPLAIN_CONCEPT_PROMPT = """You explain a concept for teaching.
Return JSON only, following the schema."""

EXPLAIN_CONCEPT_SCHEMA = {
    "name": "explain_concept_payload",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "explanation": {"type": "string"},
            "steps": {"type": "array", "items": {"type": "string"}},
            "examples": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["explanation", "steps", "examples"],
    },
}


class ExplainConceptEngine:
    def __init__(self, profile: Profile, llm: LLMService):
        self.profile = profile
        self.llm = llm

    def _build_messages(self, text: str) -> list[dict[str, str]]:
        prompt = self.profile.prompts.get("explain_concept", "").strip()
        messages = [{"role": "system", "content": EXPLAIN_CONCEPT_PROMPT}]
        if prompt:
            messages.append({"role": "system", "content": prompt})
        messages.append({"role": "user", "content": text})
        return messages

    def explain(self, text: str) -> Dict[str, Any]:
        if not self.llm:
            return {"explanation": text, "steps": [], "examples": []}
        messages = self._build_messages(text)
        payload = self.llm.structured(messages, model=None, schema=EXPLAIN_CONCEPT_SCHEMA)
        if isinstance(payload, dict) and payload.get("explanation"):
            return payload
        raw = self.llm.complete(messages, model=None)
        return {"explanation": raw or text, "steps": [], "examples": []}
