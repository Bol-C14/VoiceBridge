from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Optional

from conversation.session_manager import ConversationSession
from services.llm_base import LLMService


@dataclass
class IntentResult:
    intent: str = "other"
    topic: str = ""
    emotion: str = "neutral"
    ask_for_clarification: bool = False


INTENT_PROMPT = """You are an assistant that classifies the latest user message.
Return JSON with keys: intent (question/statement/smalltalk/complaint/request_help/other),
topic (short noun phrase), emotion (neutral/confused/frustrated/happy/serious), ask_for_clarification (true/false)."""


def _build_messages(session: ConversationSession) -> list[dict[str, str]]:
    msgs: list[dict[str, str]] = [{"role": "system", "content": INTENT_PROMPT}]
    for utt in session.get_recent_context(max_turns=6):
        msgs.append(
            {
                "role": "user" if utt.speaker.role == "local_user" else "assistant",
                "content": utt.text,
            }
        )
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
            data = raw
        return IntentResult(
            intent=str(data.get("intent", "other")),
            topic=str(data.get("topic", "")),
            emotion=str(data.get("emotion", "neutral")),
            ask_for_clarification=bool(data.get("ask_for_clarification", False)),
        )
    except Exception:
        # Fail open with defaults to avoid breaking the pipeline.
        return IntentResult()
