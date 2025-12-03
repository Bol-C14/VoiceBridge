from __future__ import annotations

import io
from typing import Optional

from openai import OpenAI

from core.types import Participant, Utterance
from services.asr_base import ASRService


class WhisperASRService(ASRService):
    """
    Wrapper around OpenAI Whisper API.
    """

    def __init__(self, api_key: str, model: str = "whisper-1"):
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def transcribe(self, audio_bytes: bytes, language_hint: Optional[str] = None) -> Utterance:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = "audio.wav"
        result = self.client.audio.transcriptions.create(
            model=self.model,
            file=audio_file,
            language=language_hint,
        )
        speaker = Participant(id="remote", role="remote_user", display_name="Remote")
        return Utterance(
            speaker=speaker,
            text=result.text,
            language=language_hint or None,
            source="mic",
        )
