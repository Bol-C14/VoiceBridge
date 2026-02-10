from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ASRResult:
    text: str
    language: Optional[str] = None
    confidence: Optional[float] = None


class ASRService(ABC):
    """Speech-to-text abstraction."""

    @abstractmethod
    def transcribe_pcm16(
        self,
        pcm_bytes: bytes,
        sample_rate: int,
        language_hint: Optional[str] = None,
    ) -> ASRResult:
        raise NotImplementedError

