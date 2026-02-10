from pathlib import Path

import yaml

from voicebridge.config import save_settings
from voicebridge.config.loader import load_profiles, load_settings


def test_load_profiles_from_temp(tmp_path: Path):
    cfg_dir = tmp_path / "profiles"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "settings.yml").write_text("asr_default_model: small\n", encoding="utf-8")

    meeting = {
        "name": "Meeting",
        "mode": "meeting",
        "audio": {"sample_rate": 16000, "channels": 1, "frame_duration_ms": 20},
        "asr": {"backend": "faster_whisper", "language": "auto"},
        "translate": {"enabled": True, "target_language": "zh"},
        "summary": {"enabled": True, "cadence_sec": 60},
        "explain": {"enabled": True},
        "storage": {"save_audio": True, "save_events": True},
        "prompts": {"translate": "x"},
    }
    (cfg_dir / "meeting.yml").write_text(yaml.safe_dump(meeting, allow_unicode=True), encoding="utf-8")

    settings = load_settings(path=tmp_path / "settings.yml", allow_missing=False)
    profiles = load_profiles(profiles_dir=cfg_dir, settings=settings)
    assert "Meeting" in profiles
    p = profiles["Meeting"]
    assert p.mode == "meeting"
    assert p.translate.enabled is True
    assert p.translate.target_language == "zh"


def test_load_settings_asr_compute_and_vad_max(tmp_path: Path):
    p = tmp_path / "settings.yml"
    p.write_text(
        "asr_mode: online\nopenai_asr_model: gpt-4o-mini-transcribe\ntranslate_enabled: false\ntranslate_target_language: ja\nasr_default_model: small\nasr_compute_type: int8\nvad_max_segment_ms: 4000\n",
        encoding="utf-8",
    )
    s = load_settings(path=p, allow_missing=False)
    assert s.asr_mode == "online"
    assert s.openai_asr_model == "gpt-4o-mini-transcribe"
    assert s.translate_enabled is False
    assert s.translate_target_language == "ja"
    assert s.asr_default_model == "small"
    assert s.asr_compute_type == "int8"
    assert s.vad_max_segment_ms == 4000

    # roundtrip through writer
    out = save_settings(s, path=p)
    s2 = load_settings(path=out, allow_missing=False)
    assert s2.asr_compute_type == "int8"
    assert s2.vad_max_segment_ms == 4000
