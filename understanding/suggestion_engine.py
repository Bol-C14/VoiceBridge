from __future__ import annotations

from typing import Any, List
import textwrap

from conversation.session_manager import ConversationSession
from core.types import Profile, Suggestion
from services.llm_base import LLMService
from understanding.intent_analyzer import IntentResult


SUGGESTION_SYSTEM_PROMPT = """You generate short, natural reply suggestions.
Respond with JSON only, following the provided schema."""


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
        system_prompt = SUGGESTION_SYSTEM_PROMPT

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

        messages.append(
            {
                "role": "system",
                "content": (
                    f"Return up to {n} suggestions as JSON using the 'suggestions' array. "
                    "Each suggestion has: text (required, string), tone (optional, string), "
                    "length (optional, short|medium|long), risk (optional, low|medium|high), "
                    "auto_send (optional, boolean). "
                    f"Keep text under {max_len} characters when possible."
                ),
            }
        )
        humor_line = (
            "Humor is allowed when appropriate."
            if self.profile.reply_strategy.allow_humor
            else "Avoid humor; keep it neutral."
        )
        messages.append({"role": "system", "content": humor_line})
        messages.append(
            {
                "role": "system",
                "content": (
                    f"Conversation intent: {intent.intent}; topic: {intent.topic}; emotion: {intent.emotion}."
                ),
            }
        )

        # Append recent chat history as messages
        messages.extend(session.to_chat_history(max_turns=8))
        return messages

    def _suggestion_schema(self, n: int) -> dict[str, Any]:
        return {
            "name": "suggestions_payload",
            "strict": True,
            "schema": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "suggestions": {
                        "type": "array",
                        "minItems": 1,
                        "maxItems": n,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "text": {"type": "string"},
                                "tone": {"type": "string"},
                                "length": {"type": "string"},
                                "risk": {"type": "string"},
                                "auto_send": {"type": "boolean"},
                            },
                            "required": ["text"],
                        },
                    }
                },
                "required": ["suggestions"],
            },
        }

    def _parse_structured_suggestions(
        self, payload: Any, n: int = 2
    ) -> List[Suggestion]:
        if not isinstance(payload, dict):
            return []

        items = payload.get("suggestions")
        if not isinstance(items, list):
            return []

        max_len = self.profile.reply_strategy.max_suggestion_length
        suggestions: List[Suggestion] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            tone = item.get("tone") or item.get("style")
            tone = str(tone) if tone else None
            length = item.get("length")
            length = str(length) if length else None
            risk = item.get("risk")
            risk = str(risk).lower() if isinstance(risk, str) else None
            if risk not in {"low", "medium", "high"}:
                risk = None
            auto_send = bool(item.get("auto_send", False))
            if risk == "high":
                auto_send = False
            if not self.profile.reply_strategy.allow_agent_mode:
                auto_send = False

            shortened = textwrap.shorten(text, width=max_len, placeholder="…")
            suggestions.append(
                Suggestion(
                    text=shortened,
                    tone=tone,
                    length=length,
                    risk=risk,
                    auto_send=auto_send,
                )
            )
            if len(suggestions) >= n:
                break
        return suggestions

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
        n = max(1, int(self.profile.reply_strategy.max_suggestions))
        messages = self._build_messages(session, intent, n=n)
        structured = self.llm.structured(
            messages, model=None, schema=self._suggestion_schema(n)
        )
        suggestions = self._parse_structured_suggestions(structured, n=n)
        if suggestions:
            return suggestions

        # Fallback to freeform parsing if structured output fails.
        response = self.llm.complete(messages, model=None)
        return self._parse_suggestions(response, n=n)
