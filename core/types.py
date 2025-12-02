from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Literal, Optional


ParticipantRole = Literal["local_user", "remote_user", "agent"]
UtteranceSource = Literal["mic", "system_audio", "keyboard", "agent"]


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
    max_suggestion_length: int = 120
    allow_agent_mode: bool = False


@dataclass
class Profile:
    name: str
    input_mode: str
    tts_backend: str
    default_voice: str
    output_device: str
    reply_strategy: ReplyStrategy
    prompts: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)


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
    style: Optional[str] = None
    confidence: Optional[float] = None
    auto_send: bool = False


@dataclass
class Session:
    id: str
    profile: Profile
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    utterances: List[Utterance] = field(default_factory=list)
    suggestions: List[Suggestion] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def add_utterance(self, utterance: Utterance) -> None:
        self.utterances.append(utterance)

    def add_suggestion(self, suggestion: Suggestion) -> None:
        self.suggestions.append(suggestion)
