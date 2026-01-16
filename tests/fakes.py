from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from services.llm_base import LLMService
from services.tts_base import TTSService


class FakeLLM(LLMService):
    def __init__(self, structured_payload: Any = None, complete_text: str = ""):
        self._structured_payload = structured_payload
        self._complete_text = complete_text

    def complete(self, messages: list[dict[str, Any]], model: str, **kwargs: Any) -> str:
        return self._complete_text

    def structured(self, messages: list[dict[str, Any]], model: str, schema: Any):
        return self._structured_payload


class FakeTTS(TTSService):
    def synthesize(self, text: str, voice_id: str, style: str | None = None) -> bytes:
        return b"audio"


class DummyOutput:
    def play_to_device(self, device_name: str, audio_bytes: bytes) -> None:
        _ = device_name
        _ = audio_bytes


@dataclass
class DummyStorage:
    events: list[dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.events is None:
            self.events = []

    def save_session(self, session) -> None:
        _ = session

    def append_event(self, session_id: str, event: dict[str, Any]) -> None:
        _ = session_id
        self.events.append(event)

    def load_session(self, session_id: str):
        _ = session_id
        return None
