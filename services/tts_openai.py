from __future__ import annotations

import io
from typing import Optional, Any

from openai import OpenAI

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

        response = self.client.audio.speech.create(
            model=self.model,
            voice=voice_id,
            input=text,
            **params,
        )
        # The SDK returns a streaming response; read() yields bytes.
        if hasattr(response, "read"):
            return response.read()
        # Fallback for potential future SDK interfaces.
        buffer = io.BytesIO()
        for chunk in response:
            buffer.write(chunk)
        return buffer.getvalue()
