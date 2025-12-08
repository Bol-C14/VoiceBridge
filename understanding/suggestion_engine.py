from __future__ import annotations

from typing import List
import textwrap

from conversation.session_manager import ConversationSession
from core.types import Profile, Suggestion
from services.llm_base import LLMService
from understanding.intent_analyzer import IntentResult


SUGGESTION_SYSTEM_PROMPT = """You generate short, natural replies. Return 2-3 options.
Keep each under {max_len} characters unless context requires more."""


class SuggestionEngine:
    """
    Generates reply suggestions based on profile and conversation context.
    """

    def __init__(self, profile: Profile, llm: LLMService):
        self.profile = profile
        self.llm = llm

    def _build_messages(
        self,
        session: ConversationSession,
        intent: IntentResult,
    ) -> list[dict[str, str]]:
        system_parts = [
            SUGGESTION_SYSTEM_PROMPT.format(
                max_len=self.profile.reply_strategy.max_suggestion_length
            )
        ]
        if intent.intent:
            system_parts.append(f"Detected intent: {intent.intent}")
        if intent.topic:
            system_parts.append(f"Topic: {intent.topic}")
        if intent.emotion:
            system_parts.append(f"User emotion: {intent.emotion}")

        system_prompt = "\n".join(system_parts)
        prompts = [{"role": "system", "content": system_prompt}]

        history = session.get_recent_context(max_turns=6)
        for utt in history:
            role = "user" if utt.speaker.role == "local_user" else "assistant"
            prompts.append({"role": role, "content": utt.text})

        suggestion_template = self.profile.prompts.get("suggestion")
        if suggestion_template:
            prompts.append({"role": "system", "content": suggestion_template})
        return prompts

    def _parse_suggestions(self, text: str) -> List[Suggestion]:
        lines = [line.strip("-• ").strip() for line in text.splitlines() if line.strip()]
        if not lines:
            lines = [text.strip()]

        max_len = self.profile.reply_strategy.max_suggestion_length
        suggestions: List[Suggestion] = []
        for line in lines:
            if not line:
                continue
            shortened = textwrap.shorten(line, width=max_len, placeholder="…")
            suggestions.append(Suggestion(text=shortened, auto_send=False))
        return suggestions

    def generate_suggestions(
        self,
        session: ConversationSession,
        intent: IntentResult,
    ) -> List[Suggestion]:
        if not self.llm:
            return []
        messages = self._build_messages(session, intent)
        response = self.llm.complete(messages, model=None)
        return self._parse_suggestions(response)
