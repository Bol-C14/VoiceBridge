from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass
class Settings:
    # LLM / OpenAI
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model_translate: str = "gpt-4o-mini"
    openai_model_summary: str = "gpt-4o-mini"
    openai_model_explain: str = "gpt-4o-mini"
    translate_enabled: bool = True
    translate_target_language: str = "zh"

    # Storage
    storage_dir: Optional[Path] = None

    # Defaults
    asr_mode: str = "offline"  # "offline" | "online"
    asr_default_model: str = "small"
    asr_compute_type: Optional[str] = None
    openai_asr_model: str = "gpt-4o-mini-transcribe"
    vad_max_segment_ms: int = 10_000
    diarization_enabled: bool = True

    # Legacy keys (kept for compatibility)
    elevenlabs_api_key: Optional[str] = None
    audio_output_device: Optional[str] = None
    audio_input_device: Optional[str] = None

    extras: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AudioConfig:
    input_device: Optional[str] = None
    sample_rate: int = 16000
    channels: int = 1
    frame_duration_ms: int = 20


@dataclass
class ASRConfig:
    backend: str = "faster_whisper"
    model: str = "small"
    language: str = "auto"
    compute_type: Optional[str] = None


@dataclass
class TranslateConfig:
    enabled: bool = True
    target_language: str = "zh"
    model: Optional[str] = None


@dataclass
class SummaryConfig:
    enabled: bool = True
    cadence_sec: int = 60
    model: Optional[str] = None


@dataclass
class ExplainConfig:
    enabled: bool = True
    model: Optional[str] = None


@dataclass
class DiarizeConfig:
    run: str = "post_meeting"  # "post_meeting" | "none"


@dataclass
class StorageConfig:
    save_audio: bool = True
    save_events: bool = True


@dataclass
class ProfileConfig:
    name: str
    mode: str = "meeting"
    audio: AudioConfig = field(default_factory=AudioConfig)
    asr: ASRConfig = field(default_factory=ASRConfig)
    translate: TranslateConfig = field(default_factory=TranslateConfig)
    summary: SummaryConfig = field(default_factory=SummaryConfig)
    explain: ExplainConfig = field(default_factory=ExplainConfig)
    diarize: DiarizeConfig = field(default_factory=DiarizeConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    prompts: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)
