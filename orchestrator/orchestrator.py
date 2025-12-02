from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from conversation.session_manager import ConversationSession
from core.types import Profile
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
        if not self.services.llm or not self.suggestion_engine:
            return
        intent = analyze_intent(self.services.llm, self.session)
        self.suggestion_engine.generate_suggestions(self.session, intent)
