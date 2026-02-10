from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from voicebridge.services.openai_http import OpenAIChatClient


class TranslateService(ABC):
    @abstractmethod
    def translate(self, text: str, source_lang: Optional[str], target_lang: str) -> str:
        raise NotImplementedError


@dataclass
class OpenAITranslateConfig:
    model: str


class OpenAITranslateService(TranslateService):
    def __init__(self, client: OpenAIChatClient, config: OpenAITranslateConfig):
        self.client = client
        self.config = config

    def translate(self, text: str, source_lang: Optional[str], target_lang: str) -> str:
        if not text.strip():
            return ""
        src = source_lang or "auto"
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a professional interpreter. Translate the user content faithfully. "
                    "Return only the translated text, no extra commentary."
                ),
            },
            {
                "role": "user",
                "content": f"Source language: {src}\nTarget language: {target_lang}\n\nText:\n{text}",
            },
        ]
        return self.client.chat(model=self.config.model, messages=messages, temperature=0.1).strip()

