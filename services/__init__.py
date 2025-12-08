"""Service facades for ASR, LLM, and TTS backends."""

from dataclasses import dataclass
from typing import Any


@dataclass
class ServiceBundle:
    asr: Any = None
    llm: Any = None
    tts: Any = None


__all__ = ["ServiceBundle"]
