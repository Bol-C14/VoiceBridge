from __future__ import annotations

from typing import Optional, Any
import logging
import time

import httpx

from services.tts_base import TTSService


class ElevenLabsTTSService(TTSService):
    """
    Minimal ElevenLabs TTS client.
    """

    def __init__(
        self,
        api_key: str,
        model_id: str = "eleven_multilingual_v2",
        base_url: str = "https://api.elevenlabs.io",
        timeout: float = 15.0,
    ):
        self.api_key = api_key
        self.model_id = model_id
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
        self.metrics_hook = None

    def _emit_metrics(self, payload: dict[str, Any]) -> None:
        hook = getattr(self, "metrics_hook", None)
        if not callable(hook):
            return
        try:
            hook(payload)
        except Exception:
            self._log().warning("Failed to emit TTS metrics.")

    def synthesize(self, text: str, voice_id: str, style: Optional[str] = None) -> bytes:
        url = f"{self.base_url}/v1/text-to-speech/{voice_id}"
        headers = {
            "xi-api-key": self.api_key,
            "Accept": "audio/mpeg",
        }
        payload = {
            "text": text,
            "model_id": self.model_id,
        }
        if style:
            payload["voice_settings"] = {"style": style}

        started = time.monotonic()
        error = None
        audio_bytes = b""
        try:
            response = self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            audio_bytes = response.content
        except httpx.TimeoutException:
            error = "timeout"
            self._log().warning("ElevenLabs TTS timeout; returning empty bytes.")
        except httpx.HTTPStatusError as exc:
            error = str(exc)
            self._log().error("ElevenLabs TTS HTTP error: %s", exc)
        except Exception as exc:
            error = str(exc)
            self._log().error("ElevenLabs TTS unexpected error: %s", exc)
        finally:
            latency_ms = int((time.monotonic() - started) * 1000)
            self._emit_metrics(
                {
                    "service": "tts",
                    "provider": "elevenlabs",
                    "model": self.model_id,
                    "latency_ms": latency_ms,
                    "input_chars": len(text),
                    "output_bytes": len(audio_bytes),
                    "success": error is None and bool(audio_bytes),
                    "error": error,
                }
            )
        return audio_bytes

    def _log(self) -> logging.Logger:
        return logging.getLogger("services.tts_elevenlabs")
