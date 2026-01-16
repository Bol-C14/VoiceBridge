from __future__ import annotations

import io
from typing import Optional, Any
import logging
import time

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
        params = {**self.default_params}
        if style:
            params.setdefault("style", style)

        started = time.monotonic()
        error = None
        audio_bytes = b""
        try:
            response = self.client.audio.speech.create(
                model=self.model,
                voice=voice_id,
                input=text,
                **params,
            )

            # The SDK returns a streaming response; read() yields bytes.
            if hasattr(response, "read"):
                audio_bytes = response.read()
            else:
                buffer = io.BytesIO()
                for chunk in response:
                    buffer.write(chunk)
                audio_bytes = buffer.getvalue()
        except APITimeoutError:
            error = "timeout"
            self._log().warning("OpenAI TTS timeout; returning empty bytes.")
        except APIError as exc:
            error = str(exc)
            self._log().error("OpenAI TTS error: %s", exc)
        finally:
            latency_ms = int((time.monotonic() - started) * 1000)
            self._emit_metrics(
                {
                    "service": "tts",
                    "provider": "openai",
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "input_chars": len(text),
                    "output_bytes": len(audio_bytes),
                    "success": error is None and bool(audio_bytes),
                    "error": error,
                }
            )
        return audio_bytes

    def _log(self) -> logging.Logger:
        return logging.getLogger("services.tts_openai")
