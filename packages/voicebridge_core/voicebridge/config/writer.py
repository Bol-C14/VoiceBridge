from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from voicebridge.config.loader import default_settings_file
from voicebridge.config.models import Settings


def save_settings(settings: Settings, path: Optional[Path] = None) -> Path:
    """
    Persist settings to YAML. Unknown keys already present in the file are preserved.

    Notes:
    - API keys are stored in plaintext. For production packaging, prefer OS keychain.
    """

    settings_path = path or default_settings_file()
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    raw: Dict[str, Any] = {}
    if settings_path.exists():
        try:
            loaded = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                raw = dict(loaded)
        except Exception:
            raw = {}

    def set_or_remove(key: str, value: Any) -> None:
        if value is None or value == "":
            raw.pop(key, None)
        else:
            raw[key] = value

    set_or_remove("openai_api_key", settings.openai_api_key)
    set_or_remove("openai_base_url", settings.openai_base_url)
    set_or_remove("openai_model_translate", settings.openai_model_translate)
    set_or_remove("openai_model_summary", settings.openai_model_summary)
    set_or_remove("openai_model_explain", settings.openai_model_explain)
    set_or_remove("openai_asr_model", settings.openai_asr_model)
    raw["translate_enabled"] = bool(settings.translate_enabled)
    set_or_remove("translate_target_language", settings.translate_target_language)

    if settings.storage_dir is None:
        raw.pop("storage_dir", None)
    else:
        raw["storage_dir"] = str(settings.storage_dir)

    set_or_remove("asr_mode", settings.asr_mode)
    set_or_remove("asr_default_model", settings.asr_default_model)
    set_or_remove("asr_compute_type", settings.asr_compute_type)
    raw["vad_max_segment_ms"] = int(settings.vad_max_segment_ms)
    raw["diarization_enabled"] = bool(settings.diarization_enabled)

    # Legacy keys (kept)
    set_or_remove("elevenlabs_api_key", settings.elevenlabs_api_key)
    set_or_remove("audio_output_device", settings.audio_output_device)
    set_or_remove("audio_input_device", settings.audio_input_device)

    extras = dict(settings.extras or {})
    if extras:
        raw["extras"] = extras
    else:
        raw.pop("extras", None)

    settings_path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return settings_path
