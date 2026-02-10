from voicebridge.runtime.vad_segmenter import VadSegmenter


def test_vad_segmenter_emits_segment():
    # Deterministic "VAD": first 10 frames are speech, next 5 are silence.
    frame_bytes = b"\x00\x00" * 320  # 20ms @16kHz mono PCM16

    def is_speech(_frame: bytes, _sr: int) -> bool:
        # patched later using closure counter
        raise RuntimeError("not set")

    counter = {"i": 0}

    def is_speech_counted(_frame: bytes, _sr: int) -> bool:
        counter["i"] += 1
        return counter["i"] <= 10

    seg = VadSegmenter(
        sample_rate=16000,
        frame_duration_ms=20,
        padding_duration_ms=100,  # 5 frames
        min_segment_ms=300,
        is_speech=is_speech_counted,
    )

    segments = []
    for _ in range(15):
        segments.extend(seg.process_frame(frame_bytes))

    assert len(segments) == 1
    s0 = segments[0]
    assert s0.start_ms == 0
    assert s0.end_ms == 300
    assert len(s0.pcm_bytes) == len(frame_bytes) * 15

