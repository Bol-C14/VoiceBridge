from __future__ import annotations

from typing import Any, Dict, List

from conversation.session_manager import ConversationSession
from core.types import Profile
from services.llm_base import LLMService


COACH_SYSTEM_PROMPT = """You are a teaching coach who guides students with short questions.
Return JSON only, following the schema."""

COACH_SCHEMA = {
    "name": "coach_payload",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "goal": {"type": "string"},
            "questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "q": {"type": "string"},
                        "expected": {"type": "string"},
                        "hint": {"type": "string"},
                    },
                    "required": ["q", "expected", "hint"],
                },
            },
            "micro_feedback": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "correct": {"type": "array", "items": {"type": "string"}},
                    "wrong": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["correct", "wrong"],
            },
            "next_action": {"type": "string"},
        },
        "required": ["goal", "questions", "micro_feedback", "next_action"],
    },
}


class CoachEngine:
    def __init__(self, profile: Profile, llm: LLMService):
        self.profile = profile
        self.llm = llm
        self.last_meta: Dict[str, Any] = {}

    def _context_transcript(self, session: ConversationSession, max_turns: int = 6) -> str:
        parts = []
        for utt in session.get_recent_context(max_turns=max_turns):
            speaker = (
                "User" if utt.speaker.role == "local_user" else utt.speaker.display_name
            )
            parts.append(f"{speaker}: {utt.text}")
        return "\n".join(parts)

    def _build_messages(
        self,
        session: ConversationSession,
        student_text: str,
    ) -> list[dict[str, str]]:
        prompt = self.profile.prompts.get("coach_student", "").strip()
        max_questions = int(
            self.profile.constraints.get(
                "max_questions", self.profile.metadata.get("max_coach_questions", 4)
            )
        )
        max_question_chars = int(
            self.profile.constraints.get(
                "max_question_chars", self.profile.metadata.get("max_coach_question_chars", 140)
            )
        )
        no_spoilers = bool(self.profile.constraints.get("no_spoilers", False))

        messages = [{"role": "system", "content": COACH_SYSTEM_PROMPT}]
        if prompt:
            messages.append({"role": "system", "content": prompt})
        messages.append(
            {
                "role": "system",
                "content": (
                    f"Provide {max_questions} or fewer short questions. "
                    f"Each question must be under {max_question_chars} characters. "
                "Hints must not give away the answer."
            ),
        }
        )
        if no_spoilers:
            messages.append(
                {
                    "role": "system",
                    "content": "Do not reveal the answer directly; keep hints high-level.",
                }
            )
        transcript = self._context_transcript(session)
        if transcript:
            messages.append({"role": "system", "content": f"Context:\n{transcript}"})
        messages.append({"role": "user", "content": student_text})
        return messages

    def _coerce_text(self, value: Any, default: str = "") -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text if text else default

    def _limit_text(self, text: str, max_chars: int | None) -> str:
        if not max_chars or len(text) <= max_chars:
            return text
        return text[:max_chars].rstrip()

    def _sanitize_questions(self, items: Any) -> List[Dict[str, str]]:
        max_questions = int(
            self.profile.constraints.get(
                "max_questions", self.profile.metadata.get("max_coach_questions", 4)
            )
        )
        max_question_chars = int(
            self.profile.constraints.get(
                "max_question_chars", self.profile.metadata.get("max_coach_question_chars", 140)
            )
        )
        max_hint_chars = int(
            self.profile.constraints.get(
                "max_hint_chars", self.profile.metadata.get("max_coach_hint_chars", 180)
            )
        )
        no_spoilers = bool(self.profile.constraints.get("no_spoilers", False))
        min_questions = int(self.profile.constraints.get("min_questions", 2))

        questions: List[Dict[str, str]] = []
        if not isinstance(items, list):
            return questions
        for item in items:
            if not isinstance(item, dict):
                continue
            q = self._coerce_text(item.get("q"))
            if not q:
                continue
            expected = self._coerce_text(item.get("expected", ""))
            hint = self._coerce_text(item.get("hint", ""))
            q = self._limit_text(q, max_question_chars)
            if no_spoilers:
                expected = "Student explains their reasoning."
            expected = self._limit_text(expected, max_question_chars)
            hint = self._limit_text(hint, max_hint_chars)
            questions.append({"q": q, "expected": expected, "hint": hint})
            if len(questions) >= max_questions:
                break
        return questions

    def _sanitize_feedback(self, payload: Any) -> Dict[str, List[str]]:
        def _coerce_list(value: Any, fallback: List[str]) -> List[str]:
            if not isinstance(value, list):
                return fallback
            items = [self._coerce_text(v) for v in value if self._coerce_text(v)]
            return items or fallback

        correct_default = ["Good. That's the key idea."]
        wrong_default = ["Almost. Check the step again."]
        correct = _coerce_list(payload.get("correct") if isinstance(payload, dict) else None, correct_default)
        wrong = _coerce_list(payload.get("wrong") if isinstance(payload, dict) else None, wrong_default)
        return {"correct": correct, "wrong": wrong}

    def _sanitize_payload(self, payload: Any, student_text: str) -> Dict[str, Any]:
        goal = self._coerce_text(
            payload.get("goal") if isinstance(payload, dict) else None,
            default=f"Clarify: {student_text}",
        )
        next_action = self._coerce_text(
            payload.get("next_action") if isinstance(payload, dict) else None,
            default="Ask the student to try a small example.",
        )
        questions = self._sanitize_questions(payload.get("questions") if isinstance(payload, dict) else None)
        min_questions = int(self.profile.constraints.get("min_questions", 2))
        if len(questions) < min_questions:
            fallback_q = {
                "q": self._limit_text(
                    "请用一句话复述题目？",
                    int(
                        self.profile.constraints.get(
                            "max_question_chars",
                            self.profile.metadata.get("max_coach_question_chars", 140),
                        )
                    ),
                ),
                "expected": "Student restates the problem clearly.",
                "hint": "先说清输入与输出。",
            }
            while len(questions) < min_questions:
                questions.append(fallback_q)
        feedback = self._sanitize_feedback(payload.get("micro_feedback") if isinstance(payload, dict) else None)
        return {
            "goal": goal,
            "questions": questions,
            "micro_feedback": feedback,
            "next_action": next_action,
        }

    def generate_coaching(
        self, session: ConversationSession, student_text: str
    ) -> Dict[str, Any]:
        self.last_meta = {"structured_ok": False, "fallback_used": False}
        if not self.llm:
            self.last_meta["fallback_used"] = True
            payload = self._sanitize_payload({}, student_text)
            self.last_meta["output_chars"] = len(str(payload))
            return payload
        messages = self._build_messages(session, student_text)
        payload = self.llm.structured(messages, model=None, schema=COACH_SCHEMA)
        if isinstance(payload, dict) and payload.get("questions"):
            self.last_meta["structured_ok"] = True
            sanitized = self._sanitize_payload(payload, student_text)
            self.last_meta["output_chars"] = len(str(sanitized))
            return sanitized
        raw = self.llm.complete(messages, model=None)
        self.last_meta["fallback_used"] = True
        fallback_payload = {"questions": [{"q": raw or student_text, "expected": "", "hint": ""}]}
        sanitized = self._sanitize_payload(fallback_payload, student_text)
        self.last_meta["output_chars"] = len(str(sanitized))
        return sanitized
