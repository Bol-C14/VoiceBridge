from __future__ import annotations

from typing import Any, Dict, List
import textwrap

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
            "title": {"type": "string"},
            "one_liner": {"type": "string"},
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "step": {"type": "integer"},
                        "say": {"type": "string"},
                        "why": {"type": "string"},
                    },
                    "required": ["step", "say", "why"],
                },
            },
            "example": {"type": "string"},
            "checkpoints": {"type": "array", "items": {"type": "string"}},
            "common_pitfalls": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "title",
            "one_liner",
            "steps",
            "example",
            "checkpoints",
            "common_pitfalls",
        ],
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

    def _coerce_text(self, value: Any, default: str = "") -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text if text else default

    def _limit_text(self, text: str, max_chars: int | None) -> str:
        if not max_chars or len(text) <= max_chars:
            return text
        return textwrap.shorten(text, width=max_chars, placeholder="...")

    def _sanitize_steps(self, steps: Any) -> List[Dict[str, Any]]:
        max_steps = int(self.profile.metadata.get("max_explain_steps", 4))
        max_step_chars = int(self.profile.metadata.get("max_explain_step_chars", 220))
        cleaned: List[Dict[str, Any]] = []
        if not isinstance(steps, list):
            return cleaned
        for idx, step in enumerate(steps, 1):
            if not isinstance(step, dict):
                continue
            say = self._coerce_text(step.get("say"))
            if not say:
                continue
            why = self._coerce_text(step.get("why", ""))
            say = self._limit_text(say, max_step_chars)
            why = self._limit_text(why, max_step_chars)
            cleaned.append({"step": idx, "say": say, "why": why})
            if len(cleaned) >= max_steps:
                break
        return cleaned

    def _sanitize_list(self, items: Any, max_items: int) -> List[str]:
        if not isinstance(items, list):
            return []
        cleaned = []
        for item in items:
            text = self._coerce_text(item)
            if not text:
                continue
            cleaned.append(text)
            if len(cleaned) >= max_items:
                break
        return cleaned

    def _sanitize_payload(self, payload: Any, topic: str) -> Dict[str, Any]:
        max_checkpoints = int(self.profile.metadata.get("max_explain_checkpoints", 3))
        max_pitfalls = int(self.profile.metadata.get("max_explain_pitfalls", 3))
        max_text = int(
            self.profile.metadata.get(
                "max_explain_text_chars",
                self.profile.metadata.get("max_explain_chars", 300),
            )
        )

        title = self._coerce_text(
            payload.get("title") if isinstance(payload, dict) else None, default=topic
        )
        one_liner = self._coerce_text(
            payload.get("one_liner") if isinstance(payload, dict) else None,
            default=topic,
        )
        example = self._coerce_text(
            payload.get("example") if isinstance(payload, dict) else None, default=""
        )
        title = self._limit_text(title, max_text)
        one_liner = self._limit_text(one_liner, max_text)
        example = self._limit_text(example, max_text)

        steps = self._sanitize_steps(payload.get("steps") if isinstance(payload, dict) else None)
        if not steps:
            steps = [{"step": 1, "say": topic, "why": ""}]

        checkpoints = self._sanitize_list(
            payload.get("checkpoints") if isinstance(payload, dict) else None,
            max_checkpoints,
        )
        pitfalls = self._sanitize_list(
            payload.get("common_pitfalls") if isinstance(payload, dict) else None,
            max_pitfalls,
        )
        return {
            "title": title,
            "one_liner": one_liner,
            "steps": steps,
            "example": example,
            "checkpoints": checkpoints,
            "common_pitfalls": pitfalls,
        }

    def explain(self, text: str) -> Dict[str, Any]:
        if not self.llm:
            return self._sanitize_payload({}, text)
        messages = self._build_messages(text)
        payload = self.llm.structured(messages, model=None, schema=EXPLAIN_CONCEPT_SCHEMA)
        if isinstance(payload, dict) and payload.get("title"):
            return self._sanitize_payload(payload, text)
        raw = self.llm.complete(messages, model=None)
        fallback_payload = {
            "title": text,
            "one_liner": raw or text,
            "steps": [{"step": 1, "say": raw or text, "why": ""}],
            "example": "",
            "checkpoints": [],
            "common_pitfalls": [],
        }
        return self._sanitize_payload(fallback_payload, text)
