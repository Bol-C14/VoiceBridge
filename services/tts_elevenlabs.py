from __future__ import annotations

from typing import Optional
import logging

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

        try:
            response = self.client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.content
        except httpx.TimeoutException:
            self._log().warning("ElevenLabs TTS timeout; returning empty bytes.")
            return b""
        except httpx.HTTPStatusError as exc:
            self._log().error("ElevenLabs TTS HTTP error: %s", exc)
            return b""
        except Exception as exc:
            self._log().error("ElevenLabs TTS unexpected error: %s", exc)
            return b""

    def _log(self) -> logging.Logger:
        return logging.getLogger("services.tts_elevenlabs")
