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
    """
    High-level scenario profile.

    Meeting mode uses nested config under ProfileConfig (see voicebridge.config.models).
    This lightweight Profile type is kept for compatibility with early Phase 0 code.
    """

    name: str
    mode: str = "generic"
    prompts: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)
    reply_strategy: ReplyStrategy = field(default_factory=ReplyStrategy)


@dataclass
class Utterance:
    speaker: Participant
    text: str
    language: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source: UtteranceSource = "agent"


@dataclass
class TranscriptSegment:
    id: str
    start_ms: int
    end_ms: int
    text: str
    language: Optional[str] = None
    speaker_id: Optional[str] = None
    confidence: Optional[float] = None


@dataclass
class TranslationSegment:
    segment_id: str
    target_lang: str
    text: str
    source_lang: Optional[str] = None


@dataclass
class MeetingSummary:
    bullets: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    glossary_suggestions: Dict[str, str] = field(default_factory=dict)


@dataclass
class SpeakerTurn:
    speaker_id: str
    start_ms: int
    end_ms: int


@dataclass
class Session:
    id: str
    profile: Profile
    started_at: datetime = field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    utterances: List[Utterance] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def add_utterance(self, utterance: Utterance) -> None:
        self.utterances.append(utterance)

