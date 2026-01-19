from __future__ import annotations

from typing import Any, Dict, List

from core.types import Profile
from services.llm_base import LLMService


EXPLAIN_CONCEPT_PROMPT = """You explain a concept for teaching as spoken script.
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
            "script": {"type": "array", "items": {"type": "string"}},
            "example": {"type": "string"},
            "checkpoints": {"type": "array", "items": {"type": "string"}},
            "common_pitfalls": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "title",
            "one_liner",
            "script",
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
        self.last_meta: Dict[str, Any] = {}

    def _build_messages(
        self, text: str, prompt_override: str | None = None
    ) -> list[dict[str, str]]:
        prompt = (
            prompt_override.strip()
            if prompt_override
            else self.profile.prompts.get("explain_concept", "").strip()
        )
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
        return text[:max_chars].rstrip()

    def _sanitize_script(self, script: Any) -> List[str]:
        max_sentences = int(
            self.profile.constraints.get(
                "max_script_sentences",
                self.profile.metadata.get("max_explain_steps", 6),
            )
        )
        max_chars = int(
            self.profile.constraints.get(
                "max_script_sentence_chars",
                self.profile.metadata.get("max_explain_step_chars", 35),
            )
        )
        cleaned: List[str] = []
        if isinstance(script, list):
            for item in script:
                text = self._coerce_text(item)
                if not text:
                    continue
                cleaned.append(self._limit_text(text, max_chars))
                if len(cleaned) >= max_sentences:
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
        max_checkpoints = int(
            self.profile.constraints.get(
                "max_explain_checkpoints",
                self.profile.metadata.get("max_explain_checkpoints", 3),
            )
        )
        max_pitfalls = int(
            self.profile.constraints.get(
                "max_explain_pitfalls",
                self.profile.metadata.get("max_explain_pitfalls", 3),
            )
        )
        max_text = int(
            self.profile.constraints.get(
                "max_explain_text_chars",
                self.profile.metadata.get(
                    "max_explain_text_chars",
                    self.profile.metadata.get("max_explain_chars", 300),
                ),
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

        script = []
        if isinstance(payload, dict) and "script" in payload:
            script = self._sanitize_script(payload.get("script"))
        if not script and isinstance(payload, dict) and "steps" in payload:
            steps = payload.get("steps")
            if isinstance(steps, list):
                script = []
                for step in steps:
                    if isinstance(step, dict):
                        script.append(self._coerce_text(step.get("say")))
                    else:
                        script.append(self._coerce_text(step))
                script = self._sanitize_script(script)
        if not script:
            script = [self._limit_text(topic, max_text)]

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
            "script": script,
            "example": example,
            "checkpoints": checkpoints,
            "common_pitfalls": pitfalls,
        }

    def explain(self, text: str, prompt_override: str | None = None) -> Dict[str, Any]:
        self.last_meta = {"structured_ok": False, "fallback_used": False}
        if not self.llm:
            self.last_meta["fallback_used"] = True
            payload = self._sanitize_payload({}, text)
            self.last_meta["output_chars"] = len(str(payload))
            return payload
        messages = self._build_messages(text, prompt_override=prompt_override)
        payload = self.llm.structured(messages, model=None, schema=EXPLAIN_CONCEPT_SCHEMA)
        if isinstance(payload, dict) and payload.get("title"):
            self.last_meta["structured_ok"] = True
            sanitized = self._sanitize_payload(payload, text)
            self.last_meta["output_chars"] = len(str(sanitized))
            return sanitized
        raw = self.llm.complete(messages, model=None)
        self.last_meta["fallback_used"] = True
        fallback_payload = {
            "title": text,
            "one_liner": raw or text,
            "script": [raw or text],
            "example": "",
            "checkpoints": [],
            "common_pitfalls": [],
        }
        sanitized = self._sanitize_payload(fallback_payload, text)
        self.last_meta["output_chars"] = len(str(sanitized))
        return sanitized
