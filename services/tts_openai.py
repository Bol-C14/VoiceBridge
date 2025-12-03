from __future__ import annotations

import io
from typing import Optional

from openai import OpenAI

from services.tts_base import TTSService


class OpenAITTSService(TTSService):
    """
    Wrapper around OpenAI TTS (audio.speech).
    """

    def __init__(self, api_key: str, model: str = "gpt-4o-mini-tts"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def synthesize(self, text: str, voice_id: str, style: Optional[str] = None) -> bytes:
        _ = style  # style not used in OpenAI TTS for now
        response = self.client.audio.speech.create(
            model=self.model,
            voice=voice_id,
            input=text,
        )
        # The SDK returns a streaming response; read() yields bytes.
        if hasattr(response, "read"):
            return response.read()
        # Fallback for potential future SDK interfaces.
        buffer = io.BytesIO()
        for chunk in response:
            buffer.write(chunk)
        return buffer.getvalue()
