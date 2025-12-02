from __future__ import annotations

from abc import ABC, abstractmethod


class TTSService(ABC):
    """Text-to-speech abstraction."""

    @abstractmethod
    def synthesize(self, text: str, voice_id: str, style: str | None = None) -> bytes:
        """
        Return audio bytes (wav/mp3).
        """
        raise NotImplementedError
