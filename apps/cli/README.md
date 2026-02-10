# voicebridge-cli

CLI tools for VoiceBridge.

Dev install (from repo root):

```bash
python3 -m pip install -e packages/voicebridge_core
python3 -m pip install -e "packages/voicebridge_core[audio,vad,asr]"
python3 -m pip install -e apps/cli
```

Run a meeting (mic → transcript):

```bash
voicebridge meeting --profile Meeting
```

Export markdown:

```bash
voicebridge export --session <id>
```

