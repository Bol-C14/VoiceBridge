from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional


ParticipantRole = Literal["local_user", "remote_user", "agent"]
UtteranceSource = Literal["mic", "asr", "system_audio", "keyboard", "agent"]
EventSource = Literal["keyboard", "asr", "system_audio", "agent"]
ActionType = Literal[
    "add_utterance",
    "run_macro",
    "suggest",
    "explain_concept",
    "explain_last",
    "coach_student",
    "translate_last",
    "summarize_session",
    "summarize",
]


@dataclass
class Participant:
    id: str
    role: ParticipantRole
    display_name: str
    language: Optional[str] = None


@dataclass
class ReplyStrategy:
    auto_suggest: bool = True
    auto_speak: bool = False
    max_suggestions: int = 2
    max_suggestion_length: int = 120
    allow_agent_mode: bool = False
    allow_humor: bool = True


@dataclass
class Profile:
    name: str
    input_mode: str
    tts_backend: str
    default_voice: str
    output_device: str
    reply_strategy: ReplyStrategy = field(default_factory=ReplyStrategy)
    constraints: Dict[str, Any] = field(default_factory=dict)
    default_action: ActionType = "suggest"
    capabilities: List[ActionType] = field(default_factory=list)
    prompts: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Utterance:
    speaker: Participant
    text: str
    language: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: UtteranceSource = "agent"


@dataclass
class Suggestion:
    text: str
    tone: Optional[str] = None
    length: Optional[str] = None
    risk: Optional[str] = None
    auto_send: bool = False
    style: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class Event:
    action: ActionType
    payload_text: Optional[str] = None
    target_lang: Optional[str] = None
    speaker_role: Optional[ParticipantRole] = None
    speaker_name: Optional[str] = None
    mode: Optional[str] = None
    source: EventSource = "keyboard"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionResult:
    action: ActionType
    intent: Optional[Any] = None
    suggestions: List[Suggestion] = field(default_factory=list)
    translation: Optional[Dict[str, Any]] = None
    explanation: Optional[Dict[str, Any]] = None
    coach: Optional[Dict[str, Any]] = None
    summary: Optional[Dict[str, Any]] = None
    spoken_text: Optional[str] = None
    segments: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class Session:
    id: str
    profile: Profile
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    utterances: List[Utterance] = field(default_factory=list)
    suggestions: List[Suggestion] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_utterance(self, utterance: Utterance) -> None:
        self.utterances.append(utterance)

    def add_suggestion(self, suggestion: Suggestion) -> None:
        self.suggestions.append(suggestion)
