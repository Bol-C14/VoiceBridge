from __future__ import annotations

from typing import List

from conversation.session_manager import ConversationSession
from core.types import Profile, Suggestion
from services.llm_base import LLMService
from understanding.intent_analyzer import IntentResult


class SuggestionEngine:
    """
    Generates reply suggestions based on profile and conversation context.
    Implementation will be filled in during later phases.
    """

    def __init__(self, profile: Profile, llm: LLMService):
        self.profile = profile
        self.llm = llm

    def generate_suggestions(
        self,
        session: ConversationSession,
        intent: IntentResult,
    ) -> List[Suggestion]:
        _ = (session, intent)
        return []
