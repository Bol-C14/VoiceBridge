from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from conversation.session_manager import ConversationSession
from services.llm_base import LLMService


@dataclass
class IntentResult:
    intent: str = "other"
    topic: str = ""
    emotion: str = "neutral"
    ask_for_clarification: bool = False


def analyze_intent(
    llm: Optional[LLMService],
    session: ConversationSession,
) -> IntentResult:
    """
    Placeholder intent analyzer. Later this will call the LLM with recent context.
    """
    _ = llm  # reserved for future use
    _ = session
    return IntentResult()
