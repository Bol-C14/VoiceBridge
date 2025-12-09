from __future__ import annotations

from typing import Optional

from core.config import Settings, is_placeholder
from services import ServiceBundle
from services.asr_whisper import WhisperASRService
from services.llm_openai import OpenAILLMService
from services.tts_elevenlabs import ElevenLabsTTSService
from services.tts_openai import OpenAITTSService


def _normalize_openai_key(settings: Settings) -> Optional[str]:
    if settings.openai and not is_placeholder(settings.openai.get("api_key")):
        return settings.openai.get("api_key")
    if not is_placeholder(settings.openai_api_key):
        return settings.openai_api_key
    return None


def build_services(settings: Settings, profile_tts_backend: str) -> ServiceBundle:
    """
    Build ServiceBundle based on settings and profile TTS backend.
    ASR is optional and will be built if OpenAI key is present.
    """
    openai_key = _normalize_openai_key(settings)

    oa_llm = (settings.openai or {}).get("llm", {}) if settings.openai else {}
    oa_tts = (settings.openai or {}).get("tts", {}) if settings.openai else {}
    oa_asr = (settings.openai or {}).get("asr", {}) if settings.openai else {}

    llm = None
    if openai_key:
        llm = OpenAILLMService(
            openai_key,
            default_model=oa_llm.get("model") or "gpt-4o-mini",
            default_params=oa_llm.get("params") or {},
        )

    tts = None
    # voice override: settings.tts_voice_id falls back if profile doesn't supply/if caller wants it
    tts_voice_id_override = settings.tts_voice_id if settings.tts_voice_id else None

    if profile_tts_backend == "elevenlabs" and settings.elevenlabs_api_key and not is_placeholder(
        settings.elevenlabs_api_key
    ):
        tts = ElevenLabsTTSService(settings.elevenlabs_api_key)
    elif profile_tts_backend in ("openai", "gpt-4o-mini-tts") and openai_key:
        tts = OpenAITTSService(
            openai_key,
            model=oa_tts.get("model") or "gpt-4o-mini-tts",
            default_params=oa_tts.get("params") or {},
        )
    elif openai_key:
        tts = OpenAITTSService(
            openai_key,
            model=oa_tts.get("model") or "gpt-4o-mini-tts",
            default_params=oa_tts.get("params") or {},
        )

    asr = None
    if openai_key:
        asr = WhisperASRService(
            openai_key,
            model=oa_asr.get("model") or "whisper-1",
            default_params=oa_asr.get("params") or {},
        )

    bundle = ServiceBundle(asr=asr, llm=llm, tts=tts)
    # Attach voice override for orchestrator to use if present.
    bundle.tts_voice_id_override = tts_voice_id_override
    return bundle
