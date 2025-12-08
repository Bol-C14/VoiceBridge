from __future__ import annotations

from typing import List
import textwrap

from conversation.session_manager import ConversationSession
from core.types import Profile, Suggestion
from services.llm_base import LLMService
from understanding.intent_analyzer import IntentResult


SUGGESTION_SYSTEM_PROMPT = """You generate short, natural replies. Return {n} options.
Keep each under {max_len} characters unless context requires more."""


class SuggestionEngine:
    """
    Generates reply suggestions based on profile and conversation context.
    """

    def __init__(self, profile: Profile, llm: LLMService):
        self.profile = profile
        self.llm = llm

    def _context_transcript(self, session: ConversationSession, max_turns: int = 8) -> str:
        parts = []
        for utt in session.get_recent_context(max_turns=max_turns):
            speaker = "User" if utt.speaker.role == "local_user" else utt.speaker.display_name or "Assistant"
            parts.append(f"{speaker}: {utt.text}")
        return "\n".join(parts)

    def _build_messages(
        self,
        session: ConversationSession,
        intent: IntentResult,
        n: int = 2,
    ) -> list[dict[str, str]]:
        max_len = self.profile.reply_strategy.max_suggestion_length
        system_prompt = SUGGESTION_SYSTEM_PROMPT.format(n=n, max_len=max_len)

        suggestion_template = self.profile.prompts.get("suggestion", "")
        transcript = self._context_transcript(session)
        template_vars = {
            "profile_name": self.profile.name,
            "mode": self.profile.name,
            "transcript": transcript,
            "max_len": max_len,
            "n": n,
            "intent": intent.intent,
            "topic": intent.topic,
            "emotion": intent.emotion,
        }

        rendered_template = suggestion_template
        try:
            rendered_template = suggestion_template.format(**template_vars)
        except Exception:
            # Fallback to raw template if formatting fails
            rendered_template = suggestion_template

        messages = [{"role": "system", "content": system_prompt}]
        if rendered_template:
            messages.append({"role": "system", "content": rendered_template})

        # Append recent chat history as messages
        messages.extend(session.to_chat_history(max_turns=8))
        return messages

    def _parse_suggestions(self, text: str, n: int = 2) -> List[Suggestion]:
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
            if len(suggestions) >= n:
                break
        return suggestions

    def generate_suggestions(
        self,
        session: ConversationSession,
        intent: IntentResult,
    ) -> List[Suggestion]:
        if not self.llm:
            return []
        n = 2
        messages = self._build_messages(session, intent, n=n)
        response = self.llm.complete(messages, model=None)
        return self._parse_suggestions(response, n=n)
