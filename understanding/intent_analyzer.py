from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Optional

from conversation.session_manager import ConversationSession
from services.llm_base import LLMService


@dataclass
class IntentResult:
    intent: str = "statement"  # question | statement
    topic: str = ""
    emotion: str = "neutral"  # neutral | confused
    ask_for_clarification: bool = False


DEFAULT_INTENT_PROMPT = """You classify the latest user message.
Return JSON with keys:
- intent: "question" or "statement"
- topic: short noun phrase
- emotion: "neutral" or "confused"
- ask_for_clarification: true/false
Be concise and only output JSON."""


def _build_messages(session: ConversationSession) -> list[dict[str, str]]:
    profile_prompt = session.profile.prompts.get("intent", "").strip()
    system_prompt = profile_prompt or DEFAULT_INTENT_PROMPT

    msgs: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    # Use recent chat history
    msgs.extend(session.to_chat_history(max_turns=4))
    return msgs


def analyze_intent(
    llm: Optional[LLMService],
    session: ConversationSession,
) -> IntentResult:
    if not llm:
        return IntentResult()

    msgs = _build_messages(session)
    try:
        raw = llm.structured(msgs, model=None, schema=None)
        if isinstance(raw, str):
            data = json.loads(raw)
        else:
            data = raw or {}
        return IntentResult(
            intent=str(data.get("intent", "statement")),
            topic=str(data.get("topic", "")),
            emotion=str(data.get("emotion", "neutral")),
            ask_for_clarification=bool(data.get("ask_for_clarification", False)),
        )
    except Exception:
        # Fail open with defaults to avoid breaking the pipeline.
        return IntentResult()
