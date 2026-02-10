from __future__ import annotations

from pathlib import Path
import os
from typing import Any, Dict, Optional

import yaml

from voicebridge.config.models import (
    ASRConfig,
    AudioConfig,
    DiarizeConfig,
    ExplainConfig,
    ProfileConfig,
    Settings,
    StorageConfig,
    SummaryConfig,
    TranslateConfig,
)


def default_config_dir() -> Path:
    env = os.environ.get("VOICEBRIDGE_CONFIG_DIR")
    if env:
        return Path(env).expanduser()
    cwd_cfg = Path.cwd() / "config"
    if cwd_cfg.exists():
        return cwd_cfg
    return Path.home() / ".voicebridge" / "config"


def default_profiles_dir() -> Path:
    return default_config_dir() / "profiles"


def default_settings_file() -> Path:
    return default_config_dir() / "settings.yml"


class ConfigError(Exception):
    """Raised when config files are missing or invalid."""


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"Expected mapping in {path}, got {type(data).__name__}")
    return data


def load_settings(path: Optional[Path] = None, allow_missing: bool = True) -> Settings:
    settings_path = path or default_settings_file()
    if not settings_path.exists():
        if allow_missing:
            return Settings()
        raise ConfigError(f"Settings file not found: {settings_path}")

    raw = _load_yaml_file(settings_path)
    known_keys = {
        "openai_api_key",
        "openai_base_url",
        "openai_model_translate",
        "openai_model_summary",
        "openai_model_explain",
        "translate_enabled",
        "translate_target_language",
        "openai_asr_model",
        "storage_dir",
        "asr_mode",
        "asr_default_model",
        "asr_compute_type",
        "vad_max_segment_ms",
        "diarization_enabled",
        # legacy keys
        "elevenlabs_api_key",
        "audio_output_device",
        "audio_input_device",
    }
    extras = {k: v for k, v in raw.items() if k not in known_keys}

    storage_dir = raw.get("storage_dir")
    storage_path = Path(storage_dir).expanduser() if storage_dir else None

    return Settings(
        openai_api_key=raw.get("openai_api_key"),
        openai_base_url=raw.get("openai_base_url", Settings.openai_base_url),
        openai_model_translate=raw.get(
            "openai_model_translate", Settings.openai_model_translate
        ),
        openai_model_summary=raw.get("openai_model_summary", Settings.openai_model_summary),
        openai_model_explain=raw.get("openai_model_explain", Settings.openai_model_explain),
        translate_enabled=bool(raw.get("translate_enabled", True)),
        translate_target_language=str(
            raw.get("translate_target_language", Settings.translate_target_language)
        ),
        openai_asr_model=raw.get("openai_asr_model", Settings.openai_asr_model),
        storage_dir=storage_path,
        asr_mode=str(raw.get("asr_mode", Settings.asr_mode) or Settings.asr_mode),
        asr_default_model=raw.get("asr_default_model", Settings.asr_default_model),
        asr_compute_type=raw.get("asr_compute_type") or None,
        vad_max_segment_ms=int(raw.get("vad_max_segment_ms", Settings.vad_max_segment_ms)),
        diarization_enabled=bool(raw.get("diarization_enabled", True)),
        elevenlabs_api_key=raw.get("elevenlabs_api_key"),
        audio_output_device=raw.get("audio_output_device"),
        audio_input_device=raw.get("audio_input_device"),
        extras=extras,
    )


def _build_profile(name: str, data: Dict[str, Any], settings: Optional[Settings] = None) -> ProfileConfig:
    mode = data.get("mode") or ("meeting" if data.get("audio") or data.get("asr") else "legacy")
    prompts = data.get("prompts", {}) or {}
    metadata = data.get("metadata", {}) or {}

    # New schema (nested)
    if "audio" in data or "asr" in data:
        audio_cfg = AudioConfig(**(data.get("audio", {}) or {}))
        asr_dict = data.get("asr", {}) or {}
        if settings and not asr_dict.get("model"):
            asr_dict = dict(asr_dict)
            asr_dict["model"] = settings.asr_default_model
        asr_cfg = ASRConfig(**asr_dict)
        translate_cfg = TranslateConfig(**(data.get("translate", {}) or {}))
        summary_cfg = SummaryConfig(**(data.get("summary", {}) or {}))
        explain_cfg = ExplainConfig(**(data.get("explain", {}) or {}))
        diarize_cfg = DiarizeConfig(**(data.get("diarize", {}) or {}))
        storage_cfg = StorageConfig(**(data.get("storage", {}) or {}))
        return ProfileConfig(
            name=data.get("name", name),
            mode=mode,
            audio=audio_cfg,
            asr=asr_cfg,
            translate=translate_cfg,
            summary=summary_cfg,
            explain=explain_cfg,
            diarize=diarize_cfg,
            storage=storage_cfg,
            prompts=prompts,
            metadata=metadata,
        )

    # Legacy schema (Phase 0): keep minimal compatibility
    # Map a few legacy keys into nested config defaults.
    audio_cfg = AudioConfig(input_device=(data.get("audio_input_device") or None))
    asr_cfg = ASRConfig(model=(settings.asr_default_model if settings else "small"))
    translate_cfg = TranslateConfig(enabled=False)
    summary_cfg = SummaryConfig(enabled=False)
    explain_cfg = ExplainConfig(enabled=False)
    storage_cfg = StorageConfig(save_audio=False, save_events=True)
    return ProfileConfig(
        name=data.get("name", name),
        mode=mode,
        audio=audio_cfg,
        asr=asr_cfg,
        translate=translate_cfg,
        summary=summary_cfg,
        explain=explain_cfg,
        storage=storage_cfg,
        prompts=prompts,
        metadata=metadata,
    )


def load_profiles(
    profiles_dir: Optional[Path] = None, settings: Optional[Settings] = None
) -> Dict[str, ProfileConfig]:
    directory = profiles_dir or default_profiles_dir()
    if not directory.exists():
        raise ConfigError(f"Profiles directory not found: {directory}")

    profiles: Dict[str, ProfileConfig] = {}
    for path in sorted(directory.glob("*.yml")):
        data = _load_yaml_file(path)
        profile_name = data.get("name") or path.stem
        profile = _build_profile(profile_name, data, settings=settings)
        profiles[profile.name] = profile
    if not profiles:
        raise ConfigError(f"No profiles found under {directory}")
    return profiles


def get_profile(profiles: Dict[str, ProfileConfig], name: str) -> ProfileConfig:
    try:
        return profiles[name]
    except KeyError as exc:
        raise ConfigError(f"Profile '{name}' not found. Available: {list(profiles)}") from exc
