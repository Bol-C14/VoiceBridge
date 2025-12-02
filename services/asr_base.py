from __future__ import annotations

from abc import ABC, abstractmethod

from core.types import Utterance


class ASRService(ABC):
    """Speech-to-text abstraction."""

    @abstractmethod
    def transcribe(self, audio_bytes: bytes, language_hint: str | None = None) -> Utterance:
        raise NotImplementedError
