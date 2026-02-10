# VoiceBridge Core

Cross-platform “meeting companion” and voice interaction core: **mic capture → realtime transcription → translation → rolling summary → on‑demand explanations**, designed to expand into teaching + gaming (VRChat) via Profiles.

## Status
- Meeting mode (hybrid) foundation implemented:
  - Local ASR pipeline scaffolding (VAD → segment → ASR)
  - OpenAI-backed translation/summaries/explanations (optional; uses `config/settings.yml`)
  - Session storage: `audio.wav`, `events.jsonl`, `transcript.jsonl`, `summary.json`, `export.md`
  - Daemon (FastAPI + WebSocket) + CLI tools
- Desktop GUI: stubbed (Tauri/React planned; see `apps/desktop/README.md`).

## Quick start (Meeting mode)
- Prereq: Python 3.9+
- One-click (recommended):
  - `bash scripts/oneclick.sh` (sets up venv + installs deps + starts daemon)
  - Or: `bash scripts/oneclick.sh meeting`
- Manual install (dev/editable):
  - Create venv, then `python -m pip install -U pip`
  - `python -m pip install -r requirements.txt`
  - Optional mic/VAD/ASR deps: `python -m pip install -e "packages/voicebridge_core[audio,vad,asr]"`
- Configure:
  - `cp config/settings.example.yml config/settings.yml`
  - Option A (recommended): start daemon and set OpenAI key in the UI (`/` page).
  - Option B: set `openai_api_key` in `config/settings.yml` if you prefer file-based config.
- Run CLI meeting:
  - `voicebridge meeting --profile Meeting` (Ctrl+C to stop)
- Run daemon:
  - `voicebridge-daemon --host 127.0.0.1 --port 8765`
  - WebSocket: `ws://127.0.0.1:8765/v1/sessions/<session_id>/ws`

## Config
- Settings: `config/settings.yml` (OpenAI models/keys, storage dir, ASR defaults).
- Profiles: `config/profiles/*.yml` (Meeting/Teaching/VRChat). Meeting profile uses nested sections:
  - `audio`, `asr`, `translate`, `summary`, `explain`, `diarize`, `storage`, `prompts`

## Repo layout (current)
- `packages/voicebridge_core/`: core library (types/events/config/runtime/storage/services)
- `apps/daemon/`: FastAPI daemon (`voicebridge-daemon`)
- `apps/cli/`: CLI tools (`voicebridge`)
- `apps/desktop/`: GUI plan + bootstrap notes
- `config/`: settings + profile YAMLs
- `docs/`: architecture + profiles guide

## Next steps
- Replace heuristic diarization with a real backend (pyannote/speechbrain plugin).
- Add system-audio/loopback capture for online meetings.
- Implement the Tauri + React desktop UI (main window + overlay).
