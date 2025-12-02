# VoiceBridge Core

Unified “listen → understand → help you think → speak” engine for teaching, VRChat accessibility, and meetings. This repo currently contains Phase 0 scaffolding (types, config, logging, stubs) to unblock early integration.

## Status
- Phase 0: core dataclasses, config loader, logging, profile samples, CLI smoke script.
- Not yet implemented: actual ASR/LLM/TTS calls, audio I/O, agent behaviors.

## Quick start (Phase 0)
- Prereq: Python 3.10+.
- Install deps: `python3 -m pip install -r requirements.txt`
- Configure: `cp config/settings.example.yml config/settings.yml` and fill API keys/devices (optional at this phase).
- Smoke test: `python3 cli/smoke.py --profile Teaching` (warns if keys missing; verifies profiles load).

## Config
- Settings: `config/settings.yml` (API keys, default audio devices, extras). Missing file is tolerated during Phase 0.
- Profiles: `config/profiles/*.yml`. Two examples exist: `Teaching` and `VRChat`. Key fields:
  - `input_mode`: "manual", "asr", or "manual+asr"
  - `tts_backend`, `default_voice`, `output_device`
  - `reply_strategy`: `auto_suggest`, `auto_speak`, `max_suggestion_length`, `allow_agent_mode`
  - `prompts`: mode-specific prompt templates (e.g., `suggestion`, `explain`, `translate`)

## Repo layout (current)
- `core/`: types, config loader, logging helpers
- `services/`: abstract ASR/LLM/TTS interfaces
- `conversation/`: session manager
- `understanding/`: intent/suggestion stubs
- `orchestrator/`: flow coordinator shell
- `audio_io/`: audio input/output interfaces
- `config/`: settings and profile YAMLs
- `cli/`: smoke test entrypoint
- `docs/architecture.md`: full architecture and phase roadmap

## Next steps
- Add concrete service implementations (OpenAI/Whisper/ElevenLabs) and wire to orchestrator.
- Implement text-only flow (intent + suggestions) in CLI.
- Extend audio I/O backends and agent auto-speak policy window.
