from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import ConfigError, get_profile, load_profiles, load_settings
from core.logging import get_logger, setup_logging
from orchestrator.orchestrator import AudioIOBundle, Orchestrator
from services.factory import build_services


def main() -> int:
    setup_logging(enable_file=True, log_file=Path("logs/voicebridge.log"))
    log = get_logger("text_demo")

    try:
        settings = load_settings(allow_missing=False)
        profiles = load_profiles()
    except ConfigError as exc:
        log.error("Config error: %s", exc)
        return 1

    # Allow selecting profile via --profile arg or VOICEBRIDGE_PROFILE env var
    profile_name = None
    if len(sys.argv) > 1:
        profile_name = sys.argv[1]
    else:
        profile_name = os.environ.get("VOICEBRIDGE_PROFILE")

    if profile_name:
        try:
            profile = get_profile(profiles, profile_name)
        except ConfigError as exc:
            log.error("%s", exc)
            return 1
    else:
        profile = profiles.get("Teaching") or next(iter(profiles.values()))
    services = build_services(settings, profile.tts_backend)

    orchestrator = Orchestrator(profile=profile, services=services, audio_io=AudioIOBundle())

    # If profile requests auto_speak but no TTS API key is configured, disable auto_speak for safety.
    try:
        tts_key_present = bool(settings.elevenlabs_api_key or settings.openai_api_key or (settings.openai or {}).get("api_key"))
    except Exception:
        tts_key_present = False
    if profile.reply_strategy.auto_speak and services.tts and not tts_key_present:
        log.warning(
            "Profile requests auto_speak but no TTS key found; disabling auto_speak for demo."
        )
        profile.reply_strategy.auto_speak = False

    if not services.llm:
        log.error("LLM not configured; set openai api_key in config/settings.yml")
        return 1

    print(f"Profile: {profile.name}")
    print("Enter text (':q' to quit)")

    try:
        while True:
            text = input("You> ").strip()
            if text in (":q", ":quit"):
                break
            suggestions = orchestrator.handle_local_text(text, speak=False) or []
            if not suggestions:
                print("(no suggestions)")
                continue

            for i, s in enumerate(suggestions, 1):
                print(f"[{i}] {s.text}")

            choice = input(f"Choose [1-{len(suggestions)}] or 's' to skip speaking: ").strip()
            if choice.lower() == "s":
                continue
            if choice == "":
                choice = "1"
            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(suggestions):
                    print("Invalid choice.")
                    continue
                text_to_speak = suggestions[idx].text
                orchestrator.handle_local_text(text_to_speak, speak=True)
            except ValueError:
                print("Invalid input. Skipping.")
    except KeyboardInterrupt:
        print("\nExiting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
