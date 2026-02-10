from __future__ import annotations

import wave
from pathlib import Path
from typing import Optional


class WavWriter:
    def __init__(self, path: Path, sample_rate: int, channels: int, sample_width_bytes: int = 2):
        self.path = path
        self.sample_rate = sample_rate
        self.channels = channels
        self.sample_width_bytes = sample_width_bytes
        self._wf: Optional[wave.Wave_write] = None

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        wf = wave.open(str(self.path), "wb")
        wf.setnchannels(self.channels)
        wf.setsampwidth(self.sample_width_bytes)
        wf.setframerate(self.sample_rate)
        self._wf = wf

    def write_pcm16(self, pcm_bytes: bytes) -> None:
        if self._wf is None:
            raise RuntimeError("WavWriter not opened")
        self._wf.writeframes(pcm_bytes)

    def close(self) -> None:
        if self._wf is not None:
            try:
                self._wf.close()
            finally:
                self._wf = None

    def __enter__(self) -> "WavWriter":
        self.open()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

