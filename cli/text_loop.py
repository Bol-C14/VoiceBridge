from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import ConfigError, is_placeholder, load_profiles, load_settings
from core.logging import get_logger, setup_logging
from orchestrator.orchestrator import AudioIOBundle, Orchestrator
from services.factory import build_services


def main() -> int:
    parser = argparse.ArgumentParser(description="VoiceBridge Phase 2 text loop (LLM suggestions + optional TTS)")
    parser.add_argument(
        "--profiles-dir",
        type=Path,
        default=None,
        help="Override profile directory (defaults to config/profiles)",
    )
    parser.add_argument(
        "--profile",
        type=str,
        default=None,
        help="Profile name to load (defaults to first available)",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=Path("logs/voicebridge.log"),
        help="File path for logs (default: logs/voicebridge.log)",
    )
    args = parser.parse_args()

    setup_logging(enable_file=True, log_file=args.log_file)
    log = get_logger("text_loop")

    try:
        settings = load_settings(allow_missing=True)
        profiles = load_profiles(args.profiles_dir)
    except ConfigError as exc:
        log.error("Config error: %s", exc)
        return 1

    profile = (
        profiles.get(args.profile)
        if args.profile
        else profiles[next(iter(profiles))]
    )

    # Normalize placeholder handling
    if is_placeholder(settings.openai_api_key):
        settings.openai_api_key = None
        if settings.openai:
            settings.openai["api_key"] = None
    if is_placeholder(settings.elevenlabs_api_key):
        settings.elevenlabs_api_key = None

    services = build_services(settings, profile.tts_backend)
    orchestrator = Orchestrator(profile=profile, services=services, audio_io=AudioIOBundle())

    if not services.llm:
        log.error("OpenAI key missing; cannot run text loop.")
        return 1

    log.info("Text loop ready with profile '%s'. Enter text and press Enter (Ctrl+C to exit).", profile.name)

    try:
        for line in sys.stdin:
            text = line.strip()
            if not text:
                continue
            orchestrator.handle_local_text(text)
            if orchestrator.session.session.suggestions:
                last = orchestrator.session.session.suggestions[-1]
                log.info("Suggestion: %s", last.text)
    except KeyboardInterrupt:
        log.info("Exiting.")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
