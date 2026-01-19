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
from audio_io import AudioIOBundle
from orchestrator.orchestrator import Orchestrator
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
    print(
        "Commands: /suggest, /explain <text|last>, /coach [text], /student <text>, "
        "/macro <id> [topic], @macro [topic], /speak 2, /feedback correct|wrong, "
        "/translate last to <lang>, /summarize [N], /export"
    )

    last_coach = None
    last_segments = []
    try:
        while True:
            text = input("You> ").strip()
            if text in (":q", ":quit"):
                break
            event, special, error = parse_command(text, profile)
            if error:
                print(error)
                continue
            if special:
                if special.get("type") == "export":
                    export_session(orchestrator)
                    continue
                if special.get("type") == "speak_segment":
                    speak_index = special.get("index", 0)
                    if not last_segments:
                        print("No segments available.")
                        continue
                    if speak_index < 0 or speak_index >= len(last_segments):
                        print("Invalid segment number.")
                        continue
                    segment = last_segments[speak_index]
                    if segment:
                        orchestrator.speak(segment)
                    continue
                if special.get("type") == "feedback":
                    if not last_coach:
                        print("No coach feedback available.")
                        continue
                    mode = special.get("mode")
                    feedback = last_coach.get("micro_feedback") if isinstance(last_coach, dict) else None
                    if not isinstance(feedback, dict):
                        print("No coach feedback available.")
                        continue
                    lines = feedback.get(mode) if mode in ("correct", "wrong") else None
                    if not isinstance(lines, list) or not lines:
                        print("No feedback available.")
                        continue
                    orchestrator.speak(str(lines[0]))
                    continue

            if not event:
                continue

            result = orchestrator.handle_event(event)
            if result.segments:
                last_segments = result.segments
            if result.coach:
                last_coach = result.coach
            render_result(result, orchestrator, event)
    except KeyboardInterrupt:
        print("\nExiting.")
    return 0


def parse_command(text: str, profile) -> tuple[Event | None, dict | None, str | None]:
    if not text:
        return None, None, None
    if text.lower().startswith("speak "):
        target = text[6:].strip()
        index = _parse_question_index(target)
        if index is None:
            return None, None, "Usage: speak q1|q2|q3 (or speak 1)"
        return None, {"type": "speak_segment", "index": index}, None
    if not text.startswith("/"):
        if text.startswith("@"):
            macro_text = text[1:].strip()
            if not macro_text:
                return None, None, "Usage: @macro_id [topic]"
            parts = macro_text.split()
            macro_id = parts[0]
            topic = " ".join(parts[1:]).strip()
            event = Event(action="run_macro", payload_text=macro_id, source="keyboard")
            if topic:
                event.metadata["topic"] = topic
            event.metadata["speak"] = True
            return event, None, None
        return (
            Event(action=profile.default_action, payload_text=text, source="keyboard"),
            None,
            None,
        )

    parts = text.split()
    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == "/export":
        return None, {"type": "export"}, None
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
    if cmd in {"/student", "/stu"}:
        payload = " ".join(args).strip()
        if not payload:
            return None, None, "Usage: /student <text>"
        return (
            Event(
                action="add_utterance",
                payload_text=payload,
                speaker_role="remote_user",
                speaker_name="Student",
                source="keyboard",
            ),
            None,
            None,
        )
    if cmd == "/coach":
        payload = " ".join(args).strip()
        event = Event(action="coach_student", payload_text=payload or None, source="keyboard")
        if not payload:
            event.metadata["use_last"] = True
        event.metadata["speak"] = True
        return event, None, None
    if cmd == "/speak":
        target = " ".join(args).strip()
        index = _parse_question_index(target)
        if index is None:
            return None, None, "Usage: /speak q1|q2|q3 (or /speak 1)"
        return None, {"type": "speak_segment", "index": index}, None
    if cmd == "/macro":
        if not args:
            return None, None, "Usage: /macro <id> [topic]"
        macro_id = args[0]
        topic = " ".join(args[1:]).strip()
        event = Event(action="run_macro", payload_text=macro_id, source="keyboard")
        if topic:
            event.metadata["topic"] = topic
        event.metadata["speak"] = True
        return event, None, None
    if cmd == "/feedback":
        if not args:
            return None, None, "Usage: /feedback correct|wrong"
        mode = args[0].lower()
        if mode not in ("correct", "wrong"):
            return None, None, "Usage: /feedback correct|wrong"
        return None, {"type": "feedback", "mode": mode}, None
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


def _parse_question_index(text: str) -> int | None:
    if not text:
        return None
    target = text.lower().strip()
    if target.startswith("q"):
        target = target[1:]
    if not target.isdigit():
        return None
    index = int(target) - 1
    if index < 0:
        return None
    return index


def render_result(
    result: ActionResult, orchestrator: Orchestrator, event: Event | None = None
) -> None:
    if result.error:
        print(f"(error) {result.error}")
        return
    if result.action == "add_utterance":
        return

    if result.suggestions:
        for i, s in enumerate(result.suggestions, 1):
            tone = s.tone or "neutral"
            length = s.length or "medium"
            risk = s.risk or "low"
            print(f"[{i}][{tone}][{length}][{risk}] {s.text}")

        if result.spoken_text:
            return

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
            suggestion = result.suggestions[idx]
            orchestrator.record_choice(suggestion, source="manual")
            orchestrator.speak(suggestion)
        except ValueError:
            print("Invalid input. Skipping.")
        return

    if result.translation:
        print(json.dumps(result.translation, ensure_ascii=False, indent=2))
        return
    if result.explanation:
        explanation = result.explanation
        script = explanation.get("script") if isinstance(explanation, dict) else None
        if isinstance(script, list) and script:
            print("Script:")
            for i, line in enumerate(script, 1):
                text = str(line).strip()
                if text:
                    print(f"[{i}] {text}")
        else:
            print(json.dumps(result.explanation, ensure_ascii=False, indent=2))
        checkpoints = (
            explanation.get("checkpoints") if isinstance(explanation, dict) else None
        )
        if isinstance(checkpoints, list) and checkpoints:
            print("Checkpoints:")
            for i, item in enumerate(checkpoints, 1):
                text = str(item).strip()
                if text:
                    print(f"- {text}")
        return
    if result.coach:
        coach = result.coach
        goal = coach.get("goal") if isinstance(coach, dict) else None
        if goal:
            print(f"Goal: {goal}")
        questions = coach.get("questions") if isinstance(coach, dict) else None
        if isinstance(questions, list) and questions:
            for i, q in enumerate(questions, 1):
                text = q.get("q") if isinstance(q, dict) else None
                hint = q.get("hint") if isinstance(q, dict) else None
                if text:
                    print(f"[{i}] {text}")
                if hint:
                    print(f"  hint: {hint}")

            if event and event.metadata.get("speak"):
                return

            choice = input(
                f"Speak question [1-{len(questions)}] or 's' to skip: "
            ).strip()
            if choice.lower() == "s":
                return
            if choice == "":
                choice = "1"
            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(questions):
                    print("Invalid choice.")
                    return
                q_text = questions[idx].get("q") if isinstance(questions[idx], dict) else None
                if q_text:
                    orchestrator.speak(q_text)
            except ValueError:
                print("Invalid input. Skipping.")
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
    log = get_logger("text_demo")
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    session_id = orchestrator.session.session.id
    transcript_path = logs_dir / f"{session_id}.jsonl"
    summary_path = logs_dir / f"{session_id}_summary.md"

    try:
        orchestrator.session.export_transcript_jsonl(transcript_path)
    except OSError as exc:
        log.warning("Failed to write transcript to %s: %s", transcript_path, exc)
        return

    summary_payload = orchestrator.session.session.metadata.get("rolling_summary_payload")
    summary_text = orchestrator.session.session.metadata.get("rolling_summary")
    if not summary_payload:
        result = orchestrator.handle_event(Event(action="summarize", source="keyboard"))
        if result.summary and isinstance(result.summary, dict):
            summary_payload = result.summary
            summary_text = result.summary.get("summary_markdown", "")
    if not summary_text:
        summary_text = "- No summary available."
    try:
        if summary_payload and isinstance(summary_payload, dict):
            orchestrator.session.export_summary_md(summary_path, summary_payload)
        else:
            orchestrator.session.export_summary_md(summary_path, summary_text)
    except OSError as exc:
        log.warning("Failed to write summary to %s: %s", summary_path, exc)
        return

    try:
        orchestrator.storage.save_session(orchestrator.session.session)
    except OSError as exc:
        log.warning("Failed to save session snapshot: %s", exc)
    print(f"Exported: {transcript_path} and {summary_path}")


if __name__ == "__main__":
    raise SystemExit(main())
