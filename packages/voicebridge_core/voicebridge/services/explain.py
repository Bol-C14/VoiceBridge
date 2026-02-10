from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from voicebridge.core.types import TranscriptSegment
from voicebridge.services.openai_http import OpenAIChatClient


class ExplainService(ABC):
    @abstractmethod
    def explain(
        self,
        term: str,
        context_segments: List[TranscriptSegment],
        target_lang: str,
    ) -> str:
        raise NotImplementedError


@dataclass
class OpenAIExplainConfig:
    model: str


class OpenAIExplainService(ExplainService):
    def __init__(self, client: OpenAIChatClient, config: OpenAIExplainConfig):
        self.client = client
        self.config = config

    def explain(
        self,
        term: str,
        context_segments: List[TranscriptSegment],
        target_lang: str,
    ) -> str:
        term = term.strip()
        if not term:
            return ""
        context = "\n".join([f"- {s.text}" for s in context_segments if s.text.strip()])[-8000:]
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a technical mentor helping someone follow an in-person meeting. "
                    "Explain the term/topic clearly and briefly, then give a 3-bullet 'why it matters here' "
                    "based on the meeting context. "
                    f"Write in: {target_lang}."
                ),
            },
            {
                "role": "user",
                "content": f"Term/topic: {term}\n\nMeeting context:\n{context}",
            },
        ]
        return self.client.chat(model=self.config.model, messages=messages, temperature=0.3).strip()

