"""Audio input/output abstractions."""

from dataclasses import dataclass
from typing import Any

from audio_io.backend_base import AudioInputBackend, AudioOutputBackend
from audio_io.basic_output import BasicAudioOutput


@dataclass
class AudioIOBundle:
    output: Any = None


__all__ = ["AudioInputBackend", "AudioOutputBackend", "BasicAudioOutput", "AudioIOBundle"]
