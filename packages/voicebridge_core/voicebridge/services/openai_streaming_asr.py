from __future__ import annotations

import io
import json
import queue
import time
import uuid
import wave
from dataclasses import dataclass
from typing import Callable, Dict, Optional

import requests

from voicebridge.core.logging import get_logger


log = get_logger("voicebridge.services.openai_streaming_asr")


@dataclass(frozen=True)
class OpenAIStreamingASRConfig:
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini-transcribe"
    language: Optional[str] = None  # ISO code; None means auto
    sample_rate: int = 16_000
    chunk_ms: int = 2_000
    timeout_sec: float = 60.0


PartialCallback = Callable[[str, Dict[str, object]], None]
FinalCallback = Callable[[str, Dict[str, object]], None]
ErrorCallback = Callable[[str], None]
ProgressCallback = Callable[[Dict[str, object]], None]


def _wav_bytes_from_pcm16_mono(pcm_bytes: bytes, *, sample_rate: int) -> bytes:
    bio = io.BytesIO()
    with wave.open(bio, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(int(sample_rate))
        wf.writeframes(pcm_bytes)
    return bio.getvalue()


class OpenAIStreamingASRWorker:
    """
    "Streaming-like" ASR using /audio/transcriptions with stream=true.

    This is not a single long-lived bidirectional stream; instead we:
    - chunk mic audio into small WAV blobs
    - POST each chunk with stream=true and parse SSE events
    - emit partial deltas as they arrive and a final transcript per chunk
    """

    def __init__(
        self,
        *,
        config: OpenAIStreamingASRConfig,
        on_partial: PartialCallback,
        on_final: FinalCallback,
        on_error: ErrorCallback,
        on_progress: Optional[ProgressCallback] = None,
    ):
        self.config = config
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_error = on_error
        self.on_progress = on_progress

        self._stopped = False

    def stop(self) -> None:
        self._stopped = True

    def run(self, *, frames: "queue.Queue[bytes]") -> None:
        bytes_per_ms = int(self.config.sample_rate * 2 / 1000)  # 16-bit mono
        chunk_bytes = max(3200, int(self.config.chunk_ms * bytes_per_ms))

        buf = bytearray()
        total_audio_ms = 0
        prev_final_tail = ""

        while not self._stopped:
            try:
                frame = frames.get(timeout=0.25)
            except Exception:
                continue
            if frame == b"":
                break
            buf.extend(frame)
            # Emit frequently if buffer is large enough.
            if len(buf) < chunk_bytes:
                continue

            pcm = bytes(buf)
            buf.clear()

            start_ms = int(total_audio_ms)
            dur_ms = int(len(pcm) / bytes_per_ms)
            end_ms = start_ms + dur_ms
            total_audio_ms = end_ms

            seg_id = str(uuid.uuid4())
            try:
                if self.on_progress:
                    self.on_progress({"state": "request", "model": self.config.model})
                text = self._transcribe_chunk_stream(
                    seg_id=seg_id,
                    pcm_bytes=pcm,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    prev_tail=prev_final_tail,
                )
                if text:
                    # Keep only a short tail for overlap de-duplication.
                    prev_final_tail = (prev_final_tail + " " + text).strip()[-300:]
            except Exception as exc:
                self.on_error(str(exc))

        # Flush remaining audio at end
        if buf:
            pcm = bytes(buf)
            start_ms = int(total_audio_ms)
            dur_ms = int(len(pcm) / bytes_per_ms)
            end_ms = start_ms + dur_ms
            seg_id = str(uuid.uuid4())
            try:
                self._transcribe_chunk_stream(
                    seg_id=seg_id,
                    pcm_bytes=pcm,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    prev_tail=prev_final_tail,
                )
            except Exception as exc:
                self.on_error(str(exc))

    def _transcribe_chunk_stream(
        self,
        *,
        seg_id: str,
        pcm_bytes: bytes,
        start_ms: int,
        end_ms: int,
        prev_tail: str,
    ) -> str:
        url = self.config.base_url.rstrip("/") + "/audio/transcriptions"
        headers = {"Authorization": f"Bearer {self.config.api_key}"}

        wav_bytes = _wav_bytes_from_pcm16_mono(pcm_bytes, sample_rate=self.config.sample_rate)
        files = {"file": ("chunk.wav", wav_bytes, "audio/wav")}
        data: Dict[str, str] = {"model": self.config.model, "stream": "true", "response_format": "json"}
        if self.config.language and self.config.language not in ("", "auto"):
            data["language"] = self.config.language

        assembled = ""
        prev_tail = (prev_tail or "").strip()

        t0 = time.time()
        with requests.post(url, headers=headers, data=data, files=files, stream=True, timeout=self.config.timeout_sec) as r:
            if r.status_code >= 400:
                raise RuntimeError(f"OpenAI transcription failed: {r.status_code}: {r.text}")

            # SSE format: lines like "event: ..." and "data: {...}"
            for raw in r.iter_lines(decode_unicode=True):
                if self._stopped:
                    break
                if raw is None:
                    continue
                line = str(raw).strip()
                if not line:
                    continue
                if not line.startswith("data:"):
                    continue
                payload = line[len("data:") :].strip()
                if payload == "[DONE]":
                    break
                try:
                    obj = json.loads(payload)
                except Exception:
                    continue
                typ = str(obj.get("type") or "")
                if typ == "transcript.text.delta":
                    delta = str(obj.get("delta") or "")
                    if not delta:
                        continue
                    assembled += delta
                    shown = _strip_overlap(prev_tail, assembled)
                    self.on_partial(
                        seg_id,
                        {
                            "text": shown,
                            "start_ms": start_ms,
                            "end_ms": end_ms,
                            "latency_ms": int((time.time() - t0) * 1000),
                        },
                    )
                elif typ == "transcript.text.done":
                    text = str(obj.get("text") or "")
                    if text:
                        assembled = text
                    break

        final_text = _strip_overlap(prev_tail, assembled).strip()
        if final_text:
            self.on_final(seg_id, {"text": final_text, "start_ms": start_ms, "end_ms": end_ms})
        return final_text


def _strip_overlap(prev_tail: str, text: str) -> str:
    """
    Best-effort de-dup across chunk boundaries.

    Some transcription backends repeat a small prefix from the previous chunk.
    We remove the longest overlap between the end of prev_tail and the start of text.
    """

    prev = (prev_tail or "").strip()
    cur = (text or "")
    if not prev or not cur:
        return cur

    # Common case: backend repeats the entire previous tail.
    if cur.startswith(prev):
        return cur[len(prev) :].lstrip()

    # Otherwise, find max suffix/prefix overlap.
    max_k = min(len(prev), len(cur), 200)
    for k in range(max_k, 12, -1):
        if prev[-k:] == cur[:k]:
            return cur[k:].lstrip()
    return cur
