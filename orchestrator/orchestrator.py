from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from conversation.session_manager import ConversationSession
from core.types import Participant, Profile, Suggestion, Utterance
from core.logging import get_logger
from understanding.intent_analyzer import analyze_intent
from understanding.suggestion_engine import SuggestionEngine


@dataclass
class ServiceBundle:
    asr: Any = None
    llm: Any = None
    tts: Any = None


@dataclass
class AudioIOBundle:
    output: Any = None


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
    ):
        self.profile = profile
        self.services = services
        self.audio_io = audio_io or AudioIOBundle()
        self.session = ConversationSession(profile)
        self.suggestion_engine = (
            SuggestionEngine(profile, services.llm) if services.llm else None
        )
        self.log = get_logger("orchestrator")
        self.local_participant = Participant(
            id="local", role="local_user", display_name="You"
        )

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

        utt = Utterance(
            speaker=self.local_participant,
            text=text.strip(),
            source="keyboard",
            language=None,
        )
        self.session.add_utterance(utt)

        if not self.services.llm or not self.suggestion_engine:
            self.log.warning("LLM service missing; cannot generate suggestions.")
            return []

        intent = analyze_intent(self.services.llm, self.session)
        suggestions = self.suggestion_engine.generate_suggestions(self.session, intent)
        for s in suggestions:
            self.session.add_suggestion(s)

        # Auto-speak policy (explicit speak flag or profile setting)
        should_speak = speak or self.profile.reply_strategy.auto_speak
        if should_speak and self.services.tts and suggestions:
            chosen: Suggestion = suggestions[0]
            voice_id = (
                getattr(self.services, "tts_voice_id_override", None)
                or getattr(self.profile, "default_voice", None)
            )
            audio = self.services.tts.synthesize(
                chosen.text, voice_id=voice_id or self.profile.default_voice
            )
            if self.audio_io.output and hasattr(self.audio_io.output, "play_to_device"):
                try:
                    self.audio_io.output.play_to_device(
                        self.profile.output_device, audio
                    )
                except Exception as exc:
                    self.log.error("Failed to play audio: %s", exc)
            else:
                self.log.info(
                    "Generated TTS audio (%d bytes) for '%s' (no output backend configured)",
                    len(audio),
                    chosen.text,
                )

        return suggestions
