from __future__ import annotations

import io
from typing import Optional, Any
import logging
import io

from openai import APIError, APITimeoutError, OpenAI

from services.tts_base import TTSService


class OpenAITTSService(TTSService):
    """
    Wrapper around OpenAI TTS (audio.speech).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini-tts",
        default_params: dict[str, Any] | None = None,
    ):
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.default_params = default_params or {}

    def synthesize(self, text: str, voice_id: str, style: Optional[str] = None) -> bytes:
        params = {**self.default_params}
        if style:
            params.setdefault("style", style)

        try:
            response = self.client.audio.speech.create(
                model=self.model,
                voice=voice_id,
                input=text,
                **params,
            )
        except APITimeoutError:
            self._log().warning("OpenAI TTS timeout; returning empty bytes.")
            return b""
        except APIError as exc:
            self._log().error("OpenAI TTS error: %s", exc)
            return b""

        # The SDK returns a streaming response; read() yields bytes.
        if hasattr(response, "read"):
            return response.read()
        buffer = io.BytesIO()
        for chunk in response:
            buffer.write(chunk)
        return buffer.getvalue()

    def _log(self) -> logging.Logger:
        return logging.getLogger("services.tts_openai")
