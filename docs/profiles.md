# Profiles Guide

Profiles capture per-scenario behavior without changing code. Each profile lives in `config/profiles/*.yml`.

## Schema (fields)
- `name`: display name (used as key when loading).
- `mode`: scenario id (e.g., `"meeting"`, `"teaching"`, `"vrchat"`).
- Meeting-mode nested fields:
  - `audio`: `input_device`, `sample_rate`, `channels`, `frame_duration_ms`
  - `asr`: `backend`, `model`, `language`
  - `translate`: `enabled`, `target_language`, `model`
  - `summary`: `enabled`, `cadence_sec`, `model`
  - `explain`: `enabled`, `model`
  - `diarize`: `run` (`post_meeting` / `none`)
  - `storage`: `save_audio`, `save_events`
- `prompts`: prompt templates keyed by use-case (e.g., `translate`, `summarize`, `explain`).
- `metadata`: optional misc values for UI or analytics.

## Examples
- `config/profiles/meeting.yml`: mic → VAD → local ASR → translate/summary/explain (OpenAI optional), persists session artifacts.
- `config/profiles/teaching.yml` / `config/profiles/vrchat.yml`: legacy Phase 0 profiles (still accepted by the loader; will be migrated to the unified schema).

## Adding a new profile
1) Copy an existing YAML in `config/profiles/`.
2) Set `name` + `mode`, then fill mode-specific config.
3) Provide prompts that match the scenario. Keep them short and explicit about style/tone.
4) Validate by running:
   - Meeting: `voicebridge meeting --profile "<ProfileName>"`
   - Daemon: `voicebridge-daemon` then `POST /v1/sessions/start` with that profile.
