# voicebridge-core

Core Python library for VoiceBridge.

This package contains:
- config + profile loading
- event schema + storage (sessions, events, transcript, summary)
- meeting runtime pipeline (mic → VAD → ASR → translate/summary/explain hooks)

Install (editable, from repo root):

```bash
python3 -m pip install -e packages/voicebridge_core
```

Optional extras:

```bash
# mic capture + VAD + local ASR
python3 -m pip install -e "packages/voicebridge_core[audio,vad,asr]"
```

