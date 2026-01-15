from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from audio_io.backend_base import AudioOutputBackend
from core.logging import get_logger


class BasicAudioOutput(AudioOutputBackend):
    """
    Minimal audio output backend that plays raw audio bytes via system tools.
    Prefers built-in macOS `afplay`, then `ffplay`/`mpg123` if available.
    """

    def __init__(self):
        self.log = get_logger("audio.basic_output")
        self.player_cmd = self._detect_player()

    def list_output_devices(self) -> list[str]:
        # Device selection is not supported; return a single default device.
        return ["default"]

    def _detect_player(self) -> str | None:
        for candidate in ("afplay", "ffplay", "mpg123"):
            if shutil.which(candidate):
                return candidate
        return None

    def play_to_device(self, device_name: str, audio_bytes: bytes) -> None:
        if not audio_bytes:
            self.log.warning("No audio bytes to play.")
            return

        if not self.player_cmd:
            self.log.info(
                "No audio player found (tried afplay/ffplay/mpg123); skipping playback."
            )
            return

        suffix = ".mp3"  # Current TTS backends emit MPEG by default.
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(audio_bytes)
                tmp_path = Path(tmp.name)

            cmd = self._build_command(tmp_path)
            subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:
            self.log.error("Failed to play audio: %s", exc)
        finally:
            if tmp_path and tmp_path.exists():
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    def _build_command(self, path: Path) -> list[str]:
        if self.player_cmd == "ffplay":
            return ["ffplay", "-nodisp", "-autoexit", str(path)]
        return [self.player_cmd, str(path)]
