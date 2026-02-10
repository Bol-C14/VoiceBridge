from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Generator, Optional

from voicebridge.core.logging import get_logger


log = get_logger("voicebridge.audio_io.mic")


@dataclass
class MicConfig:
    sample_rate: int = 16000
    channels: int = 1
    frame_duration_ms: int = 20
    device: Optional[str] = None


class SoundDeviceMicSource:
    """
    Microphone audio source using `sounddevice` (PortAudio).

    Produces fixed-size 16-bit PCM frames sized by `frame_duration_ms`.
    """

    def __init__(self, config: MicConfig):
        self.config = config
        self._queue: "queue.Queue[bytes]" = queue.Queue(maxsize=200)
        self._stop = threading.Event()
        self._stream = None

    @staticmethod
    def list_input_devices() -> list[str]:
        try:
            import sounddevice as sd  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("sounddevice is not installed. Install voicebridge-core[audio].") from exc

        devices = sd.query_devices()
        names = []
        for d in devices:
            if d.get("max_input_channels", 0) > 0:
                names.append(d.get("name", ""))
        return names

    def start(self) -> None:
        try:
            import numpy as np  # type: ignore
            import sounddevice as sd  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError(
                "Missing audio dependencies. Install voicebridge-core[audio]."
            ) from exc

        if self._stream is not None:
            return

        frames_per_block = int(self.config.sample_rate * self.config.frame_duration_ms / 1000)
        if frames_per_block <= 0:
            raise ValueError("frame_duration_ms too small")

        self._stop.clear()

        def callback(indata, _frames, _time, status):
            if status:
                log.warning("Audio callback status: %s", status)
            if self._stop.is_set():
                return
            # indata: float32 in [-1, 1]
            mono = indata
            if mono.ndim == 2 and mono.shape[1] > 1:
                mono = mono[:, 0:1]
            pcm16 = (mono * 32767.0).clip(-32768, 32767).astype(np.int16)
            try:
                self._queue.put_nowait(pcm16.tobytes())
            except queue.Full:
                # Drop frames under backpressure; better than blocking callback.
                pass

        self._stream = sd.InputStream(
            samplerate=self.config.sample_rate,
            channels=self.config.channels,
            dtype="float32",
            device=self.config.device,
            blocksize=frames_per_block,
            callback=callback,
        )
        self._stream.start()
        log.info(
            "Mic started (sr=%d ch=%d frame=%dms device=%s)",
            self.config.sample_rate,
            self.config.channels,
            self.config.frame_duration_ms,
            self.config.device or "default",
        )

    def stop(self) -> None:
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            finally:
                self._stream = None
        # Drain
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def frames(self) -> Generator[bytes, None, None]:
        """
        Yield PCM frames until stopped. Call `start()` first.
        """

        if self._stream is None:
            raise RuntimeError("Mic not started")

        while not self._stop.is_set():
            try:
                yield self._queue.get(timeout=0.5)
            except queue.Empty:
                continue

