# Profiles Guide

Profiles capture per-scenario behavior without changing code. Each profile lives in `config/profiles/*.yml`.

## Schema (fields)
- `name`: display name (used as key when loading).
- `input_mode`: `"manual"`, `"asr"`, or `"manual+asr"`.
- `tts_backend`: backend id (e.g., `elevenlabs`, `openai`).
- `default_voice`: voice id for TTS calls.
- `output_device`: audio output/virtual mic target.
- `reply_strategy`:
  - `auto_suggest` (bool): generate reply suggestions automatically.
  - `auto_speak` (bool): whether to send TTS without user confirmation.
  - `max_suggestion_length` (int): soft cap for reply length.
  - `allow_agent_mode` (bool): permit unattended agent behavior.
- `prompts`: prompt templates keyed by use-case (e.g., `suggestion`, `explain`, `translate`, `summarize`).
- `metadata`: optional misc values for UI or analytics.

## Examples
- `config/profiles/teaching.yml`: manual+ASR, no auto-speak, teaching prompts (`explain`, `suggestion`, `summarize`).
- `config/profiles/vrchat.yml`: ASR-driven, auto-speak enabled, social prompts (`suggestion`, `translate`), targets a virtual cable output.

## Adding a new profile
1) Copy an existing YAML in `config/profiles/`.
2) Update `name`, `input_mode`, TTS/backend/voice/output.
3) Tailor `reply_strategy` to the safety level you want.
4) Provide prompts that match the scenario. Keep them short and explicit about style/tone.
5) Run `python3 cli/smoke.py --profile "<ProfileName>"` to validate loading.
