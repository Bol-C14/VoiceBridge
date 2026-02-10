from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from voicebridge.core.types import MeetingSummary, TranscriptSegment
from voicebridge.services.openai_http import OpenAIChatClient


class SummarizeService(ABC):
    @abstractmethod
    def update_rolling(
        self,
        summary_so_far: Optional[MeetingSummary],
        new_segments: List[TranscriptSegment],
        target_lang: str,
    ) -> MeetingSummary:
        raise NotImplementedError


@dataclass
class OpenAISummaryConfig:
    model: str


class OpenAISummarizeService(SummarizeService):
    def __init__(self, client: OpenAIChatClient, config: OpenAISummaryConfig):
        self.client = client
        self.config = config

    def update_rolling(
        self,
        summary_so_far: Optional[MeetingSummary],
        new_segments: List[TranscriptSegment],
        target_lang: str,
    ) -> MeetingSummary:
        prior = summary_so_far or MeetingSummary()
        recent_text = "\n".join([f"- {s.text}" for s in new_segments if s.text.strip()])[-8000:]
        prior_json = json.dumps(prior.__dict__, ensure_ascii=False)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a meeting assistant. Produce a concise rolling summary in JSON. "
                    "Return STRICT JSON only (no markdown). "
                    "Keys: bullets (list of strings), decisions (list), action_items (list), "
                    "keywords (list), topics (list), open_questions (list), glossary_suggestions (object). "
                    f"Write all text in target language: {target_lang}."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Prior summary JSON:\n"
                    f"{prior_json}\n\n"
                    "New transcript segments:\n"
                    f"{recent_text}\n\n"
                    "Update the prior summary with the new segments."
                ),
            },
        ]
        obj, _raw = self.client.chat_json(
            model=self.config.model,
            messages=messages,
            temperature=0.2,
            expect_keys=[
                "bullets",
                "decisions",
                "action_items",
                "keywords",
                "topics",
                "open_questions",
                "glossary_suggestions",
            ],
        )
        return MeetingSummary(
            bullets=list(obj.get("bullets") or []),
            decisions=list(obj.get("decisions") or []),
            action_items=list(obj.get("action_items") or []),
            keywords=list(obj.get("keywords") or []),
            topics=list(obj.get("topics") or []),
            open_questions=list(obj.get("open_questions") or []),
            glossary_suggestions=dict(obj.get("glossary_suggestions") or {}),
        )

