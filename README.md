# VoiceBridge Core

Unified “listen → understand → help you think → speak” engine for teaching, VRChat accessibility, and meetings.

## Status
- Phase 0: core dataclasses, config loader, logging, profile samples, CLI smoke script.
- Phase 1: OpenAI LLM, Whisper ASR, OpenAI/ElevenLabs TTS wrappers + service factory.
- Phase 2: text-only orchestration with intent + suggestion generation, CLI demos with optional TTS trigger.
- Pending: audio I/O backends, agent/manual policy windows, translation hooks.

## Quick start
- Prereq: Python 3.9+ (3.10+ recommended).
- Install deps: `python3 -m pip install -r requirements.txt`
- Configure: edit `config/settings.yml` with your API keys/devices/models (placeholders included).
- Smoke test: `python3 cli/smoke.py --profile Teaching` (logs to `logs/voicebridge.log`).

## Demos (Phase 2)
- Text loop: `python3 cli/text_loop.py --profile Teaching` — generates suggestions; TTS bytes logged if configured (no playback backend yet).
- Text demo: `python3 cli/text_demo.py` — shows suggestions; choose a number (default 1) to trigger TTS synthesis if configured; `s` to skip.

## Config
- Settings: `config/settings.yml`
  - `openai`: `api_key`, `llm.model/params`, `tts.model/params`, `asr.model/language`. Legacy `openai_api_key` is still read.
  - `elevenlabs_api_key`, `audio_output_device`, `audio_input_device`, `tts_voice_id` (optional override), `extras`.
- Profiles: `config/profiles/*.yml` (examples: Teaching, VRChat)
  - `input_mode`, `tts_backend`, `default_voice`, `output_device`
  - `reply_strategy`: `auto_suggest`, `auto_speak`, `max_suggestion_length`, `allow_agent_mode`
  - `prompts`: `suggestion`, `explain`, `translate`, optional `intent`

## Repo layout
- `core/`: types, config loader, logging helpers
- `services/`: ASR/LLM/TTS interfaces and providers; `services/factory.py` builds ServiceBundle from settings
- `conversation/`: session manager
- `understanding/`: intent analyzer and suggestion engine
- `orchestrator/`: flow coordinator (text→intent→suggestions, optional TTS)
- `audio_io/`: audio input/output interfaces (backends pending)
- `config/`: settings and profile YAMLs
- `cli/`: smoke, text loop, text demo
- `docs/`: architecture and profiles guides

## Logging
- Console logging is always enabled.
- File logging defaults to `logs/voicebridge.log` (created on demand). Override via `--log-file` on CLI or pass a Path to `setup_logging(enable_file=True, log_file=...)`.

## Next steps
- Implement audio output backends and plug into orchestrator.
- Add agent/manual policies for auto-speak with interrupt windows.
- Add translation hook and tighter profile validation.
