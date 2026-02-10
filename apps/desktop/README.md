# voicebridge-desktop (planned)

This repo includes the **daemon** and **core** implementation. The desktop GUI will be a
**Tauri + React/TypeScript** app that talks to the local daemon over:

- HTTP: `http://127.0.0.1:8765`
- WebSocket: `ws://127.0.0.1:8765/v1/sessions/{session_id}/ws`

Until the Tauri app is built, the daemon also serves a minimal local web UI at:
- `http://127.0.0.1:8765/`
  - Includes OpenAI key entry + save.

## Bootstrap (once Node + Rust are installed)

From `apps/desktop/`:

```bash
# one-time tooling
# - install Node.js (LTS) and Rust toolchain

# create the app skeleton (recommended)
npm create tauri-app@latest .
```

UI requirements for MVP:
- Main window: start/stop, transcript (source + translation), rolling summary, keywords/topics, sessions list, export.
- Overlay window (always-on-top): last N transcript lines + translation + mini summary.

## API notes
- Start: `POST /v1/sessions/start` body `{ "profile": "Meeting" }`
- Stop: `POST /v1/sessions/stop`
- Explain: `POST /v1/sessions/{id}/explain` body `{ "term": "..." }`
- Export: `POST /v1/sessions/{id}/export`
