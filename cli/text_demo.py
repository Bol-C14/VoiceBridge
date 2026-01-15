from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure project root on path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.config import ConfigError, get_profile, load_profiles, load_settings
from core.logging import get_logger, setup_logging
from core.types import ActionResult, Event
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
    print("Commands: /suggest, /explain <text|last>, /translate last to <lang>, /summarize [N], /export")

    try:
        while True:
            text = input("You> ").strip()
            if text in (":q", ":quit"):
                break
            event, special, error = parse_command(text, profile)
            if error:
                print(error)
                continue
            if special == "export":
                export_session(orchestrator)
                continue
            if not event:
                continue

            result = orchestrator.handle_event(event)
            render_result(result, orchestrator)
    except KeyboardInterrupt:
        print("\nExiting.")
    return 0


def parse_command(text: str, profile) -> tuple[Event | None, str | None, str | None]:
    if not text:
        return None, None, None
    if not text.startswith("/"):
        return (
            Event(action=profile.default_action, payload_text=text, source="keyboard"),
            None,
            None,
        )

    parts = text.split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == "/export":
        return None, "export", None
    if cmd == "/suggest":
        payload = " ".join(args).strip()
        return Event(action="suggest", payload_text=payload, source="keyboard"), None, None
    if cmd == "/explain":
        if args and args[0].lower() == "last":
            return Event(action="explain_last", source="keyboard"), None, None
        payload = " ".join(args).strip()
        if not payload:
            return None, None, "Usage: /explain <text> or /explain last"
        return Event(action="explain_concept", payload_text=payload, source="keyboard"), None, None
    if cmd == "/translate":
        if not args or args[0].lower() != "last":
            return None, None, "Usage: /translate last to <lang>"
        target_lang = None
        if len(args) >= 3 and args[1].lower() == "to":
            target_lang = " ".join(args[2:]).strip() or None
        return (
            Event(
                action="translate_last",
                target_lang=target_lang,
                source="keyboard",
            ),
            None,
            None,
        )
    if cmd == "/summarize":
        event = Event(action="summarize", source="keyboard")
        if args and args[0].isdigit():
            event.metadata["max_turns"] = int(args[0])
        return event, None, None

    return None, None, f"Unknown command: {cmd}"


def render_result(result: ActionResult, orchestrator: Orchestrator) -> None:
    if result.error:
        print(f"(error) {result.error}")
        return

    if result.suggestions:
        for i, s in enumerate(result.suggestions, 1):
            tone = s.tone or "neutral"
            length = s.length or "medium"
            risk = s.risk or "low"
            print(f"[{i}][{tone}][{length}][{risk}] {s.text}")

        choice = input(
            f"Choose [1-{len(result.suggestions)}] or 's' to skip speaking: "
        ).strip()
        if choice.lower() == "s":
            return
        if choice == "":
            choice = "1"
        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(result.suggestions):
                print("Invalid choice.")
                return
            orchestrator.speak(result.suggestions[idx])
        except ValueError:
            print("Invalid input. Skipping.")
        return

    if result.translation:
        print(json.dumps(result.translation, ensure_ascii=False, indent=2))
        return
    if result.explanation:
        print(json.dumps(result.explanation, ensure_ascii=False, indent=2))
        return
    if result.summary:
        summary_text = result.summary.get("summary_markdown") if isinstance(result.summary, dict) else None
        if summary_text:
            print(summary_text)
        else:
            print(json.dumps(result.summary, ensure_ascii=False, indent=2))
        return

    print("(no output)")


def export_session(orchestrator: Orchestrator) -> None:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    session_id = orchestrator.session.session.id
    transcript_path = logs_dir / f"{session_id}_transcript.jsonl"
    summary_path = logs_dir / f"{session_id}_summary.md"

    transcript = orchestrator.session.export_transcript(format="jsonl")
    transcript_path.write_text(transcript, encoding="utf-8")

    summary_text = orchestrator.session.session.metadata.get("rolling_summary")
    if not summary_text and orchestrator.summarizer:
        result = orchestrator.handle_event(Event(action="summarize", source="keyboard"))
        if result.summary and isinstance(result.summary, dict):
            summary_text = result.summary.get("summary_markdown", "")
    if not summary_text:
        summary_text = "- No summary available."
    summary_path.write_text(summary_text, encoding="utf-8")

    orchestrator.storage.save_session(orchestrator.session.session)
    print(f"Exported: {transcript_path} and {summary_path}")


if __name__ == "__main__":
    raise SystemExit(main())
