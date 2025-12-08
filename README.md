# VoiceBridge Core

Unified “listen → understand → help you think → speak” engine for teaching, VRChat accessibility, and meetings. This repo currently contains Phase 0 scaffolding (types, config, logging, stubs) to unblock early integration.

## Status
- Phase 0: core dataclasses, config loader, logging, profile samples, CLI smoke script.
- Phase 1: service wrappers for OpenAI LLM/TTS and Whisper ASR, ElevenLabs TTS.
- Not yet implemented: audio I/O, agent behaviors, full text loop wiring.

## Quick start (Phase 0)
- Prereq: Python 3.9+ (3.10+ recommended).
- Install deps: `python3 -m pip install -r requirements.txt`
- Configure: edit `config/settings.yml` with your API keys/devices (file already present with placeholders).
- Smoke test: `python3 cli/smoke.py --profile Teaching` (warns if keys missing; writes logs to `logs/voicebridge.log` by default).

## Text loop (Phase 2 demo)
- Requires OpenAI key in `config/settings.yml`.
- Run: `python3 cli/text_loop.py --profile Teaching` then type messages; suggestions are logged, and TTS audio is generated if a TTS backend + key are configured (logged when no audio output backend is set yet).

## Simple text demo (Phase 2)
- Run: `python3 cli/text_demo.py` (uses Teaching profile by default) and type; prints 1–3 suggestions to console.

## Config
- Settings: `config/settings.yml` (API keys, models, default audio devices, extras). Missing file is tolerated during Phase 0.
  - `openai`: `api_key`, `llm.model/params`, `tts.model/params`, `asr.model/language`. Legacy `openai_api_key` is still read.
  - `elevenlabs_api_key`, `audio_output_device`, `audio_input_device`, `extras`.
- Profiles: `config/profiles/*.yml`. Two examples exist: `Teaching` and `VRChat`. Key fields:
  - `input_mode`: "manual", "asr", or "manual+asr"
  - `tts_backend`, `default_voice`, `output_device`
  - `reply_strategy`: `auto_suggest`, `auto_speak`, `max_suggestion_length`, `allow_agent_mode`
  - `prompts`: mode-specific prompt templates (e.g., `suggestion`, `explain`, `translate`)

## Repo layout (current)
- `core/`: types, config loader, logging helpers
- `services/`: abstract ASR/LLM/TTS interfaces
- `services/factory.py`: builds ServiceBundle (LLM/TTS/ASR) from settings
- `conversation/`: session manager
- `understanding/`: intent/suggestion stubs
- `orchestrator/`: flow coordinator shell
- `audio_io/`: audio input/output interfaces
- `config/`: settings and profile YAMLs
- `cli/`: smoke test entrypoint
- `docs/architecture.md`: full architecture and phase roadmap

## Logging
- Console logging is always enabled.
- File logging defaults to `logs/voicebridge.log` (created on demand). Override via `--log-file` on CLI or pass a Path to `setup_logging(enable_file=True, log_file=...)`.

## Next steps
- Add concrete service implementations (OpenAI/Whisper/ElevenLabs) and wire to orchestrator.
- Implement text-only flow (intent + suggestions) in CLI.
- Extend audio I/O backends and agent auto-speak policy window.
