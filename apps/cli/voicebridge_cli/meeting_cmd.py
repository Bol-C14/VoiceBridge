from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from voicebridge.config import get_profile, load_profiles, load_settings
from voicebridge.config.models import Settings
from voicebridge.core.events import Event
from voicebridge.core.logging import get_logger, setup_logging
from voicebridge.runtime.meeting import MeetingSessionRunner
from voicebridge.storage.session_store import SessionStore


log = get_logger("voicebridge.cli.meeting")


def meeting_cmd(args: Any) -> int:
    setup_logging()

    settings_path = Path(args.settings).expanduser() if args.settings else None
    settings: Settings = load_settings(path=settings_path, allow_missing=True)
    profiles_dir = Path(args.profiles_dir).expanduser() if args.profiles_dir else None
    profiles = load_profiles(profiles_dir=profiles_dir, settings=settings)
    profile = get_profile(profiles, args.profile)
    if args.device:
        profile.audio.input_device = str(args.device)

    store = SessionStore(settings.storage_dir)

    def on_event(ev: Event) -> None:
        if ev.type == "asr.segment.final":
            p = ev.payload
            log.info("ASR [%s-%s] %s", p.get("start_ms"), p.get("end_ms"), p.get("text"))
        elif ev.type == "translate.segment.final":
            p = ev.payload
            log.info("TR  %s", p.get("text"))
        elif ev.type == "summary.update":
            log.info("SUMMARY updated")
        elif ev.type == "job.error":
            log.warning("JOB error: %s", ev.payload)

    runner = MeetingSessionRunner(profile=profile, settings=settings, store=store, on_event=on_event)
    sid = runner.start()
    log.info("Meeting started. session_id=%s (Ctrl+C to stop)", sid)

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        log.info("Stopping...")
    finally:
        runner.stop()
        log.info("Meeting stopped. Export: %s", runner.paths.export_md)
    return 0
