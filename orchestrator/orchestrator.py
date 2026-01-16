from __future__ import annotations

from datetime import datetime
from typing import Any

from audio_io import AudioIOBundle, BasicAudioOutput
from conversation.session_manager import ConversationSession
from core.storage import LocalFileStorageAdapter, StorageAdapter
from core.types import (
    ActionResult,
    ActionType,
    Event,
    Participant,
    Profile,
    Suggestion,
    Utterance,
)
from core.logging import get_logger
from services import ServiceBundle
from understanding.explain_concept import ExplainConceptEngine
from understanding.explain_utterance import ExplainUtteranceEngine
from understanding.intent_analyzer import analyze_intent
from understanding.coach_engine import CoachEngine
from understanding.summarizer import Summarizer
from understanding.suggestion_engine import SuggestionEngine
from understanding.translator import TranslateEngine


class Orchestrator:
    """
    Coordinates the flow from input → understanding → suggestion → TTS/output.
    Real implementations will plug in concrete services in later phases.
    """

    def __init__(
        self,
        profile: Profile,
        services: ServiceBundle,
        audio_io: AudioIOBundle | None = None,
        storage: StorageAdapter | None = None,
    ):
        self.profile = profile
        self.services = services
        self.audio_io = audio_io or AudioIOBundle()
        if not self.audio_io.output:
            self.audio_io.output = BasicAudioOutput()
        self.storage = storage or LocalFileStorageAdapter()
        self.session = ConversationSession(profile)
        self.suggestion_engine = (
            SuggestionEngine(profile, services.llm) if services.llm else None
        )
        self.translate_engine = TranslateEngine(profile, services.llm)
        self.explain_utterance_engine = ExplainUtteranceEngine(profile, services.llm)
        self.explain_concept_engine = ExplainConceptEngine(profile, services.llm)
        self.coach_engine = CoachEngine(profile, services.llm)
        self.summarizer = Summarizer(profile, services.llm)
        self.log = get_logger("orchestrator")
        self.local_participant = Participant(
            id="local", role="local_user", display_name="You"
        )
        self.remote_participant = Participant(
            id="remote", role="remote_user", display_name="Student"
        )
        self._configure_metrics()

    def handle_remote_audio(self, audio_chunk: bytes) -> None:
        """
        Placeholder for audio pipeline (ASR → intent → suggestion → optional TTS).
        """
        _ = audio_chunk
        # Implemented in later phases.

    def handle_local_text(self, text: str, speak: bool = False):
        """
        Minimal text flow used for early smoke tests.
        If speak=True (or profile.auto_speak), will attempt TTS on the first suggestion.
        """
        if not text.strip():
            return []
        event = Event(
            action=self.profile.default_action,
            payload_text=text.strip(),
            source="keyboard",
        )
        if speak:
            event.metadata["speak"] = True
        result = self.handle_event(event)
        return result.suggestions

    def handle_event(self, event: Event) -> ActionResult:
        action = self._normalize_action(event.action)
        if not self._action_allowed(action):
            return ActionResult(
                action=action,
                error=f"Action '{action}' not enabled for profile '{self.profile.name}'.",
            )

        self._append_event_log(
            {
                "type": "event",
                "timestamp": event.timestamp.isoformat(),
                "action": action,
                "payload_text": event.payload_text,
                "target_lang": event.target_lang,
                "speaker_role": event.speaker_role,
                "speaker_name": event.speaker_name,
                "source": event.source,
                "metadata": event.metadata,
            }
        )

        if action == "suggest":
            return self._handle_suggest(event)
        if action == "add_utterance":
            return self._handle_add_utterance(event)
        if action == "translate_last":
            return self._handle_translate_last(event)
        if action == "explain_last":
            return self._handle_explain_last(event)
        if action == "explain_concept":
            return self._handle_explain_concept(event)
        if action == "coach_student":
            return self._handle_coach_student(event)
        if action == "summarize":
            return self._handle_summarize(event)

        return ActionResult(action=action, error=f"Unknown action: {action}")

    def speak(self, utterance: Suggestion | str) -> bool:
        """
        Synthesize and play a suggestion or arbitrary text without mutating session state.
        """
        if not self.services.tts:
            self.log.warning("TTS service missing; cannot speak.")
            return False

        text = utterance.text if isinstance(utterance, Suggestion) else str(utterance)
        if not text.strip():
            self.log.warning("Empty text provided to speak(); skipping.")
            return False

        voice_id = (
            getattr(self.services, "tts_voice_id_override", None)
            or getattr(self.profile, "default_voice", None)
        )
        audio = self.services.tts.synthesize(
            text.strip(), voice_id=voice_id or self.profile.default_voice
        )
        if not audio:
            self.log.warning("TTS synthesis returned no audio bytes.")
            return False

        if self.audio_io.output and hasattr(self.audio_io.output, "play_to_device"):
            try:
                self.audio_io.output.play_to_device(self.profile.output_device, audio)
                self._append_event_log(
                    {
                        "type": "spoken",
                        "timestamp": datetime.utcnow().isoformat(),
                        "text": text,
                        "success": True,
                    }
                )
                return True
            except Exception as exc:
                self.log.error("Failed to play audio: %s", exc)
                self._append_event_log(
                    {
                        "type": "spoken",
                        "timestamp": datetime.utcnow().isoformat(),
                        "text": text,
                        "success": False,
                    }
                )
                return False

        self.log.info(
            "Generated TTS audio (%d bytes) for '%s' (no output backend configured)",
            len(audio),
            text,
        )
        self._append_event_log(
            {
                "type": "spoken",
                "timestamp": datetime.utcnow().isoformat(),
                "text": text,
                "success": False,
            }
        )
        return False

    def _normalize_action(self, action: ActionType | str) -> ActionType:
        normalized = str(action).lower()
        if normalized in {
            "add_utterance",
            "suggest",
            "explain_concept",
            "explain_last",
            "coach_student",
            "translate_last",
            "summarize",
        }:
            return normalized  # type: ignore[return-value]
        if normalized == "coach":
            return "coach_student"
        if normalized == "summarize_session":
            return "summarize"
        return "suggest"

    def _action_allowed(self, action: ActionType) -> bool:
        if action == "add_utterance":
            return True
        if not self.profile.capabilities:
            return True
        if action in self.profile.capabilities:
            return True
        if action == "summarize" and "summarize_session" in self.profile.capabilities:
            return True
        return False

    def _handle_suggest(self, event: Event) -> ActionResult:
        if not event.payload_text:
            return ActionResult(action="suggest", error="No text provided for suggestion.")

        utt = Utterance(
            speaker=self.local_participant,
            text=event.payload_text.strip(),
            source=event.source,
            language=None,
        )
        self.session.add_utterance(utt)
        self._append_event_log(
            {
                "type": "utterance",
                "timestamp": utt.timestamp.isoformat(),
                "role": utt.speaker.role,
                "text": utt.text,
                "source": utt.source,
            }
        )

        if not self.services.llm or not self.suggestion_engine:
            return ActionResult(
                action="suggest",
                error="LLM service missing; cannot generate suggestions.",
            )

        intent = analyze_intent(self.services.llm, self.session)
        suggestions = self.suggestion_engine.generate_suggestions(self.session, intent)
        for s in suggestions:
            self.session.add_suggestion(s)

        self._append_event_log(
            {
                "type": "intent",
                "timestamp": datetime.utcnow().isoformat(),
                "intent": {
                    "intent": intent.intent,
                    "topic": intent.topic,
                    "emotion": intent.emotion,
                    "ask_for_clarification": intent.ask_for_clarification,
                },
            }
        )
        self._append_event_log(
            {
                "type": "suggestions",
                "timestamp": datetime.utcnow().isoformat(),
                "suggestions": [self._suggestion_to_dict(s) for s in suggestions],
            }
        )

        should_speak = bool(event.metadata.get("speak")) or self.profile.reply_strategy.auto_speak
        spoken_text = None
        if should_speak and suggestions:
            chosen = suggestions[0]
            self.record_choice(chosen, source="auto")
            spoken_text = chosen.text
            self.speak(chosen)

        return ActionResult(
            action="suggest",
            intent=intent,
            suggestions=suggestions,
            spoken_text=spoken_text,
        )

    def _handle_add_utterance(self, event: Event) -> ActionResult:
        if not event.payload_text:
            return ActionResult(action="add_utterance", error="No text provided.")
        self.add_utterance(
            event.payload_text,
            speaker_role=event.speaker_role or "remote_user",
            source=event.source,
            speaker_name=event.speaker_name,
        )
        return ActionResult(action="add_utterance")

    def _handle_translate_last(self, event: Event) -> ActionResult:
        last = self.session.select_last_utterance("remote_user")
        if not last:
            return ActionResult(
                action="translate_last", error="No remote utterance found to translate."
            )
        target_lang = (
            event.target_lang
            or self.profile.metadata.get("default_translate_lang")
            or "zh"
        )
        translation = self.translate_engine.translate(last.text, target_lang=target_lang)
        self._append_event_log(
            {
                "type": "translation",
                "timestamp": datetime.utcnow().isoformat(),
                "translation": translation,
            }
        )
        return ActionResult(action="translate_last", translation=translation)

    def _handle_explain_last(self, event: Event) -> ActionResult:
        last = self.session.select_last_utterance("remote_user")
        if not last:
            return ActionResult(
                action="explain_last", error="No remote utterance found to explain."
            )
        explanation = self.explain_utterance_engine.explain(last.text)
        self._append_event_log(
            {
                "type": "explanation",
                "timestamp": datetime.utcnow().isoformat(),
                "explanation": explanation,
            }
        )
        return ActionResult(action="explain_last", explanation=explanation)

    def _handle_explain_concept(self, event: Event) -> ActionResult:
        if not event.payload_text:
            return ActionResult(
                action="explain_concept", error="No concept provided to explain."
            )
        explanation = self.explain_concept_engine.explain(event.payload_text)
        spoken_text = self._build_explain_spoken_text(explanation)
        self._append_event_log(
            {
                "type": "explanation",
                "timestamp": datetime.utcnow().isoformat(),
                "explanation": explanation,
            }
        )
        if event.metadata.get("speak") and spoken_text:
            self.speak(spoken_text)
        return ActionResult(
            action="explain_concept",
            explanation=explanation,
            spoken_text=spoken_text,
        )

    def _handle_coach_student(self, event: Event) -> ActionResult:
        if not event.payload_text:
            return ActionResult(
                action="coach_student", error="No student message provided."
            )

        utt = Utterance(
            speaker=self.remote_participant,
            text=event.payload_text.strip(),
            source=event.source,
            language=None,
        )
        self.session.add_utterance(utt)
        self._append_event_log(
            {
                "type": "utterance",
                "timestamp": utt.timestamp.isoformat(),
                "role": utt.speaker.role,
                "text": utt.text,
                "source": utt.source,
            }
        )

        coach = self.coach_engine.generate_coaching(self.session, utt.text)
        self._append_event_log(
            {
                "type": "coach",
                "timestamp": datetime.utcnow().isoformat(),
                "coach": coach,
            }
        )

        spoken_text = None
        if event.metadata.get("speak"):
            questions = coach.get("questions") if isinstance(coach, dict) else None
            if isinstance(questions, list) and questions:
                spoken_text = str(questions[0].get("q") or "").strip()
            if spoken_text:
                self.speak(spoken_text)

        return ActionResult(action="coach_student", coach=coach, spoken_text=spoken_text)

    def _handle_summarize(self, event: Event) -> ActionResult:
        max_turns = int(event.metadata.get("max_turns", 12))
        summary = self.summarizer.summarize(self.session, max_turns=max_turns)
        self.session.session.metadata["rolling_summary"] = summary.get("summary_markdown", "")
        self.session.session.metadata["last_summary_index"] = len(
            self.session.session.utterances
        )
        self._append_event_log(
            {
                "type": "summary",
                "timestamp": datetime.utcnow().isoformat(),
                "summary": summary,
            }
        )
        return ActionResult(action="summarize", summary=summary)

    def _build_explain_spoken_text(self, explanation: dict[str, Any]) -> str:
        max_chars = int(
            self.profile.constraints.get(
                "max_explain_chars",
                self.profile.metadata.get(
                    "max_explain_chars",
                    self.profile.metadata.get("max_explain_text_chars", 900),
                ),
            )
        )
        parts: list[str] = []
        title = explanation.get("title")
        if isinstance(title, str) and title.strip():
            parts.append(title.strip())
        one_liner = explanation.get("one_liner")
        if isinstance(one_liner, str) and one_liner.strip():
            parts.append(one_liner.strip())
        steps = explanation.get("steps")
        if isinstance(steps, list):
            for step in steps:
                if not isinstance(step, dict):
                    continue
                say = step.get("say")
                if isinstance(say, str) and say.strip():
                    parts.append(say.strip())
        example = explanation.get("example")
        if isinstance(example, str) and example.strip():
            parts.append(example.strip())
        checkpoints = explanation.get("checkpoints")
        if isinstance(checkpoints, list) and checkpoints:
            joined = "; ".join([str(item) for item in checkpoints if str(item).strip()])
            if joined:
                parts.append(joined)
        spoken = "\n".join(parts).strip()
        if max_chars and len(spoken) > max_chars:
            spoken = spoken[:max_chars].rstrip()
        return spoken

    def _configure_metrics(self) -> None:
        def _hook(payload: dict[str, Any]) -> None:
            event = {
                "type": "metrics",
                "timestamp": datetime.utcnow().isoformat(),
                **payload,
            }
            self._append_event_log(event)

        for service in (self.services.llm, self.services.tts):
            if service is None:
                continue
            try:
                service.metrics_hook = _hook
            except Exception:
                self.log.debug("Failed to attach metrics hook.", exc_info=True)

    def record_choice(self, suggestion: Suggestion, source: str = "manual") -> None:
        """
        Log a suggestion choice without mutating session state.
        """
        self._append_event_log(
            {
                "type": "chosen",
                "timestamp": datetime.utcnow().isoformat(),
                "source": source,
                "suggestion": self._suggestion_to_dict(suggestion),
            }
        )

    def add_utterance(
        self,
        text: str,
        speaker_role: str = "remote_user",
        source: str = "keyboard",
        speaker_name: str | None = None,
    ) -> Utterance:
        role = str(speaker_role).strip() or "remote_user"
        speaker = self.remote_participant
        if role == "local_user":
            speaker = self.local_participant
        elif role == "agent":
            speaker = Participant(id="agent", role="agent", display_name="Agent")
        if speaker_name:
            speaker = Participant(
                id=speaker.id, role=speaker.role, display_name=speaker_name
            )

        utt = Utterance(
            speaker=speaker,
            text=text.strip(),
            source=source,  # type: ignore[arg-type]
            language=None,
        )
        self.session.add_utterance(utt)
        self._append_event_log(
            {
                "type": "utterance",
                "timestamp": utt.timestamp.isoformat(),
                "role": utt.speaker.role,
                "text": utt.text,
                "source": utt.source,
            }
        )
        return utt

    def _append_event_log(self, payload: dict[str, Any]) -> None:
        if not self.storage:
            return
        payload.setdefault("session_id", self.session.session.id)
        self.storage.append_event(self.session.session.id, payload)

    def _suggestion_to_dict(self, suggestion: Suggestion) -> dict[str, Any]:
        return {
            "text": suggestion.text,
            "tone": suggestion.tone,
            "length": suggestion.length,
            "risk": suggestion.risk,
            "auto_send": suggestion.auto_send,
            "style": suggestion.style,
            "confidence": suggestion.confidence,
        }
