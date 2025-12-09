from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml

from core.types import Profile, ReplyStrategy


DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
DEFAULT_PROFILES_DIR = DEFAULT_CONFIG_DIR / "profiles"
DEFAULT_SETTINGS_FILE = DEFAULT_CONFIG_DIR / "settings.yml"


@dataclass
class Settings:
    openai_api_key: Any = None
    elevenlabs_api_key: Any = None
    audio_output_device: Any = None
    audio_input_device: Any = None
    openai: Dict[str, Any] = field(default_factory=dict)
    tts_voice_id: str | None = None
    extras: Dict[str, Any] = field(default_factory=dict)


class ConfigError(Exception):
    """Raised when config files are missing or invalid."""


def is_placeholder(value: Any) -> bool:
    """Return True if the provided value looks like a placeholder."""
    return isinstance(value, str) and value.strip().upper().startswith("SET_ME")


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"Expected mapping in {path}, got {type(data).__name__}")
    return data


def load_settings(path: Path | None = None, allow_missing: bool = True) -> Settings:
    settings_path = path or DEFAULT_SETTINGS_FILE
    if not settings_path.exists():
        if allow_missing:
            return Settings()
        raise ConfigError(f"Settings file not found: {settings_path}")

    raw = _load_yaml_file(settings_path)
    openai_block = raw.get("openai", {}) or {}

    known_keys = {
        "openai_api_key",
        "elevenlabs_api_key",
        "audio_output_device",
        "audio_input_device",
        "openai",
        "tts_voice_id",
    }
    extras = {k: v for k, v in raw.items() if k not in known_keys}

    openai_api_key = openai_block.get("api_key") or raw.get("openai_api_key")

    # Normalize OpenAI model configs.
    def _model_cfg(block: Dict[str, Any], default_model: str | None) -> Dict[str, Any]:
        if not isinstance(block, dict):
            return {"model": default_model}
        model = block.get("model", default_model)
        params = {k: v for k, v in block.items() if k != "model"}
        return {"model": model, "params": params}

    openai_config = {
        "api_key": openai_api_key,
        "llm": _model_cfg(openai_block.get("llm", {}), default_model="gpt-4o-mini"),
        "tts": _model_cfg(openai_block.get("tts", {}), default_model="gpt-4o-mini-tts"),
        "asr": _model_cfg(openai_block.get("asr", {}), default_model="whisper-1"),
    }

    return Settings(
        openai_api_key=openai_api_key,
        elevenlabs_api_key=raw.get("elevenlabs_api_key"),
        audio_output_device=raw.get("audio_output_device"),
        audio_input_device=raw.get("audio_input_device"),
        tts_voice_id=raw.get("tts_voice_id"),
        openai=openai_config,
        extras=extras,
    )


def _build_reply_strategy(data: Dict[str, Any]) -> ReplyStrategy:
    return ReplyStrategy(
        auto_suggest=bool(data.get("auto_suggest", True)),
        auto_speak=bool(data.get("auto_speak", False)),
        max_suggestion_length=int(data.get("max_suggestion_length", 120)),
        allow_agent_mode=bool(data.get("allow_agent_mode", False)),
    )


def _build_profile(name: str, data: Dict[str, Any]) -> Profile:
    try:
        reply_strategy_data = data.get("reply_strategy", {}) or {}
        reply_strategy = _build_reply_strategy(reply_strategy_data)
        prompts = data.get("prompts", {}) or {}
        metadata = data.get("metadata", {}) or {}
        return Profile(
            name=data.get("name", name),
            input_mode=data["input_mode"],
            tts_backend=data["tts_backend"],
            default_voice=data["default_voice"],
            output_device=data["output_device"],
            reply_strategy=reply_strategy,
            prompts=prompts,
            metadata=metadata,
        )
    except KeyError as exc:
        raise ConfigError(f"Missing required field in profile '{name}': {exc}") from exc


def load_profiles(profiles_dir: Path | None = None) -> Dict[str, Profile]:
    directory = profiles_dir or DEFAULT_PROFILES_DIR
    if not directory.exists():
        raise ConfigError(f"Profiles directory not found: {directory}")

    profiles: Dict[str, Profile] = {}
    for path in sorted(directory.glob("*.yml")):
        data = _load_yaml_file(path)
        profile_name = data.get("name") or path.stem
        profile = _build_profile(profile_name, data)
        profiles[profile.name] = profile
    if not profiles:
        raise ConfigError(f"No profiles found under {directory}")
    return profiles


def get_profile(profiles: Dict[str, Profile], name: str) -> Profile:
    try:
        return profiles[name]
    except KeyError as exc:
        raise ConfigError(f"Profile '{name}' not found. Available: {list(profiles)}") from exc
