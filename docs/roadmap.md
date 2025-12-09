# VoiceBridge Roadmap (Phases)

## Phase 0 (done)
- Core types (Session/Utterance/Profile), config loader, logging.
- Profile samples (Teaching, VRChat), CLI smoke.

## Phase 1 (done)
- Service wrappers: OpenAI LLM, Whisper ASR, OpenAI/ElevenLabs TTS.
- Service factory to assemble bundles from settings.

## Phase 2 (current)
- Text-only orchestration: intent analysis, suggestion generation.
- CLI demos: `text_loop.py` (logs suggestions), `text_demo.py` (select + optional TTS synth).
- Basic error logging in services.

## Upcoming
- Audio I/O backends (e.g., CoreAudio output) and playback integration.
- Agent/manual policy: auto-speak gating, interrupt window, safer defaults.
- Translation hook (profile-driven), stronger config validation.
- Persistence (transcripts/suggestions) and diagnostics around latency.
