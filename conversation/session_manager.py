from __future__ import annotations

from uuid import uuid4

from core.types import Profile, Session, Suggestion, Utterance


class ConversationSession:
    """
    In-memory container for utterances and suggestions within a single profile-bound session.
    """

    def __init__(self, profile: Profile):
        self.session = Session(id=str(uuid4()), profile=profile)

    def add_utterance(self, utterance: Utterance) -> None:
        self.session.add_utterance(utterance)

    def add_suggestion(self, suggestion: Suggestion) -> None:
        self.session.add_suggestion(suggestion)

    def get_recent_context(self, max_turns: int = 8) -> list[Utterance]:
        return self.session.utterances[-max_turns:]

    @property
    def profile(self) -> Profile:
        return self.session.profile
