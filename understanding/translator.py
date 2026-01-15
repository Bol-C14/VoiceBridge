from __future__ import annotations

from typing import Any, Dict

from services.llm_base import LLMService
from core.types import Profile


TRANSLATE_SYSTEM_PROMPT = """You translate the provided text accurately.
Return JSON only, following the schema."""

TRANSLATE_SCHEMA = {
    "name": "translation_payload",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "src_lang": {"type": "string"},
            "tgt_lang": {"type": "string"},
            "translation": {"type": "string"},
        },
        "required": ["src_lang", "tgt_lang", "translation"],
    },
}


class TranslateEngine:
    def __init__(self, profile: Profile, llm: LLMService):
        self.profile = profile
        self.llm = llm

    def _build_messages(self, text: str, target_lang: str) -> list[dict[str, str]]:
        prompt = self.profile.prompts.get("translate", "").strip()
        messages = [{"role": "system", "content": TRANSLATE_SYSTEM_PROMPT}]
        if prompt:
            messages.append({"role": "system", "content": prompt})
        messages.append(
            {
                "role": "system",
                "content": f"Target language: {target_lang}.",
            }
        )
        messages.append({"role": "user", "content": text})
        return messages

    def translate(self, text: str, target_lang: str) -> Dict[str, Any]:
        if not self.llm:
            return {"src_lang": "", "tgt_lang": target_lang, "translation": text}
        messages = self._build_messages(text, target_lang)
        payload = self.llm.structured(messages, model=None, schema=TRANSLATE_SCHEMA)
        if isinstance(payload, dict) and payload.get("translation"):
            return payload

        # Fallback to freeform completion.
        raw = self.llm.complete(messages, model=None)
        return {"src_lang": "", "tgt_lang": target_lang, "translation": raw or text}
