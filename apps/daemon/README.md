# voicebridge-daemon

FastAPI daemon that runs meeting sessions and streams events over WebSocket.

Dev install (from repo root):

```bash
python3 -m pip install -e packages/voicebridge_core
python3 -m pip install -e apps/daemon
```

Run:

```bash
voicebridge-daemon --host 127.0.0.1 --port 8765
```

Open local UI:
- `http://127.0.0.1:8765/`

Set OpenAI key:
- In the UI, paste your key and click **Save** (stored in `config/settings.yml`).

WebSocket note:
- If you see `No supported WebSocket library detected`, install deps with:
  - `pip install -e /Volumes/Data/DevProj/VoiceBridge/apps/daemon` (will pull `websockets`)
  - or `pip install websockets`

WebSocket:
- `ws://127.0.0.1:8765/v1/sessions/{session_id}/ws`
