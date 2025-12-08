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

    def handle_local_text(self, text: str) -> None:
        """
        Minimal text flow used for early smoke tests.
        """
        if not text.strip():
            return

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

        # Auto-speak policy (disabled for now; leave logging hook)
        if self.profile.reply_strategy.auto_speak and self.services.tts and suggestions:
            chosen: Suggestion = suggestions[0]
            audio = self.services.tts.synthesize(
                chosen.text, voice_id=self.profile.default_voice
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
