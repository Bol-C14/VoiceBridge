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
- intent: "question" | "statement" | "command" | "feedback" | "other"
- topic: short noun phrase
- emotion: "neutral" | "confused" | "frustrated"
- ask_for_clarification: true/false
Be concise and only output JSON."""
INTENT_RESPONSE_SCHEMA = {
    "name": "intent_payload",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "intent": {
                "type": "string",
                "enum": ["question", "statement", "command", "feedback", "other"],
            },
            "topic": {"type": "string"},
            "emotion": {"type": "string", "enum": ["neutral", "confused", "frustrated"]},
            "ask_for_clarification": {"type": "boolean"},
        },
        "required": ["intent", "topic", "emotion", "ask_for_clarification"],
    },
}


def _build_messages(session: ConversationSession) -> list[dict[str, str]]:
    profile_prompt = session.profile.prompts.get("intent", "").strip()
    system_prompt = profile_prompt or DEFAULT_INTENT_PROMPT

    msgs: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
    msgs.append(
        {
            "role": "system",
            "content": (
                "Return a JSON object with keys intent, topic, emotion, ask_for_clarification "
                "and no additional properties."
            ),
        }
    )
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
        raw = llm.structured(msgs, model=None, schema=INTENT_RESPONSE_SCHEMA)
        if isinstance(raw, str):
            data = json.loads(raw)
        else:
            data = raw or {}

        intent_val = str(data.get("intent", "statement")).lower()
        if intent_val not in {"question", "statement", "command", "feedback", "other"}:
            intent_val = "statement"

        emotion_val = str(data.get("emotion", "neutral")).lower()
        if emotion_val not in {"neutral", "confused", "frustrated"}:
            emotion_val = "neutral"

        return IntentResult(
            intent=intent_val,
            topic=str(data.get("topic", "")),
            emotion=emotion_val,
            ask_for_clarification=bool(data.get("ask_for_clarification", False)),
        )
    except Exception:
        # Fail open with defaults to avoid breaking the pipeline.
        return IntentResult()
