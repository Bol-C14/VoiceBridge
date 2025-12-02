from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from conversation.session_manager import ConversationSession
from core.config import ConfigError, load_profiles, load_settings
from core.logging import get_logger, setup_logging


def main() -> int:
    parser = argparse.ArgumentParser(description="VoiceBridge Phase 0 smoke test")
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
    args = parser.parse_args()

    setup_logging()
    log = get_logger("smoke")

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

    session = ConversationSession(profile)

    log.info("Loaded profile '%s' (%d prompts)", profile.name, len(profile.prompts))
    log.info("Session %s ready. Output device: %s", session.session.id, profile.output_device)

    if settings.openai_api_key:
        log.info("OpenAI key configured")
    else:
        log.warning("OpenAI key missing; LLM calls will be disabled.")

    if settings.elevenlabs_api_key:
        log.info("ElevenLabs key configured")
    else:
        log.warning("ElevenLabs key missing; TTS calls will be disabled.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
