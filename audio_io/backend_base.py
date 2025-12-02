from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable


class AudioOutputBackend(ABC):
    @abstractmethod
    def list_output_devices(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def play_to_device(self, device_name: str, audio_bytes: bytes) -> None:
        raise NotImplementedError


class AudioInputBackend(ABC):
    @abstractmethod
    def list_input_devices(self) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def capture_loopback(self, device_name: str) -> Iterable[bytes]:
        raise NotImplementedError
