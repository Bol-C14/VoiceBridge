from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from voicebridge.services.asr import ASRResult, ASRService


@dataclass
class FasterWhisperConfig:
    model: str = "small"
    device: str = "auto"
    compute_type: Optional[str] = None
    beam_size: int = 1


class FasterWhisperASRService(ASRService):
    def __init__(self, config: FasterWhisperConfig):
        self.config = config
        self._model = None

    def _get_model(self):
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("faster-whisper not installed. Install voicebridge-core[asr].") from exc

        kwargs = {}
        if self.config.compute_type:
            kwargs["compute_type"] = self.config.compute_type
        self._model = WhisperModel(self.config.model, device=self.config.device, **kwargs)
        return self._model

    def transcribe_pcm16(
        self,
        pcm_bytes: bytes,
        sample_rate: int,
        language_hint: Optional[str] = None,
    ) -> ASRResult:
        try:
            import numpy as np  # type: ignore
        except Exception as exc:  # pragma: no cover
            raise RuntimeError("numpy not installed. Install voicebridge-core[asr].") from exc

        audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32) / 32768.0
        model = self._get_model()
        language = None if (language_hint in (None, "", "auto")) else language_hint

        segments, info = model.transcribe(
            audio,
            language=language,
            beam_size=self.config.beam_size,
            vad_filter=False,
        )
        texts = []
        avg_conf = None
        seg_count = 0
        for seg in segments:
            if seg.text:
                texts.append(seg.text.strip())
            # seg has avg_logprob etc; map roughly if present
            if hasattr(seg, "avg_logprob"):
                seg_count += 1
                if avg_conf is None:
                    avg_conf = 0.0
                avg_conf += float(getattr(seg, "avg_logprob"))
        if avg_conf is not None and seg_count > 0:
            avg_conf = avg_conf / seg_count
        text = " ".join([t for t in texts if t])
        detected_lang = getattr(info, "language", None) if info is not None else None
        return ASRResult(text=text, language=detected_lang, confidence=avg_conf)

