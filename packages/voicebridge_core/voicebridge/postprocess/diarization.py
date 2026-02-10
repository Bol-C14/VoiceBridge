from __future__ import annotations

from typing import List

from voicebridge.core.types import TranscriptSegment
from voicebridge.storage.session_store import SessionPaths, SessionStore


def apply_heuristic_diarization(
    store: SessionStore,
    paths: SessionPaths,
    *,
    gap_ms: int = 1200,
) -> List[TranscriptSegment]:
    """
    Extremely lightweight, dependency-free diarization heuristic:
    - labels segments as Speaker A / Speaker B
    - toggles speaker when a long pause (gap_ms) occurs between segments

    This is meant as a placeholder until a real diarization backend is added.
    """

    segments = store.read_recent_transcript(paths, limit=100_000)
    if not segments:
        return []

    speakers = ["Speaker A", "Speaker B"]
    current = 0
    prev_end = None
    updated: List[TranscriptSegment] = []

    for seg in segments:
        if prev_end is not None and seg.start_ms - prev_end >= gap_ms:
            current = 1 - current
        prev_end = seg.end_ms
        updated_seg = TranscriptSegment(
            id=seg.id,
            start_ms=seg.start_ms,
            end_ms=seg.end_ms,
            text=seg.text,
            language=seg.language,
            speaker_id=speakers[current],
            confidence=seg.confidence,
        )
        store.append_transcript_segment(paths, updated_seg)
        updated.append(updated_seg)

    return updated

